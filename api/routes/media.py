import os
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, Response

from api.config import settings
from bot.loader import bot

router = APIRouter(prefix="/media", tags=["media"])
logger = logging.getLogger(__name__)

MEDIA_DIR = Path(settings.MEDIA_CACHE_DIR)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


FALLBACK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400">
  <rect width="100%" height="100%" fill="#FFE4EC"/>
  <circle cx="200" cy="200" r="140" fill="#FFD1DC" opacity="0.6"/>
  <text x="50%" y="45%" text-anchor="middle" font-family="sans-serif" font-size="64">🌸</text>
  <text x="50%" y="60%" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="20" fill="#E75480">Sakura Shop</text>
  <text x="50%" y="68%" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#5B3A4A">Rasm yuklanmoqda...</text>
</svg>"""


@router.get("/{file_id}")
async def get_media_file(file_id: str):
    # Sanitize file_id to prevent directory traversal
    clean_id = Path(file_id).name

    # 1. Check local cache
    cached_path = MEDIA_DIR / clean_id
    if cached_path.is_file():
        return FileResponse(str(cached_path))

    # Also check with .png or .jpg extension if not provided
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        alt_path = MEDIA_DIR / f"{clean_id}{ext}"
        if alt_path.is_file():
            return FileResponse(str(alt_path))

    # 2. Try proxying from Telegram via bot.get_file
    if bot:
        try:
            tg_file = await bot.get_file(file_id)
            if tg_file and tg_file.file_path:
                ext = Path(tg_file.file_path).suffix or ".jpg"
                save_dest = MEDIA_DIR / f"{clean_id}{ext}"
                await bot.download_file(tg_file.file_path, destination=str(save_dest))
                if save_dest.is_file():
                    return FileResponse(str(save_dest))
        except Exception as e:
            logger.warning(f"Could not retrieve file_id '{file_id}' from Telegram: {e}")

    # 3. Fallback: return cute pink placeholder SVG
    return Response(content=FALLBACK_SVG, media_type="image/svg+xml")
