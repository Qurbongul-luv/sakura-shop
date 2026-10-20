import asyncio
import logging
from typing import Optional
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest
from sqlalchemy import select
from bot.loader import bot
from db.models import User
from db.session import async_session_factory

logger = logging.getLogger(__name__)


async def run_broadcast(text: str, photo_url: Optional[str] = None, admin_id: Optional[int] = None) -> None:
    if not bot:
        logger.warning("Bot is not running, broadcast cancelled")
        return

    async with async_session_factory() as session:
        res = await session.execute(select(User).where(User.blocked_bot == False))
        users = res.scalars().all()
        total_users = len(users)

    if total_users == 0:
        if admin_id:
            try:
                await bot.send_message(chat_id=admin_id, text="📣 Tarqatish uchun foydalanuvchilar topilmadi.")
            except Exception:
                pass
        return

    status_msg = None
    if admin_id:
        try:
            status_msg = await bot.send_message(
                chat_id=admin_id,
                text=f"📣 Xabar tarqatish boshlandi...\nJami qabul qiluvchilar: {total_users}\nKutilmoqda...",
            )
        except Exception as e:
            logger.warning(f"Failed to send status message to admin: {e}")

    sent_count = 0
    blocked_count = 0
    failed_count = 0

    for idx, user in enumerate(users, 1):
        try:
            if photo_url:
                await bot.send_photo(chat_id=user.telegram_id, photo=photo_url, caption=text)
            else:
                await bot.send_message(chat_id=user.telegram_id, text=text)
            sent_count += 1
        except TelegramForbiddenError:
            blocked_count += 1
            async with async_session_factory() as session:
                u_res = await session.execute(select(User).where(User.telegram_id == user.telegram_id))
                u = u_res.scalars().first()
                if u:
                    u.blocked_bot = True
                    await session.commit()
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                if photo_url:
                    await bot.send_photo(chat_id=user.telegram_id, photo=photo_url, caption=text)
                else:
                    await bot.send_message(chat_id=user.telegram_id, text=text)
                sent_count += 1
            except Exception:
                failed_count += 1
        except TelegramBadRequest as e:
            if "chat not found" in str(e).lower() or "blocked" in str(e).lower():
                blocked_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.warning(f"Error sending broadcast to {user.telegram_id}: {e}")
            failed_count += 1

        # Rate limit: ~25 messages/sec (0.04s sleep per send)
        await asyncio.sleep(0.04)

        # Update status message every 50 users
        if status_msg and idx % 50 == 0:
            try:
                await bot.edit_message_text(
                    chat_id=admin_id,
                    message_id=status_msg.message_id,
                    text=f"📣 Tarqatish jarayonda...\nBajarildi: {idx}/{total_users}\n✅ Yuborildi: {sent_count}\n🚫 Bloklangan: {blocked_count}",
                )
            except Exception:
                pass

    final_report = (
        f"✅ <b>Xabar tarqatish yakunlandi!</b> 🌸\n\n"
        f"👥 Jami: {total_users}\n"
        f"💌 Yetkazildi: {sent_count}\n"
        f"🚫 Botni bloklaganlar: {blocked_count}\n"
        f"⚠️ Xatoliklar: {failed_count}"
    )

    if admin_id and status_msg:
        try:
            await bot.edit_message_text(chat_id=admin_id, message_id=status_msg.message_id, text=final_report)
        except Exception:
            try:
                await bot.send_message(chat_id=admin_id, text=final_report)
            except Exception:
                pass
