import asyncio

from app.agent.tools import get_order_history, get_recommendations, manage_cart, search_products


async def main():
    print("search_products('winter'):")
    print(await search_products.ainvoke({"query": "winter"}))
    print()

    print("search_products('cozy winter', category=None, max_price=5000):")
    print(await search_products.ainvoke({"query": "cozy winter", "max_price": 5000}))
    print()

    print("manage_cart(add, user_id=1, product_id=1, quantity=2):")
    print(await manage_cart.ainvoke({"action": "add", "user_id": 1, "product_id": 1, "quantity": 2}))
    print()

    print("manage_cart(add, user_id=1, product_id=4, quantity=1):")
    print(await manage_cart.ainvoke({"action": "add", "user_id": 1, "product_id": 4, "quantity": 1}))
    print()

    print("manage_cart(view, user_id=1):")
    print(await manage_cart.ainvoke({"action": "view", "user_id": 1}))
    print()

    print("manage_cart(checkout, user_id=1):")
    print(await manage_cart.ainvoke({"action": "checkout", "user_id": 1}))
    print()

    print("get_order_history(user_id=1):")
    print(await get_order_history.ainvoke({"user_id": 1}))
    print()

    print("get_recommendations(user_id=1):")
    print(await get_recommendations.ainvoke({"user_id": 1}))
    print()

    print("get_recommendations(user_id=2, category='Kitchen'):")
    print(await get_recommendations.ainvoke({"user_id": 2, "category": "Kitchen"}))


if __name__ == "__main__":
    asyncio.run(main())
