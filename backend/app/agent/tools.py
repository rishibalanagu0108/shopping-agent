from langchain_core.tools import tool
from sqlalchemy import delete, select, text

from app.db.database import async_session
from app.db.schema import Cart, Order, OrderItem, Product, User


@tool
async def search_products(query: str, category: str | None = None, max_price: float | None = None) -> list[dict]:
    """Search the product catalog by free-text query, optionally filtered by category and max price."""
    # FTS5 MATCH defaults to AND between bare words, so "cozy winter" would require both
    # tokens on the same row. OR-joining the tokens instead means ANY word hit counts,
    # which is what makes a rambly query like "something cozy for winter" still surface
    # products whose text only contains "winter" — the tradeoff for not having embeddings.
    #
    # products_fts only indexes name/description/brand (see database.py), not category --
    # so a plain category browse ("find me books") legitimately matches nothing there,
    # whether or not the model bothered to pass the separate `category` arg for it. Detect
    # a query token that names a real category (DB-driven, not hardcoded) and treat that as
    # the effective category filter instead of AND-ing a MATCH clause that would zero out
    # every row a category filter alone would've found.
    tokens = [w for w in query.split() if w.isalnum()]

    async with async_session() as session:
        categories = {row[0].lower(): row[0] for row in (await session.execute(text("SELECT DISTINCT category FROM products"))).all()}

    # SQLite string comparison is case-sensitive -- canonicalize through the same
    # lowercase-keyed dict even when the model passes `category` explicitly, or a
    # perfectly correct "books" (vs. the DB's "Books") silently zeroes the whole query.
    effective_category = (
        (categories.get(category.lower()) if category else None)
        or next((categories[t.lower()] for t in tokens if t.lower() in categories), None)
    )
    if effective_category:
        category_words = {w.lower() for w in effective_category.split()}
        tokens = [t for t in tokens if t.lower() not in category_words]

    if not tokens and effective_category is None:
        return []

    params = {}
    if tokens:
        match_query = " OR ".join(tokens)
        sql = """
            SELECT p.id, p.name, p.price, p.category, p.rating, p.stock
            FROM products_fts
            JOIN products p ON p.id = products_fts.rowid
            WHERE products_fts MATCH :match_query
        """
        params["match_query"] = match_query
    else:
        sql = "SELECT id, name, price, category, rating, stock FROM products WHERE 1=1"

    prefix = "p." if tokens else ""
    if effective_category:
        sql += f" AND {prefix}category = :category"
        params["category"] = effective_category
    if max_price is not None:
        sql += f" AND {prefix}price <= :max_price"
        params["max_price"] = max_price
    sql += " ORDER BY rank LIMIT 10" if tokens else " ORDER BY rating DESC LIMIT 10"

    async with async_session() as session:
        result = await session.execute(text(sql), params)
        return [dict(row._mapping) for row in result]


@tool
async def manage_cart(
    action: str,
    user_id: int,
    product_id: int | None = None,
    product_name: str | None = None,
    quantity: int = 1,
) -> dict:
    """Manage a user's cart. action is one of: add, remove, view, clear, checkout.
    For add/remove, prefer product_name (the name as the user said it, or as it appeared
    in a recent search_products result) over product_id -- a name is resolved fresh
    against the catalog every time, whereas a numeric id has to be carried correctly
    across turns and a misremembered one silently lands on the wrong real product."""
    async with async_session() as session:
        if action in ("add", "remove"):
            # A recalled numeric id is the fragile path -- prefer resolving fresh by
            # name. Exact match first, then substring, so "Mystery at Midnight" still
            # resolves to "Mystery at Midnight (Novel)".
            if product_name:
                product = await session.scalar(select(Product).where(Product.name == product_name))
                if product is None:
                    product = await session.scalar(select(Product).where(Product.name.ilike(f"%{product_name}%")))
                if product is None:
                    return {"status": "product_not_found", "product_name": product_name}
                product_id = product.id
            elif await session.get(Product, product_id) is None:
                # product_id came with no name to resolve against -- still validate it's
                # real, or a hallucinated id silently succeeds and only surfaces later as
                # a misleadingly generic "empty_cart" at checkout (the orphan row gets
                # dropped by checkout's JOIN to Product).
                return {"status": "product_not_found", "product_id": product_id}

        if action == "add":
            product = await session.get(Product, product_id)
            existing = await session.scalar(
                select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
            )
            if existing:
                existing.quantity += quantity
            else:
                session.add(Cart(user_id=user_id, product_id=product_id, quantity=quantity))
            await session.commit()
            return {"status": "added", "product_id": product_id, "name": product.name, "price": product.price, "quantity": quantity}

        if action == "remove":
            await session.execute(delete(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id))
            await session.commit()
            return {"status": "removed", "product_id": product_id}

        if action == "clear":
            await session.execute(delete(Cart).where(Cart.user_id == user_id))
            await session.commit()
            return {"status": "cleared"}

        if action == "view":
            rows = await session.execute(
                select(Cart.product_id, Cart.quantity, Product.name, Product.price)
                .join(Product, Product.id == Cart.product_id)
                .where(Cart.user_id == user_id)
            )
            items = [
                {"product_id": pid, "name": name, "price": price, "quantity": qty, "subtotal": price * qty}
                for pid, qty, name, price in rows
            ]
            return {"items": items, "total": sum(i["subtotal"] for i in items)}

        if action == "checkout":
            rows = (
                await session.execute(
                    select(Cart.product_id, Cart.quantity, Product.price)
                    .join(Product, Product.id == Cart.product_id)
                    .where(Cart.user_id == user_id)
                )
            ).all()
            if not rows:
                return {"status": "empty_cart"}

            total = sum(qty * price for _, qty, price in rows)
            order = Order(user_id=user_id, total=total)
            session.add(order)
            await session.flush()  # assigns order.id before we reference it below

            for product_id, qty, price in rows:
                session.add(
                    OrderItem(order_id=order.id, product_id=product_id, quantity=qty, price_at_purchase=price)
                )
            await session.execute(delete(Cart).where(Cart.user_id == user_id))
            await session.commit()
            return {"status": "ordered", "order_id": order.id, "total": total, "item_count": len(rows)}

        return {"status": "unknown_action", "action": action}


@tool
async def get_order_history(user_id: int, limit: int = 5) -> list[dict]:
    """Get a user's most recent orders with their line items."""
    async with async_session() as session:
        orders = (
            await session.execute(
                select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit)
            )
        ).scalars().all()

        history = []
        for order in orders:
            items = (
                await session.execute(
                    select(OrderItem.quantity, OrderItem.price_at_purchase, Product.name)
                    .join(Product, Product.id == OrderItem.product_id)
                    .where(OrderItem.order_id == order.id)
                )
            ).all()
            history.append(
                {
                    "order_id": order.id,
                    "total": order.total,
                    "created_at": order.created_at.isoformat(),
                    "items": [{"name": name, "quantity": qty, "price": price} for qty, price, name in items],
                }
            )
        return history


@tool
async def get_recommendations(user_id: int, category: str | None = None) -> list[dict]:
    """Recommend top-rated products matching a user's preferences, or overall top-rated as fallback."""
    async with async_session() as session:
        user = await session.get(User, user_id)
        categories = [category] if category else (user.preferred_categories.split(",") if user else [])
        price_max = user.price_range_max if user else None

        query = select(Product).order_by(Product.rating.desc()).limit(5)
        if categories:
            query = query.where(Product.category.in_(categories))
        if price_max is not None:
            query = query.where(Product.price <= price_max)

        products = (await session.execute(query)).scalars().all()

        if not products:  # fallback: no prefs, or nothing matched them
            products = (
                await session.execute(select(Product).order_by(Product.rating.desc()).limit(5))
            ).scalars().all()

        return [
            {"id": p.id, "name": p.name, "price": p.price, "category": p.category, "rating": p.rating}
            for p in products
        ]
