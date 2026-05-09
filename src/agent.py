"""
src/agent.py

LangChain/LangGraph agent that autonomously orchestrates the full credit
follow-up workflow: triage invoices -> generate emails -> send (or dry-run)
-> update records -> produce a final run report.

Uses langgraph.prebuilt.create_react_agent — the current recommended pattern
for LangChain >= 1.0 where AgentExecutor has been removed.
"""

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from src import config, logger
from src.tools import ALL_TOOLS

# ── System prompt — the agent's standing instructions ────────────────────────

_AGENT_SYSTEM_PROMPT = """You are an autonomous finance credit follow-up agent for a company.

Your job is to:
1. Retrieve all pending invoices that need follow-up.
2. For each invoice, generate a personalized follow-up email appropriate to the urgency.
3. Send each email (or log it in dry-run mode).
4. Update the invoice record after each successful send.
5. Generate a final run report summarizing all actions taken.

Work through the invoice list one by one. Do not skip any invoice that needs follow-up.
Always update the record after sending. Always generate the final report at the end.

Important rules:
- Call get_pending_invoices first to see the full list.
- For each invoice in the list: call generate_followup_email, then send_email, then update_invoice_record.
- After ALL invoices are processed, call generate_run_report exactly once.
- Never invent invoice data — always use the data returned by the tools.
"""


def _build_agent(verbose: bool = True):
    """
    Construct and return the LangGraph ReAct agent with all tools attached.

    Args:
        verbose: Unused in LangGraph (streaming controls visibility instead),
                 kept for API compatibility with callers.

    Returns:
        A compiled LangGraph agent graph ready to invoke.
    """
    llm = ChatGroq(
        model=config.LLM_MODEL,
        api_key=config.GROQ_API_KEY,
        temperature=0,      # deterministic — no creative latitude for finance ops
    )

    return create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=_AGENT_SYSTEM_PROMPT,
    )


def run_agent(verbose: bool = True) -> dict:
    """
    Reset the logger, build the agent, run it to completion, and return
    the final run report summary dict.

    The agent streams its reasoning steps; each step is printed when
    verbose=True, giving full transparency into the tool-call chain.

    Args:
        verbose: If True, prints each reasoning step to stdout.

    Returns:
        dict with keys: total_processed, total_sent, total_skipped,
        total_errors, log, report_file.
    """
    # Clear any stale log entries from a previous run in the same process
    logger.reset()

    agent = _build_agent(verbose=verbose)

    user_message = (
        "Process all pending invoices. "
        "For each one: generate a follow-up email, send it, and update the record. "
        "When all invoices are done, generate the final run report."
    )

    # Stream the agent's reasoning steps for full visibility
    for step in agent.stream(
        {"messages": [HumanMessage(content=user_message)]},
        stream_mode="values",
    ):
        last_msg = step["messages"][-1]
        if verbose:
            last_msg.pretty_print()

    # Flush the structured report to disk and return the summary
    report_path = logger.flush_report(config.OUTPUT_DIR)
    summary = logger.get_summary()
    summary["report_file"] = report_path
    return summary
