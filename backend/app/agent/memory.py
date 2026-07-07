import re

from langchain_core.messages import BaseMessage, SystemMessage
from sqlalchemy import select

from app.db.database import async_session
from app.db.schema import Order, OrderItem, Product, User

# Window = ~6 turns (human+ai pairs; tool-call/tool-result messages ride along inside a
# turn). Without trimming, every past tool result and product list stays in the prompt
# forever — token cost grows unbounded per message, and past the model's context window
# the API silently drops old messages in an order we don't control.
SHORT_TERM_WINDOW = 12


def trim_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    if not messages:
        return messages
    head = [messages[0]] if isinstance(messages[0], SystemMessage) else []
    body = messages[len(head):]
    return head + body[-SHORT_TERM_WINDOW:]


PRICE_PATTERN = re.compile(r"under\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def detect_price_preference(text: str) -> float | None:
    match = PRICE_PATTERN.search(text)
    return float(match.group(1)) if match else None


async def update_long_term_memory(user_id: int, human_text: str, last_products: list[dict]) -> None:
    """Writeback to users table. Checkout is already durable via manage_cart's
    orders/order_items insert — nothing to do here for that case."""
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return

        price_pref = detect_price_preference(human_text)
        if price_pref is not None:
            user.price_range_max = price_pref

        if last_products:
            categories = {p["category"] for p in last_products if "category" in p}
            if len(categories) == 1:
                seen = {c for c in user.preferred_categories.split(",") if c}
                seen.add(categories.pop())
                user.preferred_categories = ",".join(sorted(seen))

        await session.commit()


async def load_session_intro(user_id: int) -> SystemMessage:
    """Bridges long-term -> short-term memory: profile/history live in SQLite across
    sessions, read once here at conversation start and folded into a system message so
    trim_messages' sliding window carries them on every turn without a DB hit per message."""
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return SystemMessage(content="You are a helpful shopping assistant.")

        orders = (
            await session.execute(
                select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(3)
            )
        ).scalars().all()

        order_lines = []
        for order in orders:
            items = (
                await session.execute(
                    select(OrderItem.quantity, Product.name)
                    .join(Product, Product.id == OrderItem.product_id)
                    .where(OrderItem.order_id == order.id)
                )
            ).all()
            item_str = ", ".join(f"{qty}x {name}" for qty, name in items)
            order_lines.append(f"- Order #{order.id} (₹{order.total}): {item_str}")

        history_block = "\n".join(order_lines) if order_lines else "No past orders."

        content = (
            f"You are a helpful shopping assistant for {user.name} (user_id={user.id}).\n"
            f"Always use user_id={user.id} directly when calling manage_cart, get_order_history, "
            f"or get_recommendations. Never ask the user for their user ID, you already have it.\n"
            f"Only mention products, IDs, and prices returned by a tool call this turn. Never invent "
            f"or recall product names/prices from your own knowledge. If search_products returns no "
            f"matches (or only unrelated results), tell the user plainly that nothing matched — do not "
            f"substitute a real-world product you know about.\n"
            f"For manage_cart add/remove, always pass product_name (the name as the user said it or "
            f"as it appeared in a recent search result) rather than product_id — never guess or "
            f"recall a numeric id from memory, it's easy to misremember and silently lands on the "
            f"wrong product.\n"
            f"Preferred categories: {user.preferred_categories or 'none recorded'}.\n"
            f"Usual budget: up to ₹{user.price_range_max}.\n"
            f"Recent order history:\n{history_block}"
        )
        return SystemMessage(content=content)
