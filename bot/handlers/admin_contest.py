from html import escape
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    PhotoSize,
)
from sqlalchemy import select

from api.config import settings
from db.models import Admin, Contest, ContestReferral, User, Setting, utcnow
from db.session import async_session_factory
from bot.services.contest_service import (
    get_active_contest,
    get_channel_info,
    build_contest_announcement_text,
    compute_leaderboard,
    format_tashkent_datetime,
    final_recheck_contest,
    approve_and_announce_winners,
    get_suspicious_activity,
)

logger = logging.getLogger(__name__)
router = Router(name="admin_contest")


# FSM States
class ContestWizard(StatesGroup):
    prize_1 = State()
    prize_2 = State()
    prize_3 = State()
    duration = State()
    photo = State()
    preview = State()


class ContestEditPrizes(StatesGroup):
    prize_1 = State()
    prize_2 = State()
    prize_3 = State()


class ContestExtendState(StatesGroup):
    duration = State()


class ContestDisqualifyState(StatesGroup):
    user_id = State()
    reason = State()


class ContestUserCheckState(StatesGroup):
    user_id = State()


async def check_admin(user_id: int) -> bool:
    """Checks whether the user is an owner or admin in DB or dev admin."""
    if settings.DEV_ADMIN_ID and user_id == settings.DEV_ADMIN_ID:
        return True
    async with async_session_factory() as session:
        res = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
        return res.scalars().first() is not None


async def admin_only(event: Message | CallbackQuery) -> bool:
    return event.from_user is not None and await check_admin(event.from_user.id)


# Every handler in this router is admin-only; enforce it once instead of per handler.
router.message.filter(admin_only)
router.callback_query.filter(admin_only)


# ==================== MAIN CONTEST MENU FOR ADMIN ====================
@router.callback_query(F.data == "admin_contest_menu")
async def handle_admin_contest_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await check_admin(call.from_user.id):
        await call.answer("Admin huquqi talab qilinadi!", show_alert=True)
        return

    async with async_session_factory() as session:
        active = await get_active_contest(session)

        if active:
            # Show active contest controls
            ends_str = format_tashkent_datetime(active.ends_at)
            board = await compute_leaderboard(session, active.id, limit=3)

            top_lines = []
            if board:
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                for b in board:
                    tag = f"@{b['username']}" if b["username"] else escape(b["name"])
                    top_lines.append(f"{medals.get(b['rank'], '•')} {tag} — <b>{b['score']}</b> ball")
            else:
                top_lines.append("<i>Hozircha hech kim ball to'plamagan.</i>")

            text = (
                "🎁 <b>FAOL SAKURA KONKURS BOSHQARUVI</b>\n\n"
                f"🥇 1-o'rin: {escape(active.prize_1)}\n"
                f"🥈 2-o'rin: {escape(active.prize_2)}\n"
                f"🥉 3-o'rin: {escape(active.prize_3)}\n\n"
                f"⏳ <b>Tugash:</b> {ends_str}\n"
                f"📌 <b>Holat:</b> {active.status.upper()}\n\n"
                "📊 <b>Hozirgi yetakchilar:</b>\n" + "\n".join(top_lines)
            )

            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📊 Jonli yetakchilar (Top 20)", callback_data=f"adm_c_live:{active.id}"),
                    ],
                    [
                        InlineKeyboardButton(text="⏳ Uzaytirish", callback_data=f"adm_c_extend:{active.id}"),
                        InlineKeyboardButton(text="✏️ Sovg'alarni tahrirlash", callback_data=f"adm_c_edit:{active.id}"),
                    ],
                    [
                        InlineKeyboardButton(text="🔎 Foydalanuvchini tekshirish", callback_data=f"adm_c_chk:{active.id}"),
                        InlineKeyboardButton(text="🚨 Shubhali faollik", callback_data=f"adm_c_susp:{active.id}"),
                    ],
                    [
                        InlineKeyboardButton(text="⏹ Hozir tugatish", callback_data=f"adm_c_end_confirm:{active.id}"),
                        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"adm_c_cancel_confirm:{active.id}"),
                    ],
                    [
                        InlineKeyboardButton(text="📜 O'tgan konkurslar tarixi", callback_data="adm_c_history"),
                    ],
                    [
                        InlineKeyboardButton(text="⬅️ Admin menyusiga qaytish", callback_data="admin_main_menu"),
                    ]
                ]
            )
            await call.message.edit_text(text, reply_markup=markup)
            await call.answer()
        else:
            text = (
                "🎁 <b>KONKURS BOSHQARUVI</b> 🌸\n\n"
                "Hozirda faol konkurs mavjud emas.\n"
                "Yangi konkurs boshlash orqali kanalingizga yuzlab yangi faol obunachilarni jalb qilishingiz mumkin!"
            )
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎁 Yangi konkurs boshlash", callback_data="adm_c_new")],
                    [InlineKeyboardButton(text="📜 O'tgan konkurslar tarixi", callback_data="adm_c_history")],
                    [InlineKeyboardButton(text="⬅️ Admin menyusiga qaytish", callback_data="admin_main_menu")],
                ]
            )
            await call.message.edit_text(text, reply_markup=markup)
            await call.answer()


# ==================== WIZARD: CREATE CONTEST ====================
@router.callback_query(F.data == "adm_c_new")
async def start_contest_wizard(call: CallbackQuery, state: FSMContext):
    if not await check_admin(call.from_user.id):
        await call.answer("Admin huquqi talab qilinadi!", show_alert=True)
        return

    async with async_session_factory() as session:
        active = await get_active_contest(session)
        if active:
            await call.answer("Hozirda faol konkurs allaqachon mavjud!", show_alert=True)
            return

    await state.set_state(ContestWizard.prize_1)
    await call.message.edit_text(
        "🌸 <b>YANGI KONKURS YARATISH (1/5)</b>\n\n"
        "🥇 <b>1-o'rin sovg'asini kiriting:</b>\n"
        "(Masalan: <i>Vintage pushti jempir + Lolita parik</i>)",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")]
            ]
        )
    )
    await call.answer()


@router.callback_query(F.data == "adm_c_cancel_wizard")
async def cancel_wizard(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await handle_admin_contest_menu(call, state)


@router.message(ContestWizard.prize_1)
async def process_prize_1(message: Message, state: FSMContext):
    prize_text = message.text.strip()
    if not prize_text:
        await message.answer("Iltimos, sovg'a nomini kiriting:")
        return

    await state.update_data(prize_1=prize_text)
    await state.set_state(ContestWizard.prize_2)
    await message.answer(
        "🌸 <b>YANGI KONKURS YARATISH (2/5)</b>\n\n"
        "🥈 <b>2-o'rin sovg'asini kiriting:</b>\n"
        "(Masalan: <i>Lolita parik (wig)</i>)",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_c_back_to_p1")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")],
            ]
        )
    )


@router.callback_query(F.data == "adm_c_back_to_p1")
async def back_to_p1(call: CallbackQuery, state: FSMContext):
    await state.set_state(ContestWizard.prize_1)
    await call.message.edit_text(
        "🌸 <b>YANGI KONKURS YARATISH (1/5)</b>\n\n"
        "🥇 <b>1-o'rin sovg'asini kiriting:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")]
            ]
        )
    )
    await call.answer()


@router.message(ContestWizard.prize_2)
async def process_prize_2(message: Message, state: FSMContext):
    prize_text = message.text.strip()
    if not prize_text:
        await message.answer("Iltimos, sovg'a nomini kiriting:")
        return

    await state.update_data(prize_2=prize_text)
    await state.set_state(ContestWizard.prize_3)
    await message.answer(
        "🌸 <b>YANGI KONKURS YARATISH (3/5)</b>\n\n"
        "🥉 <b>3-o'rin sovg'asini kiriting:</b>\n"
        "(Masalan: <i>Iliq yulduzli shoyi sharf</i>)",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_c_back_to_p2")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")],
            ]
        )
    )


@router.callback_query(F.data == "adm_c_back_to_p2")
async def back_to_p2(call: CallbackQuery, state: FSMContext):
    await state.set_state(ContestWizard.prize_2)
    await call.message.edit_text(
        "🌸 <b>YANGI KONKURS YARATISH (2/5)</b>\n\n"
        "🥈 <b>2-o'rin sovg'asini kiriting:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_c_back_to_p1")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")],
            ]
        )
    )
    await call.answer()


@router.message(ContestWizard.prize_3)
async def process_prize_3(message: Message, state: FSMContext):
    prize_text = message.text.strip()
    if not prize_text:
        await message.answer("Iltimos, sovg'a nomini kiriting:")
        return

    await state.update_data(prize_3=prize_text)
    await state.set_state(ContestWizard.duration)
    await message.answer(
        "🌸 <b>YANGI KONKURS YARATISH (4/5)</b>\n\n"
        "⏳ <b>Konkurs davomiyligini tanlang:</b>\n"
        "Tugmalar orqali tanlang yoki maxsus sana kiriting:\n(Masalan: <code>2026-10-30 20:00</code>)",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="1 hafta (7 kun)", callback_data="adm_c_dur:7"),
                    InlineKeyboardButton(text="2 hafta (14 kun)", callback_data="adm_c_dur:14"),
                ],
                [
                    InlineKeyboardButton(text="3 kun", callback_data="adm_c_dur:3"),
                    InlineKeyboardButton(text="1 oy (30 kun)", callback_data="adm_c_dur:30"),
                ],
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_c_back_to_p3")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")],
            ]
        )
    )


@router.callback_query(F.data == "adm_c_back_to_p3")
async def back_to_p3(call: CallbackQuery, state: FSMContext):
    await state.set_state(ContestWizard.prize_3)
    await call.message.edit_text(
        "🌸 <b>YANGI KONKURS YARATISH (3/5)</b>\n\n"
        "🥉 <b>3-o'rin sovg'asini kiriting:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_c_back_to_p2")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")],
            ]
        )
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_c_dur:"))
async def process_duration_callback(call: CallbackQuery, state: FSMContext):
    days = int(call.data.split(":")[1])
    ends_at = utcnow() + timedelta(days=days)
    await state.update_data(ends_at_iso=ends_at.isoformat())
    await state.set_state(ContestWizard.photo)

    await call.message.edit_text(
        "🌸 <b>YANGI KONKURS YARATISH (5/5)</b>\n\n"
        "🖼 <b>Konkurs e'loni uchun rasm yuborasizmi?</b>\n"
        "(Kanalga joylanadigan rasm yuboring yoki o'tkazib yuborish tugmasini bosing):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Rasmsiz davom etish", callback_data="adm_c_skip_photo")],
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_c_back_to_dur")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")],
            ]
        )
    )
    await call.answer()


@router.message(ContestWizard.duration)
async def process_custom_duration(message: Message, state: FSMContext):
    txt = message.text.strip()
    try:
        # Expected format YYYY-MM-DD HH:MM
        custom_dt = datetime.strptime(txt, "%Y-%m-%d %H:%M")
        # Treat as Tashkent time (UTC+5), convert to UTC
        tashkent_tz = timezone(timedelta(hours=5))
        custom_dt = custom_dt.replace(tzinfo=tashkent_tz)
        ends_at = custom_dt.astimezone(timezone.utc)
        if ends_at <= utcnow():
            await message.answer("Tugash vaqti kelajakda bo'lishi kerak! Masalan: <code>2026-10-30 20:00</code>")
            return
        await state.update_data(ends_at_iso=ends_at.isoformat())
        await state.set_state(ContestWizard.photo)
        await message.answer(
            "🌸 <b>YANGI KONKURS YARATISH (5/5)</b>\n\n"
            "🖼 <b>Konkurs e'loni uchun rasm yuborasizmi?</b>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➡️ Rasmsiz davom etish", callback_data="adm_c_skip_photo")],
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_c_back_to_dur")],
                    [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")],
                ]
            )
        )
    except ValueError:
        await message.answer(
            "Format noto'g'ri. Iltimos <code>YYYY-MM-DD HH:MM</code> formatida kiriting yoki yuqoridagi tugmalardan birini bosing:"
        )


@router.callback_query(F.data == "adm_c_back_to_dur")
async def back_to_dur(call: CallbackQuery, state: FSMContext):
    await state.set_state(ContestWizard.duration)
    await call.message.edit_text(
        "🌸 <b>YANGI KONKURS YARATISH (4/5)</b>\n\n"
        "⏳ <b>Konkurs davomiyligini tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="1 hafta (7 kun)", callback_data="adm_c_dur:7"),
                    InlineKeyboardButton(text="2 hafta (14 kun)", callback_data="adm_c_dur:14"),
                ],
                [
                    InlineKeyboardButton(text="3 kun", callback_data="adm_c_dur:3"),
                    InlineKeyboardButton(text="1 oy (30 kun)", callback_data="adm_c_dur:30"),
                ],
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_c_back_to_p3")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")],
            ]
        )
    )
    await call.answer()


@router.message(ContestWizard.photo, F.photo)
async def process_photo_input(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_file_id)
    await show_contest_preview(message, state)


@router.callback_query(F.data == "adm_c_skip_photo")
async def skip_photo_input(call: CallbackQuery, state: FSMContext):
    await state.update_data(photo_file_id=None)
    await show_contest_preview(call.message, state)
    await call.answer()


async def show_contest_preview(target: Message, state: FSMContext):
    data = await state.get_data()
    p1 = data.get("prize_1")
    p2 = data.get("prize_2")
    p3 = data.get("prize_3")
    ends_at = datetime.fromisoformat(data.get("ends_at_iso"))
    photo_file_id = data.get("photo_file_id")

    ends_str = format_tashkent_datetime(ends_at)

    preview_text = (
        "👀 <b>KANALDA CHIQADIGAN POST PREVIEW:</b>\n\n"
        "🌸 <b>SAKURA KONKURS</b> 🌸\n\n"
        f"🥇 <b>1-o'rin:</b> {p1}\n"
        f"🥈 <b>2-o'rin:</b> {p2}\n"
        f"🥉 <b>3-o'rin:</b> {p3}\n\n"
        "📌 <b>Shartlar:</b>\n"
        "1. Botga kiring va shaxsiy havolangizni oling\n"
        "2. Do'stlaringizni taklif qiling\n"
        "3. Ular kanalga obuna bo'lib, ✅ Tasdiqlash tugmasini bossin\n\n"
        "Eng ko'p do'st taklif qilgan g'olib bo'ladi! 💗\n"
        f"⏳ <b>Tugash:</b> {ends_str}\n\n"
        "<i>Tugma:</i> [🎁 Qatnashish]\n\n"
        "Barchasi to'g'rimi? Boshlashni tasdiqlaysizmi?"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Boshlash va kanalga chiqarish", callback_data="adm_c_launch")],
            [InlineKeyboardButton(text="✏️ Qayta tahrirlash", callback_data="adm_c_new")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_c_cancel_wizard")],
        ]
    )

    await state.set_state(ContestWizard.preview)
    if photo_file_id:
        try:
            await target.answer_photo(photo=photo_file_id, caption=preview_text, reply_markup=markup)
            return
        except Exception:
            pass

    await target.answer(preview_text, reply_markup=markup)


@router.callback_query(F.data == "adm_c_launch")
async def launch_contest_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    p1 = data.get("prize_1")
    p2 = data.get("prize_2")
    p3 = data.get("prize_3")
    ends_at = datetime.fromisoformat(data.get("ends_at_iso"))
    photo_file_id = data.get("photo_file_id")

    bot = call.bot
    bot_me = await bot.get_me()

    async with async_session_factory() as session:
        # Double check no active contest exists
        existing = await get_active_contest(session)
        if existing:
            await call.answer("Boshqa faol konkurs allaqachon mavjud!", show_alert=True)
            await state.clear()
            return

        new_contest = Contest(
            prize_1=p1,
            prize_2=p2,
            prize_3=p3,
            photo_file_id=photo_file_id,
            status="active",
            only_new_subscribers=True,
            created_at=utcnow(),
            ends_at=ends_at,
        )
        session.add(new_contest)
        await session.commit()
        await session.refresh(new_contest)

        # Post to linked channel
        channel_id, channel_url = await get_channel_info(session)
        channel_msg_id = None

        if channel_id:
            announcement_text = build_contest_announcement_text(new_contest)
            ch_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🎁 Qatnashish",
                            url=f"https://t.me/{bot_me.username}?start=konkurs"
                        )
                    ]
                ]
            )

            try:
                if photo_file_id:
                    sent = await bot.send_photo(
                        chat_id=channel_id,
                        photo=photo_file_id,
                        caption=announcement_text,
                        reply_markup=ch_markup,
                    )
                else:
                    sent = await bot.send_message(
                        chat_id=channel_id,
                        text=announcement_text,
                        reply_markup=ch_markup,
                    )
                channel_msg_id = sent.message_id
                new_contest.channel_message_id = channel_msg_id
                await session.commit()
                logger.info(f"Contest announcement posted to channel {channel_id}, msg_id={channel_msg_id}")
            except Exception as e:
                logger.error(f"Failed to post contest to channel {channel_id}: {e}")

    await state.clear()
    await call.answer("Konkurs muvaffaqiyatli boshlandi! 🌸", show_alert=True)
    await handle_admin_contest_menu(call, state)


# ==================== LIVE LEADERBOARD (TOP 20) ====================
@router.callback_query(F.data.startswith("adm_c_live:"))
async def handle_admin_live_board(call: CallbackQuery):
    contest_id = int(call.data.split(":")[1])
    async with async_session_factory() as session:
        board = await compute_leaderboard(session, contest_id, limit=20)

        lines = ["📊 <b>JONLI YETAKCHILAR RO'YXATI (TOP 20)</b> 🌸\n"]
        if board:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for it in board:
                medal = medals.get(it["rank"], f"<b>{it['rank']}.</b>")
                tag = f"@{it['username']}" if it["username"] else escape(it["name"])
                lines.append(f"{medal} {tag} (ID: <code>{it['user_id']}</code>) — <b>{it['score']}</b> ball")
        else:
            lines.append("<i>Hozircha ball to'plagan ishtirokchilar mavjud emas.</i>")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Konkurs boshqaruviga qaytish", callback_data="admin_contest_menu")]
            ]
        )
        await call.message.edit_text("\n".join(lines), reply_markup=markup)
        await call.answer()


# ==================== EXTEND CONTEST DURATION ====================
@router.callback_query(F.data.startswith("adm_c_extend:"))
async def handle_extend_prompt(call: CallbackQuery, state: FSMContext):
    contest_id = int(call.data.split(":")[1])
    await state.update_data(contest_id=contest_id)
    await state.set_state(ContestExtendState.duration)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+3 kun", callback_data="adm_c_ext_add:3"),
                InlineKeyboardButton(text="+7 kun (1 hafta)", callback_data="adm_c_ext_add:7"),
            ],
            [
                InlineKeyboardButton(text="+14 kun (2 hafta)", callback_data="adm_c_ext_add:14"),
            ],
            [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_contest_menu")]
        ]
    )
    await call.message.edit_text(
        "⏳ <b>KONKURS MUDDATINI UZAYTIRISH</b>\n\n"
        "Qancha muddat qo'shmoqchisiz? Tugmalardan birini tanlang:",
        reply_markup=markup,
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_c_ext_add:"))
async def handle_extend_apply(call: CallbackQuery, state: FSMContext):
    days = int(call.data.split(":")[1])
    data = await state.get_data()
    contest_id = data.get("contest_id")

    async with async_session_factory() as session:
        res = await session.execute(select(Contest).where(Contest.id == contest_id))
        c = res.scalars().first()
        if c:
            c.ends_at = c.ends_at + timedelta(days=days)
            await session.commit()
            logger.info(f"Contest {c.id} extended by {days} days. New ends_at: {c.ends_at}")

    await state.clear()
    await call.answer(f"Konkurs {days} kunga uzaytirildi! 🌸", show_alert=True)
    await handle_admin_contest_menu(call, state)


# ==================== EDIT PRIZES ====================
@router.callback_query(F.data.startswith("adm_c_edit:"))
async def handle_edit_prizes_start(call: CallbackQuery, state: FSMContext):
    contest_id = int(call.data.split(":")[1])
    await state.update_data(contest_id=contest_id)
    await state.set_state(ContestEditPrizes.prize_1)

    await call.message.edit_text(
        "✏️ <b>SOVG'ALARNI TAHRIRLASH (1/3)</b>\n\n"
        "🥇 Yangi 1-o'rin sovg'asini kiriting:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_contest_menu")]
            ]
        )
    )
    await call.answer()


@router.message(ContestEditPrizes.prize_1)
async def process_edit_p1(message: Message, state: FSMContext):
    await state.update_data(p1=message.text.strip())
    await state.set_state(ContestEditPrizes.prize_2)
    await message.answer(
        "✏️ <b>SOVG'ALARNI TAHRIRLASH (2/3)</b>\n\n"
        "🥈 Yangi 2-o'rin sovg'asini kiriting:"
    )


@router.message(ContestEditPrizes.prize_2)
async def process_edit_p2(message: Message, state: FSMContext):
    await state.update_data(p2=message.text.strip())
    await state.set_state(ContestEditPrizes.prize_3)
    await message.answer(
        "✏️ <b>SOVG'ALARNI TAHRIRLASH (3/3)</b>\n\n"
        "🥉 Yangi 3-o'rin sovg'asini kiriting:"
    )


@router.message(ContestEditPrizes.prize_3)
async def process_edit_p3(message: Message, state: FSMContext):
    p3 = message.text.strip()
    data = await state.get_data()
    contest_id = data.get("contest_id")
    p1 = data.get("p1")
    p2 = data.get("p2")

    bot = message.bot

    async with async_session_factory() as session:
        res = await session.execute(select(Contest).where(Contest.id == contest_id))
        c = res.scalars().first()
        if c:
            c.prize_1 = p1
            c.prize_2 = p2
            c.prize_3 = p3
            await session.commit()

            # Edit channel post if exists
            channel_id, _ = await get_channel_info(session)
            if channel_id and c.channel_message_id and bot:
                new_text = build_contest_announcement_text(c)
                try:
                    if c.photo_file_id:
                        await bot.edit_message_caption(
                            chat_id=channel_id,
                            message_id=c.channel_message_id,
                            caption=new_text,
                        )
                    else:
                        await bot.edit_message_text(
                            chat_id=channel_id,
                            message_id=c.channel_message_id,
                            text=new_text,
                        )
                except Exception as e:
                    logger.warning(f"Could not edit channel message: {e}")

    await state.clear()
    await message.answer("Sovg'alar muvaffaqiyatli yangilandi va kanal xabari tahrirlandi! 🌸")


# ==================== END NOW CONFIRMATION ====================
@router.callback_query(F.data.startswith("adm_c_end_confirm:"))
async def handle_end_now_confirm(call: CallbackQuery):
    contest_id = int(call.data.split(":")[1])
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏹ Ha, konkursni yakunlash", callback_data=f"adm_c_end_exec:{contest_id}"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Yo'q, orqaga", callback_data="admin_contest_menu"),
            ]
        ]
    )
    await call.message.edit_text(
        "⚠️ <b>Haqiqatan ham konkursni hozir yakunlamoqchimisiz?</b>\n\n"
        "Konkurs qulflanadi, barcha a'zoliklar qayta tekshiriladi va natijalar tasdiqlash uchun chiqariladi.",
        reply_markup=markup,
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_c_end_exec:"))
async def handle_end_now_execute(call: CallbackQuery):
    contest_id = int(call.data.split(":")[1])
    bot = call.bot

    await call.message.edit_text("⏳ <i>Konkurs qulflanmoqda va barcha takliflar qayta tekshirilmoqda...</i>")
    async with async_session_factory() as session:
        revoked_count = await final_recheck_contest(session, bot, contest_id)

    from bot.services.contest_scheduler import notify_owner_contest_ended
    await notify_owner_contest_ended(bot, contest_id)
    await call.answer(f"Konkurs yakunlandi! {revoked_count} ta a'zolik bekor qilindi.", show_alert=True)


# ==================== CANCEL CONTEST CONFIRMATION ====================
@router.callback_query(F.data.startswith("adm_c_cancel_confirm:"))
async def handle_cancel_confirm(call: CallbackQuery):
    contest_id = int(call.data.split(":")[1])
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Ha, bekor qilish (hech kim yutmaydi)", callback_data=f"adm_c_cancel_exec:{contest_id}"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Yo'q, orqaga", callback_data="admin_contest_menu"),
            ]
        ]
    )
    await call.message.edit_text(
        "⚠️ <b>DIQQAT: Konkursni bekor qilmoqchimisiz?</b>\n\n"
        "Konkurs butunlay to'xtatiladi va hech kimga sovg'a berilmaydi.",
        reply_markup=markup,
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_c_cancel_exec:"))
async def handle_cancel_execute(call: CallbackQuery):
    contest_id = int(call.data.split(":")[1])
    async with async_session_factory() as session:
        res = await session.execute(select(Contest).where(Contest.id == contest_id))
        c = res.scalars().first()
        if c:
            c.status = "cancelled"
            await session.commit()

    await call.answer("Konkurs bekor qilindi.", show_alert=True)
    await handle_admin_contest_menu(call, None)


# ==================== CHECK A USER ====================
@router.callback_query(F.data.startswith("adm_c_chk:"))
async def handle_check_user_prompt(call: CallbackQuery, state: FSMContext):
    contest_id = int(call.data.split(":")[1])
    await state.update_data(contest_id=contest_id)
    await state.set_state(ContestUserCheckState.user_id)

    await call.message.edit_text(
        "🔎 <b>FOYDALANUVCHINI TEKSHIRISH</b>\n\n"
        "Tekshirmoqchi bo'lgan foydalanuvchining Telegram ID raqamini yoki @username ini yuboring:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_contest_menu")]
            ]
        )
    )
    await call.answer()


@router.message(ContestUserCheckState.user_id)
async def process_check_user_input(message: Message, state: FSMContext):
    query_txt = message.text.strip().replace("@", "")
    data = await state.get_data()
    contest_id = data.get("contest_id")

    async with async_session_factory() as session:
        u_stmt = select(User).where((User.username == query_txt) | (User.telegram_id == int(query_txt) if query_txt.isdigit() else False))
        u_res = await session.execute(u_stmt)
        target_user = u_res.scalars().first()

        if not target_user:
            await message.answer("Foydalanuvchi topilmadi. Iltimos, ID yoki username ni to'g'ri kiriting:")
            return

        ref_stmt = select(ContestReferral).where(
            ContestReferral.contest_id == contest_id,
            ContestReferral.referrer_id == target_user.telegram_id,
        )
        referrals = (await session.execute(ref_stmt)).scalars().all()

        confirmed = [r for r in referrals if r.status == "confirmed"]
        pending = [r for r in referrals if r.status == "pending"]
        revoked = [r for r in referrals if r.status == "revoked"]

        lines = [
            f"👤 <b>Foydalanuvchi:</b> {escape(str(target_user.name))} (@{target_user.username or 'yoq'})",
            f"🆔 ID: <code>{target_user.telegram_id}</code>",
            f"📊 <b>Jami takliflar:</b> {len(referrals)}",
            f"✅ Tasdiqlangan: <b>{len(confirmed)}</b>",
            f"⏳ Kutilmoqda: <b>{len(pending)}</b>",
            f"❌ Chiqib ketgan (Revoked): <b>{len(revoked)}</b>\n",
            "<b>Oxirgi 10 ta taklif:</b>",
        ]

        status_icons = {"confirmed": "✅", "pending": "⏳", "revoked": "❌"}
        for r in referrals[-10:]:
            inv_u_res = await session.execute(select(User).where(User.telegram_id == r.invitee_id))
            inv_u = inv_u_res.scalars().first()
            inv_name = inv_u.name if inv_u else f"ID: {r.invitee_id}"
            lines.append(f"{status_icons.get(r.status, '•')} {escape(str(inv_name))} (ID: <code>{r.invitee_id}</code>)")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚫 Diskvalifikatsiya qilish",
                        callback_data=f"adm_c_dq_user:{contest_id}:{target_user.telegram_id}"
                    )
                ],
                [InlineKeyboardButton(text="⬅️ Konkurs menyusiga qaytish", callback_data="admin_contest_menu")]
            ]
        )
        await state.clear()
        await message.answer("\n".join(lines), reply_markup=markup)


# ==================== SUSPICIOUS ACTIVITY ====================
@router.callback_query(F.data.startswith("adm_c_susp:"))
async def handle_suspicious_activity(call: CallbackQuery):
    contest_id = int(call.data.split(":")[1])
    async with async_session_factory() as session:
        suspicious = await get_suspicious_activity(session, contest_id)

        lines = ["🚨 <b>SHUBHALI FAOLLIK HISOBOTI</b>\n"]
        if suspicious:
            lines.append("<i>(Chiqib ketganlar nisbati 40% dan yuqori bo'lgan foydalanuvchilar):</i>\n")
            for s in suspicious:
                tag = f"@{s['username']}" if s["username"] else escape(s["name"])
                lines.append(
                    f"⚠️ {tag} (ID: <code>{s['referrer_id']}</code>)\n"
                    f"   Jami: {s['total_invites']} | Chiqib ketgan: {s['revoked_invites']} ({s['revoked_ratio']}%)\n"
                )
        else:
            lines.append("<i>Shubhali holatlar aniqlanmadi. Barcha takliflar me'yorda! 🌸</i>")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Konkurs menyusiga qaytish", callback_data="admin_contest_menu")]
            ]
        )
        await call.message.edit_text("\n".join(lines), reply_markup=markup)
        await call.answer()


# ==================== RESULTS APPROVAL HANDLERS ====================
@router.callback_query(F.data.startswith("contest_approve:"))
async def handle_results_approve(call: CallbackQuery):
    contest_id = int(call.data.split(":")[1])
    bot = call.bot

    await call.message.edit_text("⏳ <i>G'oliblar e'lon qilinmoqda va xabarnomalar yuborilmoqda...</i>")
    async with async_session_factory() as session:
        res = await approve_and_announce_winners(session, bot, contest_id)

    if res.get("already_announced"):
        await call.message.edit_text("✅ <b>G'oliblar allaqachon e'lon qilingan.</b> Qayta e'lon qilinmadi 🌸")
        await call.answer()
        return

    winners = res.get("winners", [])
    tot = res.get("total_subscribers_gained", 0)

    lines = [
        "🌸 <b>TABRIKLAYMIZ! G'OLIBLAR E'LON QILINDI!</b> 🏆\n",
        f"Kanalga jami <b>+{tot}</b> yangi faol obunachilar qo'shildi! 🚀\n",
        "<b>G'oliblar ro'yxati:</b>"
    ]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for w in winners:
        tag = f"@{w['username']}" if w["username"] else escape(w["name"])
        lines.append(f"{medals.get(w['rank'], '•')} {w['rank']}-o'rin: {tag} — {w['score']} ta do'st")

    lines.append("\nG'oliblarga shaxsiy tabrik xabarlari yuborildi.")
    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Konkurs boshqaruviga qaytish", callback_data="admin_contest_menu")]
            ]
        )
    )
    await call.answer("G'oliblar kanalga e'lon qilindi!", show_alert=True)


@router.callback_query(F.data.startswith("contest_recheck:"))
async def handle_results_recheck(call: CallbackQuery):
    contest_id = int(call.data.split(":")[1])
    bot = call.bot

    await call.message.edit_text("⏳ <i>Barcha ishtirokchilar qayta tekshirilmoqda (~20 req/s)...</i>")
    async with async_session_factory() as session:
        revoked_count = await final_recheck_contest(session, bot, contest_id)

    from bot.services.contest_scheduler import notify_owner_contest_ended
    await notify_owner_contest_ended(bot, contest_id)
    await call.answer(f"Qayta tekshirildi! {revoked_count} ta a'zolik olib tashlandi.", show_alert=True)


@router.callback_query(F.data.startswith("contest_dq_menu:"))
async def handle_dq_prompt(call: CallbackQuery, state: FSMContext):
    contest_id = int(call.data.split(":")[1])
    await state.update_data(contest_id=contest_id)
    await state.set_state(ContestDisqualifyState.user_id)

    await call.message.edit_text(
        "🚫 <b>FOYDALANUVCHINI DISKVALIFIKATSIYA QILISH</b>\n\n"
        "Diskvalifikatsiya qilmoqchi bo'lgan foydalanuvchining ID raqamini kiriting:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_contest_menu")]
            ]
        )
    )
    await call.answer()


@router.message(ContestDisqualifyState.user_id)
async def process_dq_user_id(message: Message, state: FSMContext):
    txt = message.text.strip()
    if not txt.isdigit():
        await message.answer("Iltimos, faqat raqamli Telegram ID kiriting:")
        return

    await state.update_data(dq_user_id=int(txt))
    await state.set_state(ContestDisqualifyState.reason)
    await message.answer("Diskvalifikatsiya sababini yozing (masalan: <i>Soxta hisoblar orqali qoidani buzish</i>):")


@router.message(ContestDisqualifyState.reason)
async def process_dq_reason(message: Message, state: FSMContext):
    reason = message.text.strip()
    data = await state.get_data()
    contest_id = data.get("contest_id")
    dq_user_id = data.get("dq_user_id")

    async with async_session_factory() as session:
        res = await session.execute(select(Contest).where(Contest.id == contest_id))
        c = res.scalars().first()
        if c:
            dq_list = list(c.disqualified_user_ids or [])
            if dq_user_id not in dq_list:
                dq_list.append(dq_user_id)
                c.disqualified_user_ids = dq_list
                await session.commit()
                logger.info(f"User {dq_user_id} disqualified from contest {contest_id}. Reason: {reason}")

    await state.clear()
    await message.answer(f"Foydalanuvchi {dq_user_id} diskvalifikatsiya qilindi va natijalar ro'yxatidan olib tashlandi! 🌸")
    from bot.services.contest_scheduler import notify_owner_contest_ended
    await notify_owner_contest_ended(message.bot, contest_id)


# ==================== HISTORY OF PAST CONTESTS ====================
@router.callback_query(F.data == "adm_c_history")
async def handle_past_contests_history(call: CallbackQuery):
    async with async_session_factory() as session:
        res = await session.execute(
            select(Contest)
            .where(Contest.status.in_(["completed", "cancelled"]))
            .order_by(Contest.created_at.desc())
        )
        contests = res.scalars().all()

        lines = ["📜 <b>O'TGAN KONKURSLAR TARIXI</b> 🌸\n"]
        if contests:
            for c in contests:
                created_str = c.created_at.strftime("%d.%m.%Y")
                status_icon = "🏆" if c.status == "completed" else "❌"
                lines.append(f"{status_icon} <b>Konkurs #{c.id}</b> ({created_str})")
                lines.append(f"   Sovg'alar: {escape(c.prize_1)}, {escape(c.prize_2)}")
                lines.append(f"   Keltirilgan yangi obunachilar: <b>+{c.total_subscribers_gained}</b>")
                if c.winners_snapshot:
                    w_lines = []
                    for w in c.winners_snapshot:
                        tag = f"@{w['username']}" if w.get("username") else escape(w.get("name", ""))
                        w_lines.append(f"   • {w['rank']}-o'rin: {tag} ({w['score']} ball)")
                    lines.extend(w_lines)
                lines.append("")
        else:
            lines.append("<i>O'tgan konkurslar tarixi hozircha bo'sh.</i>")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Konkurs menyusiga qaytish", callback_data="admin_contest_menu")]
            ]
        )
        await call.message.edit_text("\n".join(lines), reply_markup=markup)
        await call.answer()
