import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select

from bot.loader import bot
from db.models import Order, Admin
from db.session import async_session_factory

router = Router(name="orders")
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("order_accept_"))
async def handle_order_accept(callback: CallbackQuery):
    order_id = int(callback.data.replace("order_accept_", ""))
    admin_id = callback.from_user.id
    admin_name = callback.from_user.full_name

    async with async_session_factory() as session:
        # Check admin
        res_adm = await session.execute(select(Admin).where(Admin.telegram_id == admin_id))
        if not res_adm.scalars().first():
            await callback.answer("⛔ Faqat adminlar buyurtmani qabul qilishi mumkin!", show_alert=True)
            return

        res = await session.execute(select(Order).where(Order.id == order_id))
        order = res.scalars().first()
        if not order:
            await callback.answer("Buyurtma topilmadi", show_alert=True)
            return

        order.status = "accepted"
        await session.commit()
        customer_user_id = order.user_id

    # Notify customer
    if bot and customer_user_id:
        try:
            await bot.send_message(
                chat_id=customer_user_id,
                text=(
                    f"🌸 <b>Buyurtmangiz (#{order_id}) qabul qilindi!</b> ✅\n\n"
                    f"Admin tez orada kargo va to'lov rekvizitlarini yuborish uchun siz bilan bog'lanadi.\n"
                    f"Savollaringiz bo'lsa @fkhrdnvvvva ga yozishingiz mumkin 💌"
                ),
            )
        except Exception as e:
            logger.warning(f"Could not notify customer {customer_user_id}: {e}")

    orig_text = callback.message.html_text or callback.message.text
    new_text = f"{orig_text}\n\n<b>✅ QABUL QILINDI</b> (Admin: {admin_name})"
    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.answer("✅ Buyurtma qabul qilindi!")


@router.callback_query(F.data.startswith("order_cancel_"))
async def handle_order_cancel(callback: CallbackQuery):
    order_id = int(callback.data.replace("order_cancel_", ""))
    admin_id = callback.from_user.id
    admin_name = callback.from_user.full_name

    async with async_session_factory() as session:
        res_adm = await session.execute(select(Admin).where(Admin.telegram_id == admin_id))
        if not res_adm.scalars().first():
            await callback.answer("⛔ Faqat adminlar buyurtmani bekor qilishi mumkin!", show_alert=True)
            return

        res = await session.execute(select(Order).where(Order.id == order_id))
        order = res.scalars().first()
        if not order:
            await callback.answer("Buyurtma topilmadi", show_alert=True)
            return

        order.status = "cancelled"
        await session.commit()
        customer_user_id = order.user_id

    # Notify customer
    if bot and customer_user_id:
        try:
            await bot.send_message(
                chat_id=customer_user_id,
                text=(
                    f"🌸 <b>Buyurtmangiz (#{order_id}) bekor qilindi.</b> ❌\n\n"
                    f"Batafsil ma'lumot olish yoki boshqa model tanlash uchun @fkhrdnvvvva ga murojaat qiling 💌"
                ),
            )
        except Exception as e:
            logger.warning(f"Could not notify customer {customer_user_id}: {e}")

    orig_text = callback.message.html_text or callback.message.text
    new_text = f"{orig_text}\n\n<b>❌ BEKOR QILINDI</b> (Admin: {admin_name})"
    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.answer("❌ Buyurtma bekor qilindi")
