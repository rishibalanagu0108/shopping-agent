import json
import re

from langchain_core.messages import HumanMessage, ToolMessage

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

# Ponytail: denylist, not a topic classifier — catches obviously unrelated queries,
# not every off-topic phrasing. Upgrade path: LLM-based intent check if false
# negatives (off-topic questions slipping through) become a real problem.
OFF_TOPIC_PATTERNS = [
    "weather",
    "capital of",
    "who is the president",
    "write a poem",
    "write code",
    "solve this equation",
    "translate this",
    "meaning of life",
    "current news",
    "stock market",
    "cricket score",
    "football match",
]

MIN_LENGTH = 2


def check_input(text: str) -> dict:
    """Rule-based pre-LLM check: reject off-topic/too-short/gibberish/injection attempts."""
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

    for pattern in OFF_TOPIC_PATTERNS:
        if pattern in lower:
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
