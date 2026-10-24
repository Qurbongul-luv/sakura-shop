"""Contests with up to 7 prize places (3 fixed fields + extra_prizes)."""
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from api.schemas import ContestCreate
from bot.handlers import contest as contest_handlers
from bot.handlers.admin_contest import parse_extra_prizes
from bot.services.contest_service import approve_and_announce_winners, build_contest_announcement_text
from db.models import Contest, ContestReferral, User, utcnow
from db.session import _add_missing_columns
from tests.test_contest import create_mock_bot, seed_active_contest

SEVEN = ["Jeans pants", "Baggy pants", "T shirt", "Brelok", "30% off", "Tg gift", "Tg gift"]


def _seven_prize_contest() -> Contest:
    return Contest(prize_1=SEVEN[0], prize_2=SEVEN[1], prize_3=SEVEN[2], extra_prizes=SEVEN[3:], ends_at=utcnow())


def test_prizes_property_lists_every_place_in_order():
    assert _seven_prize_contest().prizes == SEVEN
    legacy = Contest(prize_1="a", prize_2="b", prize_3="c", extra_prizes=None, ends_at=utcnow())
    assert legacy.prizes == ["a", "b", "c"]


def test_announcement_shows_all_seven_places():
    text_ = build_contest_announcement_text(_seven_prize_contest())
    assert "🥇 <b>1-o'rin:</b> Jeans pants" in text_
    assert "🥉 <b>3-o'rin:</b> T shirt" in text_
    assert "🏅 <b>5-o'rin:</b> 30% off" in text_
    assert "🏅 <b>7-o'rin:</b> Tg gift" in text_


def test_parse_extra_prizes():
    assert parse_extra_prizes("Brelok\n 30% off \n\nTg gift\nTg gift") == ["Brelok", "30% off", "Tg gift", "Tg gift"]
    assert parse_extra_prizes("a\nb\nc\nd\ne") is None  # 3 + 5 = 8 places is too many
    assert parse_extra_prizes(None) is None  # a photo instead of text must not wipe the prizes
    assert parse_extra_prizes("   ") is None


def test_api_rejects_more_than_seven_places():
    base = dict(prize_1="a", prize_2="b", prize_3="c", ends_at=utcnow() + timedelta(days=1))
    assert ContestCreate(**base, extra_prizes=SEVEN[3:]).extra_prizes == SEVEN[3:]
    with pytest.raises(ValidationError):
        ContestCreate(**base, extra_prizes=SEVEN[3:] + ["eighth"])


@pytest.mark.asyncio
async def test_seven_winners_each_get_their_own_prize(test_db_session):
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        contest.extra_prizes = SEVEN[3:]
        contest.prize_1, contest.prize_2, contest.prize_3 = SEVEN[:3]
        contest.status = "pending_approval"
        invitee = 5000
        for uid in range(1, 9):  # 8 scorers, user 1 has the most points
            session.add(User(telegram_id=uid, name=f"U{uid}"))
            for _ in range(10 - uid):
                invitee += 1
                session.add(ContestReferral(
                    contest_id=contest.id, invitee_id=invitee, referrer_id=uid,
                    status="confirmed", confirmed_at=utcnow(),
                ))
        await session.commit()

        bot = create_mock_bot()
        result = await approve_and_announce_winners(session, bot, contest.id)

        assert [w["user_id"] for w in result["winners"]] == [1, 2, 3, 4, 5, 6, 7]  # 8th place wins nothing
        dms = {c.kwargs["chat_id"]: c.kwargs["text"] for c in bot.send_message.await_args_list}
        assert "Sovg'angiz: <b>30% off</b>" in dms[5]
        assert "Sovg'angiz: <b>Jeans pants</b>" in dms[1]
        assert 8 not in dms
        channel_post = dms["-1001234567890"]
        assert "🏅 <b>7-o'rin:</b>" in channel_post and "(Tg gift)" in channel_post


@pytest.mark.asyncio
async def test_leaderboard_marks_all_prize_places(test_db_session):
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        contest.extra_prizes = SEVEN[3:]
        invitee = 7000
        for uid in range(1, 9):
            session.add(User(telegram_id=uid, name=f"U{uid}"))
            for _ in range(10 - uid):
                invitee += 1
                session.add(ContestReferral(
                    contest_id=contest.id, invitee_id=invitee, referrer_id=uid,
                    status="confirmed", confirmed_at=utcnow(),
                ))
        await session.commit()

        board, _ = await contest_handlers.build_leaderboard_view(session, contest.id, viewer_id=99)
        assert "🏅 U7 — " in board  # 7th place still wins a prize
        assert "<b>8.</b> U8 — " in board  # 8th place does not


@pytest.mark.asyncio
async def test_startup_adds_extra_prizes_column_to_existing_database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # Table as it exists on the deployed database before this change.
        await conn.execute(text(
            "CREATE TABLE contests (id INTEGER PRIMARY KEY, prize_1 VARCHAR, prize_2 VARCHAR, prize_3 VARCHAR)"
        ))
        await conn.execute(text("INSERT INTO contests VALUES (1, 'a', 'b', 'c')"))

        await conn.run_sync(_add_missing_columns)
        await conn.run_sync(_add_missing_columns)  # second startup must be a no-op

        columns = await conn.run_sync(lambda c: [col["name"] for col in inspect(c).get_columns("contests")])
        row = (await conn.execute(text("SELECT prize_1, extra_prizes FROM contests WHERE id = 1"))).one()
    await engine.dispose()

    assert "extra_prizes" in columns
    assert row == ("a", None)  # existing contest kept, no extra places
