"""
src/agent.py

Orchestrates the full credit follow-up pipeline:
  triage -> generate emails (LLM) -> send -> update records -> report.

Architecture: Python-driven loop (not an LLM-driven ReAct loop).
The LLM is used only where it adds value — email generation inside
process_invoice. The outer orchestration loop is deterministic Python,
which avoids context-window bloat on services with tight token limits.

The LangGraph ReAct agent (_build_agent) is kept for reference and can
be used if a larger-context model is available.
"""

import json

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from src import config, logger
from src.tools import ALL_TOOLS, get_pending_invoices, process_invoice, generate_run_report

# ── System prompt (used by _build_agent / full-LLM mode) ─────────────────────

_AGENT_SYSTEM_PROMPT = """You are an autonomous finance credit follow-up agent for a company.

Your workflow has exactly three phases:

PHASE 1 - Get the invoice list:
  Call get_pending_invoices once. This returns the full list of invoices needing follow-up.

PHASE 2 - Process each invoice one at a time:
  For EACH invoice_no in the list, call process_invoice(invoice_no).
  - process_invoice handles email generation, sending, and record update internally.
  - Do NOT call generate_followup_email, send_email, or update_invoice_record separately.
  - Do NOT call get_pending_invoices again after phase 1.
  - Process invoices one at a time, in order.

PHASE 3 - Final report:
  After ALL invoices have been processed, call generate_run_report once.

CRITICAL RULES:
- Use process_invoice for every invoice — never the three individual tools.
- Do not skip any invoice from the list.
- Do not call generate_run_report until every invoice has been processed.
"""


def _build_agent(verbose: bool = True):
    """
    Construct and return the LangGraph ReAct agent with all tools attached.

    Note: Requires a model with a large context window (>= 8k tokens)
    to handle the full 85-invoice payload without hitting rate limits.
    """
    llm = ChatGroq(
        model=config.LLM_MODEL,
        api_key=config.GROQ_API_KEY,
        temperature=0,
        max_tokens=512,
    )
    return create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=_AGENT_SYSTEM_PROMPT,
    )


def run_agent(limit: int = None, verbose: bool = True) -> dict:
    """
    Orchestrate the full follow-up pipeline and return the run summary.

    Uses a Python-driven sequential loop rather than an LLM ReAct loop.
    This avoids context-window accumulation when processing large invoice
    datasets on free-tier LLM APIs (e.g. Groq's 6k-token limit).

    The LLM is still called for every invoice — inside process_invoice —
    to generate a personalised email. Only the outer loop is Python.

    Args:
        limit: Maximum number of invoices to process in this run. If None, process all.
        verbose: If True, prints progress for each invoice.

    Returns:
        dict with keys: total_processed, total_sent, total_skipped,
        total_errors, log, report_file.
    """
    # Clear stale log entries from any previous run in this process
    logger.reset()

    # ── Phase 1: retrieve the triaged invoice list ───────────────────────────
    invoices = json.loads(get_pending_invoices.invoke(""))
    
    if limit is not None:
        invoices = invoices[:limit]

    total = len(invoices)
    if verbose:
        print(f"\n[AGENT] {total} invoices to process.\n")

    # ── Phase 2: process each invoice sequentially ───────────────────────────
    for i, inv in enumerate(invoices, 1):
        inv_no = inv["invoice_no"]
        tier   = inv.get("urgency_tier", "?")

        if verbose:
            print(f"[AGENT] ({i}/{total}) {inv_no}  tier={tier}")

        result = json.loads(process_invoice.invoke(inv_no))

        if verbose:
            status = result.get("send_status") or result.get("status", "?")
            subj   = result.get("email_subject", "")[:60]
            print(f"         -> {status}  |  {subj}")

    # ── Phase 3: flush the report ────────────────────────────────────────────
    report_path = logger.flush_report(config.OUTPUT_DIR)
    summary = logger.get_summary()
    summary["report_file"] = report_path
    return summary
