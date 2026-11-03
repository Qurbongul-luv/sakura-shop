import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import desc, select

from api.config import settings
from api.services.formatters import format_price
from bot.services.order_status import (
    FINAL_STATUSES,
    RESULT_CHANGED,
    RESULT_NOT_ALLOWED,
    RESULT_NOT_FOUND,
    RESULT_RACE,
    RESULT_UNCHANGED,
    STATUS_ACCEPTED,
    STATUS_CANCELLED,
    change_status_and_notify,
    label,
    order_card,
    order_markup,
)
from db.models import Admin, Order
from db.session import async_session_factory

router = Router(name="orders")
logger = logging.getLogger(__name__)

ORDERS_PAGE = 15


async def is_admin(user_id: int) -> bool:
    if settings.DEV_ADMIN_ID and user_id == settings.DEV_ADMIN_ID:
        return True
    async with async_session_factory() as session:
        res = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
        return res.scalars().first() is not None


async def admin_callback(callback: CallbackQuery) -> bool:
    return callback.from_user is not None and await is_admin(callback.from_user.id)


router.callback_query.filter(admin_callback)


async def edit_card(callback: CallbackQuery, order: Order, back_to_list: bool) -> None:
    try:
        await callback.message.edit_text(order_card(order), reply_markup=order_markup(order, back_to_list))
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def apply_status(callback: CallbackQuery, order_id: int, new_status: str) -> None:
    async with async_session_factory() as session:
        change = await change_status_and_notify(session, callback.bot, order_id, new_status)

    if change.result == RESULT_NOT_FOUND:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    # The card on screen came from the order notice or from the list; keep the list's back button.
    back = bool(callback.message.reply_markup and any(
        b.callback_data == "admin_orders" for row in callback.message.reply_markup.inline_keyboard for b in row
    ))
    if change.result == RESULT_CHANGED:
        logger.info(f"Order #{order_id}: {change.previous} -> {new_status} by {callback.from_user.id}")
        await edit_card(callback, change.order, back)
        await callback.answer(f"{label(new_status)} — mijozga xabar yuborildi")
    elif change.result in (RESULT_UNCHANGED, RESULT_RACE):
        await edit_card(callback, change.order, back)
        await callback.answer(f"Holat allaqachon: {label(change.order.status)}", show_alert=True)
    elif change.result == RESULT_NOT_ALLOWED:
        await edit_card(callback, change.order, back)
        await callback.answer(
            f"Bu holatga o'tib bo'lmaydi (hozir: {label(change.order.status)})", show_alert=True
        )


@router.callback_query(F.data.startswith("ord_st:"))
async def handle_order_status(callback: CallbackQuery):
    _, order_id, new_status = callback.data.split(":", 2)
    await apply_status(callback, int(order_id), new_status)


# Buttons on order notices sent before the status flow existed.
@router.callback_query(F.data.startswith("order_accept_"))
async def handle_order_accept(callback: CallbackQuery):
    await apply_status(callback, int(callback.data.replace("order_accept_", "")), STATUS_ACCEPTED)


@router.callback_query(F.data.startswith("order_cancel_"))
async def handle_order_cancel(callback: CallbackQuery):
    await apply_status(callback, int(callback.data.replace("order_cancel_", "")), STATUS_CANCELLED)


@router.callback_query(F.data == "admin_orders")
async def handle_orders_list(callback: CallbackQuery):
    async with async_session_factory() as session:
        res = await session.execute(
            select(Order).where(Order.status.notin_(list(FINAL_STATUSES)))
            .order_by(desc(Order.created_at)).limit(ORDERS_PAGE)
        )
        orders = res.scalars().all()

    rows = [
        [InlineKeyboardButton(
            text=f"#{o.id} {label(o.status)} · {o.customer_name[:14]} · {format_price(o.total)}"[:60],
            callback_data=f"ord_view:{o.id}",
        )]
        for o in orders
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")])
    text = (
        f"🧾 <b>Faol buyurtmalar</b> (oxirgi {ORDERS_PAGE} ta)\nHolatini o'zgartirish uchun buyurtmani tanlang:"
        if orders else "🧾 <b>Faol buyurtmalar yo'q.</b> Yetkazilgan va bekor qilinganlar bu yerda ko'rinmaydi."
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("ord_view:"))
async def handle_order_view(callback: CallbackQuery):
    order_id = int(callback.data.split(":", 1)[1])
    async with async_session_factory() as session:
        order = (await session.execute(select(Order).where(Order.id == order_id))).scalars().first()
    if order is None:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    await edit_card(callback, order, back_to_list=True)
    await callback.answer()
