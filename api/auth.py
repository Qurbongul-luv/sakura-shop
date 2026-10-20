import hashlib
import hmac
import json
import time
from typing import Optional, Dict, Any
from urllib.parse import parse_qsl, unquote

from fastapi import Header, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from db.models import Admin, User
from db.session import get_db


class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = "uz"
    is_admin: bool = False
    is_owner: bool = False


def verify_telegram_init_data(init_data_raw: str, bot_token: str, max_age_seconds: int = 86400) -> Dict[str, Any]:
    """
    Validate Telegram WebApp initData using HMAC-SHA256.
    Rejects stale auth_date values older than 24 hours.
    """
    if not init_data_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram initData header"
        )

    # Local browser dev preview convenience
    if settings.DEV_BROWSER_MODE and init_data_raw in ("dev_browser_mode", "browser_dev_mode"):
        return {
            "user": json.dumps({
                "id": 12345678,
                "first_name": "Sakura",
                "last_name": "Admin",
                "username": "fkhrdnvvvva",
                "language_code": "uz"
            }),
            "auth_date": str(int(time.time())),
            "hash": "mock_hash"
        }

    parsed = dict(parse_qsl(init_data_raw, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)

    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing hash in Telegram initData"
        )

    # Check auth_date
    auth_date_str = parsed.get("auth_date")
    if not auth_date_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing auth_date in Telegram initData"
        )

    try:
        auth_date = int(auth_date_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth_date in Telegram initData"
        )

    current_time = int(time.time())
    if current_time - auth_date > max_age_seconds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram initData has expired (>24 hours)"
        )

    # Construct data_check_string
    data_check_list = [f"{k}={v}" for k, v in sorted(parsed.items())]
    data_check_string = "\n".join(data_check_list)

    # Compute secret key and hash
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram initData signature (tampered data)"
        )

    return parsed


async def get_current_user_optional(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
    db: AsyncSession = Depends(get_db),
) -> Optional[TelegramUser]:
    """
    Extract user from Telegram initData if provided.
    If not provided or invalid, returns None (for public browsing).
    """
    if not x_telegram_init_data:
        return None

    try:
        parsed = verify_telegram_init_data(x_telegram_init_data, settings.BOT_TOKEN)
        user_raw = parsed.get("user")
        if not user_raw:
            return None
        user_dict = json.loads(user_raw)
        tg_id = int(user_dict["id"])

        # Check admin role from DB
        res = await db.execute(select(Admin).where(Admin.telegram_id == tg_id))
        admin_rec = res.scalars().first()

        is_dev_browser = settings.DEV_BROWSER_MODE and x_telegram_init_data in ("dev_browser_mode", "browser_dev_mode")
        is_dev_admin = (settings.DEV_ADMIN_ID is not None and tg_id == settings.DEV_ADMIN_ID)
        is_admin = (admin_rec is not None) or is_dev_admin or is_dev_browser
        is_owner = (admin_rec is not None and admin_rec.role == "owner") or is_dev_admin or is_dev_browser

        return TelegramUser(
            id=tg_id,
            first_name=user_dict.get("first_name", ""),
            last_name=user_dict.get("last_name"),
            username=user_dict.get("username"),
            language_code=user_dict.get("language_code", "uz"),
            is_admin=is_admin,
            is_owner=is_owner,
        )
    except Exception:
        return None


async def get_current_user(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
    db: AsyncSession = Depends(get_db),
) -> TelegramUser:
    """
    Require valid Telegram initData and return authenticated user.
    """
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Telegram-Init-Data header is required"
        )

    parsed = verify_telegram_init_data(x_telegram_init_data, settings.BOT_TOKEN)
    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User data missing from initData"
        )

    try:
        user_dict = json.loads(user_raw)
        tg_id = int(user_dict["id"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed user data in initData"
        )

    res = await db.execute(select(Admin).where(Admin.telegram_id == tg_id))
    admin_rec = res.scalars().first()

    is_dev_browser = settings.DEV_BROWSER_MODE and x_telegram_init_data in ("dev_browser_mode", "browser_dev_mode")
    is_dev_admin = (settings.DEV_ADMIN_ID is not None and tg_id == settings.DEV_ADMIN_ID)
    is_admin = (admin_rec is not None) or is_dev_admin or is_dev_browser
    is_owner = (admin_rec is not None and admin_rec.role == "owner") or is_dev_admin or is_dev_browser

    return TelegramUser(
        id=tg_id,
        first_name=user_dict.get("first_name", ""),
        last_name=user_dict.get("last_name"),
        username=user_dict.get("username"),
        language_code=user_dict.get("language_code", "uz"),
        is_admin=is_admin,
        is_owner=is_owner,
    )


async def require_admin(
    user: TelegramUser = Depends(get_current_user),
) -> TelegramUser:
    """
    Enforce that the authenticated user is an owner or admin in the database.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin huquqi talab qilinadi / Administrator access required"
        )
    return user
