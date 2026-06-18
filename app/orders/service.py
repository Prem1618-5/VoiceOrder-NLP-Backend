"""
Orders service layer.

Responsibilities:
  - Run NLP pipeline on raw text → ParsedOrder
  - Persist order to PostgreSQL via SQLAlchemy ORM
  - Fetch paginated order history for current user
  - Menu item lookup (for price enrichment + EntityRuler patterns)
"""
import logging
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.nlp.pipeline import NLPPipeline
from app.nlp.schemas import ParsedOrder
from app.orders.models import MenuItem, Order
from app.orders.schemas import OrderParseRequest

logger = logging.getLogger(__name__)

# Module-level singleton — loaded once at startup via lifespan
_pipeline: Optional[NLPPipeline] = None


def set_pipeline(pipeline: NLPPipeline) -> None:
    """Called from main.py lifespan after pipeline is initialised."""
    global _pipeline
    _pipeline = pipeline


def get_pipeline() -> NLPPipeline:
    if _pipeline is None:
        raise RuntimeError("NLP pipeline not initialised — call set_pipeline() first")
    return _pipeline


# ── Menu helpers ──────────────────────────────────────────────────────────────

async def get_all_menu_items(db: AsyncSession) -> List[MenuItem]:
    """Fetch all menu items for EntityRuler pattern loading."""
    result = await db.execute(select(MenuItem))
    return list(result.scalars().all())


async def get_menu_item_by_id(
    db: AsyncSession, item_id: uuid.UUID
) -> Optional[MenuItem]:
    result = await db.execute(select(MenuItem).where(MenuItem.id == item_id))
    return result.scalar_one_or_none()


async def seed_default_menu(db: AsyncSession) -> None:
    """
    Insert a 50-item synthetic menu if the table is empty.
    Called from lifespan on startup.
    OQ2 resolution: synthetic dataset — full control, no licensing.
    """
    count_result = await db.execute(select(func.count()).select_from(MenuItem))
    count = count_result.scalar_one()
    if count > 0:
        logger.info("Menu already seeded (%d items), skipping.", count)
        return

    items = [
        # Pizzas
        MenuItem(name="pepperoni pizza", category="pizza", price=12.99,
                 modifiers=["extra cheese", "thin crust", "no onions"],
                 tags=["popular"]),
        MenuItem(name="margherita pizza", category="pizza", price=10.99,
                 modifiers=["extra cheese", "thin crust"],
                 tags=["vegetarian"]),
        MenuItem(name="bbq chicken pizza", category="pizza", price=13.99,
                 modifiers=["extra sauce", "thin crust"],
                 tags=[]),
        MenuItem(name="veggie supreme pizza", category="pizza", price=11.99,
                 modifiers=["extra cheese", "no olives"],
                 tags=["vegetarian"]),
        MenuItem(name="four cheese pizza", category="pizza", price=12.49,
                 modifiers=["thin crust"],
                 tags=["vegetarian"]),
        # Burgers
        MenuItem(name="classic beef burger", category="burger", price=9.99,
                 modifiers=["extra patty", "no pickles", "add bacon"],
                 tags=[]),
        MenuItem(name="chicken burger", category="burger", price=8.99,
                 modifiers=["spicy", "no mayo", "add cheese"],
                 tags=[]),
        MenuItem(name="veggie burger", category="burger", price=8.49,
                 modifiers=["add cheese", "no onions"],
                 tags=["vegetarian"]),
        MenuItem(name="double smash burger", category="burger", price=12.99,
                 modifiers=["extra sauce", "no pickles"],
                 tags=["popular"]),
        MenuItem(name="mushroom swiss burger", category="burger", price=10.49,
                 modifiers=["no mushrooms", "add bacon"],
                 tags=[]),
        # Sides
        MenuItem(name="french fries", category="sides", price=3.49,
                 modifiers=["extra salt", "no salt", "add cheese"],
                 tags=[]),
        MenuItem(name="onion rings", category="sides", price=3.99,
                 modifiers=["extra crispy"],
                 tags=[]),
        MenuItem(name="coleslaw", category="sides", price=2.49,
                 modifiers=[],
                 tags=["vegetarian"]),
        MenuItem(name="garlic bread", category="sides", price=2.99,
                 modifiers=["extra butter"],
                 tags=["vegetarian"]),
        MenuItem(name="caesar salad", category="salad", price=7.99,
                 modifiers=["no croutons", "add chicken", "extra dressing"],
                 tags=[]),
        # Drinks
        MenuItem(name="coke", category="drinks", price=2.49,
                 modifiers=["no ice", "extra ice"],
                 tags=[]),
        MenuItem(name="diet coke", category="drinks", price=2.49,
                 modifiers=["no ice"],
                 tags=[]),
        MenuItem(name="lemonade", category="drinks", price=2.99,
                 modifiers=["no ice", "extra lemon"],
                 tags=[]),
        MenuItem(name="orange juice", category="drinks", price=3.49,
                 modifiers=[],
                 tags=[]),
        MenuItem(name="water", category="drinks", price=1.49,
                 modifiers=["sparkling", "still"],
                 tags=[]),
        MenuItem(name="iced tea", category="drinks", price=2.99,
                 modifiers=["no sugar", "extra lemon"],
                 tags=[]),
        MenuItem(name="milkshake", category="drinks", price=4.99,
                 modifiers=["chocolate", "vanilla", "strawberry"],
                 tags=[]),
        # Pasta
        MenuItem(name="spaghetti bolognese", category="pasta", price=11.99,
                 modifiers=["extra sauce", "no parmesan"],
                 tags=[]),
        MenuItem(name="penne arrabbiata", category="pasta", price=10.49,
                 modifiers=["extra chili", "no chili"],
                 tags=["vegetarian", "spicy"]),
        MenuItem(name="fettuccine alfredo", category="pasta", price=11.49,
                 modifiers=["add chicken", "no parmesan"],
                 tags=["vegetarian"]),
        # Wraps
        MenuItem(name="chicken wrap", category="wraps", price=8.99,
                 modifiers=["spicy", "no mayo", "add cheese"],
                 tags=[]),
        MenuItem(name="falafel wrap", category="wraps", price=7.99,
                 modifiers=["extra hummus", "no onions"],
                 tags=["vegetarian"]),
        MenuItem(name="beef wrap", category="wraps", price=9.49,
                 modifiers=["extra sauce", "no tomato"],
                 tags=[]),
        # Desserts
        MenuItem(name="chocolate brownie", category="desserts", price=4.99,
                 modifiers=["add ice cream"],
                 tags=[]),
        MenuItem(name="cheesecake", category="desserts", price=5.49,
                 modifiers=["strawberry topping", "no topping"],
                 tags=[]),
        MenuItem(name="tiramisu", category="desserts", price=5.99,
                 modifiers=[],
                 tags=[]),
        MenuItem(name="ice cream", category="desserts", price=3.99,
                 modifiers=["chocolate", "vanilla", "strawberry"],
                 tags=["vegetarian"]),
        # Chicken
        MenuItem(name="chicken wings", category="chicken", price=9.99,
                 modifiers=["spicy", "bbq", "buffalo", "no sauce"],
                 tags=["popular"]),
        MenuItem(name="chicken nuggets", category="chicken", price=6.99,
                 modifiers=["spicy", "no sauce"],
                 tags=[]),
        MenuItem(name="grilled chicken", category="chicken", price=11.99,
                 modifiers=["extra seasoning", "no seasoning"],
                 tags=[]),
        # Sandwiches
        MenuItem(name="club sandwich", category="sandwiches", price=8.99,
                 modifiers=["no mayo", "add cheese", "extra bacon"],
                 tags=[]),
        MenuItem(name="blt sandwich", category="sandwiches", price=7.99,
                 modifiers=["extra bacon", "no mayo"],
                 tags=[]),
        MenuItem(name="tuna melt", category="sandwiches", price=8.49,
                 modifiers=["no onions", "extra cheese"],
                 tags=[]),
        # Breakfast
        MenuItem(name="full english breakfast", category="breakfast", price=10.99,
                 modifiers=["no beans", "extra eggs", "no mushrooms"],
                 tags=[]),
        MenuItem(name="pancakes", category="breakfast", price=7.49,
                 modifiers=["extra syrup", "add berries", "add bacon"],
                 tags=["vegetarian"]),
        MenuItem(name="avocado toast", category="breakfast", price=8.99,
                 modifiers=["add egg", "extra avocado", "no chili flakes"],
                 tags=["vegetarian"]),
        MenuItem(name="eggs benedict", category="breakfast", price=9.49,
                 modifiers=["extra hollandaise", "no bacon"],
                 tags=[]),
        # Soups
        MenuItem(name="tomato soup", category="soups", price=4.99,
                 modifiers=["extra bread", "no cream"],
                 tags=["vegetarian"]),
        MenuItem(name="chicken noodle soup", category="soups", price=5.49,
                 modifiers=["extra noodles"],
                 tags=[]),
        # Specials
        MenuItem(name="fish and chips", category="specials", price=12.99,
                 modifiers=["extra tartar sauce", "no mushy peas"],
                 tags=["popular"]),
        MenuItem(name="steak", category="specials", price=24.99,
                 modifiers=["rare", "medium rare", "medium", "well done",
                             "extra sauce"],
                 tags=[]),
        MenuItem(name="salmon fillet", category="specials", price=18.99,
                 modifiers=["no lemon", "extra capers"],
                 tags=[]),
        MenuItem(name="risotto", category="specials", price=13.99,
                 modifiers=["add parmesan", "no parmesan"],
                 tags=["vegetarian"]),
        MenuItem(name="beef tacos", category="specials", price=10.99,
                 modifiers=["spicy", "no salsa", "extra guacamole"],
                 tags=[]),
        MenuItem(name="nachos", category="specials", price=8.99,
                 modifiers=["extra cheese", "spicy", "no jalapenos",
                             "add sour cream"],
                 tags=["vegetarian"]),
    ]

    db.add_all(items)
    await db.flush()
    logger.info("Seeded %d menu items.", len(items))


# ── Order persistence ─────────────────────────────────────────────────────────

async def persist_order(
    db: AsyncSession,
    parsed: ParsedOrder,
    user_id: uuid.UUID,
    session_id: Optional[uuid.UUID] = None,
) -> Order:
    """
    Persist a ParsedOrder to the orders table.
    Computes total_price from item unit_prices.
    Returns the created Order ORM instance.
    """
    items_json = [item.model_dump() for item in parsed.items]

    total_price: Optional[float] = None
    if all(item.unit_price is not None for item in parsed.items):
        total_price = round(
            sum((item.unit_price or 0) * item.quantity for item in parsed.items), 2
        )

    order = Order(
        session_id=session_id,
        user_id=user_id,
        items=items_json,
        total_price=total_price,
        status="pending",
        confidence=parsed.confidence,
        for_review=parsed.for_review,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    logger.info(
        "Order persisted id=%s user=%s confidence=%.2f",
        order.id, user_id, parsed.confidence,
    )
    return order


# ── History ───────────────────────────────────────────────────────────────────

async def get_order_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    size: int = 20,
) -> Tuple[List[Order], int]:
    """
    Return paginated order history for a user.
    Returns (orders, total_count).
    """
    offset = (page - 1) * size

    count_stmt = (
        select(func.count())
        .select_from(Order)
        .where(Order.user_id == user_id)
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(stmt)
    orders = list(result.scalars().all())

    return orders, total
