"""
src/data_loader.py

Reads invoice data from CSV into a clean, typed pandas DataFrame.
Also provides save_invoices() to write the DataFrame back to CSV
without data loss or column reordering.
"""

import pandas as pd
from datetime import date
from pathlib import Path


# Canonical column order — must match the original CSV header exactly.
_COLUMN_ORDER = [
    "invoice_no",
    "client_name",
    "invoice_amount",
    "due_date",
    "contact_email",
    "followup_count",
    "payment_status",
    "last_followup_date",
    "days_overdue",
]


def load_invoices(path: str) -> pd.DataFrame:
    """
    Load invoice data from a CSV file and return a clean DataFrame.

    Transformations applied:
    - Parses due_date and last_followup_date as datetime objects.
    - Fills NaT for rows where last_followup_date is empty.
    - Recalculates days_overdue dynamically against today's date
      (do not trust the stale value in the CSV).

    Args:
        path: Absolute or relative path to the CSV file.

    Returns:
        A clean DataFrame with correct dtypes, ready for triage.
    """
    df = pd.read_csv(path)

    # Parse date columns; errors='coerce' turns unparseable values into NaT
    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["last_followup_date"] = pd.to_datetime(
        df["last_followup_date"], errors="coerce"
    )

    # Ensure numeric types are correct
    df["invoice_amount"] = pd.to_numeric(df["invoice_amount"], errors="coerce")
    df["followup_count"] = pd.to_numeric(
        df["followup_count"], errors="coerce"
    ).fillna(0).astype(int)

    # Recalculate days_overdue at runtime — the CSV value is a stale snapshot
    today = pd.Timestamp(date.today())
    df["days_overdue"] = (today - df["due_date"]).dt.days.clip(lower=0)

    return df


def save_invoices(df: pd.DataFrame, path: str) -> None:
    """
    Write the DataFrame back to CSV, preserving the original column order
    and formatting date columns as ISO-8601 strings (YYYY-MM-DD).

    Args:
        df:   The DataFrame to persist (may contain extra columns from triage).
        path: Destination CSV path (typically the same as the source).
    """
    output = df.copy()

    # Format date columns back to ISO strings; NaT becomes an empty string
    output["due_date"] = output["due_date"].dt.strftime("%Y-%m-%d")
    output["last_followup_date"] = output["last_followup_date"].dt.strftime(
        "%Y-%m-%d"
    )
    # Replace 'NaT' strings (produced by strftime on NaT) with empty string
    output["last_followup_date"] = output["last_followup_date"].replace(
        "NaT", ""
    )

    # Keep only the canonical columns in the correct order
    output = output[_COLUMN_ORDER]

    output.to_csv(path, index=False)
