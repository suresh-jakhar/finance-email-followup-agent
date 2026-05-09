"""
src/triage.py

Filters and classifies pending invoices that need a follow-up email.
Assigns each an urgency_tier based on the escalation ladder defined
in the implementation plan.

Zero LLM dependency — pure Python / pandas logic.
"""

import pandas as pd
from datetime import date


# Urgency tier labels — strictly aligned with the Tone Escalation Matrix.
TIER_WARM = "stage_1_warm"              # 1-7 days
TIER_FIRM = "stage_2_firm"              # 8-14 days
TIER_SERIOUS = "stage_3_serious"        # 15-21 days
TIER_STERN = "stage_4_stern"            # 22-30 days
TIER_LEGAL = "legal_escalation"         # 30+ days (STOP)


def _assign_tier(row: pd.Series) -> str:
    """
    Determine the urgency tier for a single invoice row.

    Precedence matters: final_notice must be evaluated before escalation
    because its conditions are a strict superset of escalation conditions.

    Escalation ladder (aligned with Tone Escalation Matrix):
    - legal_escalation : days_overdue > 30
    - stage_4_stern    : 22 <= days_overdue <= 30
    - stage_3_serious  : 15 <= days_overdue <= 21
    - stage_2_firm     : 8 <= days_overdue <= 14
    - stage_1_warm     : 1 <= days_overdue <= 7
    """
    days: int = int(row["days_overdue"])

    if days > 30:
        return TIER_LEGAL

    if 22 <= days <= 30:
        return TIER_STERN

    if 15 <= days <= 21:
        return TIER_SERIOUS

    if 8 <= days <= 14:
        return TIER_FIRM

    # Default to warm if it's anywhere from 1 to 7 days
    # (or 0 if it's the exact due date, assuming oversight)
    return TIER_WARM


def triage_invoices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter and score pending invoices, returning only those that need
    a follow-up email, annotated with an urgency tier.

    Steps:
    1. Keep only Pending invoices.
    2. Drop invoices not yet actionable (not overdue AND due > 7 days away).
    3. Assign urgency_tier to every remaining row.
    4. Sort by days_overdue DESC, then invoice_amount DESC as tiebreaker.

    Args:
        df: Clean DataFrame produced by load_invoices().

    Returns:
        Filtered, sorted DataFrame with an added 'urgency_tier' column.
        The original DataFrame is not mutated.
    """
    result = df.copy()

    # Step 1 — Keep only unpaid invoices (Pending, Overdue, Critical, etc.)
    result = result[result["payment_status"] != "Paid"]

    # Step 2 — Exclude invoices that aren't yet actionable:
    #   not overdue (days_overdue == 0) AND due date is more than 7 days out
    today = pd.Timestamp(date.today())
    days_until_due = (result["due_date"] - today).dt.days
    not_yet_actionable = (result["days_overdue"] == 0) & (days_until_due > 7)
    result = result[~not_yet_actionable]

    # Step 3 — Assign urgency tier row-by-row
    result["urgency_tier"] = result.apply(_assign_tier, axis=1)

    # Step 4 — Sort: most overdue first, largest invoice as tiebreaker
    result = result.sort_values(
        by=["days_overdue", "invoice_amount"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return result
