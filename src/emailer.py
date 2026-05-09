"""
src/emailer.py

Isolated email sender with dry-run support.
Never let an SMTP failure crash the agent — all exceptions are caught
and returned as an error dict.
"""

import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from src import config


def send_email(to: str, subject: str, body: str) -> dict:
    """
    Send a plain-text email, or simulate the send in dry-run mode.

    Args:
        to:      Recipient email address.
        subject: Email subject line.
        body:    Plain-text email body.

    Returns:
        dict with keys:
          - status      : "sent" | "dry_run" | "error"
          - to          : recipient address
          - timestamp   : ISO-8601 UTC string
          - body_preview: first 200 chars of body (dry_run only)
          - reason      : error message (error only)
    """
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    if config.DRY_RUN:
        print(f"[DRY RUN] to={to} | subject={subject[:80]}")
        return {
            "status": "dry_run",
            "to": to,
            "timestamp": timestamp,
            "body_preview": body[:200],
        }

    # Build the MIME message
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = f"{config.SMTP_SENDER_NAME} <{config.SMTP_USER}>"
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg["Reply-To"] = config.SMTP_USER

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_USER, [to], msg.as_string())

        return {"status": "sent", "to": to, "timestamp": timestamp}

    except Exception as exc:
        return {"status": "error", "to": to, "timestamp": timestamp, "reason": str(exc)}
