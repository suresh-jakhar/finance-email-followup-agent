"""
prompts/email_prompt.py

LangChain ChatPromptTemplate definitions for each urgency tier.
Each template produces a personalised, professional follow-up email
when formatted with real invoice data.

Tier keys match the constants in src/triage.py:
  reminder | first_followup | second_followup | escalation | final_notice
"""

from langchain_core.prompts import ChatPromptTemplate

from src.triage import (
    TIER_REMINDER,
    TIER_FIRST_FOLLOWUP,
    TIER_SECOND_FOLLOWUP,
    TIER_ESCALATION,
    TIER_FINAL_NOTICE,
)

# ── Shared agent persona ──────────────────────────────────────────────────────

_SYSTEM_PERSONA = (
    "You are a professional credit collections specialist at a finance company. "
    "Your job is to write concise, personalised payment follow-up emails on behalf "
    "of the finance team. You always address the client by name, reference the exact "
    "invoice number and amount, and include a clear call to action. "
    "Every email must feel human — never generic or templated."
)

# ── Shared output format instruction (appended to every human message) ────────

_FORMAT_INSTRUCTION = """
Respond with ONLY the email in this exact format — no extra commentary:

Subject: <subject line>

Body:
<email body>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — REMINDER
# Condition : days_overdue == 0, followup_count == 0
# Tone      : Warm & friendly — payment day has arrived, gentle heads-up
# ─────────────────────────────────────────────────────────────────────────────

_REMINDER_HUMAN = """
Write a warm, friendly payment reminder email for the following invoice.
The payment is due today or very soon — this is the first time we are reaching out.

Invoice details:
- Client name    : {client_name}
- Invoice number : {invoice_no}
- Amount due     : ${invoice_amount}
- Due date       : {due_date}
- Days overdue   : {days_overdue}
- Follow-ups sent: {followup_count}

Instructions:
- Tone must be warm, polite, and friendly — no pressure language.
- Mention the invoice number and amount clearly.
- Include a gentle call to action: ask them to process payment or get in touch
  if they have any questions.
- Keep the email brief (3–4 short paragraphs max).
{format_instruction}
"""

PROMPT_REMINDER: ChatPromptTemplate = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PERSONA),
    ("human", _REMINDER_HUMAN),
])

# ─────────────────────────────────────────────────────────────────────────────
# Tier 2 — FIRST FOLLOW-UP
# Condition : days_overdue <= 15, followup_count <= 1
# Tone      : Professional & courteous — friendly but with a clear ask
# ─────────────────────────────────────────────────────────────────────────────

_FIRST_FOLLOWUP_HUMAN = """
Write a professional, courteous follow-up email for an overdue invoice.
The invoice is slightly overdue and this is our first or second outreach.

Invoice details:
- Client name    : {client_name}
- Invoice number : {invoice_no}
- Amount due     : ${invoice_amount}
- Due date       : {due_date}
- Days overdue   : {days_overdue}
- Follow-ups sent: {followup_count}

Instructions:
- Tone must be professional and courteous — polite but clear that payment is overdue.
- Acknowledge that oversights happen.
- Mention the invoice number, amount, and how many days overdue it is.
- Ask them to process payment promptly or confirm if there is an issue.
- Keep the email concise (3–4 paragraphs).
{format_instruction}
"""

PROMPT_FIRST_FOLLOWUP: ChatPromptTemplate = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PERSONA),
    ("human", _FIRST_FOLLOWUP_HUMAN),
])

# ─────────────────────────────────────────────────────────────────────────────
# Tier 3 — SECOND FOLLOW-UP
# Condition : 16 <= days_overdue <= 30  OR  followup_count in {2, 3}
# Tone      : Firm & urgent — previous reminders sent, we need a response
# ─────────────────────────────────────────────────────────────────────────────

_SECOND_FOLLOWUP_HUMAN = """
Write a firm, urgent follow-up email for a significantly overdue invoice.
We have already sent one or more reminders with no response or payment.

Invoice details:
- Client name    : {client_name}
- Invoice number : {invoice_no}
- Amount due     : ${invoice_amount}
- Due date       : {due_date}
- Days overdue   : {days_overdue}
- Follow-ups sent: {followup_count}

Instructions:
- Tone must be firm and convey urgency — professional but no longer gentle.
- Reference that previous reminders have been sent without resolution.
- State clearly that the invoice is now {days_overdue} days overdue.
- Request immediate payment or written confirmation of a payment date within 48 hours.
- Do NOT use aggressive or legally threatening language.
- Keep the email concise (3–4 paragraphs).
{format_instruction}
"""

PROMPT_SECOND_FOLLOWUP: ChatPromptTemplate = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PERSONA),
    ("human", _SECOND_FOLLOWUP_HUMAN),
])

# ─────────────────────────────────────────────────────────────────────────────
# Tier 4 — ESCALATION
# Condition : days_overdue > 30  OR  followup_count >= 4
# Tone      : Serious — references potential consequences, needs action now
# ─────────────────────────────────────────────────────────────────────────────

_ESCALATION_HUMAN = """
Write a serious, formal escalation email for a substantially overdue invoice.
Multiple prior follow-ups have been sent with no satisfactory response.

Invoice details:
- Client name    : {client_name}
- Invoice number : {invoice_no}
- Amount due     : ${invoice_amount}
- Due date       : {due_date}
- Days overdue   : {days_overdue}
- Follow-ups sent: {followup_count}

Instructions:
- Tone must be serious and formal — no pleasantries, straight to the point.
- Make clear that this is an escalation: multiple reminders have been ignored.
- State that continued non-payment may impact the client's credit terms and
  the business relationship with our company.
- Demand payment or a confirmed payment plan in writing within 48 hours.
- Mention that failure to respond may result in this matter being escalated
  to senior management or a collections review.
- Do NOT use explicit legal threats yet.
- Keep the email concise and direct (3–4 paragraphs).
{format_instruction}
"""

PROMPT_ESCALATION: ChatPromptTemplate = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PERSONA),
    ("human", _ESCALATION_HUMAN),
])

# ─────────────────────────────────────────────────────────────────────────────
# Tier 5 — FINAL NOTICE
# Condition : days_overdue > 60  OR  followup_count >= 5
# Tone      : Formal final notice — references legal/recovery escalation
# ─────────────────────────────────────────────────────────────────────────────

_FINAL_NOTICE_HUMAN = """
Write a formal final notice email for a severely overdue invoice.
All previous escalation attempts have been exhausted. This is the last
communication before the account is referred for legal or collections review.

Invoice details:
- Client name    : {client_name}
- Invoice number : {invoice_no}
- Amount due     : ${invoice_amount}
- Due date       : {due_date}
- Days overdue   : {days_overdue}
- Follow-ups sent: {followup_count}

Instructions:
- Tone must be cold, formal, and unambiguous — this is a final notice.
- State clearly that all previous attempts to resolve this matter have failed.
- Inform the client that this is their final opportunity to settle the balance
  before the account is formally referred to our legal and debt recovery team.
- Demand full payment within 24 hours.
- Include a note that failure to pay will result in formal legal proceedings
  and may affect the client's credit standing.
- You MAY reference legal escalation and debt recovery at this tier.
- Keep the email concise and precise (3–4 paragraphs).
{format_instruction}
"""

PROMPT_FINAL_NOTICE: ChatPromptTemplate = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PERSONA),
    ("human", _FINAL_NOTICE_HUMAN),
])

# ─────────────────────────────────────────────────────────────────────────────
# Registry — maps tier string to its ChatPromptTemplate
# ─────────────────────────────────────────────────────────────────────────────

_PROMPT_REGISTRY: dict[str, ChatPromptTemplate] = {
    TIER_REMINDER:        PROMPT_REMINDER,
    TIER_FIRST_FOLLOWUP:  PROMPT_FIRST_FOLLOWUP,
    TIER_SECOND_FOLLOWUP: PROMPT_SECOND_FOLLOWUP,
    TIER_ESCALATION:      PROMPT_ESCALATION,
    TIER_FINAL_NOTICE:    PROMPT_FINAL_NOTICE,
}


def get_prompt_for_tier(tier: str) -> ChatPromptTemplate:
    """
    Return the ChatPromptTemplate for a given urgency tier.

    Args:
        tier: One of the TIER_* constants from src.triage.

    Returns:
        The corresponding ChatPromptTemplate.

    Raises:
        KeyError: If the tier string is not recognised.
    """
    if tier not in _PROMPT_REGISTRY:
        valid = list(_PROMPT_REGISTRY.keys())
        raise KeyError(f"Unknown tier '{tier}'. Valid tiers: {valid}")
    return _PROMPT_REGISTRY[tier]
