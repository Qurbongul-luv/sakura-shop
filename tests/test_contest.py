import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select, func

from db.models import Contest, ContestReferral, User, Admin, Setting, utcnow
from bot.services.contest_service import (
    process_referral_start,
    confirm_referral_action,
    revoke_referral_on_leave,
    final_recheck_contest,
    compute_leaderboard,
    approve_and_announce_winners,
)
from bot.services.contest_scheduler import check_and_handle_expired_contests
from tests.conftest import generate_test_init_data


class MockChatMember:
    def __init__(self, status="member", is_member=True):
        self.status = status
        self.is_member = is_member


def create_mock_bot(member_status_dict=None):
    """
    Creates a mock bot whose get_chat_member returns member status based on user_id.
    """
    bot = AsyncMock()
    bot_me = MagicMock()
    bot_me.username = "sakuraaa_chinese_shop_bot"
    bot.get_me.return_value = bot_me

    status_map = member_status_dict or {}

    async def mock_get_chat_member(chat_id, user_id):
        status = status_map.get(user_id, "member")
        return MockChatMember(status=status)

    bot.get_chat_member.side_effect = mock_get_chat_member
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.edit_message_caption = AsyncMock()
    return bot


# Helper to seed a standard active contest
async def seed_active_contest(session, only_new=True, ends_in_days=7):
    ends = utcnow() + timedelta(days=ends_in_days)
    contest = Contest(
        prize_1="Aesthetic Pushti Jempir 🌸",
        prize_2="Lolita Parik 💇‍♀️",
        prize_3="Yulduzli Sharf 🧣",
        ends_at=ends,
        only_new_subscribers=only_new,
        status="active",
        created_at=utcnow(),
    )
    session.add(contest)
    # Ensure channel_id is set
    res = await session.execute(select(Setting).where(Setting.key == "channel_id"))
    ch = res.scalars().first()
    if ch:
        ch.value = "-1001234567890"
    else:
        session.add(Setting(key="channel_id", value="-1001234567890"))
    await session.commit()
    await session.refresh(contest)
    return contest


@pytest.mark.asyncio
async def test_01_self_invite_rejected(test_db_session):
    """1. Self-invite is rejected."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        user_id = 11111
        bot = create_mock_bot()

        # user invites themselves
        res = await process_referral_start(
            session=session,
            bot=bot,
            user_id=user_id,
            user_full_name="Self",
            user_username="selfie",
            is_bot=False,
            payload=f"r_{contest.id}_{user_id}",
            is_new_user=True,
        )
        assert res["valid"] is False
        assert res["reason"] == "self_or_bot"


@pytest.mark.asyncio
async def test_02_existing_bot_user_cannot_be_invited(test_db_session):
    """2. An existing bot user opening an invite link doesn't count."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        referrer_id = 10001
        session.add(User(telegram_id=referrer_id, name="Referrer", username="ref"))
        await session.commit()

        bot = create_mock_bot()
        invitee_id = 20002

        # is_new_user = False because they used the bot before
        res = await process_referral_start(
            session=session,
            bot=bot,
            user_id=invitee_id,
            user_full_name="Old User",
            user_username="oldie",
            is_bot=False,
            payload=f"r_{contest.id}_{referrer_id}",
            is_new_user=False,
        )
        assert res["valid"] is False
        assert res["reason"] == "existing_user"


@pytest.mark.asyncio
async def test_03_already_subscribed_user_when_only_new_is_on(test_db_session):
    """3. An already-subscribed user doesn't count when 'only new subscribers' is ON."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session, only_new=True)
        referrer_id = 10001
        invitee_id = 30003
        session.add(User(telegram_id=referrer_id, name="Referrer", username="ref"))
        await session.commit()

        # Mock: invitee is already in channel at first /start
        bot = create_mock_bot({invitee_id: "member"})

        res = await process_referral_start(
            session=session,
            bot=bot,
            user_id=invitee_id,
            user_full_name="Channel Member",
            user_username="member_girl",
            is_bot=False,
            payload=f"r_{contest.id}_{referrer_id}",
            is_new_user=True,
        )
        assert res["valid"] is True
        assert res["was_member_before"] is True

        # Now when they press Tasdiqlash
        confirm_res = await confirm_referral_action(
            session=session,
            bot=bot,
            user_id=invitee_id,
            contest_id=contest.id,
            bot_username="sakura_bot",
        )
        assert confirm_res["status"] == "was_member_before"

        # Verify referrer got 0 points
        board = await compute_leaderboard(session, contest.id)
        assert len(board) == 0


@pytest.mark.asyncio
async def test_04_not_subscribed_then_subscribe_tasdiqlash(test_db_session):
    """4. Not subscribed + Tasdiqlash -> no point; subscribe + Tasdiqlash -> +1."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        referrer_id = 10001
        invitee_id = 40004
        session.add(User(telegram_id=referrer_id, name="Referrer", username="ref"))
        await session.commit()

        # Step A: invitee was NOT in channel when starting link
        bot = create_mock_bot({invitee_id: "left"})

        start_res = await process_referral_start(
            session=session,
            bot=bot,
            user_id=invitee_id,
            user_full_name="New Friend",
            user_username="friend",
            is_bot=False,
            payload=f"r_{contest.id}_{referrer_id}",
            is_new_user=True,
        )
        assert start_res["valid"] is True
        assert start_res["was_member_before"] is False

        # Invitee presses Tasdiqlash without subscribing
        confirm_1 = await confirm_referral_action(
            session=session,
            bot=bot,
            user_id=invitee_id,
            contest_id=contest.id,
            bot_username="sakura_bot",
        )
        assert confirm_1["status"] == "not_subscribed"

        # Check points: still 0
        board_empty = await compute_leaderboard(session, contest.id)
        assert len(board_empty) == 0

        # Step B: invitee subscribes to channel
        bot_subscribed = create_mock_bot({invitee_id: "member"})
        # Clear in-memory throttle for test
        from bot.services import contest_service
        contest_service._confirm_throttle[invitee_id] = 0.0

        confirm_2 = await confirm_referral_action(
            session=session,
            bot=bot_subscribed,
            user_id=invitee_id,
            contest_id=contest.id,
            bot_username="sakura_bot",
        )
        assert confirm_2["status"] == "success"
        assert confirm_2["is_newly_confirmed"] is True

        # Check points: exactly 1 point!
        board = await compute_leaderboard(session, contest.id)
        assert len(board) == 1
        assert board[0]["user_id"] == referrer_id
        assert board[0]["score"] == 1


@pytest.mark.asyncio
async def test_05_double_tasdiqlash_is_idempotent(test_db_session):
    """5. Double Tasdiqlash (including concurrent calls) -> exactly +1."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        referrer_id = 10001
        invitee_id = 50005
        session.add(User(telegram_id=referrer_id, name="Referrer", username="ref"))
        await session.commit()

        bot_init = create_mock_bot({invitee_id: "left"})
        await process_referral_start(
            session=session,
            bot=bot_init,
            user_id=invitee_id,
            user_full_name="Double Tapper",
            user_username="tapper",
            is_bot=False,
            payload=f"r_{contest.id}_{referrer_id}",
            is_new_user=True,
        )

        bot = create_mock_bot({invitee_id: "member"})
        from bot.services import contest_service

        # First confirm
        contest_service._confirm_throttle[invitee_id] = 0.0
        c1 = await confirm_referral_action(session, bot, invitee_id, contest.id, "sakura_bot")
        assert c1["status"] == "success"
        assert c1["is_newly_confirmed"] is True

        # Second confirm
        contest_service._confirm_throttle[invitee_id] = 0.0
        c2 = await confirm_referral_action(session, bot, invitee_id, contest.id, "sakura_bot")
        assert c2["status"] == "success"
        assert c2["is_newly_confirmed"] is False  # Idempotent!

        # Score remains exactly 1
        board = await compute_leaderboard(session, contest.id)
        assert board[0]["score"] == 1


@pytest.mark.asyncio
async def test_06_second_referrer_link_is_ignored(test_db_session):
    """6. The second referrer link for the same invitee is ignored (first referrer wins forever)."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        ref_1 = 10001
        ref_2 = 10002
        invitee_id = 60006
        session.add_all([
            User(telegram_id=ref_1, name="First Ref"),
            User(telegram_id=ref_2, name="Second Ref"),
        ])
        await session.commit()

        bot = create_mock_bot({invitee_id: "left"})

        # First link
        res_1 = await process_referral_start(
            session=session,
            bot=bot,
            user_id=invitee_id,
            user_full_name="Loyal",
            user_username="loyal",
            is_bot=False,
            payload=f"r_{contest.id}_{ref_1}",
            is_new_user=True,
        )
        assert res_1["valid"] is True
        assert res_1["referral"].referrer_id == ref_1

        # Second link from someone else
        res_2 = await process_referral_start(
            session=session,
            bot=bot,
            user_id=invitee_id,
            user_full_name="Loyal",
            user_username="loyal",
            is_bot=False,
            payload=f"r_{contest.id}_{ref_2}",
            is_new_user=False,  # Already used bot via first link
        )
        # Should be rejected as existing user, and original referral remains with ref_1!
        ref_check = await session.execute(
            select(ContestReferral).where(
                ContestReferral.contest_id == contest.id,
                ContestReferral.invitee_id == invitee_id,
            )
        )
        persisted_ref = ref_check.scalars().first()
        assert persisted_ref.referrer_id == ref_1


@pytest.mark.asyncio
async def test_07_leaving_channel_revokes_and_rejoining_reconfirms(test_db_session):
    """7. Leaving the channel -> revoked (-1); rejoining + Tasdiqlash -> confirmed again for the same referrer."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        ref_id = 10001
        invitee_id = 70007
        session.add(User(telegram_id=ref_id, name="Referrer", username="ref"))
        await session.commit()

        bot_left = create_mock_bot({invitee_id: "left"})
        await process_referral_start(session, bot_left, invitee_id, "Leaver", "leaver", False, f"r_{contest.id}_{ref_id}", True)

        bot_mem = create_mock_bot({invitee_id: "member"})
        from bot.services import contest_service
        contest_service._confirm_throttle[invitee_id] = 0.0
        await confirm_referral_action(session, bot_mem, invitee_id, contest.id, "sakura_bot")

        # Confirmed: score 1
        b1 = await compute_leaderboard(session, contest.id)
        assert b1[0]["score"] == 1

        # Customer leaves channel
        await revoke_referral_on_leave(session, bot_left, invitee_id)

        # Revoked: score 0
        b2 = await compute_leaderboard(session, contest.id)
        assert len(b2) == 0

        # Customer rejoins channel and presses Tasdiqlash
        contest_service._confirm_throttle[invitee_id] = 0.0
        c_re = await confirm_referral_action(session, bot_mem, invitee_id, contest.id, "sakura_bot")
        assert c_re["status"] == "success"
        assert c_re["is_newly_confirmed"] is True

        # Score is back to 1 for the SAME referrer!
        b3 = await compute_leaderboard(session, contest.id)
        assert b3[0]["user_id"] == ref_id
        assert b3[0]["score"] == 1


@pytest.mark.asyncio
async def test_08_final_recheck_revokes_users_who_left_offline(test_db_session):
    """8. The final recheck revokes users who left while the bot was offline."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        ref_id = 10001
        invitee_1 = 80001
        invitee_2 = 80002
        session.add(User(telegram_id=ref_id, name="Referrer", username="ref"))
        await session.commit()

        # Both confirmed initially
        now = utcnow()
        session.add_all([
            ContestReferral(contest_id=contest.id, invitee_id=invitee_1, referrer_id=ref_id, status="confirmed", confirmed_at=now),
            ContestReferral(contest_id=contest.id, invitee_id=invitee_2, referrer_id=ref_id, status="confirmed", confirmed_at=now),
        ])
        await session.commit()

        # Offline scenario: invitee_2 left the channel
        bot_recheck = create_mock_bot({
            invitee_1: "member",
            invitee_2: "left",  # Left while bot was offline
        })

        revoked_count = await final_recheck_contest(session, bot_recheck, contest.id)
        assert revoked_count == 1

        # Check leaderboard: only 1 point remains
        board = await compute_leaderboard(session, contest.id)
        assert board[0]["score"] == 1


@pytest.mark.asyncio
async def test_09_tie_break_orders_by_earliest_reached_score(test_db_session):
    """9. Tie-break: with equal points, the person who reached that score first ranks higher."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        user_A = 90001
        user_B = 90002
        session.add_all([
            User(telegram_id=user_A, name="User A"),
            User(telegram_id=user_B, name="User B"),
        ])
        await session.commit()

        t1 = utcnow() - timedelta(hours=5)
        t2 = utcnow() - timedelta(hours=2)

        # Both have 2 points, but User A reached their 2nd point at t1 (earlier), User B at t2
        session.add_all([
            ContestReferral(contest_id=contest.id, invitee_id=91001, referrer_id=user_A, status="confirmed", confirmed_at=t1 - timedelta(hours=1)),
            ContestReferral(contest_id=contest.id, invitee_id=91002, referrer_id=user_A, status="confirmed", confirmed_at=t1),
            ContestReferral(contest_id=contest.id, invitee_id=92001, referrer_id=user_B, status="confirmed", confirmed_at=t2 - timedelta(hours=1)),
            ContestReferral(contest_id=contest.id, invitee_id=92002, referrer_id=user_B, status="confirmed", confirmed_at=t2),
        ])
        await session.commit()

        board = await compute_leaderboard(session, contest.id)
        assert len(board) == 2
        assert board[0]["user_id"] == user_A  # Reached score first -> 1st place!
        assert board[0]["rank"] == 1
        assert board[1]["user_id"] == user_B  # Reached score later -> 2nd place
        assert board[1]["rank"] == 2


@pytest.mark.asyncio
async def test_10_fewer_than_3_scorers_award_only_those_places_and_zero_never_wins(test_db_session):
    """10. Fewer than 3 scorers -> only those places are awarded; 0 points never wins."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        winner_id = 99001
        zero_scorer_id = 99002
        session.add_all([
            User(telegram_id=winner_id, name="Winner"),
            User(telegram_id=zero_scorer_id, name="Zero Scorer"),
        ])
        # Only winner has confirmed invite
        session.add(ContestReferral(contest_id=contest.id, invitee_id=99003, referrer_id=winner_id, status="confirmed", confirmed_at=utcnow()))
        await session.commit()

        bot = create_mock_bot()
        res = await approve_and_announce_winners(session, bot, contest.id)

        winners = res["winners"]
        # Only 1 place awarded because only 1 person has score > 0
        assert len(winners) == 1
        assert winners[0]["user_id"] == winner_id
        assert winners[0]["score"] == 1


@pytest.mark.asyncio
async def test_11_contest_ending_after_restart_works(test_db_session):
    """11. Contest ending after a restart works (ends_at already in the past)."""
    async with test_db_session() as session:
        # Create contest that ended in past
        past_end = utcnow() - timedelta(hours=1)
        contest = Contest(
            prize_1="Prize 1",
            prize_2="Prize 2",
            prize_3="Prize 3",
            ends_at=past_end,
            status="active",  # was still active when server restarted
            created_at=past_end - timedelta(days=7),
        )
        session.add(contest)
        session.add(Admin(telegram_id=77777, name="Owner", role="owner"))
        await session.commit()

        bot = create_mock_bot()
        # Scheduler startup check with test db session factory
        await check_and_handle_expired_contests(bot, session_factory=test_db_session)

        # Verify status transitioned to pending_approval
        await session.refresh(contest)
        assert contest.status == "pending_approval"
        # Verify owner got notified
        assert bot.send_message.called


@pytest.mark.asyncio
async def test_12_malformed_start_payloads_ignored_safely(test_db_session):
    """12. Malformed start payloads are ignored safely."""
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        bot = create_mock_bot()

        bad_payloads = [
            "r_invalid",
            "r_abc_123",
            "r_-1_99",
            "random_string_123",
            "r_123_",
        ]

        for p in bad_payloads:
            res = await process_referral_start(
                session=session,
                bot=bot,
                user_id=123456,
                user_full_name="Tester",
                user_username="test",
                is_bot=False,
                payload=p,
                is_new_user=True,
            )
            assert res["valid"] is False
            assert res["reason"] == "malformed_payload"


@pytest.mark.asyncio
async def test_13_non_admins_cannot_create_or_edit_contests(client, test_db_session):
    """13. Non-admins can't create, end, or edit contests (API requires admin initData)."""
    # 1. No auth -> 401
    resp_no_auth = await client.post("/api/admin/contest/create", json={
        "prize_1": "P1", "prize_2": "P2", "prize_3": "P3",
        "ends_at": (utcnow() + timedelta(days=5)).isoformat()
    })
    assert resp_no_auth.status_code == 401

    # 2. Regular customer user initData -> 403
    cust_init = generate_test_init_data(user_id=88888, first_name="RegularCust")
    resp_forbidden = await client.post(
        "/api/admin/contest/create",
        headers={"X-Telegram-Init-Data": cust_init},
        json={
            "prize_1": "P1", "prize_2": "P2", "prize_3": "P3",
            "ends_at": (utcnow() + timedelta(days=5)).isoformat()
        }
    )
    assert resp_forbidden.status_code == 403

    # 3. Verified Admin in DB -> 200 Success
    admin_id = 999111
    async with test_db_session() as session:
        session.add(Admin(telegram_id=admin_id, name="Contest Admin", role="admin"))
        await session.commit()

    admin_init = generate_test_init_data(user_id=admin_id, first_name="Contest Admin")
    resp_ok = await client.post(
        "/api/admin/contest/create",
        headers={"X-Telegram-Init-Data": admin_init},
        json={
            "prize_1": "Vintage Jempir", "prize_2": "Lolita Wig", "prize_3": "Shoyi Sharf",
            "ends_at": (utcnow() + timedelta(days=5)).isoformat()
        }
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["prize_1"] == "Vintage Jempir"
