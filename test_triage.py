"""Smoke test for Step 2 — Triage Engine. Run with: python test_triage.py"""

import pandas as pd
from datetime import date

from src.config import DATA_PATH
from src.data_loader import load_invoices
from src.triage import (
    triage_invoices,
    _assign_tier,
    TIER_REMINDER,
    TIER_FIRST_FOLLOWUP,
    TIER_SECOND_FOLLOWUP,
    TIER_ESCALATION,
    TIER_FINAL_NOTICE,
)

df = load_invoices(DATA_PATH)
triaged = triage_invoices(df)

print("=== TRIAGE RESULTS ===")
print(f"Total rows in dataset    : {len(df)}")
print(f"Pending rows             : {len(df[df['payment_status'] == 'Pending'])}")
print(f"After triage (actionable): {len(triaged)}")
print()

print("=== TIER DISTRIBUTION ===")
print(triaged["urgency_tier"].value_counts().to_string())
print()

print("=== TOP 5 (most overdue) ===")
cols = ["invoice_no", "client_name", "days_overdue", "followup_count", "urgency_tier"]
print(triaged[cols].head(5).to_string(index=False))
print()

# ── Edge case tests ────────────────────────────────────────────────────────
today = pd.Timestamp(date.today())


def make_row(days_overdue: int, followup_count: int) -> pd.Series:
    due_date = today - pd.Timedelta(days=days_overdue)
    return pd.Series({
        "days_overdue": days_overdue,
        "followup_count": followup_count,
        "due_date": due_date,
        "invoice_amount": 1000,
        "payment_status": "Pending",
    })


cases = [
    (make_row(0, 0),  TIER_REMINDER,        "days=0,  count=0  -> reminder"),
    (make_row(5, 1),  TIER_FIRST_FOLLOWUP,  "days=5,  count=1  -> first_followup"),
    (make_row(15, 0), TIER_FIRST_FOLLOWUP,  "days=15, count=0  -> first_followup"),
    (make_row(16, 0), TIER_SECOND_FOLLOWUP, "days=16, count=0  -> second_followup"),
    (make_row(30, 1), TIER_SECOND_FOLLOWUP, "days=30, count=1  -> second_followup"),
    (make_row(0, 2),  TIER_SECOND_FOLLOWUP, "days=0,  count=2  -> second_followup"),
    (make_row(0, 3),  TIER_SECOND_FOLLOWUP, "days=0,  count=3  -> second_followup"),
    (make_row(31, 0), TIER_ESCALATION,      "days=31, count=0  -> escalation"),
    (make_row(0, 4),  TIER_ESCALATION,      "days=0,  count=4  -> escalation"),
    (make_row(60, 4), TIER_ESCALATION,      "days=60, count=4  -> escalation (exactly 60)"),
    (make_row(61, 0), TIER_FINAL_NOTICE,    "days=61, count=0  -> final_notice"),
    (make_row(0, 5),  TIER_FINAL_NOTICE,    "days=0,  count=5  -> final_notice"),
    (make_row(30, 5), TIER_FINAL_NOTICE,    "days=30, count=5  -> final_notice"),
]

print("=== EDGE CASE TESTS ===")
all_passed = True
for row, expected, label in cases:
    result = _assign_tier(row)
    status = "PASS" if result == expected else "FAIL"
    if status == "FAIL":
        all_passed = False
    print(f"  [{status}] {label}  (got: {result})")

print()
# Verify original df was not mutated
assert "urgency_tier" not in df.columns, "Original DataFrame was mutated!"
print("  [PASS] Original DataFrame not mutated")

# Verify sort order: days_overdue should be descending
assert list(triaged["days_overdue"]) == sorted(
    triaged["days_overdue"], reverse=True
), "Sort order is wrong!"
print("  [PASS] Sort order is correct (days_overdue DESC)")

# Verify no Paid invoices slipped through
assert (triaged["payment_status"] == "Paid").sum() == 0, "Paid invoices in result!"
print("  [PASS] No Paid invoices in triaged output")

print()
if all_passed:
    print("ALL CHECKS PASSED.")
else:
    print("SOME CHECKS FAILED — see above.")
    raise SystemExit(1)
