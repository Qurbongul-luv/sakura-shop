from html import escape
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, update, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest

from api.config import settings
from db.models import Contest, ContestReferral, ContestReferralAudit, User, Setting, Admin, utcnow

logger = logging.getLogger(__name__)

# In-memory throttle for Tasdiqlash button: user_id -> timestamp
_confirm_throttle: Dict[int, float] = {}

UZBEK_MONTHS = {
    1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel",
    5: "may", 6: "iyun", 7: "iyul", 8: "avgust",
    9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
}


def to_tashkent_tz(dt: datetime) -> datetime:
    """Converts UTC datetime to Asia/Tashkent (UTC+5)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    tashkent_tz = timezone(timedelta(hours=5))
    return dt.astimezone(tashkent_tz)


def ensure_utc(dt: datetime) -> datetime:
    """Ensures datetime is timezone-aware in UTC."""
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_tashkent_datetime(dt: datetime) -> str:
    """Formats datetime clearly in Asia/Tashkent, e.g. '26-oktabr, 20:00 gacha'."""
    t_dt = to_tashkent_tz(dt)
    month_name = UZBEK_MONTHS.get(t_dt.month, "")
    return f"{t_dt.day}-{month_name}, {t_dt.strftime('%H:%M')} gacha"


async def get_channel_info(session: AsyncSession) -> Tuple[Optional[str], str]:
    """Retrieves channel_id and channel_url from settings."""
    res_id = await session.execute(select(Setting).where(Setting.key == "channel_id"))
    ch_id_rec = res_id.scalars().first()
    channel_id = ch_id_rec.value.strip() if ch_id_rec and ch_id_rec.value.strip() else None

    res_url = await session.execute(select(Setting).where(Setting.key == "channel_url"))
    ch_url_rec = res_url.scalars().first()
    channel_url = ch_url_rec.value.strip() if ch_url_rec and ch_url_rec.value.strip() else "https://t.me/sakuraaa_chinese_shop"

    return channel_id, channel_url


async def get_active_contest(session: AsyncSession) -> Optional[Contest]:
    """Retrieves the single currently active contest if any."""
    res = await session.execute(
        select(Contest)
        .where(Contest.status == "active")
        .order_by(Contest.created_at.desc())
    )
    return res.scalars().first()


def build_contest_announcement_text(contest: Contest) -> str:
    """Builds cute channel announcement text matching channel vibe."""
    ends_str = format_tashkent_datetime(contest.ends_at)
    return (
        "🌸 <b>SAKURA KONKURS</b> 🌸\n\n"
        f"🥇 <b>1-o'rin:</b> {escape(contest.prize_1)}\n"
        f"🥈 <b>2-o'rin:</b> {escape(contest.prize_2)}\n"
        f"🥉 <b>3-o'rin:</b> {escape(contest.prize_3)}\n\n"
        "📌 <b>Shartlar:</b>\n"
        "1. Botga kiring va shaxsiy havolangizni oling\n"
        "2. Do'stlaringizni taklif qiling\n"
        "3. Ular kanalga obuna bo'lib, ✅ Tasdiqlash tugmasini bossin\n\n"
        "Eng ko'p do'st taklif qilgan g'olib bo'ladi! 💗\n"
        f"⏳ <b>Tugash:</b> {ends_str}"
    )


async def process_referral_start(
    session: AsyncSession,
    bot: Optional[Bot],
    user_id: int,
    user_full_name: str,
    user_username: Optional[str],
    is_bot: bool,
    payload: str,
    is_new_user: bool,
) -> Dict[str, Any]:
    """
    Handles when a user opens an invite link: /start r_<contest_id>_<referrer_id>.
    Strictly checks all counting rules.
    """
    m = re.match(r"^r_(\d+)_(\d+)$", payload.strip())
    if not m:
        return {"valid": False, "reason": "malformed_payload"}

    contest_id = int(m.group(1))
    referrer_id = int(m.group(2))

    # Rule: no bots, no self-invites
    if is_bot or user_id == referrer_id:
        return {"valid": False, "reason": "self_or_bot"}

    # Rule: check active contest
    active = await get_active_contest(session)
    if not active or active.id != contest_id or ensure_utc(active.ends_at) <= utcnow():
        return {
            "valid": False,
            "reason": "no_active_contest",
            "message": "Hozircha faol konkurs yo'q 🌸"
        }

    # Rule: referrer must exist in database
    ref_user_res = await session.execute(select(User).where(User.telegram_id == referrer_id))
    referrer_user = ref_user_res.scalars().first()
    if not referrer_user:
        return {"valid": False, "reason": "invalid_referrer"}

    # Rule: existing bot user cannot be invited
    if not is_new_user:
        return {
            "valid": False,
            "reason": "existing_user",
            "message": (
                "Siz avval ham botimizdan foydalangansiz 🌸\n"
                "Do'stingizga taklif balli hisoblanmaydi, lekin siz ham konkursda qatnashib, sovg'alarni yutib olishingiz mumkin! 🎁"
            )
        }

    # Rule: first referrer wins forever. Check if referral record already exists
    ref_rec_res = await session.execute(
        select(ContestReferral).where(
            ContestReferral.contest_id == contest_id,
            ContestReferral.invitee_id == user_id,
        )
    )
    existing_ref = ref_rec_res.scalars().first()
    if existing_ref:
        return {
            "valid": True,
            "already_registered": True,
            "referral": existing_ref,
            "contest": active,
        }

    # Rule: check if invitee was already a channel member before
    channel_id, channel_url = await get_channel_info(session)
    was_member_before = False
    if channel_id and bot:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ("creator", "administrator", "member"):
                was_member_before = True
            elif member.status == "restricted" and getattr(member, "is_member", True):
                was_member_before = True
        except Exception as e:
            logger.warning(f"Could not check membership for user {user_id} in channel {channel_id}: {e}")

    # Create pending referral record
    new_referral = ContestReferral(
        contest_id=contest_id,
        invitee_id=user_id,
        referrer_id=referrer_id,
        status="pending",
        was_member_before=was_member_before,
        started_at=utcnow(),
    )
    session.add(new_referral)
    await session.flush()

    # Audit log
    session.add(
        ContestReferralAudit(
            contest_id=contest_id,
            referral_id=new_referral.id,
            invitee_id=user_id,
            referrer_id=referrer_id,
            action="created_pending",
            reason=f"was_member_before={was_member_before}",
        )
    )
    await session.commit()

    return {
        "valid": True,
        "already_registered": False,
        "referral": new_referral,
        "contest": active,
        "channel_url": channel_url,
        "was_member_before": was_member_before,
    }


async def confirm_referral_action(
    session: AsyncSession,
    bot: Optional[Bot],
    user_id: int,
    contest_id: int,
    bot_username: str,
) -> Dict[str, Any]:
    """
    Called when invitee clicks ✅ Tasdiqlash.
    Throttled to 1 check per 3 seconds.
    Atomically transitions referral from pending/revoked -> confirmed.
    """
    now_ts = datetime.now().timestamp()
    last_ts = _confirm_throttle.get(user_id, 0.0)
    if now_ts - last_ts < 3.0:
        return {
            "status": "throttled",
            "message": "Iltimos, 3 soniya kuting ⏳"
        }
    _confirm_throttle[user_id] = now_ts

    # Check active contest
    active = await get_active_contest(session)
    if not active or active.id != contest_id or ensure_utc(active.ends_at) <= utcnow():
        return {
            "status": "ended",
            "message": "Konkurs yakunlangan yoki faol emas 🌸"
        }

    # Query referral record
    ref_res = await session.execute(
        select(ContestReferral).where(
            ContestReferral.contest_id == contest_id,
            ContestReferral.invitee_id == user_id,
        )
    )
    referral = ref_res.scalars().first()
    if not referral:
        return {
            "status": "not_found",
            "message": "Taklif ma'lumoti topilmadi 🌸"
        }

    channel_id, channel_url = await get_channel_info(session)
    if not channel_id:
        return {
            "status": "error",
            "message": "Kanal biriktirilmagan, iltimos adminga xabar bering 💌"
        }

    # Verify channel membership
    is_subscribed = False
    if bot:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ("creator", "administrator", "member"):
                is_subscribed = True
            elif member.status == "restricted" and getattr(member, "is_member", True):
                is_subscribed = True
        except Exception as e:
            logger.warning(f"get_chat_member failed for user {user_id}: {e}")

    if not is_subscribed:
        return {
            "status": "not_subscribed",
            "message": "Siz hali obuna bo'lmagansiz 🙈",
            "channel_url": channel_url,
        }

    # If already a member before and contest allows only new subscribers
    if referral.was_member_before and active.only_new_subscribers:
        personal_link = f"https://t.me/{bot_username}?start=r_{active.id}_{user_id}"
        return {
            "status": "was_member_before",
            "message": (
                "Siz avvaldan kanal a'zosi bo'lganingiz uchun taklif balli hisoblanmadi 🌸\n\n"
                "Lekin siz ham konkursda qatnashib, do'stlaringizni taklif qilishingiz va sovg'alarni yutishingiz mumkin! 🎁"
            ),
            "personal_link": personal_link,
        }

    # Atomic idempotent update: pending/revoked -> confirmed
    now = utcnow()
    stmt = (
        update(ContestReferral)
        .where(
            ContestReferral.contest_id == contest_id,
            ContestReferral.invitee_id == user_id,
            ContestReferral.status.in_(["pending", "revoked"]),
        )
        .values(status="confirmed", confirmed_at=now, revoked_at=None)
    )
    res = await session.execute(stmt)
    is_newly_confirmed = (res.rowcount > 0)

    personal_link = f"https://t.me/{bot_username}?start=r_{active.id}_{user_id}"

    if is_newly_confirmed:
        # Audit log
        session.add(
            ContestReferralAudit(
                contest_id=contest_id,
                referral_id=referral.id,
                invitee_id=user_id,
                referrer_id=referral.referrer_id,
                action="confirmed",
                reason="Subscribed and confirmed",
            )
        )
        await session.commit()

        # Compute referrer's updated score
        score_stmt = select(func.count(ContestReferral.id)).where(
            ContestReferral.contest_id == contest_id,
            ContestReferral.referrer_id == referral.referrer_id,
            ContestReferral.status == "confirmed",
        )
        total_score = (await session.execute(score_stmt)).scalar() or 0

        # DM Referrer
        if bot:
            try:
                invitee_u_res = await session.execute(select(User).where(User.telegram_id == user_id))
                invitee_u = invitee_u_res.scalars().first()
                name_str = invitee_u.name if invitee_u and invitee_u.name else f"ID: {user_id}"
                msg = f"🎉 <b>+1 ball!</b> {escape(str(name_str))} kanalga obuna bo'ldi.\nJami ballingiz: <b>{total_score}</b> 🌸"
                await bot.send_message(chat_id=referral.referrer_id, text=msg)
            except TelegramForbiddenError:
                logger.info(f"Referrer {referral.referrer_id} blocked the bot.")
            except Exception as e:
                logger.warning(f"Could not notify referrer {referral.referrer_id}: {e}")

    return {
        "status": "success",
        "message": "Rahmat! 🌸 Siz konkursda ham qatnashishingiz mumkin.",
        "personal_link": personal_link,
        "is_newly_confirmed": is_newly_confirmed,
    }


async def revoke_referral_on_leave(
    session: AsyncSession,
    bot: Optional[Bot],
    user_id: int,
) -> Optional[int]:
    """
    Called when invitee leaves the channel. Sets referral status to revoked
    and decrements point from referrer.
    """
    active = await get_active_contest(session)
    if not active or active.status != "active":
        return None

    res = await session.execute(
        select(ContestReferral).where(
            ContestReferral.contest_id == active.id,
            ContestReferral.invitee_id == user_id,
            ContestReferral.status == "confirmed",
        )
    )
    referral = res.scalars().first()
    if not referral:
        return None

    referral.status = "revoked"
    referral.revoked_at = utcnow()

    session.add(
        ContestReferralAudit(
            contest_id=active.id,
            referral_id=referral.id,
            invitee_id=user_id,
            referrer_id=referral.referrer_id,
            action="revoked_left_channel",
            reason="User left channel",
        )
    )
    await session.commit()

    if bot:
        try:
            await bot.send_message(
                chat_id=referral.referrer_id,
                text="Do'stingiz kanaldan chiqdi, 1 ball olib tashlandi 💔",
            )
        except Exception as e:
            logger.info(f"Could not notify referrer {referral.referrer_id} of leave: {e}")

    return referral.referrer_id


async def compute_leaderboard(
    session: AsyncSession,
    contest_id: int,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Computes exact live leaderboard:
    COUNT(*) WHERE status='confirmed' GROUP BY referrer_id
    Tie-break: ordered by score DESC, and earliest confirmed_at of last referral ASC.
    """
    res_c = await session.execute(select(Contest).where(Contest.id == contest_id))
    contest = res_c.scalars().first()
    disqualified = contest.disqualified_user_ids if contest else []

    stmt = (
        select(
            ContestReferral.referrer_id,
            func.count(ContestReferral.id).label("score"),
            func.max(ContestReferral.confirmed_at).label("last_confirmed_at"),
        )
        .where(
            ContestReferral.contest_id == contest_id,
            ContestReferral.status == "confirmed",
        )
        .group_by(ContestReferral.referrer_id)
        .order_by(desc("score"), asc("last_confirmed_at"))
    )
    rows = (await session.execute(stmt)).all()

    leaderboard = []
    rank = 1
    for row in rows:
        uid = row.referrer_id
        if uid in disqualified:
            continue
        user_res = await session.execute(select(User).where(User.telegram_id == uid))
        user_obj = user_res.scalars().first()
        name = user_obj.name if user_obj else f"Foydalanuvchi {uid}"
        username = user_obj.username if user_obj else None

        leaderboard.append({
            "rank": rank,
            "user_id": uid,
            "name": name,
            "username": username,
            "score": row.score,
            "last_confirmed_at": row.last_confirmed_at,
        })
        rank += 1
        if len(leaderboard) >= limit:
            break

    return leaderboard


async def get_user_contest_info(
    session: AsyncSession,
    bot_username: str,
    user_id: int,
) -> Dict[str, Any]:
    """Retrieves full contest stats for a specific participant."""
    active = await get_active_contest(session)
    if not active:
        return {
            "has_active_contest": False,
            "contest": None,
            "user_id": user_id,
            "invite_link": "",
            "score": 0,
            "rank": None,
            "next_rank_score": None,
            "invites": [],
        }

    # User score
    score_stmt = select(func.count(ContestReferral.id)).where(
        ContestReferral.contest_id == active.id,
        ContestReferral.referrer_id == user_id,
        ContestReferral.status == "confirmed",
    )
    user_score = (await session.execute(score_stmt)).scalar() or 0

    # User rank from leaderboard
    full_board = await compute_leaderboard(session, active.id, limit=500)
    user_rank = None
    next_rank_score = None
    for entry in full_board:
        if entry["user_id"] == user_id:
            user_rank = entry["rank"]
            break

    if user_rank and user_rank > 1:
        prev_entry = full_board[user_rank - 2]
        next_rank_score = prev_entry["score"] - user_score

    # Invites list
    invites_stmt = (
        select(ContestReferral)
        .where(
            ContestReferral.contest_id == active.id,
            ContestReferral.referrer_id == user_id,
        )
        .order_by(desc(ContestReferral.started_at))
    )
    invites_rows = (await session.execute(invites_stmt)).scalars().all()

    invites_out = []
    for inv in invites_rows:
        u_res = await session.execute(select(User).where(User.telegram_id == inv.invitee_id))
        u = u_res.scalars().first()
        invites_out.append({
            "id": inv.id,
            "invitee_id": inv.invitee_id,
            "name": u.name if u else f"ID: {inv.invitee_id}",
            "username": u.username if u else None,
            "status": inv.status,
            "started_at": inv.started_at,
            "confirmed_at": inv.confirmed_at,
        })

    # Total stats
    total_parts_stmt = select(func.count(func.distinct(ContestReferral.referrer_id))).where(
        ContestReferral.contest_id == active.id
    )
    total_participants = (await session.execute(total_parts_stmt)).scalar() or 0

    total_conf_stmt = select(func.count(ContestReferral.id)).where(
        ContestReferral.contest_id == active.id,
        ContestReferral.status == "confirmed",
    )
    total_confirmed = (await session.execute(total_conf_stmt)).scalar() or 0

    _, channel_url = await get_channel_info(session)

    contest_dict = {
        "id": active.id,
        "prize_1": active.prize_1,
        "prize_2": active.prize_2,
        "prize_3": active.prize_3,
        "photo_file_id": active.photo_file_id,
        "channel_message_id": active.channel_message_id,
        "status": active.status,
        "only_new_subscribers": active.only_new_subscribers,
        "created_at": active.created_at,
        "ends_at": active.ends_at,
        "formatted_ends_at": format_tashkent_datetime(active.ends_at),
        "is_active": (active.status == "active" and ensure_utc(active.ends_at) > utcnow()),
        "total_participants": total_participants,
        "total_confirmed_invites": total_confirmed,
        "channel_url": channel_url,
    }

    return {
        "has_active_contest": True,
        "contest": contest_dict,
        "user_id": user_id,
        "invite_link": f"https://t.me/{bot_username}?start=r_{active.id}_{user_id}",
        "score": user_score,
        "rank": user_rank,
        "next_rank_score": next_rank_score,
        "invites": invites_out,
    }


async def final_recheck_contest(
    session: AsyncSession,
    bot: Optional[Bot],
    contest_id: int,
) -> int:
    """
    Final recheck: locks contest to 'pending_approval' and checks all confirmed invitees
    with get_chat_member (~20 req/s with retry). Revokes users who left.
    Returns count of revoked members.
    """
    res_c = await session.execute(select(Contest).where(Contest.id == contest_id))
    contest = res_c.scalars().first()
    if not contest:
        return 0

    # A completed or cancelled contest must never be reopened by a recheck.
    if contest.status not in ("active", "paused", "pending_approval"):
        return 0

    contest.status = "pending_approval"
    await session.commit()

    channel_id, _ = await get_channel_info(session)
    if not channel_id or not bot:
        logger.warning("No channel or bot configured for final recheck")
        return 0

    ref_res = await session.execute(
        select(ContestReferral).where(
            ContestReferral.contest_id == contest_id,
            ContestReferral.status == "confirmed",
        )
    )
    confirmed_refs = ref_res.scalars().all()
    revoked_count = 0
    unchecked_count = 0

    for ref in confirmed_refs:
        await asyncio.sleep(0.05)  # Throttle ~20 req/sec
        member = None
        for _attempt in range(3):
            try:
                member = await bot.get_chat_member(chat_id=channel_id, user_id=ref.invitee_id)
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except Exception as e:
                logger.warning(f"Recheck attempt failed for {ref.invitee_id}: {e}")
                await asyncio.sleep(1)

        # Only take a point away when Telegram clearly says the user is not in the channel.
        # A network error or lost admin rights must never wipe honest points.
        if member is None:
            unchecked_count += 1
            continue

        is_member = member.status in ("creator", "administrator", "member") or (
            member.status == "restricted" and getattr(member, "is_member", True)
        )

        if not is_member:
            ref.status = "revoked"
            ref.revoked_at = utcnow()
            session.add(
                ContestReferralAudit(
                    contest_id=contest_id,
                    referral_id=ref.id,
                    invitee_id=ref.invitee_id,
                    referrer_id=ref.referrer_id,
                    action="recheck_revoked",
                    reason="Not in channel during final recheck",
                )
            )
            revoked_count += 1

    await session.commit()
    if unchecked_count:
        logger.warning(
            f"Final recheck of contest #{contest_id}: {unchecked_count} invitees could not be checked; "
            "their points were kept. Press 'Qayta tekshirish' to retry."
        )
    return revoked_count


async def approve_and_announce_winners(
    session: AsyncSession,
    bot: Optional[Bot],
    contest_id: int,
) -> Dict[str, Any]:
    """
    Owner approved results:
    1. Sets status to 'completed'
    2. Takes top 3 (score > 0)
    3. Posts winners to channel
    4. DMs each winner
    5. Saves snapshot and growth stats
    """
    res_c = await session.execute(select(Contest).where(Contest.id == contest_id))
    contest = res_c.scalars().first()
    if not contest:
        raise ValueError("Contest not found")

    # Claim the announcement atomically: a double tap or two admins pressing at once
    # must post the winners only once.
    claim = await session.execute(
        update(Contest)
        .where(Contest.id == contest_id, Contest.status.in_(["active", "pending_approval"]))
        .values(status="announcing")
    )
    await session.commit()
    if claim.rowcount == 0:
        return {
            "contest_id": contest_id,
            "winners": [],
            "total_subscribers_gained": contest.total_subscribers_gained or 0,
            "already_announced": True,
        }
    await session.refresh(contest)

    leaderboard = await compute_leaderboard(session, contest_id, limit=3)
    # Filter out zero scores: A score of 0 never wins!
    winners = [entry for entry in leaderboard if entry["score"] > 0][:3]

    winners_clean = []
    for w in winners:
        w_dict = dict(w)
        if isinstance(w_dict.get("last_confirmed_at"), datetime):
            w_dict["last_confirmed_at"] = w_dict["last_confirmed_at"].isoformat()
        winners_clean.append(w_dict)

    # Total confirmed subscribers gained
    tot_res = await session.execute(
        select(func.count(ContestReferral.id)).where(
            ContestReferral.contest_id == contest_id,
            ContestReferral.status == "confirmed",
        )
    )
    total_gained = tot_res.scalar() or 0

    contest.status = "completed"
    contest.winners_snapshot = winners_clean
    contest.total_subscribers_gained = total_gained
    await session.commit()

    channel_id, _ = await get_channel_info(session)
    contact_username = "fkhrdnvvvva"

    # Post channel announcement
    if channel_id and bot and winners:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = ["🌸 <b>SAKURA KONKURS G'OLIBLARI!</b> 🏆\n"]
        for w in winners:
            medal = medals.get(w["rank"], "🎖")
            tag = f"@{w['username']}" if w["username"] else escape(w["name"])
            lines.append(f"{medal} <b>{w['rank']}-o'rin:</b> {tag} — {w['score']} ta do'st")

        lines.append("\nBarcha ishtirokchilarga katta rahmat! 💗✨")
        lines.append(f"Sovg'alarni olish uchun @{contact_username} ga yozing 💌")
        channel_post = "\n".join(lines)

        try:
            await bot.send_message(chat_id=channel_id, text=channel_post)
        except Exception as e:
            logger.error(f"Failed to post winners to channel: {e}")

    # DM each winner
    if bot:
        for w in winners:
            try:
                dm_text = (
                    f"Tabriklaymiz! 🎉 Siz Sakura shop konkursida <b>{w['rank']}-o'rin</b>ni egalladingiz! 🌸\n"
                    f"Natijangiz: <b>{w['score']}</b> ta taklif qilingan do'st.\n\n"
                    f"Sovg'angizni qabul qilish uchun do'kon egamiz @{contact_username} ga yozing 💌"
                )
                await bot.send_message(chat_id=w["user_id"], text=dm_text)
            except Exception as e:
                logger.warning(f"Could not DM winner {w['user_id']}: {e}")

    return {
        "contest_id": contest_id,
        "winners": winners,
        "total_subscribers_gained": total_gained,
    }


async def get_suspicious_activity(
    session: AsyncSession,
    contest_id: int,
) -> List[Dict[str, Any]]:
    """
    Finds referrers with suspicious behavior, e.g. high ratio of revoked invitees.
    """
    stmt = (
        select(
            ContestReferral.referrer_id,
            func.count(ContestReferral.id).label("total"),
            func.count(func.nullif(ContestReferral.status != "confirmed", True)).label("confirmed"),
            func.count(func.nullif(ContestReferral.status != "revoked", True)).label("revoked"),
        )
        .where(ContestReferral.contest_id == contest_id)
        .group_by(ContestReferral.referrer_id)
        .having(func.count(ContestReferral.id) >= 3)
    )
    rows = (await session.execute(stmt)).all()

    suspicious = []
    for row in rows:
        revoked_ratio = row.revoked / row.total if row.total > 0 else 0
        if revoked_ratio >= 0.4:  # 40%+ leaves is suspicious
            u_res = await session.execute(select(User).where(User.telegram_id == row.referrer_id))
            u = u_res.scalars().first()
            suspicious.append({
                "referrer_id": row.referrer_id,
                "name": u.name if u else f"ID: {row.referrer_id}",
                "username": u.username if u else None,
                "total_invites": row.total,
                "confirmed_invites": row.confirmed,
                "revoked_invites": row.revoked,
                "revoked_ratio": round(revoked_ratio * 100, 1),
            })

    suspicious.sort(key=lambda x: x["revoked_ratio"], reverse=True)
    return suspicious


async def send_pending_reminders(
    session: AsyncSession,
    bot: Optional[Bot],
) -> int:
    """
    Sends a one-time reminder to invitees who joined > 1 hour ago and haven't confirmed yet.
    """
    active = await get_active_contest(session)
    if not active or not bot:
        return 0

    cutoff = utcnow() - timedelta(hours=1)
    stmt = select(ContestReferral).where(
        ContestReferral.contest_id == active.id,
        ContestReferral.status == "pending",
        ContestReferral.started_at <= cutoff,
        ContestReferral.reminder_sent == False,
    )
    pending_refs = (await session.execute(stmt)).scalars().all()
    sent_count = 0

    for ref in pending_refs:
        try:
            await bot.send_message(
                chat_id=ref.invitee_id,
                text="🌸 <b>Eslatma:</b> Konkursda qatnashish va do'stingizga ball berish uchun kanalga obuna bo'lib, ✅ <b>Tasdiqlash</b> tugmasini bosishni unutmang 🎀",
            )
            ref.reminder_sent = True
            sent_count += 1
        except Exception:
            ref.reminder_sent = True  # don't retry failed DMs infinitely

    await session.commit()
    return sent_count
