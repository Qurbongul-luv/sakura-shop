"""
Admin sends a Taobao/Tmall link → the bot fetches the item, shows photos and the computed price,
asks for the Uzbek name, category, colors and sizes, and saves only after the admin confirms.
"""
import asyncio
import logging
from html import escape
from typing import Any, Dict, List, Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)
from sqlalchemy import select

from api.config import settings
from api.services.formatters import format_price
from api.services.taobao import (
    PriceRule,
    TaobaoItem,
    TaobaoLink,
    calculate_cost,
    calculate_price,
    find_taobao_link,
    parse_rule_input,
    rule_from_settings,
    rule_to_settings,
)
from bot.services.channel_post import post_product_to_channel
from bot.services.taobao_client import TaobaoFetchError, download_image, fetch_item, resolve_short_link
from db.models import Admin, Category, Product, Setting
from db.session import async_session_factory

router = Router(name="taobao_import")
logger = logging.getLogger(__name__)

EXAMPLE_YUAN = 100


class TaobaoImport(StatesGroup):
    title = State()
    category = State()
    colors = State()
    sizes = State()
    price = State()
    confirm = State()


class TaobaoPricing(StatesGroup):
    waiting_rule = State()


async def is_admin(user_id: int) -> bool:
    if settings.DEV_ADMIN_ID and user_id == settings.DEV_ADMIN_ID:
        return True
    async with async_session_factory() as session:
        res = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
        return res.scalars().first() is not None


async def admin_event(event: Message | CallbackQuery) -> bool:
    return event.from_user is not None and await is_admin(event.from_user.id)


async def has_taobao_link(message: Message) -> Dict[str, Any] | bool:
    link = find_taobao_link(message.text or message.caption)
    return {"link": link} if link else False


router.callback_query.filter(admin_event)

# Step answers: never swallow /cancel or the reply-keyboard cancel button handled by the admin router.
TEXT_ANSWER = F.text & ~F.text.startswith("/") & (F.text != "❌ Bekor qilish")


# ==================== PRICE RULE ====================
async def load_rule() -> PriceRule:
    async with async_session_factory() as session:
        rows = (await session.execute(select(Setting).where(Setting.key.like("taobao_%")))).scalars().all()
    return rule_from_settings({s.key: s.value for s in rows})


async def save_rule(rule: PriceRule) -> None:
    async with async_session_factory() as session:
        existing = {
            s.key: s
            for s in (await session.execute(select(Setting).where(Setting.key.like("taobao_%")))).scalars().all()
        }
        for key, value in rule_to_settings(rule).items():
            if key in existing:
                existing[key].value = value
            else:
                session.add(Setting(key=key, value=value))
        await session.commit()


def rule_summary(rule: PriceRule) -> str:
    if not rule.is_configured:
        return "<i>Hali sozlanmagan.</i>"
    return (
        f"💱 Kurs: <b>1 ¥ = {format_price(rule.yuan_rate)}</b>\n"
        f"📈 Ustama: <b>{rule.markup_percent:g}%</b>\n"
        f"➕ Qo'shimcha foyda: <b>{format_price(rule.markup_fixed)}</b>\n"
        f"🔢 Yaxlitlash: <b>{format_price(rule.round_to)}</b> gacha (yuqoriga)\n\n"
        f"Misol: {EXAMPLE_YUAN} ¥ → <b>{format_price(calculate_price(EXAMPLE_YUAN, rule))}</b>"
    )


RULE_PROMPT = (
    "Narx formulasini bitta qatorda yozing:\n"
    "<code>kurs ustama% [foyda] [yaxlitlash]</code>\n\n"
    "Masalan: <code>1800 30 20000 1000</code>\n"
    "= 1 ¥ 1800 so'm, ustiga 30%, yana 20.000 so'm, 1.000 gacha yaxlitlanadi.\n"
    "Faqat kurs va foiz: <code>1800 30</code>"
)


async def ask_for_rule(message: Message, state: FSMContext, intro: str) -> None:
    await state.set_state(TaobaoPricing.waiting_rule)
    await message.answer(f"{intro}\n\n{RULE_PROMPT}\n\n/cancel — bekor qilish")


@router.callback_query(F.data == "admin_taobao_pricing")
async def handle_pricing_menu(callback: CallbackQuery, state: FSMContext):
    rule = await load_rule()
    await ask_for_rule(callback.message, state, f"💱 <b>Taobao narx formulasi</b>\n\n{rule_summary(rule)}")
    await callback.answer()


@router.message(Command("taobao"), admin_event)
async def handle_pricing_command(message: Message, state: FSMContext):
    rule = await load_rule()
    await ask_for_rule(message, state, f"💱 <b>Taobao narx formulasi</b>\n\n{rule_summary(rule)}")


@router.message(TaobaoPricing.waiting_rule, TEXT_ANSWER)
async def handle_rule_input(message: Message, state: FSMContext):
    rule = parse_rule_input(message.text)
    if rule is None:
        await message.answer(f"⚠️ Tushunmadim.\n\n{RULE_PROMPT}")
        return
    await save_rule(rule)
    data = await state.get_data()
    pending: Optional[str] = data.get("pending_link")
    await state.clear()
    await message.answer(f"✅ <b>Saqlandi!</b>\n\n{rule_summary(rule)}")
    if pending:
        link = find_taobao_link(pending)
        if link:
            await start_import(message, state, link)


# ==================== LINK → PREVIEW ====================
@router.message(StateFilter(None), ~F.forward_origin, admin_event, has_taobao_link)
async def handle_taobao_link(message: Message, state: FSMContext, link: TaobaoLink):
    rule = await load_rule()
    if not rule.is_configured:
        await state.update_data(pending_link=link.url)
        await ask_for_rule(message, state, "💱 Avval narx formulasini bir marta sozlaymiz, keyin mahsulotni tayyorlayman.")
        return
    await start_import(message, state, link)


async def start_import(message: Message, state: FSMContext, link: TaobaoLink) -> None:
    status = await message.answer("⏳ Taobao'dan ma'lumot olinmoqda... (odatda 20–60 soniya)")
    try:
        item_id = link.item_id or await resolve_short_link(link.url)
        existing = await find_existing(item_id)
        if existing:
            await status.edit_text(
                f"♻️ Bu mahsulot allaqachon do'konda bor: <b>#{existing.id}</b> {escape(existing.title)}",
                reply_markup=manage_markup(existing.id),
            )
            return
        item = await fetch_item(item_id)
    except TaobaoFetchError as e:
        await status.edit_text(str(e))
        return

    photos = await upload_photos(message.bot, message.chat.id, item)
    if not photos:
        await status.edit_text("😔 Mahsulot rasmlarini yuklab bo'lmadi. Boshqa havola yuboring yoki qo'lda qo'shing.")
        return

    rule = await load_rule()
    await state.set_state(TaobaoImport.title)
    await state.update_data(
        item_id=item.item_id, title_cn=item.title, price_yuan=item.price_yuan,
        price=calculate_price(item.price_yuan, rule), cost_som=calculate_cost(item.price_yuan, rule),
        photos=photos, colors=[], sizes=[],
    )
    await status.edit_text(
        f"✅ <b>Taobao'dan olindi</b> ({len(photos)} ta rasm)\n\n"
        f"🇨🇳 {escape(item.title or '—')}\n"
        f"💴 {item.price_yuan:g} ¥ → <b>{format_price(calculate_price(item.price_yuan, rule))}</b>\n\n"
        "🎀 <b>1/4:</b> Mahsulot nomini o'zbekcha yozing:",
        reply_markup=skip_markup("Xitoycha nomni qoldirish ⏭️"),
    )


async def find_existing(item_id: str) -> Optional[Product]:
    async with async_session_factory() as session:
        res = await session.execute(select(Product).where(Product.taobao_item_id == item_id))
        return res.scalars().first()


async def upload_photos(bot: Bot, chat_id: int, item: TaobaoItem) -> List[str]:
    """
    Sends the photos to the admin as an album; the file_ids Telegram returns are what the shop stores,
    so photos keep working even if Taobao later removes them.
    """
    blobs = await asyncio.gather(*(download_image(u) for u in item.images))
    media = [
        InputMediaPhoto(media=BufferedInputFile(blob, filename=f"tb_{item.item_id}_{i}.jpg"))
        for i, blob in enumerate(blobs) if blob
    ]
    if not media:
        return []
    try:
        sent = await bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        logger.warning(f"Could not send Taobao photos for item {item.item_id}: {e}")
        return []
    return [m.photo[-1].file_id for m in sent if m.photo]


def skip_markup(text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data="tb_skip")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tb_cancel")],
        ]
    )


def manage_markup(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⚙️ Boshqarish", callback_data=f"admin_prod_manage_{product_id}")]]
    )


def split_list(text: str) -> List[str]:
    return [p.strip() for p in text.replace(";", ",").split(",") if p.strip()][:30]


# ==================== STEPS ====================
@router.message(TaobaoImport.title, TEXT_ANSWER)
async def step_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip()[:255])
    await ask_category(message, state)


async def ask_category(message: Message, state: FSMContext) -> None:
    async with async_session_factory() as session:
        cats = (await session.execute(select(Category).order_by(Category.sort_order))).scalars().all()
    rows, row = [], []
    for c in cats:
        row.append(InlineKeyboardButton(text=f"{c.emoji} {c.name}"[:40], callback_data=f"tb_cat:{c.slug}"[:64]))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tb_cancel")])
    await state.set_state(TaobaoImport.category)
    await message.answer("🏷️ <b>2/4:</b> Kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(TaobaoImport.category, F.data.startswith("tb_cat:"))
async def step_category(callback: CallbackQuery, state: FSMContext):
    await state.update_data(category=callback.data.split(":", 1)[1])
    await state.set_state(TaobaoImport.colors)
    await callback.message.answer(
        "🎨 <b>3/4:</b> Ranglarni vergul bilan yozing (masalan: <i>qora, jigarrang</i>):",
        reply_markup=skip_markup("O'tkazib yuborish ⏭️"),
    )
    await callback.answer()


@router.message(TaobaoImport.colors, TEXT_ANSWER)
async def step_colors(message: Message, state: FSMContext):
    await state.update_data(colors=split_list(message.text))
    await ask_sizes(message, state)


async def ask_sizes(message: Message, state: FSMContext) -> None:
    await state.set_state(TaobaoImport.sizes)
    await message.answer(
        "📏 <b>4/4:</b> O'lchamlarni vergul bilan yozing (masalan: <i>36, 37, 38</i> yoki <i>S, M, L</i>):",
        reply_markup=skip_markup("O'tkazib yuborish ⏭️"),
    )


@router.message(TaobaoImport.sizes, TEXT_ANSWER)
async def step_sizes(message: Message, state: FSMContext):
    await state.update_data(sizes=split_list(message.text))
    await show_confirm(message, state)


@router.callback_query(F.data == "tb_skip")
async def step_skip(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    await callback.answer()
    if current == TaobaoImport.title.state:
        data = await state.get_data()
        await state.update_data(title=(data.get("title_cn") or "Taobao mahsulot")[:255])
        await ask_category(callback.message, state)
    elif current == TaobaoImport.colors.state:
        await state.update_data(colors=[])
        await ask_sizes(callback.message, state)
    elif current == TaobaoImport.sizes.state:
        await state.update_data(sizes=[])
        await show_confirm(callback.message, state)


async def show_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(TaobaoImport.confirm)
    text = (
        "🌸 <b>MAHSULOT TAYYOR — tekshiring:</b>\n\n"
        f"🎀 <b>Nomi:</b> {escape(data.get('title', ''))}\n"
        f"🏷️ <b>Kategoriya:</b> #{escape(data.get('category', ''))}\n"
        f"💰 <b>Narxi:</b> {format_price(data.get('price', 0))} ({data.get('price_yuan', 0):g} ¥)\n"
        f"🎨 <b>Ranglar:</b> {escape(', '.join(data.get('colors') or []) or '—')}\n"
        f"📏 <b>O'lchamlar:</b> {escape(', '.join(data.get('sizes') or []) or '—')}\n"
        f"📸 <b>Rasmlar:</b> {len(data.get('photos') or [])} ta"
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Saqlash", callback_data="tb_save"),
                InlineKeyboardButton(text="📢 Saqlash + kanal", callback_data="tb_save_post"),
            ],
            [InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data="tb_price")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tb_cancel")],
        ]
    )
    await message.answer(text, reply_markup=markup)


@router.callback_query(TaobaoImport.confirm, F.data == "tb_price")
async def step_price_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TaobaoImport.price)
    await callback.message.answer("💰 Yangi narxni so'mda yozing (masalan: <code>145000</code> yoki <code>145.000</code>):")
    await callback.answer()


@router.message(TaobaoImport.price, TEXT_ANSWER)
async def step_price(message: Message, state: FSMContext):
    raw = message.text.replace(".", "").replace(",", "").replace(" ", "").replace("so'm", "").strip()
    if not raw.isdigit() or not 1000 <= int(raw) <= 100_000_000:
        await message.answer("⚠️ Narxni raqam bilan yozing (masalan: 145000):")
        return
    await state.update_data(price=int(raw))
    await show_confirm(message, state)


@router.callback_query(F.data == "tb_cancel")
async def step_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Taobao import bekor qilindi.")
    await callback.answer()


@router.callback_query(TaobaoImport.confirm, F.data.in_({"tb_save", "tb_save_post"}))
async def step_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("photos") or not data.get("price") or not data.get("category"):
        await state.clear()
        await callback.answer("Ma'lumot topilmadi, havolani qayta yuboring.", show_alert=True)
        return
    await state.clear()  # first, so a double tap can't save twice
    product = await save_product(data)
    await callback.answer("Saqlandi!")
    note = ""
    if callback.data == "tb_save_post":
        posted = await post_product_to_channel(product)
        note = "\n📢 Kanalga ham joylandi." if posted.get("success") else f"\n⚠️ Kanalga joylanmadi: {escape(str(posted.get('error')))}"
    await callback.message.answer(
        f"✅ <b>Mahsulot do'konga qo'shildi! (#{product.id})</b> 🌸{note}",
        reply_markup=manage_markup(product.id),
    )


async def save_product(data: Dict[str, Any]) -> Product:
    async with async_session_factory() as session:
        product = Product(
            title=data.get("title") or data.get("title_cn") or "Taobao mahsulot",
            description="",
            price=int(data["price"]),
            category=data["category"],
            photos=list(data["photos"]),
            sizes=list(data.get("sizes") or []),
            colors=list(data.get("colors") or []),
            in_stock=True,
            is_new=True,
            taobao_item_id=data.get("item_id"),
            cost_som=data.get("cost_som"),
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product
