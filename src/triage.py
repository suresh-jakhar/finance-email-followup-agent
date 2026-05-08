"""
src/triage.py

Filters and classifies pending invoices that need a follow-up email.
Assigns each an urgency_tier based on the escalation ladder defined
in the implementation plan.

Zero LLM dependency — pure Python / pandas logic.
"""

import pandas as pd
from datetime import date


# Urgency tier labels — ordered from lowest to highest severity.
TIER_REMINDER = "reminder"
TIER_FIRST_FOLLOWUP = "first_followup"
TIER_SECOND_FOLLOWUP = "second_followup"
TIER_ESCALATION = "escalation"
TIER_FINAL_NOTICE = "final_notice"


def _assign_tier(row: pd.Series) -> str:
    """
    Determine the urgency tier for a single invoice row.

    Precedence matters: final_notice must be evaluated before escalation
    because its conditions are a strict superset of escalation conditions.

    Escalation ladder (from the implementation plan):
    - final_notice   : days_overdue > 60  OR  followup_count >= 5
    - escalation     : days_overdue > 30  OR  followup_count >= 4
    - second_followup: 16 <= days_overdue <= 30  OR  followup_count in {2, 3}
    - first_followup : days_overdue <= 15  AND  followup_count <= 1
    - reminder       : days_overdue == 0  AND  followup_count == 0
    """
    days: int = int(row["days_overdue"])
    count: int = int(row["followup_count"])

    if days > 60 or count >= 5:
        return TIER_FINAL_NOTICE

    if days > 30 or count >= 4:
        return TIER_ESCALATION

    if (16 <= days <= 30) or count in (2, 3):
        return TIER_SECOND_FOLLOWUP

    if days <= 15 and count <= 1:
        # Distinguish a first-ever reminder (nothing sent yet, not overdue)
        # from a first follow-up (already overdue or one prior send).
        if days == 0 and count == 0:
            return TIER_REMINDER
        return TIER_FIRST_FOLLOWUP

    # Fallback — shouldn't be reached given filter logic, but be explicit
    return TIER_FIRST_FOLLOWUP


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

    # Step 1 — Keep only unpaid invoices
    result = result[result["payment_status"] == "Pending"]

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
