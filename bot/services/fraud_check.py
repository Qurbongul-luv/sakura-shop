"""
Passive anti-cheat scoring for contest referrals.

Nothing here touches the invitee flow: it only reads confirmed referrals and rates each
referrer so the admin can decide. It never revokes points or disqualifies anyone itself,
because real people also have fresh accounts or no username.
"""
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ContestReferral, User
from bot.services.contest_service import ensure_utc

# Telegram hands out IDs roughly in order; IDs above this belong to accounts created from ~2025 on.
NEW_ACCOUNT_ID_THRESHOLD = 8_000_000_000
# This many confirmations for one referrer inside the window looks like a farm, not friends.
BURST_WINDOW = timedelta(minutes=10)
BURST_MIN_CONFIRMS = 5
# An invitee counts as suspicious only when several signals agree.
FLAGS_FOR_SUSPICIOUS_INVITEE = 2
RED_RATIO = 0.6
YELLOW_RATIO = 0.3
# Too few invites to judge a ratio fairly.
MIN_INVITES_TO_RATE = 3

FLAG_NEW_ACCOUNT = "new_account"
FLAG_NO_USERNAME = "no_username"
FLAG_BLANK_NAME = "blank_name"
FLAG_BURST = "burst"

FLAG_LABELS: Dict[str, str] = {
    FLAG_NEW_ACCOUNT: "yangi akkaunt",
    FLAG_NO_USERNAME: "username yo'q",
    FLAG_BLANK_NAME: "ko'rinmas ism",
    FLAG_BURST: "to'lqin bo'lib kelgan",
}

LEVEL_RED = "red"
LEVEL_YELLOW = "yellow"
LEVEL_GREEN = "green"
LEVEL_EMOJI: Dict[str, str] = {LEVEL_RED: "🔴", LEVEL_YELLOW: "🟡", LEVEL_GREEN: "🟢"}
_LEVEL_ORDER: Dict[str, int] = {LEVEL_RED: 0, LEVEL_YELLOW: 1, LEVEL_GREEN: 2}

# Letters Unicode does not class as invisible but that render as blank space.
_BLANK_LOOKING_CHARS = frozenset({"ᅟ", "ᅠ", "ㅤ", "ﾠ", "⠀"})
_INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Mn", "Me", "Zs", "Zl", "Zp"})
_NO_TIME = datetime.min.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class InviteeSignal:
    invitee_id: int
    name: Optional[str]
    username: Optional[str]
    confirmed_at: Optional[datetime]
    flags: FrozenSet[str]

    @property
    def is_suspicious(self) -> bool:
        return len(self.flags) >= FLAGS_FOR_SUSPICIOUS_INVITEE


@dataclass(frozen=True)
class ReferrerFraudReport:
    referrer_id: int
    name: Optional[str]
    username: Optional[str]
    total: int
    suspicious: int
    flag_counts: Mapping[str, int]
    level: str
    invitees: Tuple[InviteeSignal, ...]

    @property
    def suspicious_ratio(self) -> float:
        return self.suspicious / self.total if self.total else 0.0


def is_blank_name(name: Optional[str]) -> bool:
    """True when a display name has no visible character at all."""
    if not name:
        return True
    return all(
        ch in _BLANK_LOOKING_CHARS or unicodedata.category(ch) in _INVISIBLE_CATEGORIES
        for ch in name
    )


def find_burst_positions(times: Sequence[datetime]) -> Set[int]:
    """
    Positions (in the given ascending order) that fall inside any BURST_WINDOW
    holding at least BURST_MIN_CONFIRMS confirmations. Linear two-pointer scan.
    """
    burst: Set[int] = set()
    left = 0
    last_marked = -1
    for right, current in enumerate(times):
        while current - times[left] > BURST_WINDOW:
            left += 1
        if right - left + 1 >= BURST_MIN_CONFIRMS:
            for pos in range(max(left, last_marked + 1), right + 1):
                burst.add(pos)
            last_marked = right
    return burst


def rate_level(total: int, suspicious: int) -> str:
    if total < MIN_INVITES_TO_RATE:
        return LEVEL_GREEN
    ratio = suspicious / total
    if ratio >= RED_RATIO:
        return LEVEL_RED
    if ratio >= YELLOW_RATIO:
        return LEVEL_YELLOW
    return LEVEL_GREEN


def build_referrer_report(
    referrer_id: int,
    referrer_name: Optional[str],
    referrer_username: Optional[str],
    invitees: Sequence[Tuple[int, Optional[str], Optional[str], Optional[datetime]]],
) -> ReferrerFraudReport:
    """Scores one referrer from (invitee_id, name, username, confirmed_at) rows."""
    ordered = sorted(
        invitees,
        key=lambda row: (row[3] is None, ensure_utc(row[3]) if row[3] else _NO_TIME),
    )
    timed = [ensure_utc(row[3]) for row in ordered if row[3] is not None]
    burst_positions = find_burst_positions(timed)

    signals: List[InviteeSignal] = []
    for pos, (invitee_id, name, username, confirmed_at) in enumerate(ordered):
        flags: Set[str] = set()
        if invitee_id >= NEW_ACCOUNT_ID_THRESHOLD:
            flags.add(FLAG_NEW_ACCOUNT)
        if not username:
            flags.add(FLAG_NO_USERNAME)
        if is_blank_name(name):
            flags.add(FLAG_BLANK_NAME)
        # Rows without a timestamp sort last, so their positions never reach the timed list.
        if confirmed_at is not None and pos in burst_positions:
            flags.add(FLAG_BURST)
        signals.append(
            InviteeSignal(
                invitee_id=invitee_id,
                name=name,
                username=username,
                confirmed_at=ensure_utc(confirmed_at) if confirmed_at else None,
                flags=frozenset(flags),
            )
        )

    flag_counts = {flag: sum(1 for s in signals if flag in s.flags) for flag in FLAG_LABELS}
    suspicious = sum(1 for s in signals if s.is_suspicious)
    return ReferrerFraudReport(
        referrer_id=referrer_id,
        name=referrer_name,
        username=referrer_username,
        total=len(signals),
        suspicious=suspicious,
        flag_counts=flag_counts,
        level=rate_level(len(signals), suspicious),
        invitees=tuple(signals),
    )


async def analyze_contest_referrers(
    session: AsyncSession,
    contest_id: int,
    referrer_ids: Optional[Sequence[int]] = None,
) -> List[ReferrerFraudReport]:
    """
    Rates every referrer with confirmed invites (or only `referrer_ids`), worst first.
    Two queries total: referrals joined with invitee users, then the referrers' own names.
    """
    stmt = (
        select(
            ContestReferral.referrer_id,
            ContestReferral.invitee_id,
            ContestReferral.confirmed_at,
            User.name,
            User.username,
        )
        .outerjoin(User, User.telegram_id == ContestReferral.invitee_id)
        .where(
            ContestReferral.contest_id == contest_id,
            ContestReferral.status == "confirmed",
        )
    )
    if referrer_ids is not None:
        if not referrer_ids:
            return []
        stmt = stmt.where(ContestReferral.referrer_id.in_(list(referrer_ids)))

    grouped: Dict[int, List[Tuple[int, Optional[str], Optional[str], Optional[datetime]]]] = {}
    for row in (await session.execute(stmt)).all():
        grouped.setdefault(row.referrer_id, []).append(
            (row.invitee_id, row.name, row.username, row.confirmed_at)
        )
    if not grouped:
        return []

    ref_users = (
        await session.execute(select(User).where(User.telegram_id.in_(list(grouped))))
    ).scalars().all()
    ref_by_id = {u.telegram_id: u for u in ref_users}

    reports = [
        build_referrer_report(
            referrer_id,
            ref_by_id[referrer_id].name if referrer_id in ref_by_id else None,
            ref_by_id[referrer_id].username if referrer_id in ref_by_id else None,
            rows,
        )
        for referrer_id, rows in grouped.items()
    ]
    return sorted(reports, key=lambda r: (_LEVEL_ORDER[r.level], -r.suspicious, -r.total))
