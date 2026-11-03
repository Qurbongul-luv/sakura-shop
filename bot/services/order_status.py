"""
Order lifecycle shared by the bot buttons and the Mini App admin API.

Statuses only move forward (skipping steps is allowed), or to cancelled before delivery, so a
mis-tap can't send a customer back to "accepted". The change is a conditional UPDATE on the
status the admin saw: two admins tapping at once produce one change and one customer message.
"""
import logging
from dataclasses import dataclass
from html import escape
from typing import Dict, List, Optional, Tuple

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.formatters import format_price
from db.models import Order, Setting, utcnow

logger = logging.getLogger(__name__)

STATUS_NEW = "new"
STATUS_ACCEPTED = "accepted"
STATUS_PURCHASED = "purchased"
STATUS_SHIPPING = "shipping"
STATUS_ARRIVED = "arrived"
STATUS_DELIVERED = "delivered"
STATUS_CANCELLED = "cancelled"

STATUS_FLOW: Tuple[str, ...] = (
    STATUS_NEW, STATUS_ACCEPTED, STATUS_PURCHASED, STATUS_SHIPPING, STATUS_ARRIVED, STATUS_DELIVERED,
)
ALL_STATUSES: Tuple[str, ...] = STATUS_FLOW + (STATUS_CANCELLED,)
FINAL_STATUSES = frozenset({STATUS_DELIVERED, STATUS_CANCELLED})

STATUS_LABELS: Dict[str, str] = {
    STATUS_NEW: "🆕 Yangi",
    STATUS_ACCEPTED: "✅ Qabul qilindi",
    STATUS_PURCHASED: "🛒 Xitoyda sotib olindi",
    STATUS_SHIPPING: "✈️ Yo'lda",
    STATUS_ARRIVED: "📍 Toshkentga keldi",
    STATUS_DELIVERED: "🎁 Yetkazildi",
    STATUS_CANCELLED: "❌ Bekor qilindi",
}

_CUSTOMER_TEXT: Dict[str, str] = {
    STATUS_ACCEPTED: "Buyurtmangiz qabul qilindi! ✅\nAdmin tez orada kargo va to'lov bo'yicha siz bilan bog'lanadi.",
    STATUS_PURCHASED: "Mahsulotingiz Xitoyda sotib olindi 🛒🇨🇳\nEndi u kargo orqali jo'natiladi.",
    STATUS_SHIPPING: "Buyurtmangiz yo'lda! ✈️\nToshkentga yetib kelishi bilan xabar beramiz.",
    STATUS_ARRIVED: "Buyurtmangiz Toshkentga yetib keldi! 📍\nYetkazib berish uchun tez orada bog'lanamiz.",
    STATUS_DELIVERED: "Buyurtmangiz yetkazildi! 🎁\nXaridingiz uchun katta rahmat 💗",
    STATUS_CANCELLED: "Buyurtmangiz bekor qilindi. ❌",
}

RESULT_CHANGED = "changed"
RESULT_UNCHANGED = "unchanged"
RESULT_NOT_ALLOWED = "not_allowed"
RESULT_NOT_FOUND = "not_found"
RESULT_RACE = "race"


@dataclass(frozen=True)
class StatusChange:
    result: str
    order: Optional[Order]
    previous: Optional[str] = None


def label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def is_allowed(current: str, new: str) -> bool:
    if new not in ALL_STATUSES or current in FINAL_STATUSES or current == new:
        return False
    if new == STATUS_CANCELLED:
        return True
    if current not in STATUS_FLOW:
        return False
    return STATUS_FLOW.index(new) > STATUS_FLOW.index(current)


def next_status(current: str) -> Optional[str]:
    if current not in STATUS_FLOW or current == STATUS_DELIVERED:
        return None
    return STATUS_FLOW[STATUS_FLOW.index(current) + 1]


async def change_status(session: AsyncSession, order_id: int, new_status: str) -> StatusChange:
    order = (await session.execute(select(Order).where(Order.id == order_id))).scalars().first()
    if order is None:
        return StatusChange(RESULT_NOT_FOUND, None)
    current = order.status
    if current == new_status:
        return StatusChange(RESULT_UNCHANGED, order, current)
    if not is_allowed(current, new_status):
        return StatusChange(RESULT_NOT_ALLOWED, order, current)

    now = utcnow()
    values = {"status": new_status, "status_updated_at": now}
    if new_status == STATUS_DELIVERED:
        values["delivered_at"] = now
    res = await session.execute(
        update(Order).where(Order.id == order_id, Order.status == current).values(**values)
    )
    await session.commit()
    if res.rowcount == 0:
        await session.refresh(order)
        return StatusChange(RESULT_RACE, order, current)
    await session.refresh(order)
    return StatusChange(RESULT_CHANGED, order, current)


async def contact_username(session: AsyncSession) -> str:
    rec = (await session.execute(select(Setting).where(Setting.key == "contact_username"))).scalars().first()
    return (rec.value if rec and rec.value else "fkhrdnvvvva").replace("@", "").strip()


def customer_message(order: Order, contact: str) -> str:
    body = _CUSTOMER_TEXT.get(order.status, f"Holati: {label(order.status)}")
    return (
        f"🌸 <b>Buyurtma #{order.id}</b>\n\n{body}\n\n"
        f"Savollar bo'lsa @{escape(contact)} ga yozing 💌"
    )


async def notify_customer(bot: Optional[Bot], session: AsyncSession, order: Order) -> bool:
    if not bot or not order.user_id:
        return False
    try:
        await bot.send_message(chat_id=order.user_id, text=customer_message(order, await contact_username(session)))
        return True
    except Exception as e:
        logger.warning(f"Could not notify customer {order.user_id} about order #{order.id}: {e}")
        return False


async def change_status_and_notify(
    session: AsyncSession, bot: Optional[Bot], order_id: int, new_status: str
) -> StatusChange:
    change = await change_status(session, order_id, new_status)
    if change.result == RESULT_CHANGED and change.order is not None:
        await notify_customer(bot, session, change.order)
    return change


def order_card(order: Order) -> str:
    """Admin-facing summary; never includes cost or profit (admins aren't all owners)."""
    lines: List[str] = [
        f"🧾 <b>Buyurtma #{order.id}</b> — {label(order.status)}",
        f"👤 {escape(order.customer_name or 'Mijoz')}"
        + (f" (@{escape(order.customer_username)})" if order.customer_username else ""),
        "",
    ]
    for item in order.items_snapshot or []:
        attrs = ", ".join(str(a) for a in (item.get("size"), item.get("color")) if a)
        lines.append(
            f"• {escape(str(item.get('title', 'Mahsulot')))}"
            + (f" ({escape(attrs)})" if attrs else "")
            + f" × {int(item.get('qty', 1))} — {format_price(int(item.get('price', 0)) * int(item.get('qty', 1)))}"
        )
    lines.append("")
    lines.append(f"💰 <b>Jami:</b> {format_price(order.total)}")
    if order.estimated_cargo:
        lines.append(f"📦 Kargo (taxminan): {format_price(order.estimated_cargo)}")
    return "\n".join(lines)


def order_markup(order: Order, back_to_list: bool = False) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    step = next_status(order.status)
    if step:
        rows.append([InlineKeyboardButton(text=f"➡️ {label(step)}", callback_data=f"ord_st:{order.id}:{step}")])
    if order.status not in FINAL_STATUSES:
        later = [s for s in STATUS_FLOW if is_allowed(order.status, s) and s != step]
        if later:
            rows.append([
                InlineKeyboardButton(text=label(s), callback_data=f"ord_st:{order.id}:{s}") for s in later[:2]
            ])
        rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"ord_st:{order.id}:{STATUS_CANCELLED}")])
    profile = f"https://t.me/{order.customer_username}" if order.customer_username else f"tg://user?id={order.user_id}"
    rows.append([InlineKeyboardButton(text="👤 Mijoz profili", url=profile)])
    if back_to_list:
        rows.append([InlineKeyboardButton(text="⬅️ Buyurtmalar", callback_data="admin_orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
