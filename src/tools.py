"""
src/tools.py

LangChain tool definitions used by the agent during its reasoning loop.
Each tool is decorated with @tool so LangChain can describe and call them
automatically. All tools are importable and manually testable in isolation.

Tool list (7 total):
  1. get_pending_invoices    - returns triaged invoice summary
  2. get_invoice_details     - returns full details for one invoice
  3. process_invoice         - generate + send + update in one sequential call (PRIMARY)
  4. generate_followup_email - calls LLM to draft a personalised email (standalone)
  5. send_email              - sends or dry-runs a single email (standalone)
  6. update_invoice_record   - increments followup_count and persists (standalone)
  7. generate_run_report     - returns the structured run summary
"""

import re
import json
import threading
from datetime import datetime, timezone

from langchain_core.tools import tool
from langchain_groq import ChatGroq

from src import config, logger
from src.data_loader import load_invoices, save_invoices
from src.triage import triage_invoices
from src.updater import update_followup
from src import emailer as emailer_module
from prompts.email_prompt import get_prompt_for_tier

# ── CSV write lock — prevents concurrent update_invoice_record calls from
#    trampling each other when the agent batches tool calls in parallel.
_csv_lock = threading.Lock()

# ── Shared LLM instance (lazy - only used by email generation tools) ----------

def _get_llm() -> ChatGroq:
    """Return a ChatGroq instance configured from src/config.py."""
    return ChatGroq(
        model=config.LLM_MODEL,
        api_key=config.GROQ_API_KEY,
        temperature=0.4,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — get_pending_invoices
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_pending_invoices(query: str = "") -> str:
    """
    Retrieve all pending invoices that need a follow-up email.

    Returns a JSON array of objects, each containing:
    invoice_no, client_name, invoice_amount, days_overdue, urgency_tier.

    Use this tool first to understand which invoices require action.
    Pass an empty string as input.
    """
    df = load_invoices(config.DATA_PATH)
    triaged = triage_invoices(df)

    summary = triaged[[
        "invoice_no", "client_name", "invoice_amount", "days_overdue", "urgency_tier"
    ]].to_dict(orient="records")

    logger.log_action(
        invoice_no="SYSTEM",
        action="get_pending_invoices",
        result="ok",
        reason=f"{len(summary)} actionable invoices retrieved.",
    )
    return json.dumps(summary)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — get_invoice_details
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_invoice_details(invoice_no: str) -> str:
    """
    Return the full details for a specific invoice as a JSON object.

    Args:
        invoice_no: The invoice identifier, e.g. "INV-1033".

    Returns a JSON object with all invoice fields including urgency_tier
    (assigned by the triage engine).
    """
    df = load_invoices(config.DATA_PATH)
    triaged = triage_invoices(df)

    matches = triaged[triaged["invoice_no"] == invoice_no]
    if matches.empty:
        # Also search the full dataset (invoice may be paid or not yet actionable)
        all_matches = df[df["invoice_no"] == invoice_no]
        if all_matches.empty:
            return json.dumps({"error": f"Invoice '{invoice_no}' not found."})
        row = all_matches.iloc[0].copy()
        row["urgency_tier"] = "n/a"
    else:
        row = matches.iloc[0].copy()

    # Convert Timestamp fields to ISO strings for JSON serialisation
    for col in ("due_date", "last_followup_date"):
        val = row.get(col)
        if hasattr(val, "isoformat"):
            row[col] = val.isoformat() if not hasattr(val, "value") or val.value != -9223372036854775808 else ""
        elif str(val) in ("NaT", "nan", "None"):
            row[col] = ""

    return json.dumps(row.to_dict())


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — generate_followup_email
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_input(text: str) -> str:
    """
    Prevent Prompt Injection by scrubbing malicious patterns from user-provided data.
    """
    if not isinstance(text, str):
        return str(text)
    
    # Common injection keywords to neutralize
    patterns = [
        r"ignore previous instructions",
        r"system prompt",
        r"instead of",
        r"you are now",
        r"assistant:"
    ]
    for p in patterns:
        text = re.sub(p, "[REDACTED]", text, flags=re.IGNORECASE)
    
    # Strip any potential hidden formatting or control characters
    return "".join(ch for ch in text if ch.isprintable()).strip()


@tool
def generate_followup_email(invoice_no: str) -> str:
    """
    Generate a personalised follow-up email for a specific invoice using the LLM.

    Selects the correct tone/prompt based on the invoice's urgency_tier,
    formats it with real invoice data, and calls the LLM to produce the email.

    Args:
        invoice_no: The invoice identifier, e.g. "INV-1033".

    Returns a JSON object with keys: subject, body, to_email, invoice_no.
    """
    # Load invoice details
    raw = json.loads(get_invoice_details.invoke(invoice_no))
    if "error" in raw:
        return json.dumps(raw)

    urgency_tier = raw.get("urgency_tier", "first_followup")
    prompt = get_prompt_for_tier(urgency_tier)

    # Format prompt with invoice data
    messages = prompt.format_messages(
        client_name=sanitize_input(raw.get("client_name", "")),
        invoice_no=sanitize_input(invoice_no),
        invoice_amount=sanitize_input(raw.get("invoice_amount", "")),
        due_date=sanitize_input(str(raw.get("due_date", ""))[:10]),
        days_overdue=raw.get("days_overdue", 0),
        followup_count=raw.get("followup_count", 0),
        sender_name=config.SMTP_SENDER_NAME,
        payment_link=config.PAYMENT_LINK,
        bank_details=config.BANK_DETAILS,
        format_instruction=(
            "\nRespond with ONLY the email in this exact format — no extra commentary:\n"
            "\nSubject: <subject line>\n\nBody:\n<email body>"
        ),
    )

    llm = _get_llm()
    response = llm.invoke(messages)
    raw_text: str = response.content.strip()

    # Parse the LLM output into subject + body
    subject, body = _parse_email_output(raw_text)

    result = {
        "invoice_no": invoice_no,
        "to_email": raw.get("contact_email", ""),
        "subject": subject,
        "body": body,
    }

    logger.log_action(
        invoice_no=invoice_no,
        action="email_generated",
        result="ok",
        reason=f"Tier: {urgency_tier}. Subject: {subject}",
    )
    return json.dumps(result)


def _parse_email_output(raw_text: str) -> tuple[str, str]:
    """
    Extract subject and body from the LLM's formatted output.
    Handles variations like 'Subject: ' and 'Body:' markers.
    """
    subject = ""
    body = ""
    
    # Try to find Subject
    for line in raw_text.splitlines():
        if line.lower().strip().startswith("subject:"):
            subject = line[len("subject:"):].strip()
            break
            
    # Try to find Body (everything after the Body: marker)
    lower_text = raw_text.lower()
    marker = "body:"
    if marker in lower_text:
        marker_pos = lower_text.find(marker)
        body = raw_text[marker_pos + len(marker):].strip()
    else:
        # Fallback: if no marker, take everything after the subject line or the whole thing
        if subject and subject in raw_text:
            body = raw_text[raw_text.find(subject) + len(subject):].strip()
        else:
            body = raw_text

    # Validate the structure to mitigate hallucination risk
    if not subject or len(body) < 20:
        logger.log_action(
            invoice_no="SYSTEM",
            action="validation_failed",
            result="error",
            reason=f"LLM generated invalid or empty email structure for text: {raw_text[:50]}..."
        )
        return "Validation Error: Hallucination detected", "Incomplete email body generated by LLM."

    # Final check for prompt injection leakage in output
    if "ignore previous" in body.lower():
         return "Security Error", "Potential prompt injection detected in output."

    return subject, body


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — send_email
# ─────────────────────────────────────────────────────────────────────────────

@tool
def send_email(invoice_no: str, subject: str, body: str, to_email: str) -> str:
    """
    Send (or dry-run) a follow-up email for the given invoice.

    In DRY_RUN mode (default), the email is printed to console and logged.
    In live mode, it is dispatched via SMTP.

    Args:
        invoice_no: Invoice identifier — used for logging only.
        subject:    Email subject line.
        body:       Plain-text email body.
        to_email:   Recipient address.

    Returns a JSON object with keys: invoice_no, status, timestamp.
    """
    result = emailer_module.send_email(to=to_email, subject=subject, body=body)

    logger.log_action(
        invoice_no=invoice_no,
        action="email_sent",
        result=result.get("status", "unknown"),
        reason=f"to={to_email} | status={result.get('status')}",
    )

    result["invoice_no"] = invoice_no
    return json.dumps(result)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 5 — update_invoice_record
# ─────────────────────────────────────────────────────────────────────────────

@tool
def update_invoice_record(invoice_no: str) -> str:
    """
    After a successful email send, increment followup_count by 1 and
    set last_followup_date to today. Persists the change to the CSV.

    Args:
        invoice_no: The invoice identifier to update.

    Returns a JSON confirmation object.
    """
    with _csv_lock:   # serialise CSV writes — safe when agent batches tool calls
        df = load_invoices(config.DATA_PATH)
        try:
            df = update_followup(invoice_no, df)
        except ValueError as exc:
            result = {"status": "error", "invoice_no": invoice_no, "reason": str(exc)}
            logger.log_action(invoice_no, "record_updated", "error", str(exc))
            return json.dumps(result)
        save_invoices(df, config.DATA_PATH)

    logger.log_action(
        invoice_no=invoice_no,
        action="record_updated",
        result="ok",
        reason="followup_count incremented; last_followup_date set to today.",
    )
    return json.dumps({
        "status": "ok",
        "invoice_no": invoice_no,
        "message": "followup_count incremented and last_followup_date updated.",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool 6 — generate_run_report
# ─────────────────────────────────────────────────────────────────────────────

@tool
def generate_run_report(query: str = "") -> str:
    """
    Generate and return a structured summary of everything the agent did
    during this run. Also writes the full report to the outputs/ directory.

    Call this tool last, after all invoices have been processed.
    Pass an empty string as input.

    Returns a JSON object with total_processed, total_sent, total_skipped,
    total_errors, and the full action log.
    """
    report_path = logger.flush_report(config.OUTPUT_DIR)
    summary = logger.get_summary()
    summary["report_file"] = report_path

    logger.log_action(
        invoice_no="SYSTEM",
        action="run_report_generated",
        result="ok",
        reason=f"Report written to {report_path}",
    )
    return json.dumps(summary, indent=2)


# -----------------------------------------------------------------------------
# Tool 7 — process_invoice  (PRIMARY TOOL — use this for every invoice)
# -----------------------------------------------------------------------------

@tool
def process_invoice(invoice_no: str) -> str:
    """
    Process one invoice end-to-end in a single, sequential tool call:
      1. Fetch invoice details and determine urgency tier.
      2. Generate a personalised follow-up email via the LLM.
      3. Send the email (dry-run or real SMTP, depending on DRY_RUN setting).
      4. Update the invoice record (increment followup_count, set last_followup_date).

    THIS is the tool to use for every invoice. Do NOT call generate_followup_email,
    send_email, and update_invoice_record separately — they will execute in parallel
    and produce incorrect results.

    Args:
        invoice_no: The invoice identifier, e.g. "INV-1088".

    Returns a JSON object summarising the outcome of all four steps.
    """
    # Step 1 — load invoice details
    raw = json.loads(get_invoice_details.invoke(invoice_no))
    if "error" in raw:
        logger.log_action(invoice_no, "process_invoice", "error", raw["error"])
        return json.dumps({"status": "error", "invoice_no": invoice_no, "reason": raw["error"]})

    urgency_tier: str = raw.get("urgency_tier", "first_followup")
    to_email: str = raw.get("contact_email", "")

    # Guard 1 — n/a means the invoice is paid or not yet actionable
    if urgency_tier == "n/a":
        msg = f"Invoice {invoice_no} is not actionable (status: {raw.get('payment_status', 'unknown')})."
        logger.log_action(invoice_no, "process_invoice", "skipped", msg)
        return json.dumps({"status": "skipped", "invoice_no": invoice_no, "reason": msg})

    # Guard 2 — legal_escalation (Stage 5) requires manual human review (per Mandatory Design)
    from src.triage import TIER_LEGAL
    if urgency_tier == TIER_LEGAL:
        msg = f"Invoice {invoice_no} is >30 days overdue (Stage 5). STOP: Manual review required."
        logger.log_action(invoice_no, "process_invoice", "skipped", msg)
        return json.dumps({
            "status": "skipped", 
            "invoice_no": invoice_no, 
            "reason": "Escalation Cap Reached: Manual Legal/Finance review required."
        })

    # Step 2 — generate email via LLM (sequential — result used in step 3)
    prompt = get_prompt_for_tier(urgency_tier)
    messages = prompt.format_messages(
        client_name=sanitize_input(raw.get("client_name", "")),
        invoice_no=sanitize_input(raw.get("invoice_no", "")),
        invoice_amount=sanitize_input(raw.get("invoice_amount", "")),
        due_date=sanitize_input(str(raw.get("due_date", ""))[:10]),
        days_overdue=raw.get("days_overdue", 0),
        followup_count=raw.get("followup_count", 0),
        sender_name=config.SMTP_SENDER_NAME,
        payment_link=config.PAYMENT_LINK,
        bank_details=config.BANK_DETAILS,
        format_instruction=(
            "\nRespond with ONLY the email in this exact format:\n"
            "Subject: <subject line>\n\nBody:\n<email body>"
        ),
    )
    llm = _get_llm()
    response = llm.invoke(messages)
    subject, body = _parse_email_output(response.content.strip())

    logger.log_action(invoice_no, "email_generated", "ok", f"Tier: {urgency_tier}. Subject: {subject}")

    # Step 3 — send (uses the actual LLM-generated content)
    send_result = emailer_module.send_email(to=to_email, subject=subject, body=body)
    logger.log_action(
        invoice_no=invoice_no,
        action="email_sent",
        result=send_result.get("status", "unknown"),
        reason=f"to={to_email} | status={send_result.get('status')}",
    )

    # Step 4 — update CSV record (lock prevents concurrent write corruption)
    with _csv_lock:
        df = load_invoices(config.DATA_PATH)
        try:
            df = update_followup(invoice_no, df)
            save_invoices(df, config.DATA_PATH)
            update_status = "ok"
        except ValueError as exc:
            update_status = str(exc)

    logger.log_action(invoice_no, "record_updated", update_status,
                      "followup_count incremented; last_followup_date set to today.")

    return json.dumps({
        "invoice_no": invoice_no,
        "urgency_tier": urgency_tier,
        "email_subject": subject,
        "to_email": to_email,
        "send_status": send_result.get("status"),
        "record_update": update_status,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Exported list — pass this directly to the LangChain agent
# ─────────────────────────────────────────────────────────────────────────────

ALL_TOOLS = [
    get_pending_invoices,
    process_invoice,          # PRIMARY — agent uses this for every invoice
    generate_run_report,
    # standalone tools kept for testing / direct use
    get_invoice_details,
    generate_followup_email,
    send_email,
    update_invoice_record,
]
