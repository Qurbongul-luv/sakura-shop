"""
Three days after an order is delivered, the customer is asked once for a review. The request is
claimed with a conditional UPDATE before the message goes out, so a restart or a second worker
never asks the same customer twice. Submitted reviews wait for an admin's approval.
"""
import logging
from datetime import timedelta
from typing import List, Optional, Sequence

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Order, Review, utcnow

REVIEW_DELAY = timedelta(days=3)
BATCH_SIZE = 30
MAX_REVIEW_PHOTOS = 5
MAX_REVIEW_TEXT = 1000

logger = logging.getLogger(__name__)


def request_markup(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⭐ Fikr qoldirish", callback_data=f"rv_start:{order_id}")]]
    )


def request_text(order_id: int) -> str:
    return (
        f"🌸 <b>Buyurtmangiz (#{order_id}) sizga yoqdimi?</b>\n\n"
        "Mahsulot rasmi va bir-ikki so'z fikringizni yuborsangiz, boshqa xaridorlarga katta yordam bo'ladi 💗"
    )


async def due_orders(session: AsyncSession) -> List[Order]:
    cutoff = utcnow() - REVIEW_DELAY
    stmt = (
        select(Order)
        .where(
            Order.status == "delivered",
            Order.delivered_at.is_not(None),
            Order.delivered_at <= cutoff,
            Order.review_requested_at.is_(None),
            Order.reviewed_at.is_(None),
        )
        .order_by(Order.delivered_at)
        .limit(BATCH_SIZE)
    )
    return list((await session.execute(stmt)).scalars().all())


async def send_review_requests(session: AsyncSession, bot: Optional[Bot]) -> int:
    if not bot:
        return 0
    sent = 0
    for order in await due_orders(session):
        claim = await session.execute(
            update(Order)
            .where(Order.id == order.id, Order.review_requested_at.is_(None))
            .values(review_requested_at=utcnow())
        )
        await session.commit()
        if claim.rowcount == 0:
            continue
        try:
            await bot.send_message(chat_id=order.user_id, text=request_text(order.id), reply_markup=request_markup(order.id))
            sent += 1
        except Exception as e:
            # Kept as requested anyway: a customer who blocked the bot must not be retried forever.
            logger.info(f"Review request for order #{order.id} not delivered: {e}")
    return sent


async def save_review(
    session: AsyncSession,
    order_id: int,
    user_id: int,
    customer_name: str,
    text: str,
    photos: Sequence[str],
) -> Optional[Review]:
    """Stores the review unapproved; None if the order isn't this user's, isn't delivered, or was reviewed."""
    claim = await session.execute(
        update(Order)
        .where(
            Order.id == order_id,
            Order.user_id == user_id,
            Order.status == "delivered",
            Order.reviewed_at.is_(None),
        )
        .values(reviewed_at=utcnow())
    )
    if claim.rowcount == 0:
        return None  # nothing was changed; a rollback would only expire the caller's objects
    review = Review(
        customer_name=(customer_name or "Mijoz")[:255],
        text=(text or "").strip()[:MAX_REVIEW_TEXT],
        photos=list(photos)[:MAX_REVIEW_PHOTOS],
        approved=False,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review
