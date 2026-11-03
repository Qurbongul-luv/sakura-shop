"""
Network side of the Taobao import: short-link resolving, the Apify scraper call, image download.

Every failure is raised as TaobaoFetchError carrying a message the admin can act on, so the bot
never goes silent. The Apify token comes from the APIFY_TOKEN environment variable only.
"""
import asyncio
import logging
from typing import Optional
from urllib.parse import urljoin, urlsplit

import httpx

from api.config import settings
from api.services.taobao import (
    SHORT_LINK_HOSTS,
    TaobaoItem,
    item_id_from_text,
    item_id_from_url,
    normalize_image_url,
    parse_item,
)

logger = logging.getLogger(__name__)

APIFY_RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
# Apify keeps a synchronous run open for at most 300 s; one product normally takes well under 60 s.
APIFY_RUN_TIMEOUT_SECONDS = 120
APIFY_HTTP_TIMEOUT_SECONDS = APIFY_RUN_TIMEOUT_SECONDS + 20
APIFY_RETRIES = 2
RETRY_BACKOFF_SECONDS = 3.0

SHORT_LINK_TIMEOUT_SECONDS = 15
SHORT_LINK_MAX_HOPS = 5
SHORT_LINK_MAX_BODY = 300_000
# Redirect targets a share link may pass through; anything else stops the walk.
_REDIRECT_HOST_SUFFIXES = SHORT_LINK_HOSTS + ("taobao.com", "tmall.com")

IMAGE_TIMEOUT_SECONDS = 20
MAX_IMAGE_BYTES = 9 * 1024 * 1024  # under Telegram's 10 MB photo limit
_BROWSER_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


class TaobaoFetchError(Exception):
    """Carries an Uzbek message that is shown to the admin as is."""


def _allowed_redirect(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return urlsplit(url).scheme == "https" and any(
        host == sfx or host.endswith("." + sfx) for sfx in _REDIRECT_HOST_SUFFIXES
    )


async def resolve_short_link(url: str, client: Optional[httpx.AsyncClient] = None) -> str:
    """Follows a m.tb.cn share link hop by hop (Taobao hosts only) and returns the item id."""
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=SHORT_LINK_TIMEOUT_SECONDS, headers={"User-Agent": _BROWSER_UA})
    try:
        current = url
        for _ in range(SHORT_LINK_MAX_HOPS):
            if not _allowed_redirect(current):
                break
            found = item_id_from_url(current)
            if found:
                return found
            try:
                resp = await client.get(current, follow_redirects=False)
            except httpx.HTTPError as e:
                logger.warning(f"Short link hop failed for {current}: {e}")
                break
            location = resp.headers.get("location")
            if resp.is_redirect and location:
                current = urljoin(current, location)
                continue
            # The share page itself embeds the product URL in a script.
            found = item_id_from_text(resp.text[:SHORT_LINK_MAX_BODY])
            if found:
                return found
            break
        found = item_id_from_url(current)
        if found:
            return found
    finally:
        if own_client:
            await client.aclose()
    raise TaobaoFetchError(
        "⚠️ Qisqa havoladan mahsulotni aniqlab bo'lmadi. Taobao'da mahsulotni brauzerda oching va "
        "to'liq havolani yuboring (unda <code>id=</code> bo'ladi)."
    )


def _apify_error(status: int) -> TaobaoFetchError:
    if status == 401:
        return TaobaoFetchError("⛔ Apify token noto'g'ri. Render → Environment'da <code>APIFY_TOKEN</code> ni tekshiring.")
    if status in (402, 403):
        return TaobaoFetchError("💳 Apify krediti tugagan yoki ruxsat yo'q. apify.com → Billing'ni tekshiring.")
    if status == 404:
        return TaobaoFetchError("⚠️ Apify actor topilmadi. <code>APIFY_TAOBAO_ACTOR</code> sozlamasini tekshiring.")
    if status == 408:
        return TaobaoFetchError("⏳ Taobao juda sekin javob berdi. Birozdan keyin qayta yuboring.")
    return TaobaoFetchError(f"⚠️ Apify xatosi ({status}). Birozdan keyin qayta urinib ko'ring.")


async def fetch_item(item_id: str, client: Optional[httpx.AsyncClient] = None) -> TaobaoItem:
    token = (settings.APIFY_TOKEN or "").strip()
    if not token:
        raise TaobaoFetchError(
            "⚙️ Taobao import hali ulanmagan: Render → Environment'ga <code>APIFY_TOKEN</code> qo'shing."
        )
    url = APIFY_RUN_URL.format(actor=settings.APIFY_TAOBAO_ACTOR)
    payload = {"productUrls": [item_id], "maxConcurrency": 1}
    params = {"timeout": APIFY_RUN_TIMEOUT_SECONDS, "clean": "true"}
    headers = {"Authorization": f"Bearer {token}"}

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=APIFY_HTTP_TIMEOUT_SECONDS)
    try:
        for attempt in range(APIFY_RETRIES + 1):
            try:
                resp = await client.post(url, json=payload, params=params, headers=headers)
            except httpx.HTTPError as e:
                logger.warning(f"Apify request failed (attempt {attempt + 1}) for item {item_id}: {e}")
                if attempt < APIFY_RETRIES:
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise TaobaoFetchError("📡 Apify'ga ulanib bo'lmadi. Birozdan keyin qayta urinib ko'ring.") from e

            if resp.status_code >= 500 and attempt < APIFY_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            if resp.status_code not in (200, 201):
                logger.warning(f"Apify returned {resp.status_code} for item {item_id}: {resp.text[:300]}")
                raise _apify_error(resp.status_code)
            try:
                rows = resp.json()
            except ValueError as e:
                raise TaobaoFetchError("⚠️ Apify noto'g'ri javob qaytardi. Qayta urinib ko'ring.") from e
            break
    finally:
        if own_client:
            await client.aclose()

    if not isinstance(rows, list):
        raise TaobaoFetchError("⚠️ Apify noto'g'ri javob qaytardi. Qayta urinib ko'ring.")
    for row in rows:
        item = parse_item(row, fallback_id=item_id)
        if item:
            return item
    raise TaobaoFetchError(
        "😔 Bu mahsulotni Taobao'dan o'qib bo'lmadi (o'chirilgan, yopiq yoki narxi/rasmi yo'q). "
        "Boshqa havola yuboring yoki mahsulotni qo'lda qo'shing."
    )


async def download_image(url: str, client: Optional[httpx.AsyncClient] = None) -> Optional[bytes]:
    """Image bytes from a Taobao CDN URL, or None (wrong host, too big, not an image, network error)."""
    safe_url = normalize_image_url(url)
    if not safe_url:
        return None
    own_client = client is None
    client = client or httpx.AsyncClient(
        timeout=IMAGE_TIMEOUT_SECONDS, headers={"User-Agent": _BROWSER_UA, "Referer": "https://item.taobao.com/"}
    )
    try:
        async with client.stream("GET", safe_url, follow_redirects=False) as resp:
            if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image/"):
                return None
            chunks = []
            size = 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    return None
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError as e:
        logger.info(f"Image download failed for {safe_url}: {e}")
        return None
    finally:
        if own_client:
            await client.aclose()
