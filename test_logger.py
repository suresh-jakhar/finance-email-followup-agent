"""
Dedicated smoke test for Step 6 — Run Logger (src/logger.py).
Run with: python test_logger.py

Tests all behaviours specified in the implementation plan:
  - log_action() appends entries with all required fields
  - Each entry contains: timestamp, invoice_no, action, result, reason
  - get_summary() returns correct counts
  - flush_report() writes a valid JSON file to outputs/ with ISO timestamp name
  - reset() clears the log between runs
  - get_summary() returns a copy — callers cannot mutate internal state
"""

import json
import os
import glob
import tempfile
from datetime import timezone, datetime

import src.logger as logger

print("=== STEP 6 - RUN LOGGER TESTS ===\n")

# Always start clean
logger.reset()

# ── Test 1: log_action() appends with all required fields ────────────────────
print("[1] log_action() appends entries with all required fields")
logger.log_action("INV-1001", "email_generated", "ok", "First follow-up generated.")
logger.log_action("INV-1002", "email_sent", "dry_run", "Sent in dry-run mode.")
logger.log_action("INV-1003", "email_sent", "error", "SMTP connection refused.")
logger.log_action("INV-1004", "record_updated", "skipped", "Already paid.")

summary = logger.get_summary()
assert len(summary["log"]) == 4, f"Expected 4 entries, got {len(summary['log'])}"
print(f"    PASS  4 entries appended")

REQUIRED_FIELDS = {"timestamp", "invoice_no", "action", "result", "reason"}
for entry in summary["log"]:
    missing = REQUIRED_FIELDS - entry.keys()
    assert not missing, f"Entry missing fields: {missing} in {entry}"
print(f"    PASS  All entries have required fields: {sorted(REQUIRED_FIELDS)}")
print()

# ── Test 2: timestamps are valid ISO-8601 UTC strings ────────────────────────
print("[2] Timestamps are valid ISO-8601 UTC strings")
for entry in summary["log"]:
    ts = entry["timestamp"]
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None, f"Timestamp has no timezone: {ts}"
    print(f"    PASS  {ts}")
print()

# ── Test 3: get_summary() counts are correct ─────────────────────────────────
print("[3] get_summary() returns correct aggregate counts")
# total_processed = entries where action == "email_generated" → 1
# total_sent      = entries where result in ("sent", "dry_run")  → 1
# total_skipped   = entries where result == "skipped"            → 1
# total_errors    = entries where result == "error"              → 1
assert summary["total_processed"] == 1, f"total_processed wrong: {summary['total_processed']}"
assert summary["total_sent"] == 1,      f"total_sent wrong: {summary['total_sent']}"
assert summary["total_skipped"] == 1,   f"total_skipped wrong: {summary['total_skipped']}"
assert summary["total_errors"] == 1,    f"total_errors wrong: {summary['total_errors']}"
print(f"    PASS  total_processed = {summary['total_processed']}")
print(f"    PASS  total_sent      = {summary['total_sent']}")
print(f"    PASS  total_skipped   = {summary['total_skipped']}")
print(f"    PASS  total_errors    = {summary['total_errors']}")
print()

# ── Test 4: get_summary() returns a copy — internal state is safe ─────────────
print("[4] get_summary() log is a copy — mutating it does not affect internal log")
summary_copy = logger.get_summary()
summary_copy["log"].clear()          # mutate the returned copy
summary_after = logger.get_summary()
assert len(summary_after["log"]) == 4, "Internal log was mutated by caller!"
print("    PASS  Mutating returned log does not affect internal _log")
print()

# ── Test 5: flush_report() writes a valid JSON file ──────────────────────────
print("[5] flush_report() writes run_report_<timestamp>.json to output_dir")
tmp_dir = tempfile.mkdtemp()
report_path = logger.flush_report(tmp_dir)

assert os.path.isfile(report_path), f"Report file not found: {report_path}"
filename = os.path.basename(report_path)
assert filename.startswith("run_report_"), f"Unexpected filename: {filename}"
assert filename.endswith(".json"), f"Expected .json extension: {filename}"

with open(report_path, encoding="utf-8") as f:
    written = json.load(f)

for key in ("total_processed", "total_sent", "total_skipped", "total_errors", "log"):
    assert key in written, f"Missing key '{key}' in written report"
assert len(written["log"]) == 4
print(f"    PASS  Report file created: {filename}")
print(f"    PASS  JSON is valid and contains all required keys")
print(f"    PASS  Log has {len(written['log'])} entries in written file")

# Verify filename timestamp format: run_report_YYYYMMDDTHHMMSSZ.json
import re
ts_part = filename[len("run_report_"):-len(".json")]
assert re.match(r"^\d{8}T\d{6}Z$", ts_part), f"Timestamp format wrong: '{ts_part}'"
print(f"    PASS  Filename timestamp format correct: {ts_part}")

# Cleanup
import shutil
shutil.rmtree(tmp_dir)
print()

# ── Test 6: reset() clears the log ───────────────────────────────────────────
print("[6] reset() clears the in-memory log")
assert len(logger.get_summary()["log"]) == 4  # still 4 from earlier
logger.reset()
assert len(logger.get_summary()["log"]) == 0, "Log not cleared after reset()"
counts = logger.get_summary()
assert counts["total_processed"] == 0
assert counts["total_sent"] == 0
assert counts["total_skipped"] == 0
assert counts["total_errors"] == 0
print("    PASS  All entries cleared after reset()")
print("    PASS  All counts are 0 after reset()")
print()

# ── Test 7: append-only behaviour — entries accumulate correctly ──────────────
print("[7] Append-only: multiple log_action calls accumulate in order")
logger.reset()
for i in range(5):
    logger.log_action(f"INV-{1000+i}", "email_generated", "ok", f"Reason {i}")

entries = logger.get_summary()["log"]
assert len(entries) == 5
for i, e in enumerate(entries):
    assert e["invoice_no"] == f"INV-{1000+i}", f"Order wrong at index {i}"
print("    PASS  5 entries appended in insertion order")
print("    PASS  invoice_no values are in correct sequence")
print()

print("ALL LOGGER CHECKS PASSED.")
