from html import escape
import asyncio
import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from db.models import Contest, Admin, utcnow
from db.session import async_session_factory
from bot.services.contest_service import (
    final_recheck_contest,
    compute_leaderboard,
    send_pending_reminders,
    ensure_utc,
)

logger = logging.getLogger(__name__)


async def notify_owner_contest_ended(bot: Bot, contest_id: int, session_factory=None):
    """Sends owner the results approval DM with action buttons."""
    sf = session_factory or async_session_factory
    async with sf() as session:
        res_c = await session.execute(select(Contest).where(Contest.id == contest_id))
        contest = res_c.scalars().first()
        if not contest:
            return

        leaderboard = await compute_leaderboard(session, contest_id, limit=3)
        winners = [w for w in leaderboard if w["score"] > 0][:3]

        res_admins = await session.execute(select(Admin).where(Admin.role == "owner"))
        owners = res_admins.scalars().all()
        if not owners:
            res_all_admins = await session.execute(select(Admin))
            owners = res_all_admins.scalars().all()

        lines = [
            "🏆 <b>Konkurs vaqti tugadi! Natijalar tayyor:</b>\n",
            f"🥇 1-o'rin sovg'asi: {escape(contest.prize_1)}",
            f"🥈 2-o'rin sovg'asi: {escape(contest.prize_2)}",
            f"🥉 3-o'rin sovg'asi: {escape(contest.prize_3)}\n",
            "📊 <b>Yetakchilar (Top 3):</b>"
        ]

        if winners:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for w in winners:
                medal = medals.get(w["rank"], "🎖")
                tag = f"@{w['username']}" if w["username"] else escape(w["name"])
                lines.append(f"{medal} {w['rank']}-o'rin: {tag} (ID: <code>{w['user_id']}</code>) — <b>{w['score']}</b> ball")
        else:
            lines.append("<i>Ball to'plagan ishtirokchilar mavjud emas.</i>")

        lines.append("\nQuyidagi tugmalar orqali natijani tasdiqlang yoki qayta tekshiring:")

        text = "\n".join(lines)
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ E'lon qilish", callback_data=f"contest_approve:{contest.id}"),
                    InlineKeyboardButton(text="🔁 Qayta tekshirish", callback_data=f"contest_recheck:{contest.id}"),
                ],
                [
                    InlineKeyboardButton(text="🚫 Diskvalifikatsiya qilish", callback_data=f"contest_dq_menu:{contest.id}"),
                ]
            ]
        )

        for owner in owners:
            try:
                await bot.send_message(chat_id=owner.telegram_id, text=text, reply_markup=markup)
            except Exception as e:
                logger.warning(f"Could not notify owner {owner.telegram_id} of contest end: {e}")


async def check_and_handle_expired_contests(bot: Optional[Bot], session_factory=None):
    """Checks for contests that expired and locks them for owner approval."""
    if not bot:
        return

    sf = session_factory or async_session_factory
    async with sf() as session:
        now = utcnow()
        stmt = select(Contest).where(Contest.status == "active")
        active_contests = (await session.execute(stmt)).scalars().all()

        expired_contests = [c for c in active_contests if ensure_utc(c.ends_at) <= now]

        for contest in expired_contests:
            logger.info(f"Contest #{contest.id} has reached ends_at. Starting final recheck and locking.")
            # 1. Lock and run final recheck
            revoked_count = await final_recheck_contest(session, bot, contest.id)
            logger.info(f"Contest #{contest.id} recheck complete: {revoked_count} revoked.")

            # 2. Notify owner
            await notify_owner_contest_ended(bot, contest.id, session_factory=sf)


async def run_contest_scheduler(bot: Optional[Bot]):
    """Background loop checking expired contests and sending 1h reminders."""
    if not bot:
        return

    logger.info("Contest background scheduler started.")
    reminder_tick = 0
    while True:
        try:
            await check_and_handle_expired_contests(bot)

            # Every ~15 minutes check reminders
            reminder_tick += 1
            if reminder_tick >= 15:
                reminder_tick = 0
                async with async_session_factory() as session:
                    reminders_sent = await send_pending_reminders(session, bot)
                    if reminders_sent > 0:
                        logger.info(f"Sent {reminders_sent} pending referral reminders.")
        except asyncio.CancelledError:
            logger.info("Contest scheduler stopped.")
            break
        except Exception as e:
            logger.error(f"Error in contest scheduler loop: {e}")

        await asyncio.sleep(60)
