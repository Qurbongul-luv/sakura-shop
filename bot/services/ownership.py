import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from db.models import Admin, Setting

# The default that ships in the public repo; it must never grant ownership.
DEFAULT_SETUP_CODE = "sakura_owner_secret_998877_setup"
MIN_SETUP_CODE_LENGTH = 16
INVITE_SETTING_KEY = "owner_invite_code"


def setup_code_is_safe() -> bool:
    code = settings.OWNER_SETUP_CODE or ""
    return len(code) >= MIN_SETUP_CODE_LENGTH and code != DEFAULT_SETUP_CODE


async def claim_ownership(
    session: AsyncSession,
    code: str,
    user_id: int,
    full_name: str,
    username: Optional[str],
) -> str:
    """
    Returns "claimed", "already_owner" or "invalid".
    - OWNER_SETUP_CODE works only while the shop has no owner yet (first claim).
    - After that, new owners need a single-use invite created by an existing owner.
    """
    code = (code or "").strip()
    me = (await session.execute(select(Admin).where(Admin.telegram_id == user_id))).scalars().first()
    if me and me.role == "owner":
        return "already_owner"
    if not code:
        return "invalid"

    # Single-use invite: the conditional delete succeeds for exactly one claimer.
    used_invite = await session.execute(
        delete(Setting).where(Setting.key == INVITE_SETTING_KEY, Setting.value == code)
    )
    valid = used_invite.rowcount == 1

    if not valid:
        owner_exists = (
            await session.execute(select(Admin.telegram_id).where(Admin.role == "owner"))
        ).first() is not None
        valid = (
            not owner_exists
            and setup_code_is_safe()
            and hmac.compare_digest(code.encode("utf-8"), settings.OWNER_SETUP_CODE.encode("utf-8"))
        )

    if not valid:
        await session.rollback()
        return "invalid"

    if me:
        me.role = "owner"
    else:
        session.add(Admin(telegram_id=user_id, name=full_name or "Owner", username=username, role="owner"))

    now_iso = datetime.now(timezone.utc).isoformat()
    claimed = (await session.execute(select(Setting).where(Setting.key == "owner_claimed_at"))).scalars().first()
    if claimed:
        claimed.value = now_iso
    else:
        session.add(Setting(key="owner_claimed_at", value=now_iso))

    await session.commit()
    return "claimed"


async def create_owner_invite(session: AsyncSession) -> str:
    """Creates a fresh single-use owner invite token, replacing any unused older one."""
    token = secrets.token_urlsafe(24)
    existing = (await session.execute(select(Setting).where(Setting.key == INVITE_SETTING_KEY))).scalars().first()
    if existing:
        existing.value = token
    else:
        session.add(Setting(key=INVITE_SETTING_KEY, value=token))
    await session.commit()
    return token
