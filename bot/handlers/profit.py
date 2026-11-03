"""Owner-only profit report and product cost entry. Every entry point re-checks the owner role."""
import logging
from html import escape
from typing import Optional

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from api.services.formatters import format_price
from bot.services.profit import ProfitReport, build_report, is_owner
from db.models import Product
from db.session import async_session_factory

router = Router(name="profit")
logger = logging.getLogger(__name__)

PERIODS = ((7, "7 kun"), (30, "30 kun"), (0, "Hammasi"))
MAX_COST = 100_000_000


class OwnerCost(StatesGroup):
    waiting = State()


async def owner_event(event: Message | CallbackQuery) -> bool:
    if event.from_user is None:
        return False
    async with async_session_factory() as session:
        return await is_owner(session, event.from_user.id)


router.callback_query.filter(owner_event)

# Never take /cancel or the reply-keyboard cancel button as a cost.
TEXT_ANSWER = F.text & ~F.text.startswith("/") & (F.text != "❌ Bekor qilish")


def report_text(report: ProfitReport, period_label: str) -> str:
    lines = [f"💰 <b>FOYDA HISOBOTI — {period_label}</b> 👑\n"]
    if not report.orders:
        lines.append("<i>Bu davrda sotilgan (qabul qilingan) buyurtma yo'q.</i>")
        return "\n".join(lines)
    lines += [
        f"🧾 Buyurtmalar: <b>{report.orders}</b> ta",
        f"💵 Tushum: <b>{format_price(report.revenue)}</b>",
    ]
    if report.costed_orders:
        margin = report.margin_percent
        lines += [
            "",
            f"🛒 Tannarx ({report.costed_orders} ta buyurtma): {format_price(report.cost)}",
            f"📈 <b>Sof foyda: {format_price(report.profit)}</b>"
            + (f" ({margin:g}%)" if margin is not None else ""),
        ]
    if report.uncosted_orders:
        lines.append(
            f"\n⚠️ {report.uncosted_orders} ta buyurtmada tannarx noma'lum — foydaga qo'shilmadi. "
            "Mahsulot sahifasida 💴 Tannarx tugmasi bilan kiriting."
        )
    if report.top_products:
        lines.append("\n🏆 <b>Eng ko'p sotilganlar:</b>")
        for i, (title, qty, revenue) in enumerate(report.top_products, 1):
            lines.append(f"{i}. {escape(title[:40])} — {qty} dona, {format_price(revenue)}")
    lines.append("\n<i>Kargo hisobga olinmagan: uni mijoz alohida to'laydi.</i>")
    return "\n".join(lines)


def report_markup(active: int) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text=("• " if days == active else "") + label, callback_data=f"own_profit:{days}")
        for days, label in PERIODS
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[row, [InlineKeyboardButton(text="⬅️ Admin menyusi", callback_data="admin_menu")]]
    )


async def render(days: int) -> str:
    async with async_session_factory() as session:
        report = await build_report(session, days or None)
    return report_text(report, dict(PERIODS)[days])


@router.message(Command("foyda"), owner_event)
async def handle_profit_command(message: Message):
    await message.answer(await render(30), reply_markup=report_markup(30))


@router.callback_query(F.data.startswith("own_profit:"))
async def handle_profit_period(callback: CallbackQuery):
    raw = callback.data.split(":", 1)[1]
    days = int(raw) if raw.isdigit() and int(raw) in dict(PERIODS) else 30
    try:
        await callback.message.edit_text(await render(days), reply_markup=report_markup(days))
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()


@router.callback_query(F.data.startswith("own_cost:"))
async def handle_cost_prompt(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":", 1)[1])
    async with async_session_factory() as session:
        product = (await session.execute(select(Product).where(Product.id == product_id))).scalars().first()
    if product is None:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return
    await state.set_state(OwnerCost.waiting)
    await state.update_data(cost_product_id=product_id)
    current = format_price(product.cost_som) if product.cost_som is not None else "kiritilmagan"
    await callback.message.answer(
        f"💴 <b>{escape(product.title)}</b>\nSotuv narxi: {format_price(product.price)}\nHozirgi tannarx: {current}\n\n"
        "Bitta dona uchun sotib olish narxini so'mda yozing (masalan: <code>95000</code>).\n"
        "O'chirish uchun <code>0</code> yozing. /cancel — bekor."
    )
    await callback.answer()


def parse_cost(text: str) -> Optional[int]:
    raw = text.replace(".", "").replace(",", "").replace(" ", "").replace("so'm", "").strip()
    if not raw.isdigit():
        return None
    value = int(raw)
    return value if value <= MAX_COST else None


@router.message(OwnerCost.waiting, TEXT_ANSWER, owner_event)
async def handle_cost_input(message: Message, state: FSMContext):
    value = parse_cost(message.text)
    if value is None:
        await message.answer("⚠️ Narxni raqam bilan yozing (masalan: 95000), yoki /cancel.")
        return
    product_id = (await state.get_data()).get("cost_product_id")
    await state.clear()
    async with async_session_factory() as session:
        product = (await session.execute(select(Product).where(Product.id == product_id))).scalars().first()
        if product is None:
            await message.answer("Mahsulot topilmadi.")
            return
        product.cost_som = value or None
        await session.commit()
        margin = f"\n📈 Bir donadan foyda: {format_price(product.price - value)}" if value else ""
    logger.info(f"Owner {message.from_user.id} set cost of product #{product_id} to {value}")
    await message.answer(
        f"✅ Tannarx saqlandi: {format_price(value) if value else 'olib tashlandi'}{margin}\n"
        "<i>Faqat bundan keyingi buyurtmalarga ta'sir qiladi.</i>"
    )
