"""Customer side of the post-delivery review: tap the button, send photo(s) and text in one go."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bot.services.channel_import import AlbumCollector, IncomingPost, admin_chat_ids
from bot.services.review_requests import save_review
from db.models import Order
from db.session import async_session_factory

router = Router(name="review_request")
logger = logging.getLogger(__name__)

# Album photos of one review arrive as separate messages.
review_albums = AlbumCollector()

CANCEL_MARKUP = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="rv_cancel")]]
)
ANSWER = F.photo | (F.text & ~F.text.startswith("/"))


class ReviewSubmit(StatesGroup):
    waiting = State()


@router.callback_query(F.data.startswith("rv_start:"))
async def handle_review_start(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":", 1)[1])
    async with async_session_factory() as session:
        order = (await session.execute(select(Order).where(Order.id == order_id))).scalars().first()
    if order is None or order.user_id != callback.from_user.id or order.status != "delivered":
        await callback.answer("Bu buyurtma topilmadi 🌸", show_alert=True)
        return
    if order.reviewed_at is not None:
        await callback.answer("Siz bu buyurtmaga fikr qoldirgansiz, rahmat! 💗", show_alert=True)
        return
    await state.set_state(ReviewSubmit.waiting)
    await state.update_data(review_order_id=order_id)
    await callback.message.answer(
        "📸 Mahsulot rasmini (bir nechta bo'lsa ham bo'ladi) va fikringizni <b>bitta xabarda</b> yuboring.\n"
        "Rasmsiz, faqat matn yozsangiz ham bo'ladi 🌸",
        reply_markup=CANCEL_MARKUP,
    )
    await callback.answer()


@router.callback_query(F.data == "rv_cancel")
async def handle_review_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Mayli 🌸 Istalgan vaqt yuqoridagi tugma orqali fikr qoldirishingiz mumkin.")
    await callback.answer()


@router.message(ReviewSubmit.waiting, ANSWER)
async def handle_review_message(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("review_order_id")
    bot = message.bot
    user = message.from_user

    async def finish(post: IncomingPost) -> None:
        await state.clear()
        if not post.photos and not post.caption.strip():
            await bot.send_message(user.id, "Rasm yoki matn yuboring 🌸", reply_markup=CANCEL_MARKUP)
            await state.set_state(ReviewSubmit.waiting)
            await state.update_data(review_order_id=order_id)
            return
        async with async_session_factory() as session:
            review = await save_review(
                session, int(order_id), user.id, user.first_name or "Mijoz", post.caption, post.photos
            )
            if review is None:
                await bot.send_message(user.id, "Bu buyurtmaga fikr allaqachon qabul qilingan, rahmat! 💗")
                return
            await bot.send_message(user.id, "💗 <b>Rahmat!</b> Fikringiz qabul qilindi va tez orada do'konda ko'rinadi 🌸")
            await notify_admins(bot, await admin_chat_ids(session), review.id, int(order_id), user.first_name, post)

    await review_albums.add(
        receiving_chat_id=message.chat.id,
        source_chat_id=message.chat.id,
        message_id=message.message_id,
        media_group_id=message.media_group_id,
        photo_id=message.photo[-1].file_id if message.photo else None,
        caption=message.caption or message.text,
        handler=finish,
    )


async def notify_admins(bot: Bot, admin_ids, review_id: int, order_id: int, name: str, post: IncomingPost) -> None:
    text = (
        f"⭐ <b>Yangi fikr (buyurtma #{order_id})</b>\n"
        f"👤 {escape(name or 'Mijoz')} · 📸 {len(post.photos)} ta rasm\n\n"
        f"<i>{escape(post.caption.strip()[:500]) or '—'}</i>\n\n"
        "Do'konda ko'rinishi uchun tasdiqlang:"
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_toggle_rev_{review_id}"),
            InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"admin_del_rev_{review_id}"),
        ]]
    )
    for chat_id in admin_ids:
        try:
            if post.photos:
                await bot.send_photo(chat_id=chat_id, photo=post.photos[0])
            # Buttons go on a text message: the approve handler edits it with edit_text.
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
        except Exception as e:
            logger.info(f"Could not notify admin {chat_id} about review #{review_id}: {e}")
