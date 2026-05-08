"""Smoke test for Step 3 — Prompt Templates. Run with: python test_prompts.py"""

from langchain_core.prompts import ChatPromptTemplate

from src.triage import (
    TIER_REMINDER,
    TIER_FIRST_FOLLOWUP,
    TIER_SECOND_FOLLOWUP,
    TIER_ESCALATION,
    TIER_FINAL_NOTICE,
)
from prompts.email_prompt import (
    get_prompt_for_tier,
    PROMPT_REMINDER,
    PROMPT_FIRST_FOLLOWUP,
    PROMPT_SECOND_FOLLOWUP,
    PROMPT_ESCALATION,
    PROMPT_FINAL_NOTICE,
    _PROMPT_REGISTRY,
)

ALL_TIERS = [
    TIER_REMINDER,
    TIER_FIRST_FOLLOWUP,
    TIER_SECOND_FOLLOWUP,
    TIER_ESCALATION,
    TIER_FINAL_NOTICE,
]

# Sample invoice values used to format every template
SAMPLE = {
    "client_name": "Acme Corp",
    "invoice_no": "INV-1033",
    "invoice_amount": "6597.43",
    "due_date": "2026-03-24",
    "days_overdue": "45",
    "followup_count": "5",
    "format_instruction": "",   # placeholder — agent will supply real instruction
}

print("=== STEP 3 — PROMPT TEMPLATE TESTS ===\n")

# Test 1: all 5 tiers are in the registry
print("[1] Registry completeness")
for tier in ALL_TIERS:
    assert tier in _PROMPT_REGISTRY, f"Missing tier in registry: {tier}"
    print(f"    PASS  '{tier}' registered")

print()

# Test 2: get_prompt_for_tier returns correct type for each tier
print("[2] get_prompt_for_tier() returns ChatPromptTemplate")
for tier in ALL_TIERS:
    prompt = get_prompt_for_tier(tier)
    assert isinstance(prompt, ChatPromptTemplate), (
        f"Expected ChatPromptTemplate for '{tier}', got {type(prompt)}"
    )
    print(f"    PASS  '{tier}'")

print()

# Test 3: unknown tier raises KeyError
print("[3] Unknown tier raises KeyError")
try:
    get_prompt_for_tier("nonexistent_tier")
    print("    FAIL  No error raised for unknown tier")
except KeyError as e:
    print(f"    PASS  KeyError raised: {e}")

print()

# Test 4: each template has system + human messages (2 messages)
print("[4] Each template has exactly 2 messages (system + human)")
for tier in ALL_TIERS:
    prompt = get_prompt_for_tier(tier)
    msg_count = len(prompt.messages)
    assert msg_count == 2, f"Tier '{tier}' has {msg_count} messages, expected 2"
    print(f"    PASS  '{tier}' has {msg_count} messages")

print()

# Test 5: all required input variables are present in each template
print("[5] Required input variables present in each template")
REQUIRED_VARS = {
    "client_name", "invoice_no", "invoice_amount",
    "due_date", "days_overdue", "followup_count",
}
for tier in ALL_TIERS:
    prompt = get_prompt_for_tier(tier)
    template_vars = set(prompt.input_variables)
    missing = REQUIRED_VARS - template_vars
    assert not missing, f"Tier '{tier}' missing variables: {missing}"
    print(f"    PASS  '{tier}' has all required variables")

print()

# Test 6: format the template with sample data — must not error
print("[6] Template formatting with sample invoice data")
for tier in ALL_TIERS:
    prompt = get_prompt_for_tier(tier)
    messages = prompt.format_messages(**SAMPLE)
    assert len(messages) == 2
    # Verify the client name is injected into the human message
    human_content = messages[1].content
    assert "Acme Corp" in human_content, f"client_name not injected for tier '{tier}'"
    assert "INV-1033" in human_content, f"invoice_no not injected for tier '{tier}'"
    print(f"    PASS  '{tier}' formatted correctly")

print()
print("ALL PROMPT TEMPLATE CHECKS PASSED.")
