"""Regression tests for the issues found in the code review."""
import pytest
from fastapi import HTTPException

from api.auth import verify_telegram_init_data
from api.config import settings
from api.services.formatters import build_order_summary, build_channel_caption
from bot.handlers import admin, admin_contest
from bot.services.contest_service import (
    final_recheck_contest,
    approve_and_announce_winners,
    compute_leaderboard,
    build_contest_announcement_text,
)
from db.models import Contest, ContestReferral, User, utcnow
from tests.conftest import TEST_BOT_TOKEN
from tests.test_contest import create_mock_bot, seed_active_contest


def test_dev_browser_mode_rejected_by_default():
    assert settings.DEV_BROWSER_MODE is False
    with pytest.raises(HTTPException) as exc_info:
        verify_telegram_init_data("dev_browser_mode", TEST_BOT_TOKEN)
    assert exc_info.value.status_code == 401


def test_dev_browser_mode_only_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "DEV_BROWSER_MODE", True)
    parsed = verify_telegram_init_data("dev_browser_mode", TEST_BOT_TOKEN)
    assert "user" in parsed


def _filter_callbacks(observer):
    return [f.callback for f in observer._handler.filters or []]


def test_admin_routers_guard_every_button():
    assert admin.admin_only in _filter_callbacks(admin.router.callback_query)
    assert admin_contest.admin_only in _filter_callbacks(admin_contest.router.callback_query)
    assert admin_contest.admin_only in _filter_callbacks(admin_contest.router.message)


@pytest.mark.asyncio
async def test_recheck_keeps_points_when_telegram_errors(test_db_session):
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        session.add(User(telegram_id=10001, name="Referrer"))
        session.add_all([
            ContestReferral(contest_id=contest.id, invitee_id=80001, referrer_id=10001, status="confirmed", confirmed_at=utcnow()),
            ContestReferral(contest_id=contest.id, invitee_id=80002, referrer_id=10001, status="confirmed", confirmed_at=utcnow()),
        ])
        await session.commit()

        bot = create_mock_bot({80002: "left"})
        original = bot.get_chat_member.side_effect

        async def flaky(chat_id, user_id):
            if user_id == 80001:
                raise RuntimeError("network down")
            return await original(chat_id, user_id)

        bot.get_chat_member.side_effect = flaky

        revoked = await final_recheck_contest(session, bot, contest.id)
        assert revoked == 1  # only the user who really left
        board = await compute_leaderboard(session, contest.id)
        assert board[0]["score"] == 1  # the unreachable user's point is kept


@pytest.mark.asyncio
async def test_recheck_never_reopens_completed_contest(test_db_session):
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        contest.status = "completed"
        await session.commit()

        assert await final_recheck_contest(session, create_mock_bot(), contest.id) == 0
        await session.refresh(contest)
        assert contest.status == "completed"


@pytest.mark.asyncio
async def test_winners_announced_only_once(test_db_session):
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        session.add(User(telegram_id=99001, name="Winner"))
        session.add(ContestReferral(contest_id=contest.id, invitee_id=99003, referrer_id=99001, status="confirmed", confirmed_at=utcnow()))
        contest.status = "pending_approval"
        await session.commit()

        bot = create_mock_bot()
        first = await approve_and_announce_winners(session, bot, contest.id)
        calls_after_first = bot.send_message.await_count
        second = await approve_and_announce_winners(session, bot, contest.id)

        assert len(first["winners"]) == 1
        assert second.get("already_announced") is True
        assert bot.send_message.await_count == calls_after_first  # nothing posted twice
        await session.refresh(contest)
        assert contest.status == "completed"


@pytest.mark.asyncio
async def test_winner_name_with_html_chars_is_escaped(test_db_session):
    async with test_db_session() as session:
        contest = await seed_active_contest(session)
        session.add(User(telegram_id=99001, name="Tom & <Jerry>"))
        session.add(ContestReferral(contest_id=contest.id, invitee_id=99003, referrer_id=99001, status="confirmed", confirmed_at=utcnow()))
        await session.commit()

        bot = create_mock_bot()
        await approve_and_announce_winners(session, bot, contest.id)
        texts = [c.kwargs["text"] for c in bot.send_message.await_args_list]
        assert any("Tom &amp; &lt;Jerry&gt;" in t for t in texts)
        assert not any("<Jerry>" in t for t in texts)


def test_announcement_escapes_prizes():
    contest = Contest(prize_1="Sumka & sharf", prize_2="<b>", prize_3="ok", ends_at=utcnow())
    text = build_contest_announcement_text(contest)
    assert "Sumka &amp; sharf" in text
    assert "&lt;b&gt;" in text


def test_order_summary_escapes_customer_and_items():
    summary = build_order_summary(
        order_id=1,
        user_id=1,
        customer_name="A&B <script>",
        customer_username=None,
        items=[{"title": "Sumka <3", "price": 1000, "qty": 1, "size": "S&M"}],
        total=1000,
    )
    for key in ("admin_text", "customer_text"):
        assert "<script>" not in summary[key]
        assert "A&amp;B" in summary[key]
        assert "Sumka &lt;3" in summary[key]
    assert "A&B <script>" in summary["copyable_block"]  # plain text stays readable


def test_channel_caption_escapes_title():
    caption = build_channel_caption("sumka", 45000, title="Sumka & sharf")
    assert "Sumka &amp; sharf" in caption
