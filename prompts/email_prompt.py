"""
prompts/email_prompt.py

LangChain ChatPromptTemplate definitions for each urgency tier.
Aligned with the Tone Escalation Matrix.

"""

from langchain_core.prompts import ChatPromptTemplate

from src.triage import (
    TIER_WARM,
    TIER_FIRM,
    TIER_SERIOUS,
    TIER_STERN,
    TIER_LEGAL,
)


_SYSTEM_PERSONA = (
    "You are a Senior Accounts Receivable Manager specializing in strategic debt recovery. "
    "Your communication style is surgical: precise, professional, and authoritative, yet "
    "carefully calibrated to preserve the long-term commercial relationship. "
    "\n\nGUIDELINES:"
    "\n- PRECISION: Use exact data (dates, amounts) to create accountability."
    "\n- SCANNABILITY: Keep paragraphs short and the 'Call to Action' unmistakable."
    "\n- BREVITY: Avoid filler. Every sentence must serve the goal of securing payment."
    "\n- SIGNATURE: Consistently sign off as {sender_name}."
    "\n\nSTRICT VOCABULARY RULES:"
    "\n- BAN: Do NOT use the word 'outstanding' or the phrase 'slipped through the cracks'."
    "\n- MANDATORY ALTERNATIVES: Use ONLY 'pending invoice', 'unpaid invoice', 'payment due', or 'open invoice'."
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
Write a professional and concise payment reminder.
Assume a simple oversight and maintain a helpful tone.

Invoice Details:
- Client: {client_name}
- Invoice No: {invoice_no}
- Amount: ${invoice_amount}
- Due Date: {due_date}

Tone: Helpful & Professional.
Instructions: Mention that payment is now overdue.
CTA: Provide the Payment Link: {payment_link} and Bank Details: {bank_details}.
Sign off as: {sender_name}
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
Write a firm and direct follow-up email.
State that the payment remains unsettled and we require a confirmed payment date.

Invoice Details:
- Client: {client_name}
- Invoice No: {invoice_no}
- Amount: ${invoice_amount}
- Due Date: {due_date}

Tone: Firm & Direct.
Instructions: Mention that payment is now overdue.
CTA: Ask for a confirmed payment date. Remind them they can pay at {payment_link}.
Sign off as: {sender_name}
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
Write a formal and serious notification.
Express concern regarding the unresolved balance and the potential impact on their credit terms.

Invoice Details:
- Client: {client_name}
- Invoice No: {invoice_no}
- Amount: ${invoice_amount}
- Days Overdue: {days_overdue}

Tone: Formal & Serious.
CTA: Demand a response within 48 hours. Provide payment link {payment_link} and bank details {bank_details}.
Sign off as: {sender_name}
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
Write a stern final warning.
This is the last notice before the account is referred to legal/debt recovery.

Invoice Details:
- Client: {client_name}
- Invoice No: {invoice_no}
- Amount: ${invoice_amount}

Tone: Stern & Urgent.
CTA: Demand immediate payment via {payment_link}.
Sign off as: {sender_name}
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
