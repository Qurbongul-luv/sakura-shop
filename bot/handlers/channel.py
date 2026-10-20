from html import escape
import logging
from aiogram import Router, F
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from api.config import settings
from bot.loader import bot
from db.models import Admin, Setting
from db.session import async_session_factory

router = Router(name="channel")
logger = logging.getLogger(__name__)


@router.my_chat_member()
async def handle_bot_chat_member_update(event: ChatMemberUpdated):
    """
    Detects when the bot is added as administrator to a channel, or removed.
    """
    chat = event.chat
    if chat.type not in ["channel", "supergroup"]:
        return

    from_user = event.from_user
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    async with async_session_factory() as session:
        # Get owner
        res_owner = await session.execute(select(Admin).where(Admin.role == "owner"))
        owner = res_owner.scalars().first()
        owner_id = owner.telegram_id if owner else settings.DEV_ADMIN_ID

        # Case 1: Bot added as Administrator
        if new_status == ChatMemberStatus.ADMINISTRATOR:
            # Only accept channels added by the verified shop owner
            if not owner_id or from_user.id != owner_id:
                logger.warning(
                    f"Bot added to channel {escape(str(chat.title))} ({chat.id}) by non-owner {from_user.id}. Ignored."
                )
                return

            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Ha, ulash / Link",
                            callback_data=f"confirm_link_channel_{chat.id}"
                        ),
                        InlineKeyboardButton(
                            text="❌ Yo'q / Cancel",
                            callback_data="cancel_link_channel"
                        )
                    ]
                ]
            )

            try:
                await bot.send_message(
                    chat_id=owner_id,
                    text=(
                        f"🌸 <b>Yangi kanal aniqlandi:</b>\n"
                        f"📢 <b>Nomi:</b> {escape(str(chat.title))}\n"
                        f"🔗 <b>Username:</b> @{chat.username or 'mavjud emas'}\n"
                        f"🆔 <b>ID:</b> <code>{chat.id}</code>\n\n"
                        f"Ushbu kanalni do'konga ulaymi? / Link this channel?"
                    ),
                    reply_markup=markup,
                )
            except Exception as e:
                logger.error(f"Could not send DM to owner {owner_id}: {e}")

        # Case 2: Bot removed or kicked
        elif new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
            res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
            ch_setting = res_ch.scalars().first()
            if ch_setting and ch_setting.value == str(chat.id):
                ch_setting.value = ""
                await session.commit()

                if owner_id:
                    try:
                        await bot.send_message(
                            chat_id=owner_id,
                            text=(
                                f"⚠️ <b>Bot '{escape(str(chat.title))}' kanalidan chiqarildi.</b>\n"
                                f"Kanal do'kondan avtomatik tarzda uzildi."
                            )
                        )
                    except Exception:
                        pass


@router.callback_query(F.data.startswith("confirm_link_channel_"))
async def handle_confirm_link_channel(callback: CallbackQuery):
    chat_id = callback.data.replace("confirm_link_channel_", "").strip()
    user_id = callback.from_user.id

    async with async_session_factory() as session:
        # Check owner permission
        res_admin = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
        admin = res_admin.scalars().first()
        is_owner = (admin and admin.role == "owner") or (user_id == settings.DEV_ADMIN_ID)

        if not is_owner:
            await callback.answer("⛔ Faqat do'kon egasi kanalni ulashi mumkin!", show_alert=True)
            return

        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        ch_setting = res_ch.scalars().first()
        if ch_setting:
            ch_setting.value = chat_id
        else:
            session.add(Setting(key="channel_id", value=chat_id))

        await session.commit()

    await callback.message.edit_text(
        f"✅ <b>Kanal muvaffaqiyatli ulandi!</b> 🌸\n"
        f"Kanal ID: <code>{chat_id}</code>\n\n"
        f"Endi har safar yangi mahsulot qo'shganingizda uni bir bosishda kanalingizga joylashingiz mumkin!"
    )
    await callback.answer("✅ Kanal ulandi!")


@router.callback_query(F.data == "cancel_link_channel")
async def handle_cancel_link_channel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Kanal ulanmadi.")
    await callback.answer("Bekor qilindi.")
