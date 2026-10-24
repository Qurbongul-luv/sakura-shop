"""Reply-keyboard contest buttons and the live leaderboard with its refresh button."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from bot.handlers import contest as contest_handlers
from bot.keyboards.reply import CONTEST_BUTTON_TEXT, RATING_BUTTON_TEXT, get_main_reply_keyboard
from db.models import ContestReferral, User, utcnow
from tests.test_contest import seed_active_contest


def test_main_keyboard_has_contest_and_rating_buttons():
    labels = [button.text for row in get_main_reply_keyboard().keyboard for button in row]
    assert CONTEST_BUTTON_TEXT in labels
    assert RATING_BUTTON_TEXT in labels


async def _add_confirmed(session, contest_id, referrer_id, invitee_id):
    session.add(ContestReferral(
        contest_id=contest_id, invitee_id=invitee_id, referrer_id=referrer_id,
        status="confirmed", confirmed_at=utcnow(),
    ))
    await session.commit()


@pytest.mark.asyncio
async def test_refresh_shows_points_added_since_last_view(test_db_session):
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        session.add_all([User(telegram_id=1, name="Ali", username="ali"), User(telegram_id=2, name="Vali")])
        await session.commit()
        await _add_confirmed(session, contest.id, referrer_id=1, invitee_id=100)

        first, markup = await contest_handlers.build_leaderboard_view(session, contest.id, viewer_id=2)
        assert "@ali — <b>1</b> ball" in first
        assert "Siz hali ball to'plamadingiz" in first
        assert markup.inline_keyboard[0][0].callback_data == f"rating_refresh:{contest.id}"

        # Someone joins through Vali's link while the leaderboard is open; refresh must show it.
        await _add_confirmed(session, contest.id, referrer_id=2, invitee_id=101)
        await _add_confirmed(session, contest.id, referrer_id=2, invitee_id=102)
        second, _ = await contest_handlers.build_leaderboard_view(session, contest.id, viewer_id=2)
        assert "🥇 Vali — <b>2</b> ball ⬅️ <i>siz</i>" in second
        assert "🥈 @ali — <b>1</b> ball" in second
        assert "🕐 Yangilandi:" in second


@pytest.mark.asyncio
async def test_viewer_outside_top10_sees_own_place(test_db_session):
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        for uid in range(1, 13):
            session.add(User(telegram_id=uid, name=f"U{uid}"))
        await session.commit()
        invitee = 1000
        for uid in range(1, 13):
            for _ in range(13 - uid):  # user 1 has most points, user 12 the fewest
                invitee += 1
                await _add_confirmed(session, contest.id, uid, invitee)

        text, _ = await contest_handlers.build_leaderboard_view(session, contest.id, viewer_id=12)
        assert "U12 — " not in text.split("\n📍")[0]  # not inside the top-10 list
        assert "📍 Siz: <b>12-o'rin</b> — 1 ball" in text


@pytest.mark.asyncio
async def test_refresh_button_tolerates_unchanged_message(test_db_session, monkeypatch):
    monkeypatch.setattr(contest_handlers, "async_session_factory", test_db_session)
    async with test_db_session() as session:
        contest = await seed_active_contest(session)

    call = MagicMock()
    call.data = f"rating_refresh:{contest.id}"
    call.from_user = SimpleNamespace(id=5)
    call.message.edit_text = AsyncMock(
        side_effect=TelegramBadRequest(MagicMock(), "Bad Request: message is not modified")
    )
    call.answer = AsyncMock()

    await contest_handlers.handle_show_top10(call)  # must not raise

    call.message.edit_text.assert_awaited_once()
    call.answer.assert_awaited_once()
