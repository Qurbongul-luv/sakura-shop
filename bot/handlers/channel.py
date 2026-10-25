from html import escape
import logging
import re
from typing import Tuple

from aiogram import Bot, Router, F
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ChatMemberUpdated, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from bot.loader import bot
from bot.services.contest_service import get_active_contest
from db.models import Admin, Setting
from db.session import async_session_factory

router = Router(name="channel")
logger = logging.getLogger(__name__)

CHANNEL_REF_RE = re.compile(r"(?:https?://)?(?:t\.me/|@)?([A-Za-z0-9_]{5,32})/?")


class ChannelLinkState(StatesGroup):
    waiting_for_username = State()


async def is_shop_owner(session: AsyncSession, user_id: int) -> bool:
    if settings.DEV_ADMIN_ID and user_id == settings.DEV_ADMIN_ID:
        return True
    res = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
    admin = res.scalars().first()
    return admin is not None and admin.role == "owner"


async def save_channel_id(session: AsyncSession, chat_id: str) -> None:
    res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
    ch_setting = res_ch.scalars().first()
    if ch_setting:
        ch_setting.value = chat_id
    else:
        session.add(Setting(key="channel_id", value=chat_id))
    await session.commit()


async def link_channel_by_username(session: AsyncSession, tg_bot: Bot, user_id: int, raw: str) -> Tuple[bool, str]:
    """Links a channel where the bot can post and user_id is an admin. Returns (linked, reply text)."""
    m = CHANNEL_REF_RE.fullmatch(raw.strip())
    if not m:
        return False, "❌ Kanal @username ini yuboring (masalan: <code>@sakuraaa_chinese_shop</code>) yoki /cancel."
    ref = f"@{m.group(1)}"
    try:
        chat = await tg_bot.get_chat(ref)
        me = await tg_bot.get_me()
        bot_member = await tg_bot.get_chat_member(chat_id=chat.id, user_id=me.id)
        user_member = await tg_bot.get_chat_member(chat_id=chat.id, user_id=user_id)
    except Exception as e:
        logger.warning(f"Channel link lookup failed for {ref}: {e}")
        return False, f"❌ {escape(ref)} topilmadi yoki bot u yerda yo'q. Botni kanalga admin qilib, qayta yuboring."

    if chat.type not in ["channel", "supergroup"]:
        return False, "❌ Bu kanal emas."
    if bot_member.status != ChatMemberStatus.ADMINISTRATOR or (
        chat.type == "channel" and not getattr(bot_member, "can_post_messages", False)
    ):
        return False, "❌ Bot bu kanalda post joylash huquqi bilan admin emas."
    if user_member.status not in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR):
        return False, "❌ Siz bu kanalda admin emassiz."

    await save_channel_id(session, str(chat.id))
    return True, f"✅ <b>Kanal ulandi:</b> {escape(str(chat.title))} (<code>{chat.id}</code>) 🌸"


async def unlink_channel(session: AsyncSession) -> Tuple[bool, str]:
    # Unlinking mid-contest would make every invitee's ✅ Tasdiqlash fail.
    if await get_active_contest(session):
        return False, "⛔ Faol konkurs bor. Avval konkursni tugating yoki bekor qiling, keyin kanalni uzing."
    await save_channel_id(session, "")
    return True, "📢 Kanal uzildi. Qayta ulash: ⚙️ Sozlamalar → 🔗 Kanalni ulash."


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
            # Accept channels added by any verified shop owner, not only the first one in the table
            if not await is_shop_owner(session, from_user.id):
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
                    chat_id=from_user.id,
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
                logger.error(f"Could not send DM to owner {from_user.id}: {e}")

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
        if not await is_shop_owner(session, user_id):
            await callback.answer("⛔ Faqat do'kon egasi kanalni ulashi mumkin!", show_alert=True)
            return
        await save_channel_id(session, chat_id)

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


# Manual linking for when the bot was made admin by someone who isn't a shop owner in the bot.
@router.callback_query(F.data == "admin_link_channel")
async def handle_link_channel_prompt(callback: CallbackQuery, state: FSMContext):
    async with async_session_factory() as session:
        if not await is_shop_owner(session, callback.from_user.id):
            await callback.answer("⛔ Faqat do'kon egasi kanalni ulashi mumkin!", show_alert=True)
            return
    await state.set_state(ChannelLinkState.waiting_for_username)
    await callback.message.answer(
        "🔗 <b>Kanalni ulash</b>\n\n"
        "Kanal @username ini yuboring (masalan: <code>@sakuraaa_chinese_shop</code>).\n"
        "Bot kanalda post joylash huquqi bilan admin bo'lishi, siz esa kanal admini bo'lishingiz kerak.\n\n"
        "Bekor qilish: /cancel"
    )
    await callback.answer()


@router.message(ChannelLinkState.waiting_for_username)
async def process_link_channel(message: Message, state: FSMContext):
    text_val = (message.text or "").strip()
    if text_val.lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Kanal ulanmadi.")
        return
    async with async_session_factory() as session:
        linked, reply = await link_channel_by_username(session, message.bot, message.from_user.id, text_val)
    if linked:
        await state.clear()
    await message.answer(reply)


@router.callback_query(F.data == "admin_unlink_channel")
async def handle_unlink_channel(callback: CallbackQuery):
    async with async_session_factory() as session:
        if not await is_shop_owner(session, callback.from_user.id):
            await callback.answer("⛔ Faqat do'kon egasi kanalni uzishi mumkin!", show_alert=True)
            return
        _, reply = await unlink_channel(session)
    await callback.answer(reply, show_alert=True)
