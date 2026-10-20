from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Setting
from db.session import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=Dict[str, Any])
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Setting))
    rows = res.scalars().all()
    data = {s.key: s.value for s in rows}

    return {
        "cargo_rate": int(data.get("cargo_rate", 12000)),
        "delivery_days": data.get("delivery_days", "10–15 kun"),
        "delivery_scope": data.get("delivery_scope", "O'zbekiston bo'ylab"),
        "payment_terms": data.get("payment_terms", "100% oldindan to'lov"),
        "location": data.get("location", "Toshkent"),
        "contact_username": data.get("contact_username", "fkhrdnvvvva"),
        "channel_url": data.get("channel_url", "https://t.me/sakuraaa_chinese_shop"),
        "has_linked_channel": bool(data.get("channel_id")),
        "welcome_text": data.get("welcome_text", "Sakura shop ga xush kelibsiz! 🌸"),
    }
