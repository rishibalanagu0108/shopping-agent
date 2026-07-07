from fastapi import APIRouter

from app.agent.tools import get_order_history

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/{user_id}")
async def list_orders(user_id: int, limit: int = 20):
    return await get_order_history.ainvoke({"user_id": user_id, "limit": limit})
