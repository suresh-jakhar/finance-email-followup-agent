import pandas as pd
from datetime import date


def update_followup(invoice_no: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Increment followup_count and set last_followup_date to today for one invoice.

    The DataFrame is mutated in-place and also returned so callers can chain.
    Persistence (save_invoices) is deliberately NOT called here — this separation
    makes the function easy to test and keeps responsibilities single.

    Args:
        invoice_no: The invoice identifier to update (e.g. "INV-1033").
        df:         The full invoice DataFrame loaded by load_invoices().

    Returns:
        The mutated DataFrame.

    Raises:
        ValueError: If the invoice_no is not found in the DataFrame.
    """
    mask = df["invoice_no"] == invoice_no
    if not mask.any():
        raise ValueError(f"Invoice '{invoice_no}' not found in DataFrame.")

    today_str = date.today().isoformat()

    df.loc[mask, "followup_count"] = df.loc[mask, "followup_count"] + 1
    df.loc[mask, "last_followup_date"] = pd.Timestamp(today_str)

    return df
