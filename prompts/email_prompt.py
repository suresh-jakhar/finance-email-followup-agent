"""
prompts/email_prompt.py

LangChain ChatPromptTemplate definitions for each urgency tier.
Strictly aligned with the Mandatory Tone Escalation Matrix.
"""

from langchain_core.prompts import ChatPromptTemplate

from src.triage import (
    TIER_WARM,
    TIER_FIRM,
    TIER_SERIOUS,
    TIER_STERN,
    TIER_LEGAL,
)

# ── Shared agent persona ──────────────────────────────────────────────────────

_SYSTEM_PERSONA = (
    "You are a professional credit collections specialist. Your goal is to "
    "maintain professional communication while following a strict escalation "
    "ladder to reduce DSO (Days Sales Outstanding). You must vary your tone "
    "and urgency exactly as instructed."
)

_FORMAT_INSTRUCTION = """
Respond with ONLY the email in this exact format:

Subject: <subject line>

Body:
<email body>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — WARM (1-7 days)
# Tone      : Warm & Friendly
# Message   : Gentle reminder, assume oversight
# CTA       : Pay now link / bank details
# ─────────────────────────────────────────────────────────────────────────────

_WARM_HUMAN = """
Write a WARM and FRIENDLY payment reminder email.
Assume the client simply overlooked the invoice (gentle reminder).

Invoice Details:
- Client: {client_name}
- Invoice No: {invoice_no}
- Amount: ${invoice_amount}
- Due Date: {due_date}
- Days Overdue: {days_overdue}

Mandatory Tone: Warm & Friendly.
Mandatory CTA: Include a link to pay now or provide bank details for immediate transfer.
{format_instruction}
"""

PROMPT_WARM = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PERSONA),
    ("human", _WARM_HUMAN),
])

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — FIRM (8-14 days)
# Tone      : Polite but Firm
# Message   : Payment still pending; request confirmation
# CTA       : Confirm payment date
# ─────────────────────────────────────────────────────────────────────────────

_FIRM_HUMAN = """
Write a POLITE BUT FIRM follow-up email.
State that the payment is still pending and we require confirmation.

Invoice Details:
- Client: {client_name}
- Invoice No: {invoice_no}
- Amount: ${invoice_amount}
- Due Date: {due_date}
- Days Overdue: {days_overdue}

Mandatory Tone: Polite but Firm.
Mandatory CTA: Ask the client to provide a confirmed payment date.
{format_instruction}
"""

PROMPT_FIRM = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PERSONA),
    ("human", _FIRM_HUMAN),
])

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — SERIOUS (15-21 days)
# Tone      : Formal & Serious
# Message   : Escalating concern; mention impact on credit/relationship
# CTA       : Respond within 48 hrs
# ─────────────────────────────────────────────────────────────────────────────

_SERIOUS_HUMAN = """
Write a FORMAL and SERIOUS follow-up email.
Mention our escalating concern and that continued non-payment may impact their credit terms.

Invoice Details:
- Client: {client_name}
- Invoice No: {invoice_no}
- Amount: ${invoice_amount}
- Due Date: {due_date}
- Days Overdue: {days_overdue}

Mandatory Tone: Formal & Serious.
Mandatory CTA: Request a response within the next 48 hours.
{format_instruction}
"""

PROMPT_SERIOUS = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PERSONA),
    ("human", _SERIOUS_HUMAN),
])

# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — STERN (22-30 days)
# Tone      : Stern & Urgent
# Message   : Final reminder before escalation to legal/debt recovery
# CTA       : Pay immediately or call us
# ─────────────────────────────────────────────────────────────────────────────

_STERN_HUMAN = """
Write a STERN and URGENT final reminder email.
This is the last warning before the account is referred to our legal/recovery team.

Invoice Details:
- Client: {client_name}
- Invoice No: {invoice_no}
- Amount: ${invoice_amount}
- Due Date: {due_date}
- Days Overdue: {days_overdue}

Mandatory Tone: Stern & Urgent.
Mandatory CTA: Demand payment immediately or instruct them to call our office right away.
{format_instruction}
"""

PROMPT_STERN = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PERSONA),
    ("human", _STERN_HUMAN),
])

# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

_PROMPT_REGISTRY = {
    TIER_WARM: PROMPT_WARM,
    TIER_FIRM: PROMPT_FIRM,
    TIER_SERIOUS: PROMPT_SERIOUS,
    TIER_STERN: PROMPT_STERN,
}

def get_prompt_for_tier(tier: str):
    """Return the prompt template for the given tier. 
    Note: TIER_LEGAL should be handled by the caller as a 'Stop' condition."""
    if tier not in _PROMPT_REGISTRY:
        if tier == TIER_LEGAL:
            raise ValueError("legal_escalation does not have an automated email prompt.")
        raise KeyError(f"Unknown tier: {tier}")
    return _PROMPT_REGISTRY[tier]
