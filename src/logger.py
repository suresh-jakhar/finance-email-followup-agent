"""
src/logger.py

Structured, append-only in-memory logger for a single agent run.
Writes a JSON run report to the outputs/ directory at the end of the run.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


# In-memory log for the current run — module-level so every tool call appends here.
_log: list[dict] = []


def log_action(
    invoice_no: str,
    action: str,
    result: str,
    reason: str,
) -> None:
    """
    Append one action entry to the in-memory run log.

    Args:
        invoice_no: The invoice this action relates to (use "SYSTEM" for global actions).
        action:     Short label for what happened (e.g. "email_generated", "email_sent").
        result:     Outcome of the action (e.g. "dry_run", "sent", "skipped", "error").
        reason:     Human-readable explanation of why this action was taken or skipped.
    """
    _log.append({
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "invoice_no": invoice_no,
        "action": action,
        "result": result,
        "reason": reason,
    })


def get_summary() -> dict:
    """
    Return aggregate counts for the current run.

    Returns:
        dict with keys: total_processed, total_sent, total_skipped, total_errors,
        and a copy of all log entries so callers cannot mutate the internal list.
    """
    total_processed = sum(1 for e in _log if e["action"] == "email_generated")
    total_sent = sum(1 for e in _log if e["result"] in ("sent", "dry_run"))
    total_skipped = sum(1 for e in _log if e["result"] == "skipped")
    total_errors = sum(1 for e in _log if e["result"] == "error")

    return {
        "total_processed": total_processed,
        "total_sent": total_sent,
        "total_skipped": total_skipped,
        "total_errors": total_errors,
        "log": list(_log),
    }


def reset() -> None:
    """
    Clear the in-memory log.

    Call this at the start of each agent run to prevent entries from a
    previous run (in the same Python process) bleeding into the next report.
    """
    _log.clear()


def flush_report(output_dir: str) -> str:
    """
    Write the full run log to a timestamped JSON file in output_dir.

    Args:
        output_dir: Directory path where the report file will be created.

    Returns:
        Absolute path of the written report file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = Path(output_dir) / f"run_report_{ts}.json"

    report = get_summary()
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[LOGGER] Run report written to: {report_path}")
    return str(report_path)
