from html import escape
import logging
from datetime import datetime, timezone
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select

from api.config import settings
from api.services.formatters import format_price, calculate_cargo
from bot.keyboards.reply import get_main_reply_keyboard
from db.models import User, Admin, Setting, Product, Review
from db.session import async_session_factory

router = Router(name="start")
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    full_name = message.from_user.full_name or "Mijoz"
    username = message.from_user.username
    payload = command.args or ""

    # 1. Update or create user in DB, tracking whether they existed before
    is_new_user = False
    async with async_session_factory() as session:
        u_res = await session.execute(select(User).where(User.telegram_id == user_id))
        user_obj = u_res.scalars().first()
        now = datetime.now(timezone.utc)

        if not user_obj:
            is_new_user = True
            user_obj = User(
                telegram_id=user_id,
                name=full_name,
                username=username,
                language="uz",
                first_seen=now,
                last_seen=now,
                blocked_bot=False,
            )
            session.add(user_obj)
        else:
            user_obj.name = full_name
            user_obj.username = username
            user_obj.last_seen = now
            user_obj.blocked_bot = False

        await session.commit()

    # Check for CONTEST direct link: /start konkurs
    if payload == "konkurs":
        from bot.handlers.contest import show_user_contest_dashboard
        await show_user_contest_dashboard(message, user_id)
        return

    # Check for CONTEST REFERRAL deep link: /start r_<contest_id>_<referrer_id>
    if payload.startswith("r_"):
        from bot.services.contest_service import process_referral_start, get_channel_info
        async with async_session_factory() as session:
            ref_result = await process_referral_start(
                session=session,
                bot=message.bot,
                user_id=user_id,
                user_full_name=full_name,
                user_username=username,
                is_bot=message.from_user.is_bot or False,
                payload=payload,
                is_new_user=is_new_user,
            )

            if not ref_result.get("valid"):
                reason = ref_result.get("reason")
                if reason == "no_active_contest":
                    await message.answer(
                        "🌸 <b>Hozircha faol konkurs yo'q</b> 🎀\nLekin do'konimizdan bahramand bo'lishingiz mumkin!",
                        reply_markup=get_main_reply_keyboard(),
                    )
                elif reason == "existing_user":
                    await message.answer(
                        ref_result.get("message"),
                        reply_markup=get_main_reply_keyboard(),
                    )
                # Malformed, self, or invalid payloads are safely ignored and continue to regular greeting
            else:
                contest = ref_result["contest"]
                channel_url = ref_result.get("channel_url", "https://t.me/sakuraaa_chinese_shop")
                was_member_before = ref_result.get("was_member_before", False)

                if was_member_before and contest.only_new_subscribers:
                    bot_me = await message.bot.get_me()
                    personal_link = f"https://t.me/{bot_me.username}?start=r_{contest.id}_{user_id}"
                    markup = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🎁 Konkursda qatnashish", callback_data=f"my_stats:{contest.id}")],
                            [InlineKeyboardButton(text="🌸 Do'konni ochish", web_app=WebAppInfo(url=settings.WEBAPP_URL))],
                        ]
                    )
                    await message.answer(
                        "🌸 <b>Siz allaqachon kanalimiz a'zosisiz!</b> 🎀\n\n"
                        "Do'stingizga taklif balli hisoblanmadi, lekin siz ham konkursda qatnashib, qimmatbaho sovg'alarni yutib olishingiz mumkin! 🎁\n\n"
                        f"🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n<code>{personal_link}</code>",
                        reply_markup=markup,
                    )
                    return

                # Normal new invitee flow: show subscription prompt
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📢 Kanalga o'tish", url=channel_url)],
                        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_sub:{contest.id}:{user_id}")],
                    ]
                )
                await message.answer(
                    "🌸 <b>Konkursda qatnashish uchun kanalga obuna bo'ling</b> 🎀\n\n"
                    "Kanalimizga a'zo bo'ling va quyidagi <b>✅ Tasdiqlash</b> tugmasini bosing:",
                    reply_markup=markup,
                )
                return

    # 2. Check for OWNER CLAIM deep link: /start claim_<CODE>
    if payload.startswith("claim_"):
        claim_code = payload[6:].strip()
        async with async_session_factory() as session:
            # Check if owner already claimed
            res_claimed = await session.execute(select(Setting).where(Setting.key == "owner_claimed_at"))
            claimed_setting = res_claimed.scalars().first()
            already_claimed = bool(claimed_setting and claimed_setting.value.strip())

            # Check if this user is already an owner
            res_me = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
            me = res_me.scalars().first()
            if me and me.role == "owner":
                await message.answer(
                    "🌸 <b>Siz allaqachon do'kon egasisiz!</b>\n"
                    "Boshqaruv menyusini ochish uchun /admin buyrug'ini bosing.",
                    reply_markup=get_main_reply_keyboard(),
                )
                return

            # Verify claim code
            if claim_code != settings.OWNER_SETUP_CODE:
                await message.answer(
                    "❌ <b>Noto'g'ri claim kodi!</b> Do'konni biriktirib bo'lmadi.",
                    reply_markup=get_main_reply_keyboard(),
                )
                return

            # Claim ownership (supports multiple co-owners with the code)
            if me:
                me.role = "owner"
            else:
                new_owner = Admin(
                    telegram_id=user_id,
                    name=full_name,
                    username=username,
                    role="owner",
                )
                session.add(new_owner)

            if claimed_setting:
                claimed_setting.value = datetime.now(timezone.utc).isoformat()
            else:
                session.add(Setting(key="owner_claimed_at", value=datetime.now(timezone.utc).isoformat()))

            await session.commit()

            owner_welcome = (
                "🌸 <b>Bu do'kon endi sizniki / This shop is now yours</b> 🎀\n\n"
                "Tabriklaymiz! Siz <b>Sakura shop</b>ning rasmiy egasi etib tayinlandingiz.\n\n"
                "✨ <b>Qisqa qo'llanma (3 ta qadam):</b>\n"
                "1️⃣ <b>Yangi mahsulot:</b> /admin buyrug'ini bosing yoki Mini App ichidagi 👑 Admin tugmasidan foydalaning.\n"
                "2️⃣ <b>Kanalni ulash:</b> Botni o'z kanalingizga (@sakuraaa_chinese_shop) admin qilib qo'shing — bot avtomatik aniqlaydi va tasdiqlashingiz bilan ulaydi.\n"
                "3️⃣ <b>Buyurtmalar:</b> Mijozlar do'kondan buyurtma berishi bilan bu yerga chiroyli xabar bo'lib keladi.\n\n"
                "Boshqaruv menyusini ochish uchun <b>/admin</b> buyrug'ini bosing! 💗"
            )
            await message.answer(owner_welcome, reply_markup=get_main_reply_keyboard())
            return

    # 3. Check for PRODUCT deep link: /start product_<ID>
    if payload.startswith("product_"):
        try:
            prod_id = int(payload[8:])
            async with async_session_factory() as session:
                res_p = await session.execute(select(Product).where(Product.id == prod_id))
                product = res_p.scalars().first()
                if product:
                    product.views += 1
                    await session.commit()

                    cargo = calculate_cargo(product.weight_grams)
                    desc_text = f"\n\n{product.description}" if product.description else ""
                    stock_badge = "" if product.in_stock else "\n\n❌ <b>Sotildi (Hozirda mavjud emas)</b>"

                    text = (
                        f"🌸 <b>{escape(str(product.title))}</b>\n"
                        f"💰 <b>Narxi:</b> {format_price(product.price)}\n"
                        f"📦 <b>Kargo:</b> ~{format_price(cargo)}"
                        f"{desc_text}"
                        f"{stock_badge}\n\n"
                        f"💌 Buyurtma berish uchun @fkhrdnvvvva ga yozing"
                    )

                    markup = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="🌸 Do'konda ochish",
                                    web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?product={product.id}"),
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    text="💌 Admin bilan bog'lanish",
                                    url="https://t.me/fkhrdnvvvva",
                                )
                            ]
                        ]
                    )

                    # Send with photo if available
                    media_dir = Path(settings.MEDIA_CACHE_DIR)
                    if product.photos:
                        photo_id = product.photos[0]
                        local_file = media_dir / photo_id
                        photo_obj = FSInputFile(str(local_file)) if local_file.is_file() else photo_id
                        try:
                            await message.answer_photo(photo=photo_obj, caption=text, reply_markup=markup)
                            return
                        except Exception:
                            pass

                    await message.answer(text, reply_markup=markup)
                    return
        except Exception as e:
            logger.warning(f"Error handling product deep link: {e}")

    # 4. Standard welcome message
    banner_path = Path(settings.MEDIA_CACHE_DIR) / "bot_banner.png"
    greeting_text = (
        "🌸 <b>Sakura shop ga xush kelibsiz!</b> 💗\n\n"
        "Xitoy brendlari va aesthetic kiyimlar, jempirlar, pariklar va nozik aksessuarlar do'koni ✨\n\n"
        "🛍️ <b>Do'konni ochish</b> tugmasini bosib, barcha go'zal mahsulotlarni qulay Mini App orqali tomosha qiling va savatga qo'shing!\n\n"
        "📍 Toshkent | 🚚 O'zbekiston bo'ylab yetkazib berish\n"
        "💌 Savollar va buyurtma uchun: @fkhrdnvvvva"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌸 Do'konni ochish",
                    web_app=WebAppInfo(url=settings.WEBAPP_URL),
                )
            ],
            [
                InlineKeyboardButton(text="📢 Rasmiy kanal", url="https://t.me/sakuraaa_chinese_shop"),
                InlineKeyboardButton(text="💌 Bog'lanish", url="https://t.me/fkhrdnvvvva"),
            ]
        ]
    )

    if banner_path.is_file():
        try:
            await message.answer_photo(
                photo=FSInputFile(str(banner_path)),
                caption=greeting_text,
                reply_markup=markup,
            )
            return
        except Exception:
            pass

    await message.answer(greeting_text, reply_markup=get_main_reply_keyboard())


# Fast reply button handlers
@router.message(F.text == "🆕 Yangi mahsulotlar")
async def handle_new_products(message: Message):
    async with async_session_factory() as session:
        res = await session.execute(
            select(Product).where(Product.is_new == True, Product.in_stock == True).limit(5)
        )
        prods = res.scalars().all()
        if not prods:
            await message.answer("🌸 Hozircha yangi mahsulotlar kutilmoqda. Do'konni ochib barcha modellarni ko'rishingiz mumkin!")
            return

        lines = ["🌸 <b>Yangi mahsulotlar:</b>\n"]
        for p in prods:
            lines.append(f"• <b>{escape(str(p.title))}</b> — {format_price(p.price)}")
        lines.append(f"\n🛍️ Do'konni ochish tugmasini bosing:")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🌸 Do'konni ochish", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?tab=new"))]
            ]
        )
        await message.answer("\n".join(lines), reply_markup=markup)


@router.message(F.text == "⭐ Fikrlar")
async def handle_reviews(message: Message):
    async with async_session_factory() as session:
        res = await session.execute(
            select(Review).where(Review.approved == True).order_by(Review.created_at.desc()).limit(3)
        )
        revs = res.scalars().all()
        if not revs:
            await message.answer("🌸 Mijozlarimiz fikrlari tez orada bu yerda ko'rinadi!")
            return

        lines = ["⭐ <b>Mijozlarimizdan fikrlar (#отзыв):</b>\n"]
        for r in revs:
            lines.append(f"💬 <i>\"{escape(str(r.text))}\"</i>\n   — <b>{escape(str(r.customer_name))}</b>\n")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🌸 Barcha fikrlar Mini App'da", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?tab=reviews"))]
            ]
        )
        await message.answer("\n".join(lines), reply_markup=markup)


@router.message(F.text == "💌 Admin bilan bog'lanish")
async def handle_contact(message: Message):
    await message.answer(
        "🌸 Har qanday savol va buyurtma uchun to'g'ridan-to'g'ri egamiz @fkhrdnvvvva ga yozishingiz mumkin! 💌",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💌 @fkhrdnvvvva ga yozish", url="https://t.me/fkhrdnvvvva")]
            ]
        ),
    )


@router.message(F.text == "📢 Kanal")
async def handle_channel_link(message: Message):
    await message.answer(
        "🌸 Bizning rasmiy Telegram kanalimizga a'zo bo'ling va yangi kolleksiyalarni birinchi bo'lib ko'ring!\n\n👉 @sakuraaa_chinese_shop",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga o'tish", url="https://t.me/sakuraaa_chinese_shop")]
            ]
        ),
    )
