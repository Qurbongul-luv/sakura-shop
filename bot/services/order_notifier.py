import logging
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from api.services.formatters import build_order_summary
from bot.loader import bot
from db.models import Admin, Setting, User
from db.session import async_session_factory

logger = logging.getLogger(__name__)


async def notify_new_order(
    order_id: int,
    user_id: int,
    customer_name: str,
    customer_username: Optional[str],
    items: List[Dict[str, Any]],
    total: int,
    estimated_cargo: int = 0,
) -> None:
    if not bot:
        logger.info(f"Bot not active, skipped Telegram notification for order #{order_id}")
        return

    async with async_session_factory() as session:
        # Get contact username
        res_contact = await session.execute(select(Setting).where(Setting.key == "contact_username"))
        contact_setting = res_contact.scalars().first()
        contact_username = contact_setting.value if contact_setting else "fkhrdnvvvva"

        # Get all admins
        res_admins = await session.execute(select(Admin))
        admins = res_admins.scalars().all()

        summaries = build_order_summary(
            order_id=order_id,
            user_id=user_id,
            customer_name=customer_name,
            customer_username=customer_username,
            items=items,
            total=total,
            estimated_cargo=estimated_cargo,
            contact_username=contact_username,
        )

        # 1. Send to all admins
        admin_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Qabul qilindi", callback_data=f"order_accept_{order_id}"),
                    InlineKeyboardButton(text="❌ Bekor", callback_data=f"order_cancel_{order_id}"),
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Mijoz profili",
                        url=f"https://t.me/{customer_username}" if customer_username else f"tg://user?id={user_id}"
                    )
                ]
            ]
        )

        for admin in admins:
            try:
                await bot.send_message(
                    chat_id=admin.telegram_id,
                    text=summaries["admin_text"],
                    reply_markup=admin_markup,
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin.telegram_id} for order #{order_id}: {e}")

        # 2. Send to customer
        clean_contact = contact_username.replace("@", "")
        customer_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"💌 @{clean_contact} ga yozish",
                        url=f"https://t.me/{clean_contact}"
                    )
                ]
            ]
        )

        try:
            await bot.send_message(
                chat_id=user_id,
                text=summaries["customer_text"],
                reply_markup=customer_markup,
            )
        except Exception as e:
            logger.error(f"Failed to send confirmation to customer {user_id} for order #{order_id}: {e}")
