"""
Pure Taobao helpers: recognising links in a message, validating the scraper's item payload,
and turning a yuan price into a shop price with the owner's own formula. No network here.
"""
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import parse_qs, urlsplit

MAX_IMAGES = 10
MAX_ITEM_ID_LEN = 20
MIN_YUAN_RATE = 100
MAX_YUAN_RATE = 100_000

# Hosts whose product pages carry the item id in the URL itself.
_PRODUCT_HOSTS = (
    "item.taobao.com", "detail.tmall.com", "world.taobao.com", "h5.m.taobao.com",
    "m.intl.taobao.com", "detail.m.tmall.com", "market.m.taobao.com", "item.m.taobao.com",
)
# Share links from the Taobao app ("https://m.tb.cn/h.5xYz?tk=...") redirect to a product page.
SHORT_LINK_HOSTS = ("m.tb.cn", "e.tb.cn", "tb.cn")
# Image hosts the bot may download from; anything else is refused (no fetching arbitrary URLs).
IMAGE_HOST_SUFFIXES = (".alicdn.com", ".taobaocdn.com", ".tbcdn.cn")

_URL_RE = re.compile(r"https?://[^\s<>\"'「」【】]+", re.IGNORECASE)
_PATH_ID_RE = re.compile(r"/(?:item|i)/?(\d{6,20})\.htm", re.IGNORECASE)
_ANY_ID_RE = re.compile(r"[?&]id=(\d{6,20})")


@dataclass(frozen=True)
class TaobaoLink:
    url: str
    item_id: Optional[str]  # None for a short link that still has to be resolved

    @property
    def is_short(self) -> bool:
        return self.item_id is None


@dataclass(frozen=True)
class TaobaoItem:
    item_id: str
    title: str
    price_yuan: float
    images: Tuple[str, ...]
    url: str
    category_path: Tuple[str, ...]


@dataclass(frozen=True)
class PriceRule:
    yuan_rate: int  # so'm per 1 yuan
    markup_percent: float = 0.0
    markup_fixed: int = 0  # so'm added after the percentage
    round_to: int = 1000  # final price is rounded UP to this step

    @property
    def is_configured(self) -> bool:
        return self.yuan_rate > 0


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _host_matches(host: str, allowed: Tuple[str, ...]) -> bool:
    return any(host == a or host.endswith("." + a) for a in allowed)


def item_id_from_url(url: str) -> Optional[str]:
    """Item id from a full product URL, or None."""
    if not _host_matches(_host(url), _PRODUCT_HOSTS):
        return None
    parts = urlsplit(url)
    for key in ("id", "itemId", "item_id"):
        values = parse_qs(parts.query).get(key)
        if values and values[0].isdigit() and len(values[0]) <= MAX_ITEM_ID_LEN:
            return values[0]
    m = _PATH_ID_RE.search(parts.path)
    return m.group(1) if m else None


def item_id_from_text(text: str) -> Optional[str]:
    """Item id inside a resolved page URL or page body (used after following a short link)."""
    m = _ANY_ID_RE.search(text) or _PATH_ID_RE.search(text)
    return m.group(1) if m else None


def find_taobao_link(text: Optional[str]) -> Optional[TaobaoLink]:
    """First Taobao/Tmall link in a message, including the app's long share text."""
    for raw in _URL_RE.findall(text or ""):
        url = raw.rstrip(".,;:!?)」】")
        host = _host(url)
        if _host_matches(host, SHORT_LINK_HOSTS):
            return TaobaoLink(url=url, item_id=None)
        item_id = item_id_from_url(url)
        if item_id:
            return TaobaoLink(url=url, item_id=item_id)
    return None


def normalize_image_url(url: Any) -> Optional[str]:
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if not url.startswith("https://"):
        return None
    host = _host(url)
    if not any(host.endswith(sfx) or host == sfx.lstrip(".") for sfx in IMAGE_HOST_SUFFIXES):
        return None
    return url


def _positive_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        m = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
        if not m:
            return None
        number = float(m.group(0))
    else:
        return None
    return number if number > 0 and math.isfinite(number) else None


def parse_item(row: Mapping[str, Any], fallback_id: Optional[str] = None) -> Optional[TaobaoItem]:
    """Validates one scraper row; None when it is unusable (no price or no photo)."""
    if not isinstance(row, Mapping):
        return None
    promo = _positive_number(row.get("promoPrice"))
    price = promo or _positive_number(row.get("price"))
    if price is None:
        return None

    raw_images: List[Any] = list(row.get("images") or []) if isinstance(row.get("images"), list) else []
    raw_images.insert(0, row.get("imageUrl"))
    images: List[str] = []
    for raw in raw_images:
        candidate = raw.get("url") if isinstance(raw, Mapping) else raw
        url = normalize_image_url(candidate)
        if url and url not in images:
            images.append(url)
    if not images:
        return None

    item_id = str(row.get("itemId") or fallback_id or "").strip()
    if not item_id.isdigit() or len(item_id) > MAX_ITEM_ID_LEN:
        return None
    title = str(row.get("title") or "").strip()[:255]
    path = row.get("categoryPath")
    category_path = tuple(str(p) for p in path if p) if isinstance(path, list) else ()
    return TaobaoItem(
        item_id=item_id,
        title=title,
        price_yuan=round(price, 2),
        images=tuple(images[:MAX_IMAGES]),
        url=str(row.get("url") or f"https://item.taobao.com/item.htm?id={item_id}"),
        category_path=category_path,
    )


def calculate_price(price_yuan: float, rule: PriceRule) -> int:
    """yuan × rate, plus percent, plus fixed, rounded up to the step (so a price is never undercut)."""
    if not rule.is_configured or price_yuan <= 0:
        return 0
    raw = price_yuan * rule.yuan_rate * (1 + rule.markup_percent / 100) + rule.markup_fixed
    step = max(1, rule.round_to)
    return int(math.ceil(round(raw, 6) / step) * step)


def calculate_cost(price_yuan: float, rule: PriceRule) -> Optional[int]:
    """Purchase cost in so'm (yuan × rate, no markup), for the owner's profit report."""
    if not rule.is_configured or price_yuan <= 0:
        return None
    return int(math.ceil(round(price_yuan * rule.yuan_rate, 6)))


SETTING_RATE = "taobao_yuan_rate"
SETTING_PERCENT = "taobao_markup_percent"
SETTING_FIXED = "taobao_markup_fixed"
SETTING_ROUND = "taobao_round_to"


def rule_from_settings(values: Mapping[str, str]) -> PriceRule:
    def _int(key: str, default: int) -> int:
        try:
            return max(0, int(float(values.get(key, default))))
        except (TypeError, ValueError):
            return default

    def _float(key: str, default: float) -> float:
        try:
            number = float(values.get(key, default))
            return number if math.isfinite(number) and number >= 0 else default
        except (TypeError, ValueError):
            return default

    return PriceRule(
        yuan_rate=_int(SETTING_RATE, 0),
        markup_percent=_float(SETTING_PERCENT, 0.0),
        markup_fixed=_int(SETTING_FIXED, 0),
        round_to=_int(SETTING_ROUND, 1000) or 1000,
    )


def rule_to_settings(rule: PriceRule) -> Dict[str, str]:
    percent = int(rule.markup_percent) if float(rule.markup_percent).is_integer() else rule.markup_percent
    return {
        SETTING_RATE: str(rule.yuan_rate),
        SETTING_PERCENT: str(percent),
        SETTING_FIXED: str(rule.markup_fixed),
        SETTING_ROUND: str(rule.round_to),
    }


def parse_rule_input(text: str) -> Optional[PriceRule]:
    """
    Owner types 2–4 numbers: 'kurs foiz [foyda] [yaxlitlash]', e.g. '1800 30 20000 1000'.
    Thousand separators inside a number are allowed ('20.000').
    """
    # Spaces separate the numbers, so only '.' and ',' may group thousands.
    numbers = re.findall(r"\d+(?:[.,]\d+)*", text or "")
    values: List[float] = []
    for compact in numbers:
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", compact):
            compact = re.sub(r"[.,]", "", compact)
        else:
            compact = compact.replace(",", ".")
        try:
            values.append(float(compact))
        except ValueError:
            return None
    if not 2 <= len(values) <= 4:
        return None
    rate = int(values[0])
    # A yuan is worth well over 100 so'm; '1 800 30' (a space inside the rate) must be re-asked, not saved as 1.
    if not MIN_YUAN_RATE <= rate <= MAX_YUAN_RATE or values[1] > 1000:
        return None
    return PriceRule(
        yuan_rate=rate,
        markup_percent=values[1],
        markup_fixed=int(values[2]) if len(values) > 2 else 0,
        round_to=int(values[3]) if len(values) > 3 and values[3] >= 1 else 1000,
    )
