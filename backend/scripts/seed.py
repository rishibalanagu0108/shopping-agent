import asyncio
import random

from app.db.database import async_session, engine, init_db
from app.db.schema import Category, Product, User

random.seed(42)

CATALOG = {
    "Electronics": {
        "brands": ["Samsung", "Boat", "Noise", "Mi", "OnePlus", "JBL", "Sony", "Realme"],
        "items": [
            "Wireless Bluetooth Earbuds", "Noise Cancelling Headphones", "Smartwatch Pro",
            "Portable Bluetooth Speaker", "Fast Charging Power Bank 20000mAh", "USB-C Charging Cable",
            "Wireless Mouse", "Mechanical Keyboard", "4K Webcam", "Laptop Stand",
            "Gaming Controller", "Smart LED Bulb", "Wi-Fi Router Dual Band", "Portable SSD 1TB",
            "Bluetooth Car Adapter",
        ],
        "price": (399, 15999),
    },
    "Books": {
        "brands": ["Penguin", "HarperCollins", "Rupa", "Bloomsbury", "Scholastic", "Westland"],
        "items": [
            "The Silent Mountain (Novel)", "Modern Python Programming", "History of Ancient India",
            "Mindfulness for Busy People", "The Startup Playbook", "Classic Poetry Collection",
            "Data Science Handbook", "The Art of Cooking", "Children's Bedtime Stories",
            "Personal Finance Made Simple", "Mystery at Midnight (Novel)", "World Atlas Illustrated",
            "The Productivity Journal", "Science for Curious Minds", "Biography of a Freedom Fighter",
        ],
        "price": (149, 899),
    },
    "Clothing": {
        "brands": ["H&M", "Levis", "Zara", "Allen Solly", "Puma", "Adidas", "Fabindia"],
        "items": [
            "Men's Cotton Casual Shirt", "Women's Denim Jacket", "Slim Fit Jeans", "Cotton Kurta Set",
            "Running Track Pants", "Woolen Winter Sweater", "Graphic Print T-Shirt", "Formal Blazer",
            "Cotton Nightwear Set", "Sports Sneakers", "Leather Belt", "Woolen Muffler Scarf",
            "Rain Jacket Waterproof", "Ethnic Silk Saree", "Kids Hoodie",
        ],
        "price": (299, 3499),
    },
    "Kitchen": {
        "brands": ["Prestige", "Pigeon", "Milton", "Bergner", "Cello", "Borosil"],
        "items": [
            "Non-Stick Frying Pan", "Stainless Steel Pressure Cooker", "Electric Kettle 1.5L",
            "Insulated Steel Water Bottle", "Ceramic Dinner Set 16pc", "Glass Storage Jars Set",
            "Hand Blender 250W", "Chopping Board Set", "Induction Cooktop", "Coffee Maker Drip",
            "Air Fryer 4L", "Cutlery Set 24pc", "Roti Maker Electric", "Lunch Box Insulated",
            "Spice Rack Organizer",
        ],
        "price": (249, 5999),
    },
    "Sports": {
        "brands": ["Nivia", "Cosco", "Yonex", "Nike", "Wildcraft", "Decathlon"],
        "items": [
            "Football Size 5", "Badminton Racket Set", "Yoga Mat Anti-Slip", "Cricket Bat Kashmir Willow",
            "Adjustable Dumbbell Set", "Cycling Helmet", "Skipping Rope", "Table Tennis Paddle Set",
            "Gym Resistance Bands", "Running Shoes", "Trekking Backpack 40L", "Basketball Size 7",
            "Fitness Tracker Band", "Swimming Goggles", "Camping Tent 2-Person",
        ],
        "price": (199, 4999),
    },
    "Toys": {
        "brands": ["Funskool", "Hasbro", "LEGO", "Mattel", "Fisher-Price", "Hot Wheels"],
        "items": [
            "Building Blocks Set 200pc", "Remote Control Car", "Plush Teddy Bear", "Puzzle 1000 Pieces",
            "Action Figure Set", "Board Game Family Pack", "Doll House Playset", "Toy Kitchen Set",
            "Race Track Set", "Educational Alphabet Blocks", "Rubik's Cube", "Water Gun Blaster",
            "Musical Toy Piano", "Toy Tool Kit", "Art & Craft Kit",
        ],
        "price": (149, 2999),
    },
}

DESC_TEMPLATES = [
    "The {name} from {brand} combines everyday reliability with thoughtful design. "
    "Built for daily use, it holds up well under regular wear and tear. "
    "A solid pick for anyone looking for good value in this category.",
    "{brand} brings quality and durability together in this {name_lower}. "
    "Customers appreciate its practical design and consistent performance. "
    "Makes a great addition to your collection or a thoughtful gift.",
    "This {name_lower} by {brand} is designed for comfort and long-term use. "
    "It balances style with functionality, fitting easily into daily routines. "
    "A dependable choice backed by {brand}'s reputation for quality.",
]

USERS = [
    {"name": "Shyam", "preferred_categories": "Electronics,Sports", "price_range_max": 8000},
    {"name": "Priya", "preferred_categories": "Books,Kitchen", "price_range_max": 3000},
    {"name": "Ravi", "preferred_categories": "Clothing,Toys", "price_range_max": 2500},
]


def make_products():
    products = []
    pid = 1
    for category, spec in CATALOG.items():
        for i, item in enumerate(spec["items"]):
            brand = spec["brands"][i % len(spec["brands"])]
            lo, hi = spec["price"]
            price = round(random.uniform(lo, hi), 2)
            desc = random.choice(DESC_TEMPLATES).format(name=item, name_lower=item.lower(), brand=brand)
            products.append(
                Product(
                    id=pid,
                    name=item,
                    description=desc,
                    category=category,
                    price=price,
                    brand=brand,
                    stock=random.randint(5, 200),
                    image_url=f"https://picsum.photos/seed/{pid}/300/300",
                    rating=round(random.uniform(3.5, 5.0), 1),
                )
            )
            pid += 1
    return products


async def seed():
    await init_db()
    products = make_products()

    async with async_session() as session:
        session.add_all(Category(name=name) for name in CATALOG)
        session.add_all(User(**u) for u in USERS)
        session.add_all(products)
        await session.commit()

    await engine.dispose()

    print(f"\nSeeded {len(products)} products, {len(CATALOG)} categories, {len(USERS)} users\n")
    print(f"{'Category':<15}{'Count':<8}{'Price Range (INR)':<25}")
    print("-" * 48)
    for category in CATALOG:
        cat_products = [p for p in products if p.category == category]
        prices = [p.price for p in cat_products]
        print(f"{category:<15}{len(cat_products):<8}Rs.{min(prices):.2f} - Rs.{max(prices):.2f}")


if __name__ == "__main__":
    asyncio.run(seed())
