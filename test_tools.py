"""
Smoke test for Step 4 — LangChain Tools (dry-run, no LLM call).
Run with: python test_tools.py

Tests tools 1, 2, 4, 5, 6 in isolation (no API key needed).
Tool 3 (generate_followup_email) requires LLM — skipped here unless key present.
"""

import json
import os

# ── Test 1: import & ALL_TOOLS list ──────────────────────────────────────────
print("=== STEP 4 - TOOLS TESTS ===\n")

print("[1] Import and ALL_TOOLS list")
from src.tools import (
    ALL_TOOLS,
    get_pending_invoices,
    get_invoice_details,
    send_email,
    update_invoice_record,
    generate_run_report,
)
assert len(ALL_TOOLS) == 6, f"Expected 6 tools, got {len(ALL_TOOLS)}"
print(f"    PASS  ALL_TOOLS has {len(ALL_TOOLS)} tools")
for t in ALL_TOOLS:
    print(f"    PASS  Tool registered: '{t.name}'")
print()

# ── Test 2: get_pending_invoices ──────────────────────────────────────────────
print("[2] get_pending_invoices")
result_raw = get_pending_invoices.invoke("")
result = json.loads(result_raw)
assert isinstance(result, list), "Expected a list"
assert len(result) > 0, "Expected at least one actionable invoice"
first = result[0]
for key in ("invoice_no", "client_name", "invoice_amount", "days_overdue", "urgency_tier"):
    assert key in first, f"Missing key '{key}' in result"
print(f"    PASS  {len(result)} actionable invoices returned")
print(f"    PASS  All required keys present in each record")
print(f"    INFO  Top invoice: {first['invoice_no']} | {first['client_name']} | "
      f"{first['days_overdue']} days | tier={first['urgency_tier']}")
print()

# ── Test 3: get_invoice_details — known invoice ───────────────────────────────
print("[3] get_invoice_details — known invoice")
sample_no = result[0]["invoice_no"]
detail_raw = get_invoice_details.invoke(sample_no)
detail = json.loads(detail_raw)
assert "error" not in detail, f"Unexpected error: {detail}"
assert detail["invoice_no"] == sample_no
assert "urgency_tier" in detail
print(f"    PASS  Details returned for {sample_no}")
print(f"    PASS  urgency_tier present: {detail['urgency_tier']}")
print()

# ── Test 4: get_invoice_details — unknown invoice ─────────────────────────────
print("[4] get_invoice_details — unknown invoice")
unknown_raw = get_invoice_details.invoke("INV-DOES-NOT-EXIST")
unknown = json.loads(unknown_raw)
assert "error" in unknown, "Expected an error dict for unknown invoice"
print(f"    PASS  Returns error dict: {unknown}")
print()

# ── Test 5: send_email (dry-run) ──────────────────────────────────────────────
print("[5] send_email — dry-run mode")
from src import config
assert config.DRY_RUN is True, "DRY_RUN must be True for this test"

send_raw = send_email.invoke({
    "invoice_no": sample_no,
    "subject": "TEST - Invoice Reminder",
    "body": "This is a test email body.",
    "to_email": "test@example.com",
})
send_result = json.loads(send_raw)
assert send_result["status"] == "dry_run", f"Expected dry_run, got: {send_result['status']}"
assert send_result["invoice_no"] == sample_no
assert "timestamp" in send_result
print(f"    PASS  status=dry_run for {sample_no}")
print(f"    PASS  timestamp present: {send_result['timestamp']}")
print()

# ── Test 6: update_invoice_record ─────────────────────────────────────────────
print("[6] update_invoice_record")
import tempfile, shutil, pandas as pd
from src.data_loader import load_invoices, save_invoices

# Work on a temp copy so we don't mutate the real CSV
tmp_path = tempfile.mktemp(suffix=".csv")
shutil.copy(config.DATA_PATH, tmp_path)
original_path = config.DATA_PATH

# Patch config.DATA_PATH to point at temp copy
config.DATA_PATH = tmp_path

before_df = load_invoices(tmp_path)
target = before_df[before_df["payment_status"] == "Pending"].iloc[0]["invoice_no"]
before_count = int(before_df[before_df["invoice_no"] == target]["followup_count"].iloc[0])

upd_raw = update_invoice_record.invoke(target)
upd_result = json.loads(upd_raw)
assert upd_result["status"] == "ok", f"Expected ok, got: {upd_result}"

after_df = load_invoices(tmp_path)
after_count = int(after_df[after_df["invoice_no"] == target]["followup_count"].iloc[0])
assert after_count == before_count + 1, f"followup_count not incremented: {before_count} -> {after_count}"
after_date = str(after_df[after_df["invoice_no"] == target]["last_followup_date"].iloc[0])[:10]
from datetime import date
assert after_date == date.today().isoformat(), f"last_followup_date not today: {after_date}"

config.DATA_PATH = original_path  # restore
os.unlink(tmp_path)

print(f"    PASS  followup_count: {before_count} -> {after_count} for {target}")
print(f"    PASS  last_followup_date set to today: {after_date}")
print()

# ── Test 7: generate_run_report ───────────────────────────────────────────────
print("[7] generate_run_report")
import glob
before_reports = glob.glob(f"{config.OUTPUT_DIR}/run_report_*.json")

report_raw = generate_run_report.invoke("")
report = json.loads(report_raw)
for key in ("total_processed", "total_sent", "total_skipped", "total_errors", "log", "report_file"):
    assert key in report, f"Missing key '{key}' in report"

after_reports = glob.glob(f"{config.OUTPUT_DIR}/run_report_*.json")
new_reports = set(after_reports) - set(before_reports)
assert len(new_reports) == 1, f"Expected 1 new report file, found: {new_reports}"

print(f"    PASS  Report keys present: {list(report.keys())}")
print(f"    PASS  Report file written: {list(new_reports)[0]}")
print(f"    INFO  total_processed={report['total_processed']} | total_sent={report['total_sent']}")
print()

print("ALL TOOL CHECKS PASSED.")
