"""
Dedicated smoke test for Step 5 — Email Sender (src/emailer.py).
Run with: python test_emailer.py

Tests all behaviours specified in the implementation plan:
  - dry_run mode returns correct dict without hitting SMTP
  - body_preview is first 200 chars of body
  - all required keys present in dry_run response
  - SMTP exception is caught and returned as error dict (not raised)
  - send_email signature matches spec: send_email(to, subject, body) -> dict
"""

import inspect
from unittest.mock import patch, MagicMock

from src import config, emailer

print("=== STEP 5 - EMAIL SENDER TESTS ===\n")

# ── Test 1: signature matches spec ────────────────────────────────────────────
print("[1] Function signature: send_email(to, subject, body) -> dict")
sig = inspect.signature(emailer.send_email)
params = list(sig.parameters.keys())
assert params == ["to", "subject", "body"], f"Wrong params: {params}"
print(f"    PASS  params = {params}")
print()

# ── Test 2: dry_run mode — correct status and keys ───────────────────────────
print("[2] DRY_RUN=True returns correct dict without SMTP call")
assert config.DRY_RUN is True, "Set DRY_RUN=true in .env.example / environment"

result = emailer.send_email(
    to="billing@acmecorp.com",
    subject="Invoice #INV-1033 — Payment Overdue",
    body="Dear Acme Corp, your invoice INV-1033 for $6597.43 is overdue.",
)
assert result["status"] == "dry_run", f"Expected dry_run, got: {result['status']}"
assert result["to"] == "billing@acmecorp.com"
assert "timestamp" in result
assert "body_preview" in result
print("    PASS  status='dry_run'")
print("    PASS  'to' key matches recipient")
print("    PASS  'timestamp' key present")
print("    PASS  'body_preview' key present")
print()

# ── Test 3: body_preview is exactly body[:200] ────────────────────────────────
print("[3] body_preview is first 200 characters of body")
long_body = "X" * 300
result_long = emailer.send_email(to="a@b.com", subject="S", body=long_body)
assert result_long["body_preview"] == long_body[:200], "body_preview not truncated to 200 chars"
assert len(result_long["body_preview"]) == 200
print("    PASS  body_preview correctly truncated to 200 chars")

short_body = "Short body."
result_short = emailer.send_email(to="a@b.com", subject="S", body=short_body)
assert result_short["body_preview"] == short_body
print("    PASS  body_preview preserves full body when under 200 chars")
print()

# ── Test 4: SMTP exception caught — returns error dict, never raises ──────────
print("[4] SMTP error is caught and returned as error dict — never raised")

# Temporarily switch to live mode to exercise the SMTP path
original_dry_run = config.DRY_RUN
config.DRY_RUN = False

with patch("smtplib.SMTP") as mock_smtp:
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
    mock_server.login.side_effect = Exception("Authentication failed")

    err_result = emailer.send_email(
        to="billing@acmecorp.com",
        subject="Test",
        body="Test body",
    )

config.DRY_RUN = original_dry_run  # restore

assert err_result["status"] == "error", f"Expected error, got: {err_result['status']}"
assert "reason" in err_result, "Missing 'reason' key in error dict"
assert "Authentication failed" in err_result["reason"]
assert "timestamp" in err_result
print("    PASS  SMTP exception caught — status='error'")
print(f"    PASS  reason key present: '{err_result['reason']}'")
print("    PASS  agent-safe — no exception raised to caller")
print()

# ── Test 5: live mode builds correct MIME message ─────────────────────────────
print("[5] Live mode: MIMEText built with correct headers")
config.DRY_RUN = False

captured = {}
with patch("smtplib.SMTP") as mock_smtp:
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    def capture_sendmail(from_addr, to_addrs, msg_str):
        captured["from"] = from_addr
        captured["to"] = to_addrs
        captured["msg"] = msg_str

    mock_server.sendmail.side_effect = capture_sendmail

    sent_result = emailer.send_email(
        to="billing@acmecorp.com",
        subject="Invoice Reminder",
        body="Please pay your invoice.",
    )

config.DRY_RUN = original_dry_run  # restore

assert sent_result["status"] == "sent", f"Expected sent, got: {sent_result['status']}"
assert "timestamp" in sent_result
assert "billing@acmecorp.com" in captured.get("to", [])
assert "Invoice Reminder" in captured.get("msg", "")
print("    PASS  status='sent' in live mode")
print("    PASS  sendmail called with correct recipient")
print("    PASS  subject injected into MIME message")
print()

print("ALL EMAIL SENDER CHECKS PASSED.")
