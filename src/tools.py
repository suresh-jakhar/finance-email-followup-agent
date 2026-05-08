"""
src/tools.py

LangChain tool definitions used by the agent during its reasoning loop.
Each tool is decorated with @tool so LangChain can describe and call them
automatically. All tools are importable and manually testable in isolation.

Tool list (6 total):
  1. get_pending_invoices    — returns triaged invoice summary
  2. get_invoice_details     — returns full details for one invoice
  3. generate_followup_email — calls LLM to draft a personalised email
  4. send_email              — sends or dry-runs a single email
  5. update_invoice_record   — increments followup_count and persists
  6. generate_run_report     — returns the structured run summary
"""

import json
from datetime import datetime, timezone

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from src import config, logger
from src.data_loader import load_invoices, save_invoices
from src.triage import triage_invoices
from src.updater import update_followup
from src import emailer as emailer_module
from prompts.email_prompt import get_prompt_for_tier

# ── Shared LLM instance (lazy — only used by generate_followup_email) ─────────

def _get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI instance configured from src/config.py."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=config.LLM_API_KEY,
        temperature=0.4,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — get_pending_invoices
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_pending_invoices(dummy: str = "") -> str:
    """
    Retrieve all pending invoices that need a follow-up email.

    Returns a JSON array of objects, each containing:
    invoice_no, client_name, invoice_amount, days_overdue, urgency_tier.

    Use this tool first to understand which invoices require action.
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
        client_name=raw.get("client_name", ""),
        invoice_no=raw.get("invoice_no", ""),
        invoice_amount=raw.get("invoice_amount", ""),
        due_date=str(raw.get("due_date", ""))[:10],
        days_overdue=raw.get("days_overdue", 0),
        followup_count=raw.get("followup_count", 0),
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

    Expected format:
        Subject: <line>

        Body:
        <rest of text>
    """
    subject = ""
    body = raw_text

    lines = raw_text.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line[len("subject:"):].strip()
        if line.lower().strip() == "body:":
            body = "\n".join(lines[i + 1:]).strip()
            break

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
def generate_run_report(dummy: str = "") -> str:
    """
    Generate and return a structured summary of everything the agent did
    during this run. Also writes the full report to the outputs/ directory.

    Call this tool last, after all invoices have been processed.

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


# ─────────────────────────────────────────────────────────────────────────────
# Exported list — pass this directly to the LangChain agent
# ─────────────────────────────────────────────────────────────────────────────

ALL_TOOLS = [
    get_pending_invoices,
    get_invoice_details,
    generate_followup_email,
    send_email,
    update_invoice_record,
    generate_run_report,
]
