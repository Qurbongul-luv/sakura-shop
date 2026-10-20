from html import escape
import os
import re
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile,
    WebAppInfo,
)
from sqlalchemy import select, func, desc, delete

from api.config import settings
from api.services.formatters import format_price, calculate_cargo, parse_channel_post, build_channel_caption
from bot.keyboards.reply import get_admin_main_keyboard, get_main_reply_keyboard
from bot.services.channel_post import post_product_to_channel
from db.models import Admin, Product, Category, Review, Order, User, Setting
from db.session import async_session_factory

router = Router(name="admin")
logger = logging.getLogger(__name__)


# FSM States for Add Product Wizard
class ProductWizard(StatesGroup):
    photos = State()
    title = State()
    price = State()
    category = State()
    sizes = State()
    colors = State()
    weight = State()
    description = State()
    confirm = State()


# FSM States for Add Admin & Broadcast
class AdminSettingsState(StatesGroup):
    waiting_for_admin_forward = State()
    waiting_for_broadcast_text = State()


async def is_user_admin(user_id: int) -> bool:
    if settings.DEV_ADMIN_ID and user_id == settings.DEV_ADMIN_ID:
        return True
    async with async_session_factory() as session:
        res = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
        return res.scalars().first() is not None


async def admin_only(event: CallbackQuery) -> bool:
    return event.from_user is not None and await is_user_admin(event.from_user.id)


# All buttons in this router are admin-only (messages are checked in /admin and the forward handler;
# wizard states are only reachable from admin buttons).
router.callback_query.filter(admin_only)


@router.message(Command("admin"))
async def handle_admin_command(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if not await is_user_admin(user_id):
        await message.answer("⛔ Kechirasiz, sizda admin huquqi yo'q.")
        return

    welcome_text = (
        "👑 <b>Sakura shop — Admin Paneli</b> 🌸\n\n"
        "Quyidagi bo'limlardan birini tanlang yoki kanaldagi istalgan postni bu yerga <b>forward</b> qiling (sehrli tezkor import ✨):"
    )
    await message.answer(welcome_text, reply_markup=get_admin_main_keyboard())


# Cancel command
@router.message(Command("cancel"))
@router.message(F.text.lower() == "/cancel")
@router.message(F.text == "❌ Bekor qilish")
async def handle_cancel_wizard(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Jarayon bekor qilindi.", reply_markup=get_main_reply_keyboard())
    await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())


# ==================== MAGIC SHORTCUT: FORWARDED CHANNEL POST ====================
@router.message(F.forward_from_chat | F.forward_date)
async def handle_forwarded_post(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_user_admin(user_id):
        return

    text = message.caption or message.text or ""

    # Check if this is a review screenshot or product
    if message.photo and ("#отзыв" in text.lower() or "fikr" in text.lower() or "rahmat" in text.lower()):
        # Treat as review
        photo_id = message.photo[-1].file_id
        async with async_session_factory() as session:
            rev = Review(
                customer_name=message.forward_sender_name or "Mijoz 💌",
                text=text.replace("#отзыв", "").strip() or "Mijoz fikri 🌸",
                photos=[photo_id],
                approved=True,
            )
            session.add(rev)
            await session.commit()
        await message.answer("⭐ <b>Mijoz fikri (#отзыв) avtomatik saqlandi va tasdiqlandi!</b> 🌸")
        return

    # Parse product channel post
    parsed = parse_channel_post(text)
    photos = []
    if message.photo:
        photos.append(message.photo[-1].file_id)

    await state.update_data(
        photos=photos,
        title=parsed["title"] or f"{parsed['category'].capitalize()} 🌸",
        price=parsed["price"] or 0,
        category=parsed["category"],
        sizes=[],
        colors=[],
        weight_grams=None,
        description=text,
    )

    summary = (
        "✨ <b>Sehrli import: Kanaldagi post ma'lumotlari aniqlandi!</b> 🌸\n\n"
        f"🏷️ <b>Kategoriya:</b> #{parsed['category']}\n"
        f"🌸 <b>Nomi:</b> {parsed['title'] or parsed['category']}\n"
        f"💰 <b>Narxi:</b> {format_price(parsed['price'])}\n"
        f"📸 <b>Rasmlar:</b> {len(photos)} ta\n\n"
        "Ushbu mahsulotni saqlaymizmi yoki ma'lumotlarni to'ldirasizmi?"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ To'g'ri, saqlash", callback_data="wizard_save_fast"),
                InlineKeyboardButton(text="✏️ O'zgartirish", callback_data="admin_add_product"),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor", callback_data="admin_cancel"),
            ]
        ]
    )
    await message.answer(summary, reply_markup=markup)


# ==================== ADD PRODUCT WIZARD (FSM) ====================
@router.callback_query(F.data == "admin_add_product")
async def start_add_product_wizard(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ProductWizard.photos)
    await state.update_data(photos=[])

    msg = (
        "🌸 <b>Yangi mahsulot qo'shish — 1/8 qadam</b>\n\n"
        "Mahsulot rasmini (yoki 1 tadan 10 tagacha rasmlarni) yuboring 📸\n\n"
        "<i>Rasmlarni yuborib bo'lgach, 'Keyingisi ➡️' tugmasini bosing yoki /cancel bosing.</i>"
    )

    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Keyingisi ➡️")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await callback.message.answer(msg, reply_markup=markup)
    await callback.answer()


@router.message(ProductWizard.photos, F.photo)
async def process_wizard_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    await message.answer(f"📸 Rasm qo'shildi! Jami rasmlar: {len(photos)} ta.\n\nYana rasm yuborishingiz yoki 'Keyingisi ➡️' tugmasini bosishingiz mumkin.")


@router.message(ProductWizard.photos, F.text == "Keyingisi ➡️")
async def process_photos_done(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await message.answer("⚠️ Kamida 1 ta rasm yuborishingiz kerak!")
        return

    await state.set_state(ProductWizard.title)
    await message.answer(
        "🌸 <b>2/8 qadam:</b> Mahsulot nomini kiriting:\n(Masalan: <i>Aesthetic Vintage Pushti Jempir 🌸</i>)",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Orqaga")], [KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.title, F.text)
async def process_wizard_title(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.set_state(ProductWizard.photos)
        await message.answer("Rasmlarni yuboring:")
        return

    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(ProductWizard.price)
    await message.answer(
        f"💰 <b>3/8 qadam:</b> Narxini so'mda kiriting:\n(Masalan: <code>99000</code> yoki <code>99.000</code>)",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Orqaga")], [KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.price, F.text)
async def process_wizard_price(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.set_state(ProductWizard.title)
        await message.answer("Nomini kiriting:")
        return

    raw = message.text.replace(".", "").replace(" ", "").replace("so'm", "").replace("som", "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("⚠️ Iltimos, to'g'ri son kiriting (masalan: 99000):")
        return

    price = int(raw)
    await state.update_data(price=price)

    # Categories
    async with async_session_factory() as session:
        res = await session.execute(select(Category).order_by(Category.sort_order))
        categories = res.scalars().all()

    buttons = []
    row = []
    for c in categories:
        row.append(InlineKeyboardButton(text=f"#{c.slug} {c.emoji}", callback_data=f"cat_pick_{c.slug}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    await state.set_state(ProductWizard.category)
    await message.answer(
        f"🏷️ <b>4/8 qadam:</b> Kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(ProductWizard.category, F.data.startswith("cat_pick_"))
async def process_wizard_category(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.replace("cat_pick_", "")
    await state.update_data(category=slug)

    await state.set_state(ProductWizard.sizes)
    await callback.message.answer(
        "📏 <b>5/8 qadam:</b> O'lchamlarni kiriting (vergul bilan ajratib, masalan: <i>S, M, L</i>) yoki o'tkazib yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="O'tkazib yuborish ⏭️")],
                [KeyboardButton(text="⬅️ Orqaga"), KeyboardButton(text="❌ Bekor qilish")],
            ],
            resize_keyboard=True,
        ),
    )
    await callback.answer()


@router.message(ProductWizard.sizes, F.text)
async def process_wizard_sizes(message: Message, state: FSMContext):
    sizes = []
    if message.text != "O'tkazib yuborish ⏭️" and message.text != "⬅️ Orqaga":
        sizes = [s.strip() for s in message.text.split(",") if s.strip()]

    await state.update_data(sizes=sizes)
    await state.set_state(ProductWizard.colors)
    await message.answer(
        "🎨 <b>6/8 qadam:</b> Ranglarni kiriting (vergul bilan ajratib, masalan: <i>Pushti 🌸, Oq 🤍</i>) yoki o'tkazib yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="O'tkazib yuborish ⏭️")],
                [KeyboardButton(text="⬅️ Orqaga"), KeyboardButton(text="❌ Bekor qilish")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.colors, F.text)
async def process_wizard_colors(message: Message, state: FSMContext):
    colors = []
    if message.text != "O'tkazib yuborish ⏭️" and message.text != "⬅️ Orqaga":
        colors = [c.strip() for c in message.text.split(",") if c.strip()]

    await state.update_data(colors=colors)
    await state.set_state(ProductWizard.weight)
    await message.answer(
        "⚖️ <b>7/8 qadam:</b> Mahsulot og'irligini grammda kiriting (kargoni hisoblash uchun, masalan: <i>350</i>) yoki o'tkazib yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="O'tkazib yuborish ⏭️")],
                [KeyboardButton(text="⬅️ Orqaga"), KeyboardButton(text="❌ Bekor qilish")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.weight, F.text)
async def process_wizard_weight(message: Message, state: FSMContext):
    weight_grams = None
    if message.text != "O'tkazib yuborish ⏭️" and message.text != "⬅️ Orqaga":
        raw = re.sub(r"\D", "", message.text)
        if raw:
            weight_grams = int(raw)

    await state.update_data(weight_grams=weight_grams)
    await state.set_state(ProductWizard.description)
    await message.answer(
        "📝 <b>8/8 qadam:</b> Tavsif/qo'shimcha ma'lumot kiriting yoki o'tkazib yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="O'tkazib yuborish ⏭️")],
                [KeyboardButton(text="⬅️ Orqaga"), KeyboardButton(text="❌ Bekor qilish")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.description, F.text)
async def process_wizard_description(message: Message, state: FSMContext):
    desc_val = ""
    if message.text != "O'tkazib yuborish ⏭️" and message.text != "⬅️ Orqaga":
        desc_val = message.text.strip()

    await state.update_data(description=desc_val)
    data = await state.get_data()

    # Build Preview
    cargo = calculate_cargo(data.get("weight_grams"))
    sizes_str = ", ".join(data.get("sizes", [])) or "Ko'rsatilmagan"
    colors_str = ", ".join(data.get("colors", [])) or "Ko'rsatilmagan"

    preview = (
        "🌸 <b>MAHSULOT PREVIEW (Ko'rinishi):</b>\n\n"
        f"🏷️ <b>Kategoriya:</b> #{data['category']}\n"
        f"🎀 <b>Nomi:</b> {escape(data['title'])}\n"
        f"💰 <b>Narxi:</b> {format_price(data['price'])}\n"
        f"📦 <b>Kargo:</b> ~{format_price(cargo)}\n"
        f"📏 <b>O'lchamlar:</b> {escape(sizes_str)}\n"
        f"🎨 <b>Ranglar:</b> {escape(colors_str)}\n"
        f"📝 <b>Tavsif:</b> {escape(data['description'] or 'Mavjud emas')}\n"
        f"📸 <b>Rasmlar:</b> {len(data['photos'])} ta"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Saqlash", callback_data="wizard_save"),
                InlineKeyboardButton(text="✏️ Qayta kiritish", callback_data="admin_add_product"),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel"),
            ]
        ]
    )

    await state.set_state(ProductWizard.confirm)
    await message.answer(preview, reply_markup=markup)


@router.callback_query(F.data.in_(["wizard_save", "wizard_save_fast"]))
async def handle_save_product(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data or not data.get("title") or not data.get("price"):
        await callback.answer("Ma'lumotlar topilmadi, qaytadan urinib ko'ring.", show_alert=True)
        return

    async with async_session_factory() as session:
        prod = Product(
            title=data["title"],
            description=data.get("description", ""),
            price=data["price"],
            category=data.get("category", "jempir"),
            photos=data.get("photos", []),
            sizes=data.get("sizes", []),
            colors=data.get("colors", []),
            weight_grams=data.get("weight_grams"),
            in_stock=True,
            is_new=True,
        )
        session.add(prod)
        await session.commit()
        await session.refresh(prod)
        prod_id = prod.id

    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Mahsulot muvaffaqiyatli saqlandi! (#{prod_id})</b> 🌸\n\n"
        f"📢 <b>Ushbu mahsulotni hoziroq Telegram kanalga ham joylaysizmi?</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📢 Ha, kanalga joylash",
                        callback_data=f"post_channel_now_{prod_id}",
                    ),
                    InlineKeyboardButton(
                        text="Yo'q, faqat do'konda",
                        callback_data="admin_done",
                    )
                ]
            ]
        )
    )
    await callback.answer("Saqlandi!")


@router.callback_query(F.data.startswith("post_channel_now_"))
async def handle_post_channel_now(callback: CallbackQuery):
    prod_id = int(callback.data.replace("post_channel_now_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Product).where(Product.id == prod_id))
        prod = res.scalars().first()
        if not prod:
            await callback.answer("Mahsulot topilmadi", show_alert=True)
            return

        result = await post_product_to_channel(prod)

    if result.get("success"):
        await callback.message.edit_text(
            f"✅ <b>Mahsulot kanalga muvaffaqiyatli joylandi!</b> 🌸\n"
            f"Do'konda ko'rish havolasi bilan birga post qilindi."
        )
    else:
        await callback.message.edit_text(
            f"⚠️ <b>Kanalga joylashda xatolik:</b>\n{result.get('error')}\n\n"
            f"Bot kanalingizda administrator ekanligini va ruxsatlari borligini tekshiring."
        )
    await callback.answer()


# ==================== PRODUCT LIST & MANAGEMENT ====================
@router.callback_query(F.data == "admin_list_products")
async def handle_list_products(callback: CallbackQuery):
    async with async_session_factory() as session:
        res = await session.execute(select(Product).order_by(desc(Product.created_at)).limit(10))
        products = res.scalars().all()

    if not products:
        await callback.message.edit_text(
            "🌸 Hozircha birorta ham mahsulot yo'q.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="➕ Qo'shish", callback_data="admin_add_product")]]
            )
        )
        await callback.answer()
        return

    buttons = []
    for p in products:
        stock_emoji = "✅" if p.in_stock else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{stock_emoji} {p.title[:25]} ({format_price(p.price)})",
                callback_data=f"admin_prod_manage_{p.id}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")])

    await callback.message.edit_text(
        "📦 <b>Mahsulotlar ro'yxati:</b>\nBoshqarish yoki o'zgartirish uchun mahsulotni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_prod_manage_"))
async def handle_manage_single_product(callback: CallbackQuery):
    prod_id = int(callback.data.replace("admin_prod_manage_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Product).where(Product.id == prod_id))
        p = res.scalars().first()

    if not p:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    stock_text = "Mavjud (In stock) ✅" if p.in_stock else "Sotildi ❌"
    hit_str = "Ha" if p.is_hit else "Yo'q"
    new_str = "Ha" if p.is_new else "Yo'q"
    text = (
        f"🌸 <b>{escape(str(p.title))}</b>\n"
        f"🏷️ Kategoriya: #{p.category}\n"
        f"💰 Narxi: {format_price(p.price)}\n"
        f"📊 Holati: <b>{stock_text}</b>\n"
        f"👁️ Ko'rishlar: {p.views}\n"
        f"🔥 Hit: {hit_str} | 🆕 Yangi: {new_str}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Holatni almashtirish 🔄 (Sotildi/Mavjud)",
                    callback_data=f"admin_toggle_stock_{p.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Kanalga joylash",
                    callback_data=f"post_channel_now_{p.id}"
                ),
                InlineKeyboardButton(
                    text="🔥 Hit / 🆕 Yangi",
                    callback_data=f"admin_toggle_badges_{p.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ O'chirish",
                    callback_data=f"admin_confirm_delete_prod_{p.id}"
                ),
                InlineKeyboardButton(text="⬅️ Ro'yxatga", callback_data="admin_list_products"),
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_toggle_stock_"))
async def handle_toggle_stock(callback: CallbackQuery):
    prod_id = int(callback.data.replace("admin_toggle_stock_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Product).where(Product.id == prod_id))
        p = res.scalars().first()
        if p:
            p.in_stock = not p.in_stock
            await session.commit()
    await handle_manage_single_product(callback)


@router.callback_query(F.data.startswith("admin_confirm_delete_prod_"))
async def handle_confirm_delete_prod(callback: CallbackQuery):
    prod_id = int(callback.data.replace("admin_confirm_delete_prod_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Product).where(Product.id == prod_id))
        p = res.scalars().first()
        if p:
            await session.delete(p)
            await session.commit()

    await callback.answer("🗑️ Mahsulot o'chirildi", show_alert=True)
    await handle_list_products(callback)


# ==================== STATS ====================
@router.callback_query(F.data == "admin_stats")
async def handle_admin_stats(callback: CallbackQuery):
    async with async_session_factory() as session:
        total_users = (await session.execute(select(func.count(User.telegram_id)))).scalar() or 0
        total_orders = (await session.execute(select(func.count(Order.id)))).scalar() or 0
        new_orders = (await session.execute(select(func.count(Order.id)).where(Order.status == "new"))).scalar() or 0
        total_prods = (await session.execute(select(func.count(Product.id)))).scalar() or 0
        in_stock_prods = (await session.execute(select(func.count(Product.id)).where(Product.in_stock == True))).scalar() or 0

    text = (
        "📊 <b>Sakura shop — Statistika:</b> 🌸\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {total_users} ta\n"
        f"🧾 <b>Jami buyurtmalar:</b> {total_orders} ta\n"
        f"⏳ <b>Yangi (kutilayotgan) buyurtmalar:</b> {new_orders} ta\n"
        f"📦 <b>Jami mahsulotlar:</b> {total_prods} ta\n"
        f"✅ <b>Sotuvda mavjud:</b> {in_stock_prods} ta\n\n"
        "Batafsil grafiklar va monitoring Mini App 👑 Admin bo'limida mavjud!"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👑 Mini App'da to'liq statistika", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?tab=admin"))],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


# ==================== SETTINGS & ADMIN MANAGEMENT ====================
@router.callback_query(F.data == "admin_settings")
async def handle_admin_settings_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with async_session_factory() as session:
        res = await session.execute(select(Admin))
        admins = res.scalars().all()
        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        ch = res_ch.scalars().first()
        channel_status = f"Uланган ({ch.value}) ✅" if (ch and ch.value) else "Ulanmagan ❌"

    admin_lines = []
    for a in admins:
        role_badge = "👑 Egasi (Owner)" if a.role == "owner" else "Admin"
        admin_lines.append(f"• {escape(str(a.name))} (<code>{a.telegram_id}</code>) — {role_badge}")

    text = (
        "⚙️ <b>Do'kon sozlamalari:</b> 🌸\n\n"
        f"📢 <b>Kanal:</b> {channel_status}\n\n"
        f"👥 <b>Adminlar ro'yxati:</b>\n" + "\n".join(admin_lines) + "\n\n"
        "Yangi admin qo'shish yoki sozlamalarni o'zgartirish:"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="admin_add_new_admin"),
                InlineKeyboardButton(text="📢 Kanalni uzish", callback_data="admin_unlink_channel"),
            ],
            [
                InlineKeyboardButton(text="⚠️ Barcha ma'lumotlarni tozalash", callback_data="admin_reset_confirm"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "admin_add_new_admin")
async def handle_start_add_admin(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSettingsState.waiting_for_admin_forward)
    await callback.message.answer(
        "👤 <b>Yangi admin qo'shish:</b>\n\n"
        "Iltimos, o'sha odamning istalgan xabarini bu yerga <b>forward</b> qiling, yoki uning kontaktini yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True,
        )
    )
    await callback.answer()


@router.message(AdminSettingsState.waiting_for_admin_forward)
async def process_new_admin_forward(message: Message, state: FSMContext):
    new_admin_id = None
    new_admin_name = ""

    if message.forward_from:
        new_admin_id = message.forward_from.id
        new_admin_name = message.forward_from.full_name
    elif message.contact:
        new_admin_id = message.contact.user_id
        new_admin_name = message.contact.first_name
    elif message.text and message.text.isdigit():
        new_admin_id = int(message.text)
        new_admin_name = "Admin"

    if not new_admin_id:
        await message.answer("⚠️ Foydalanuvchini aniqlab bo'lmadi. Iltimos, xabarni forward qiling yoki uning Telegram ID raqamini yozing:")
        return

    async with async_session_factory() as session:
        existing = await session.execute(select(Admin).where(Admin.telegram_id == new_admin_id))
        if existing.scalars().first():
            await message.answer("Ushbu foydalanuvchi allaqachon admin!")
        else:
            session.add(Admin(telegram_id=new_admin_id, name=new_admin_name, role="admin"))
            await session.commit()
            await message.answer(f"✅ <b>{new_admin_name}</b> (ID: <code>{new_admin_id}</code>) muvaffaqiyatli admin etib tayinlandi! 🌸")

    await state.clear()
    await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())


@router.callback_query(F.data == "admin_menu")
async def handle_return_admin_menu(callback: CallbackQuery):
    await callback.message.edit_text("👑 <b>Sakura shop — Admin Paneli</b> 🌸", reply_markup=get_admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_cancel")
async def handle_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Jarayon bekor qilindi.", reply_markup=get_admin_main_keyboard())
    await callback.answer()
