import logging
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, KICKED, LEFT, RESTRICTED, MEMBER, ADMINISTRATOR
from sqlalchemy import select

from db.models import Admin, Contest, Setting
from db.session import async_session_factory
from bot.services.contest_service import revoke_referral_on_leave, get_channel_info

logger = logging.getLogger(__name__)
router = Router(name="channel_member")


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=True))
async def handle_channel_member_updated(event: ChatMemberUpdated):
    """
    Tracks channel member status changes:
    1. If user leaves the channel -> revoke referral point and notify referrer.
    2. If bot itself loses admin rights -> alert owner and pause contest.
    """
    bot = event.bot
    chat_id = event.chat.id
    user = event.new_chat_member.user

    async with async_session_factory() as session:
        stored_channel_id, _ = await get_channel_info(session)
        if not stored_channel_id:
            return

        # Ensure event is from the linked channel
        try:
            if str(chat_id) != str(stored_channel_id):
                return
        except Exception:
            return

        # Check if bot itself lost admin rights
        bot_me = await bot.get_me()
        if user.id == bot_me.id:
            old_status = event.old_chat_member.status
            new_status = event.new_chat_member.status

            if old_status in ("administrator", "creator") and new_status not in ("administrator", "creator"):
                logger.warning("Bot lost admin rights in the channel! Pausing active contest.")
                # Pause active contest
                res_c = await session.execute(select(Contest).where(Contest.status == "active"))
                active_c = res_c.scalars().first()
                if active_c:
                    active_c.status = "paused"
                    await session.commit()

                # Notify owner
                res_adm = await session.execute(select(Admin).where(Admin.role == "owner"))
                owners = res_adm.scalars().all()
                for o in owners:
                    try:
                        await bot.send_message(
                            chat_id=o.telegram_id,
                            text=(
                                "🚨 <b>DIQQAT! Bot kanalda admin huquqidan mahrum bo'ldi!</b>\n\n"
                                "Konkurs hisob-kitobida xatolik bo'lmasligi uchun konkurs vaqtincha to'xtatildi (Pauza).\n"
                                "Iltimos, botni qaytadan kanalga to'liq admin qilib qo'ying."
                            )
                        )
                    except Exception:
                        pass
            return

        # Handle customer leaving the channel
        old_status = event.old_chat_member.status
        new_status = event.new_chat_member.status

        was_member = old_status in ("member", "administrator", "creator") or (
            old_status == "restricted" and getattr(event.old_chat_member, "is_member", True)
        )
        is_left = new_status in ("left", "kicked")

        if was_member and is_left:
            logger.info(f"User {user.id} left the channel. Revoking contest point if applicable.")
            await revoke_referral_on_leave(session, bot, user.id)
