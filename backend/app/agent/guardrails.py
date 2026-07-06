import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

# Rule-based and pre-LLM on purpose: rejecting junk here costs zero tokens and zero
# latency, vs. paying for a full LLM call (and risking a jailbreak succeeding) just to
# find out the input was gibberish or an injection attempt.
INJECTION_PATTERNS = [
    "ignore previous",
    "ignore all previous",
    "ignore the above",
    "disregard previous",
    "disregard your instructions",
    "forget your role",
    "forget your instructions",
    "act as",
    "you are now",
    "new instructions",
    "override your instructions",
    "system prompt",
    "jailbreak",
]

MIN_LENGTH = 2

# Off-topic detection needs semantic judgement (a denylist can't enumerate every
# off-topic phrasing), so this is the one guardrail check that costs an LLM call.
# Kept cheap: separate no-tools client, temperature=0. max_tokens=300, not 5 -- this
# model is a reasoning variant that emits chain-of-thought before its final word, so a
# tight token cap cuts it off mid-thought (e.g. "We need to decide if") and it never
# reaches YES/NO at all.
_topic_classifier = ChatOpenAI(
    base_url="https://openrouter.ai/api/v1",
    model="nvidia/nemotron-3-super-120b-a12b:free",
    api_key=os.environ["OPENROUTER_API_KEY"],
    temperature=0,
    max_tokens=300,
)

TOPIC_CLASSIFIER_PROMPT = (
    "You are a strict binary topic classifier guarding a shopping assistant chatbot. "
    "The assistant only handles: searching products, prices, cart, checkout, orders, "
    "and recommendations. Reply with exactly one word, YES or NO. YES if the message "
    "below is on-topic for this shopping assistant. NO for anything else (coding help, "
    "general knowledge, math, translation, news, weather, small talk unrelated to "
    "shopping, etc.)."
)


async def _is_on_topic(text: str) -> bool:
    response = await _topic_classifier.ainvoke(
        [SystemMessage(content=TOPIC_CLASSIFIER_PROMPT), HumanMessage(content=text)]
    )
    return response.content.strip().upper().startswith("YES")


async def check_input(text: str) -> dict:
    """Reject too-short/gibberish/injection attempts via zero-cost rules first, then
    off-topic via LLM classifier (see _is_on_topic) only if those cheap checks pass."""
    stripped = text.strip()
    if len(stripped) < MIN_LENGTH:
        return {"allowed": False, "reason": "too_short"}

    lower = stripped.lower()

    for pattern in INJECTION_PATTERNS:
        if pattern in lower:
            return {"allowed": False, "reason": "injection_detected"}

    alpha_chars = sum(c.isalpha() for c in stripped)
    if alpha_chars / len(stripped) < 0.3:
        return {"allowed": False, "reason": "gibberish"}

    words = [w for w in lower.split() if len(w) > 2]
    if words and not any(any(v in w for v in "aeiou") for w in words):
        return {"allowed": False, "reason": "gibberish"}

    if not await _is_on_topic(stripped):
        return {"allowed": False, "reason": "off_topic"}

    return {"allowed": True, "reason": None}


PRICE_PATTERN = re.compile(r"(?:₹|rs\.?)\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE)

FALLBACK_RESPONSE = (
    "Sorry, I couldn't verify that pricing/product info against our catalog — "
    "could you rephrase, or ask me to search again?"
)


def extract_last_products(messages: list) -> list[dict]:
    """Pull product dicts out of ToolMessages since the last HumanMessage — these are
    the only products actually grounded in a DB query this turn."""
    products = []
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            break
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, list):
                products.extend(p for p in data if isinstance(p, dict) and "name" in p and "price" in p)
    return products


def verify_output(response: str, last_products: list[dict]) -> dict:
    """
    Anti-hallucination check (the Rufus-style failure this guards against: an LLM
    confidently quoting a product or price it invented). Cross-references any product
    name mentioned in the response against last_products — which came straight from a
    DB-backed tool call this turn — and checks quoted prices land within 10% of the
    real price. Post-LLM because the model has already generated the text by this
    point; we can only verify and swap in a safe fallback, not prevent generation.
    Ponytail: only catches mismatches against *this turn's* tool results, not every
    conceivable hallucination (an invented product with no price mentioned at all
    slips through) — upgrade path is a stricter parse or NER pass if that matters.
    """
    if not last_products:
        return {"safe": True, "response": response}

    lower = response.lower()
    mentioned = [p for p in last_products if p["name"].lower() in lower]
    if not mentioned:
        return {"safe": True, "response": response}

    quoted_prices = [float(m.replace(",", "")) for m in PRICE_PATTERN.findall(response)]
    for product in mentioned:
        if quoted_prices and not any(abs(q - product["price"]) / product["price"] <= 0.10 for q in quoted_prices):
            return {"safe": False, "response": FALLBACK_RESPONSE}

    return {"safe": True, "response": response}
