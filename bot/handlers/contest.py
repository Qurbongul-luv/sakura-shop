from html import escape
import logging
import urllib.parse
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy import select

from db.models import User, Contest, ContestReferral
from db.session import async_session_factory
from bot.services.contest_service import (
    get_active_contest,
    get_user_contest_info,
    confirm_referral_action,
    get_channel_info,
    format_tashkent_datetime,
)

logger = logging.getLogger(__name__)
router = Router(name="contest_participant")


@router.message(F.text == "🎁 Konkurs")
async def handle_konkurs_button(message: Message):
    """Handles the '🎁 Konkurs' button from reply keyboard."""
    await show_user_contest_dashboard(message, message.from_user.id)


async def show_user_contest_dashboard(target: Message, user_id: int):
    """Renders the participant's contest dashboard."""
    bot = target.bot
    bot_me = await bot.get_me()

    async with async_session_factory() as session:
        data = await get_user_contest_info(session, bot_me.username, user_id)

        if not data["has_active_contest"]:
            await target.answer(
                "🌸 <b>Hozircha faol konkurs yo'q</b> 🎀\n\n"
                "Tez orada yangi sovg'ali tanlov e'lon qilinadi. Do'konimiz va kanalimizni kuzatib boring! ✨",
            )
            return

        c = data["contest"]
        score = data["score"]
        rank = data["rank"]
        next_dist = data["next_rank_score"]
        link = data["invite_link"]

        # Rank message
        if rank:
            if rank == 1:
                rank_str = f"🏆 Siz <b>1-o'rinda</b>siz! Ajoyib natija! 🌸"
            elif next_dist is not None:
                rank_str = f"Siz <b>{rank}-o'rindasiz</b>, oldingi o'ringa <b>{next_dist} ball</b> qoldi! 🌸"
            else:
                rank_str = f"Siz <b>{rank}-o'rindasiz</b> 🌸"
        else:
            rank_str = "Siz hali ball to'plamadingiz. Do'stlaringizni taklif qiling! 🌸"

        # Share text
        share_text = (
            f"🌸 Sakura shop do'konining go'zal konkursida qatnashib, ajoyib sovg'alarni yutib oling! ✨\n"
            f"Sovg'alar: {escape(c['prize_1'])}, {escape(c['prize_2'])}, {escape(c['prize_3'])} 🎀\n\n"
            f"Qatnashish uchun bosing: {link}"
        )
        share_url = f"https://t.me/share/url?url={urllib.parse.quote(link)}&text={urllib.parse.quote(share_text)}"

        # Invites summary
        invites = data["invites"][:5]
        inv_lines = []
        if invites:
            status_map = {
                "confirmed": "✅ Tasdiqlangan",
                "pending": "⏳ Kutilmoqda",
                "revoked": "❌ Chiqib ketgan",
            }
            inv_lines.append("\n<b>So'nggi takliflaringiz:</b>")
            for it in invites:
                inv_lines.append(f"• {escape(str(it['name']))} — {status_map.get(it['status'], it['status'])}")
        else:
            inv_lines.append("\n<i>Hozircha taklif qilinganlar yo'q.</i>")

        text = (
            "🌸 <b>SAKURA REFERRAL KONKURS</b> 🎁\n\n"
            f"🥇 <b>1-o'rin:</b> {escape(c['prize_1'])}\n"
            f"🥈 <b>2-o'rin:</b> {escape(c['prize_2'])}\n"
            f"🥉 <b>3-o'rin:</b> {escape(c['prize_3'])}\n\n"
            f"⏳ <b>Tugash vaqti:</b> {c['formatted_ends_at']}\n\n"
            f"📊 <b>Ballingiz:</b> {score} ta do'st\n"
            f"📍 {rank_str}\n\n"
            f"🔗 <b>Shaxsiy taklif havolangiz:</b>\n<code>{link}</code>\n"
            + "\n".join(inv_lines)
        )

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url),
                ],
                [
                    InlineKeyboardButton(text="🏆 Yetakchilar jadvali", callback_data=f"show_top10:{c['id']}"),
                ]
            ]
        )

        await target.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("show_top10:"))
async def handle_show_top10(call: CallbackQuery):
    """Shows top 10 leaderboard with medal badges."""
    contest_id = int(call.data.split(":")[1])
    async with async_session_factory() as session:
        from bot.services.contest_service import compute_leaderboard
        board = await compute_leaderboard(session, contest_id, limit=10)

        lines = ["🏆 <b>YETAKCHILAR JADVALI (TOP 10)</b> 🌸\n"]
        if board:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for it in board:
                medal = medals.get(it["rank"], f"<b>{it['rank']}.</b>")
                tag = f"@{it['username']}" if it["username"] else escape(it["name"])
                lines.append(f"{medal} {tag} — <b>{it['score']}</b> ball")
        else:
            lines.append("<i>Hozircha hech kim ball to'plamadi. Birinchi bo'ling! 🌸</i>")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Mening natijam", callback_data=f"my_stats:{contest_id}")]
            ]
        )
        await call.message.edit_text("\n".join(lines), reply_markup=markup)
        await call.answer()


@router.callback_query(F.data.startswith("my_stats:"))
async def handle_back_my_stats(call: CallbackQuery):
    """Returns to user's contest stats."""
    await call.message.delete()
    await show_user_contest_dashboard(call.message, call.from_user.id)
    await call.answer()


@router.callback_query(F.data.startswith("confirm_sub:"))
async def handle_confirm_sub_button(call: CallbackQuery):
    """
    Invitee pressed ✅ Tasdiqlash.
    Callback data: confirm_sub:<contest_id>:<user_id>
    """
    parts = call.data.split(":")
    contest_id = int(parts[1])
    invitee_id = int(parts[2])

    if call.from_user.id != invitee_id:
        await call.answer("Bu tugma faqat taklif qilingan foydalanuvchi uchun 🌸", show_alert=True)
        return

    bot = call.bot
    bot_me = await bot.get_me()

    async with async_session_factory() as session:
        result = await confirm_referral_action(
            session=session,
            bot=bot,
            user_id=invitee_id,
            contest_id=contest_id,
            bot_username=bot_me.username,
        )

        status = result.get("status")
        msg = result.get("message", "")

        if status == "throttled":
            await call.answer(msg, show_alert=True)
            return

        if status == "not_subscribed":
            _, ch_url = await get_channel_info(session)
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📢 Kanalga o'tish", url=ch_url)],
                    [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_sub:{contest_id}:{invitee_id}")]
                ]
            )
            await call.answer(msg, show_alert=True)
            try:
                await call.message.edit_text(
                    f"🙈 <b>Siz hali kanalga obuna bo'lmadingiz!</b>\n\n"
                    "Konkursda qatnashish uchun avval kanalimizga a'zo bo'ling va so'ngra <b>✅ Tasdiqlash</b> tugmasini bosing 🌸",
                    reply_markup=markup
                )
            except Exception:
                pass
            return

        if status in ("success", "was_member_before"):
            personal_link = result.get("personal_link", "")
            share_text = f"🌸 Sakura shop konkursida qatnashing va go'zal sovg'alarni yutib oling! ✨\n{personal_link}"
            share_url = f"https://t.me/share/url?url={urllib.parse.quote(personal_link)}&text={urllib.parse.quote(share_text)}"

            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🎁 Mening havolam", callback_data=f"my_stats:{contest_id}"),
                        InlineKeyboardButton(text="📤 Ulashish", url=share_url),
                    ]
                ]
            )

            await call.answer("Tasdiqlandi! 🌸", show_alert=False)
            await call.message.edit_text(
                f"🎉 <b>{msg}</b>\n\n"
                f"🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n<code>{personal_link}</code>\n\n"
                "Ushbu havolani do'stlaringizga yuboring. Har bir a'zo bo'lgan do'stingiz uchun sizga +1 ball beriladi! 💗",
                reply_markup=markup
            )
            return

        # Fallback for ended/not_found
        await call.answer(msg, show_alert=True)
