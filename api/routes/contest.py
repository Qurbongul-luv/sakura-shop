import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, TelegramUser, require_admin
from api.schemas import (
    ContestCreate,
    ContestOut,
    ContestUpdatePrizes,
    ContestExtend,
    LeaderboardEntry,
    MyContestStatsOut,
    SuspiciousUserItem,
    DisqualifyPayload,
)
from bot.loader import bot
from bot.services.contest_service import (
    get_active_contest,
    get_channel_info,
    build_contest_announcement_text,
    compute_leaderboard,
    get_user_contest_info,
    format_tashkent_datetime,
    final_recheck_contest,
    approve_and_announce_winners,
    get_suspicious_activity,
)
from db.models import Contest, ContestReferral, User, utcnow
from db.session import get_db
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contest", tags=["contest"])
admin_router = APIRouter(prefix="/admin/contest", tags=["admin-contest"])


# ==================== PUBLIC / PARTICIPANT ENDPOINTS ====================
@router.get("/active")
async def get_active_contest_info(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    active = await get_active_contest(db)
    if not active:
        return {"has_active_contest": False, "contest": None}

    channel_id, channel_url = await get_channel_info(db)
    return {
        "has_active_contest": True,
        "contest": ContestOut(
            id=active.id,
            prize_1=active.prize_1,
            prize_2=active.prize_2,
            prize_3=active.prize_3,
            photo_file_id=active.photo_file_id,
            channel_message_id=active.channel_message_id,
            status=active.status,
            only_new_subscribers=active.only_new_subscribers,
            created_at=active.created_at,
            ends_at=active.ends_at,
            formatted_ends_at=format_tashkent_datetime(active.ends_at),
            is_active=(active.status == "active" and active.ends_at > utcnow()),
            channel_url=channel_url,
            winners_snapshot=active.winners_snapshot,
            total_subscribers_gained=active.total_subscribers_gained,
        )
    }


@router.get("/my-stats", response_model=MyContestStatsOut)
async def get_my_contest_stats(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bot_username = "sakuraaa_chinese_shop_bot"
    if bot:
        try:
            bot_me = await bot.get_me()
            bot_username = bot_me.username
        except Exception:
            pass

    info = await get_user_contest_info(db, bot_username, user.id)
    return MyContestStatsOut(**info)


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_contest_leaderboard(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_contest(db)
    if not active:
        return []
    board = await compute_leaderboard(db, active.id, limit=limit)
    return [LeaderboardEntry(**b) for b in board]


# ==================== ADMIN ENDPOINTS ====================
@admin_router.post("/create", response_model=ContestOut)
async def create_contest(
    payload: ContestCreate,
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_contest(db)
    if active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faol konkurs allaqachon mavjud! Yangi boshlashdan oldin eskisini yakunlang.",
        )

    if payload.ends_at <= utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tugash vaqti kelajakda bo'lishi kerak.",
        )

    new_c = Contest(
        prize_1=payload.prize_1,
        prize_2=payload.prize_2,
        prize_3=payload.prize_3,
        photo_file_id=payload.photo_file_id,
        ends_at=payload.ends_at,
        only_new_subscribers=payload.only_new_subscribers,
        status="active",
        created_at=utcnow(),
    )
    db.add(new_c)
    await db.commit()
    await db.refresh(new_c)

    # Post to channel if configured
    channel_id, channel_url = await get_channel_info(db)
    if channel_id and bot:
        bot_username = "sakuraaa_chinese_shop_bot"
        try:
            bot_me = await bot.get_me()
            bot_username = bot_me.username
        except Exception:
            pass

        text = build_contest_announcement_text(new_c)
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Qatnashish", url=f"https://t.me/{bot_username}?start=konkurs")]
            ]
        )
        try:
            if new_c.photo_file_id:
                sent = await bot.send_photo(chat_id=channel_id, photo=new_c.photo_file_id, caption=text, reply_markup=markup)
            else:
                sent = await bot.send_message(chat_id=channel_id, text=text, reply_markup=markup)
            new_c.channel_message_id = sent.message_id
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to post contest announcement: {e}")

    return ContestOut(
        id=new_c.id,
        prize_1=new_c.prize_1,
        prize_2=new_c.prize_2,
        prize_3=new_c.prize_3,
        photo_file_id=new_c.photo_file_id,
        channel_message_id=new_c.channel_message_id,
        status=new_c.status,
        only_new_subscribers=new_c.only_new_subscribers,
        created_at=new_c.created_at,
        ends_at=new_c.ends_at,
        formatted_ends_at=format_tashkent_datetime(new_c.ends_at),
        is_active=True,
        channel_url=channel_url,
    )


@admin_router.put("/prizes", response_model=ContestOut)
async def update_contest_prizes(
    payload: ContestUpdatePrizes,
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_contest(db)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faol konkurs topilmadi.")

    active.prize_1 = payload.prize_1
    active.prize_2 = payload.prize_2
    active.prize_3 = payload.prize_3
    await db.commit()

    channel_id, channel_url = await get_channel_info(db)
    if channel_id and active.channel_message_id and bot:
        text = build_contest_announcement_text(active)
        try:
            if active.photo_file_id:
                await bot.edit_message_caption(chat_id=channel_id, message_id=active.channel_message_id, caption=text)
            else:
                await bot.edit_message_text(chat_id=channel_id, message_id=active.channel_message_id, text=text)
        except Exception as e:
            logger.warning(f"Could not edit channel announcement: {e}")

    return ContestOut(
        id=active.id,
        prize_1=active.prize_1,
        prize_2=active.prize_2,
        prize_3=active.prize_3,
        photo_file_id=active.photo_file_id,
        channel_message_id=active.channel_message_id,
        status=active.status,
        only_new_subscribers=active.only_new_subscribers,
        created_at=active.created_at,
        ends_at=active.ends_at,
        formatted_ends_at=format_tashkent_datetime(active.ends_at),
        is_active=True,
        channel_url=channel_url,
    )


@admin_router.post("/extend", response_model=ContestOut)
async def extend_contest(
    payload: ContestExtend,
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_contest(db)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faol konkurs topilmadi.")

    if payload.additional_days:
        active.ends_at = active.ends_at + timedelta(days=payload.additional_days)
    elif payload.new_ends_at:
        if payload.new_ends_at <= utcnow():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tugash vaqti kelajakda bo'lishi kerak.")
        active.ends_at = payload.new_ends_at

    await db.commit()
    _, channel_url = await get_channel_info(db)

    return ContestOut(
        id=active.id,
        prize_1=active.prize_1,
        prize_2=active.prize_2,
        prize_3=active.prize_3,
        photo_file_id=active.photo_file_id,
        channel_message_id=active.channel_message_id,
        status=active.status,
        only_new_subscribers=active.only_new_subscribers,
        created_at=active.created_at,
        ends_at=active.ends_at,
        formatted_ends_at=format_tashkent_datetime(active.ends_at),
        is_active=True,
        channel_url=channel_url,
    )


@admin_router.post("/end-now")
async def end_contest_now(
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_contest(db)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faol konkurs topilmadi.")

    revoked_count = await final_recheck_contest(db, bot, active.id)
    board = await compute_leaderboard(db, active.id, limit=3)

    return {
        "status": "pending_approval",
        "revoked_count": revoked_count,
        "preliminary_winners": board,
    }


@admin_router.post("/cancel")
async def cancel_contest(
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_contest(db)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faol konkurs topilmadi.")

    active.status = "cancelled"
    await db.commit()
    return {"status": "cancelled", "message": "Konkurs bekor qilindi."}


@admin_router.get("/suspicious", response_model=List[SuspiciousUserItem])
async def get_suspicious_users(
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_contest(db)
    if not active:
        return []
    res = await get_suspicious_activity(db, active.id)
    return [SuspiciousUserItem(**r) for r in res]


@admin_router.get("/user-check/{user_id}")
async def check_user_invites(
    user_id: int,
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_contest(db)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faol konkurs topilmadi.")

    target_res = await db.execute(select(User).where(User.telegram_id == user_id))
    target = target_res.scalars().first()

    ref_res = await db.execute(
        select(ContestReferral).where(
            ContestReferral.contest_id == active.id,
            ContestReferral.referrer_id == user_id,
        )
    )
    referrals = ref_res.scalars().all()

    inv_list = []
    for r in referrals:
        iu_res = await db.execute(select(User).where(User.telegram_id == r.invitee_id))
        iu = iu_res.scalars().first()
        inv_list.append({
            "invitee_id": r.invitee_id,
            "name": iu.name if iu else f"ID: {r.invitee_id}",
            "username": iu.username if iu else None,
            "status": r.status,
            "started_at": r.started_at,
            "confirmed_at": r.confirmed_at,
        })

    return {
        "user_id": user_id,
        "name": target.name if target else f"ID: {user_id}",
        "username": target.username if target else None,
        "total_invites": len(referrals),
        "confirmed_invites": len([r for r in referrals if r.status == "confirmed"]),
        "revoked_invites": len([r for r in referrals if r.status == "revoked"]),
        "invites": inv_list,
    }


@admin_router.post("/disqualify")
async def disqualify_participant(
    payload: DisqualifyPayload,
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_contest(db)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faol konkurs topilmadi.")

    dq_list = list(active.disqualified_user_ids or [])
    if payload.user_id not in dq_list:
        dq_list.append(payload.user_id)
        active.disqualified_user_ids = dq_list
        await db.commit()

    return {"status": "disqualified", "user_id": payload.user_id, "reason": payload.reason}


@admin_router.post("/approve-results")
async def approve_results(
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Find active or pending_approval contest
    res = await db.execute(
        select(Contest)
        .where(Contest.status.in_(["active", "pending_approval"]))
        .order_by(Contest.created_at.desc())
    )
    c = res.scalars().first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tasdiqlanadigan konkurs topilmadi.")

    result = await approve_and_announce_winners(db, bot, c.id)
    return result


@admin_router.get("/history")
async def get_contests_history(
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Contest)
        .where(Contest.status.in_(["completed", "cancelled"]))
        .order_by(Contest.created_at.desc())
    )
    contests = res.scalars().all()

    out = []
    for c in contests:
        out.append({
            "id": c.id,
            "prize_1": c.prize_1,
            "prize_2": c.prize_2,
            "prize_3": c.prize_3,
            "status": c.status,
            "created_at": c.created_at,
            "ends_at": c.ends_at,
            "total_subscribers_gained": c.total_subscribers_gained,
            "winners_snapshot": c.winners_snapshot or [],
        })
    return out
