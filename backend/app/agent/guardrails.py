import json
import os
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

# Must not rely on graph.py's load_dotenv() running first -- this module reads
# OPENROUTER_API_KEY at import time too, and graph.py imports guardrails before
# calling load_dotenv() itself, so the env var isn't loaded yet at that point.
load_dotenv()

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
    model="moonshotai/kimi-k2.5",
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
            # manage_cart's "added" result is a single dict, not a list -- it's still a
            # DB-grounded name+price (see tools.py) worth cross-checking the confirmation
            # text against, same as a search_products row.
            elif isinstance(data, dict) and "name" in data and "price" in data:
                products.append(data)
    return products


def extract_last_totals(messages: list) -> list[float]:
    """manage_cart's view/checkout actions return a dict with a "total" key, not a
    product list -- extract_last_products can't see those. A checkout confirmation
    quoting the real order total would otherwise look identical to a hallucinated
    price with nothing to cross-check against."""
    totals = []
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            break
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, dict) and isinstance(data.get("total"), (int, float)):
                totals.append(data["total"])
    return totals


def verify_output(response: str, last_products: list[dict], last_totals: list[float] | None = None) -> dict:
    """
    Anti-hallucination check (the Rufus-style failure this guards against: an LLM
    confidently quoting a product or price it invented). Cross-references any product
    name mentioned in the response against last_products — which came straight from a
    DB-backed tool call this turn — and checks quoted prices land within 10% of the
    real price. Post-LLM because the model has already generated the text by this
    point; we can only verify and swap in a safe fallback, not prevent generation.

    A response that quotes a price but names no product from last_products (or
    last_products is empty because the tool found nothing/nothing relevant) is the
    exact shape of an invented listing — flagged unsafe even without a name match,
    since a real grounded answer would only ever quote prices from this turn's tool
    result. last_totals covers the one legitimate exception: a cart/checkout total,
    which is a real price with no product name to match against. Ponytail: still
    can't catch a hallucinated product name with zero price quoted at all — upgrade
    path is a stricter parse or NER pass if that matters.
    """
    quoted_prices = [float(m.replace(",", "")) for m in PRICE_PATTERN.findall(response)]
    last_totals = last_totals or []
    total_grounded = any(abs(q - t) / t <= 0.10 for q in quoted_prices for t in last_totals if t)

    if not last_products:
        safe = not quoted_prices or total_grounded
        return {"safe": safe, "response": response if safe else FALLBACK_RESPONSE}

    lower = response.lower()
    mentioned = [p for p in last_products if p["name"].lower() in lower]
    if not mentioned:
        safe = not quoted_prices or total_grounded
        return {"safe": safe, "response": response if safe else FALLBACK_RESPONSE}

    for product in mentioned:
        if quoted_prices and not any(abs(q - product["price"]) / product["price"] <= 0.10 for q in quoted_prices):
            return {"safe": False, "response": FALLBACK_RESPONSE}

    return {"safe": True, "response": response}
