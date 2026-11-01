import pytest
from datetime import datetime, timezone, timedelta

from db.models import Contest, ContestReferral, User, utcnow
from bot.services.fraud_check import (
    FLAG_BLANK_NAME,
    FLAG_BURST,
    FLAG_NEW_ACCOUNT,
    FLAG_NO_USERNAME,
    LEVEL_GREEN,
    LEVEL_RED,
    LEVEL_YELLOW,
    analyze_contest_referrers,
    build_referrer_report,
    find_burst_positions,
    is_blank_name,
    rate_level,
)

BASE = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
OLD_ID = 500_000_000
NEW_ID = 8_300_000_000


def test_blank_name_detects_invisible_tricks():
    assert is_blank_name(None)
    assert is_blank_name("")
    # The exact name seen on the live leaderboard's 1st place: Hangul filler + variation selectors.
    assert is_blank_name("ᅠ ︎︎")
    assert is_blank_name("­­­")
    assert is_blank_name("ㅤ​")
    assert not is_blank_name("Saidov_na")
    assert not is_blank_name("ш.")
    assert not is_blank_name("ᅠ a")


def test_burst_marks_only_dense_windows():
    spaced = [BASE + timedelta(hours=i) for i in range(6)]
    assert find_burst_positions(spaced) == set()

    dense = [BASE + timedelta(minutes=i) for i in range(5)]
    assert find_burst_positions(dense) == {0, 1, 2, 3, 4}

    four_dense_then_far = [BASE + timedelta(minutes=i) for i in range(4)] + [BASE + timedelta(hours=3)]
    assert find_burst_positions(four_dense_then_far) == set()


def test_burst_window_edge_is_inclusive():
    times = [BASE + timedelta(minutes=2.5 * i) for i in range(5)]  # spans exactly 10 minutes
    assert find_burst_positions(times) == {0, 1, 2, 3, 4}


def test_rate_level_thresholds():
    assert rate_level(2, 2) == LEVEL_GREEN  # too few to judge
    assert rate_level(10, 6) == LEVEL_RED
    assert rate_level(10, 3) == LEVEL_YELLOW
    assert rate_level(10, 2) == LEVEL_GREEN
    assert rate_level(0, 0) == LEVEL_GREEN


def test_honest_friends_stay_green():
    rows = [(OLD_ID + i, f"Do'st {i}", f"friend{i}", BASE + timedelta(hours=i)) for i in range(10)]
    report = build_referrer_report(1, "Ref", "ref", rows)
    assert report.level == LEVEL_GREEN
    assert report.suspicious == 0
    assert all(not s.flags for s in report.invitees)


def test_single_signal_is_not_suspicious():
    # Real people may have a fresh account; one flag alone never counts.
    rows = [(NEW_ID + i, f"Real {i}", f"real{i}", BASE + timedelta(hours=i)) for i in range(10)]
    report = build_referrer_report(1, "Ref", None, rows)
    assert report.flag_counts[FLAG_NEW_ACCOUNT] == 10
    assert report.suspicious == 0
    assert report.level == LEVEL_GREEN


def test_farm_pattern_is_red():
    rows = [(NEW_ID + i, "ㅤ", None, BASE + timedelta(seconds=30 * i)) for i in range(20)]
    report = build_referrer_report(1, "ᅠ", None, rows)
    assert report.level == LEVEL_RED
    assert report.suspicious == 20
    assert report.flag_counts == {
        FLAG_NEW_ACCOUNT: 20,
        FLAG_NO_USERNAME: 20,
        FLAG_BLANK_NAME: 20,
        FLAG_BURST: 20,
    }


def test_missing_timestamps_and_naive_datetimes_are_handled():
    rows = [
        (NEW_ID, None, None, None),
        (NEW_ID + 1, "A", None, BASE.replace(tzinfo=None)),
        (OLD_ID, "B", "b", BASE + timedelta(minutes=1)),
    ]
    report = build_referrer_report(1, "Ref", "ref", rows)
    assert report.total == 3
    no_time = next(s for s in report.invitees if s.invitee_id == NEW_ID)
    assert no_time.confirmed_at is None
    assert FLAG_BURST not in no_time.flags
    assert no_time.is_suspicious  # new account + no username + blank name
    assert all(s.confirmed_at is None or s.confirmed_at.tzinfo is not None for s in report.invitees)


@pytest.mark.asyncio
async def test_analyze_contest_referrers_from_db(test_db_session):
    async with test_db_session() as session:
        contest = Contest(
            prize_1="A", prize_2="B", prize_3="C",
            ends_at=utcnow() + timedelta(days=7), status="active", created_at=utcnow(),
        )
        session.add(contest)
        farmer_id, honest_id = 7_000_000_001, 7_000_000_002
        session.add_all([
            User(telegram_id=farmer_id, name="ᅠ ︎︎", username=None),
            User(telegram_id=honest_id, name="Honest", username="honest"),
        ])
        await session.commit()
        await session.refresh(contest)

        start = utcnow() - timedelta(hours=5)
        for i in range(8):
            inv = NEW_ID + i
            session.add(User(telegram_id=inv, name="ㅤ", username=None))
            session.add(ContestReferral(
                contest_id=contest.id, invitee_id=inv, referrer_id=farmer_id,
                status="confirmed", started_at=start, confirmed_at=start + timedelta(seconds=20 * i),
            ))
        for i in range(4):
            inv = OLD_ID + i
            session.add(User(telegram_id=inv, name=f"Friend {i}", username=f"friend{i}"))
            session.add(ContestReferral(
                contest_id=contest.id, invitee_id=inv, referrer_id=honest_id,
                status="confirmed", started_at=start, confirmed_at=start + timedelta(hours=i),
            ))
        # Revoked invites are ignored: they no longer give points.
        session.add(User(telegram_id=NEW_ID + 100, name="ㅤ", username=None))
        session.add(ContestReferral(
            contest_id=contest.id, invitee_id=NEW_ID + 100, referrer_id=honest_id,
            status="revoked", started_at=start,
        ))
        await session.commit()

        reports = await analyze_contest_referrers(session, contest.id)
        assert [r.referrer_id for r in reports] == [farmer_id, honest_id]
        farmer, honest = reports
        assert farmer.level == LEVEL_RED and farmer.suspicious == 8 and farmer.total == 8
        assert honest.level == LEVEL_GREEN and honest.total == 4
        assert honest.username == "honest"

        only_honest = await analyze_contest_referrers(session, contest.id, [honest_id])
        assert [r.referrer_id for r in only_honest] == [honest_id]
        assert await analyze_contest_referrers(session, contest.id, []) == []
