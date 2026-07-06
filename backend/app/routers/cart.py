from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.tools import manage_cart

router = APIRouter(prefix="/api/cart", tags=["cart"])


class AddItem(BaseModel):
    product_id: int
    quantity: int = 1


@router.get("/{user_id}")
async def view_cart(user_id: int):
    return await manage_cart.ainvoke({"action": "view", "user_id": user_id})


@router.post("/{user_id}/add")
async def add_to_cart(user_id: int, item: AddItem):
    return await manage_cart.ainvoke(
        {"action": "add", "user_id": user_id, "product_id": item.product_id, "quantity": item.quantity}
    )


@router.delete("/{user_id}/remove/{product_id}")
async def remove_from_cart(user_id: int, product_id: int):
    return await manage_cart.ainvoke({"action": "remove", "user_id": user_id, "product_id": product_id})


@router.post("/{user_id}/checkout")
async def checkout(user_id: int):
    return await manage_cart.ainvoke({"action": "checkout", "user_id": user_id})
