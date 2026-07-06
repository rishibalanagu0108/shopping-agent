from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.agent.tools import search_products
from app.db.database import async_session
from app.db.schema import Category, Product

router = APIRouter(prefix="/api/products", tags=["products"])


def _serialize(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "category": p.category,
        "price": p.price,
        "brand": p.brand,
        "stock": p.stock,
        "image_url": p.image_url,
        "rating": p.rating,
    }


@router.get("/categories")
async def list_categories():
    async with async_session() as session:
        return (await session.execute(select(Category.name))).scalars().all()


@router.get("")
async def list_products(category: str | None = None, search: str | None = None, max_price: float | None = None):
    # search present -> reuse the agent's FTS5 tool so keyword ranking stays identical
    # between chat and the product grid; no search -> plain filtered listing (no MATCH needed).
    if search:
        hits = await search_products.ainvoke({"query": search, "category": category, "max_price": max_price})
        async with async_session() as session:
            ids = [h["id"] for h in hits]
            rows = {p.id: p for p in (await session.execute(select(Product).where(Product.id.in_(ids)))).scalars()}
            # tool's ids come back FTS5-rank ordered; the DB IN-clause doesn't preserve
            # that, so re-order by the ranked id list instead of the query's own order.
            return [_serialize(rows[i]) for i in ids if i in rows]

    async with async_session() as session:
        query = select(Product)
        if category:
            query = query.where(Product.category == category)
        if max_price is not None:
            query = query.where(Product.price <= max_price)
        products = (await session.execute(query)).scalars().all()
        return [_serialize(p) for p in products]


@router.get("/{product_id}")
async def get_product(product_id: int):
    async with async_session() as session:
        product = await session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return _serialize(product)
