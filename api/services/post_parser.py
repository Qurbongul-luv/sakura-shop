"""
Reads a product out of a channel post caption, e.g.:

    #boots
    🤎Narx: 145.000
    🤎Razmerlari bor
    🤎Ranglari: qora, jigarrang, молочный
    🤎Kargo: 100gr-12.000
    🐱Buyurtma berish uchun @fkhrdnvvvva ga yozing

Only labelled lines are trusted ("Narx: ..."), so a cargo rate or a delivery term is never
mistaken for the price. A post without a price is not a product and is ignored.
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

MIN_PRICE = 1000  # so'm; anything lower is a typo or a cargo rate, never a product price
MAX_TITLE_LEN = 255
MAX_SLUG_LEN = 100

REVIEW_TAGS = frozenset({"отзыв", "отзывы", "otziv", "otzyv", "fikr", "fikrlar", "review"})

_APOSTROPHES = str.maketrans({"ʻ": "'", "ʼ": "'", "’": "'", "‘": "'", "`": "'", "´": "'"})
_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
_LEADING_DECOR_RE = re.compile(r"^[^\w#]+", re.UNICODE)
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:[.,\s]\d{3})+|\d+)\s*(k\b|ming\b|тыс)?", re.IGNORECASE)
_SOM_AMOUNT_RE = re.compile(
    r"(\d{1,3}(?:[.,\s]\d{3})+|\d+)\s*(?:so'm|som\b|sum\b|сум|сўм)", re.IGNORECASE
)
_LIST_SPLIT_RE = re.compile(r"\s*(?:[,;/|]|\s\bva\b\s|\s\bи\b\s)\s*", re.IGNORECASE)

_PRICE_LABELS = ("narxi", "narx", "narhi", "narh", "нарх", "нархи", "цена", "price")
_TITLE_LABELS = ("nomi", "nom", "mahsulot", "название", "name")
_SIZE_LABELS = ("razmerlari", "razmerlar", "razmeri", "razmer", "o'lchamlari", "o'lchamlar", "o'lcham",
                "размеры", "размер", "sizes", "size")
_COLOR_LABELS = ("ranglari", "ranglar", "rangi", "rang", "цвета", "цвет", "colors", "color")
_WEIGHT_LABELS = ("og'irligi", "og'irlik", "vazni", "vazn", "вес", "weight")
# Lines that carry numbers but are never the price.
_NON_PRICE_WORDS = ("kargo", "cargo", "карго", "dastavka", "yetkazib", "доставка", "kun", "gr", "100g")
_NO_VALUE_WORDS = frozenset({"bor", "mavjud", "bor bor", "есть", "hammasi bor", "barcha razmerlar"})


@dataclass(frozen=True)
class ParsedPost:
    category: Optional[str]
    title: Optional[str]
    price: int
    sizes: Tuple[str, ...]
    colors: Tuple[str, ...]
    weight_grams: Optional[int]
    description: str
    is_review: bool

    @property
    def is_product(self) -> bool:
        return self.price >= MIN_PRICE and not self.is_review


def _normalize(line: str) -> str:
    return line.translate(_APOSTROPHES).strip()


def _strip_decor(line: str) -> str:
    """Drops leading emoji/bullets: '🤎Narx: 145.000' -> 'Narx: 145.000'."""
    return _LEADING_DECOR_RE.sub("", line).strip()


def _match_label(line: str, labels: Tuple[str, ...], require_colon: bool = False) -> Optional[str]:
    """Returns the value after a label ('Narx: 145.000' -> '145.000'), or None."""
    lower = line.lower()
    for label in labels:
        if lower.startswith(label):
            rest = line[len(label):]
            if rest and rest[0].isalpha():
                continue  # 'narxlar...' or 'rangli' is a different word
            if require_colon and not rest.lstrip().startswith(":"):
                continue  # 'Mahsulot sifati zo'r' is a sentence, not a title
            return rest.lstrip(" :-–—=").strip()
    return None


def parse_amount(value: str) -> int:
    """'145.000' / '145 000 so'm' / '1.250.000' / '145k' / '145 ming' -> so'm, or 0."""
    m = _AMOUNT_RE.search(value)
    if not m:
        return 0
    amount = int(re.sub(r"[.,\s]", "", m.group(1)))
    if m.group(2):
        amount *= 1000
    return amount if amount >= MIN_PRICE else 0


def _split_list(value: str) -> Tuple[str, ...]:
    if value.strip().lower() in _NO_VALUE_WORDS:
        return ()
    parts = [p.strip(" .") for p in _LIST_SPLIT_RE.split(value)]
    return tuple(p for p in parts if p and p.lower() not in _NO_VALUE_WORDS)


def _parse_weight(value: str) -> Optional[int]:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|кг)?", value, re.IGNORECASE)
    if not m:
        return None
    number = float(m.group(1).replace(",", "."))
    grams = int(round(number * 1000)) if m.group(2) else int(number)
    return grams if grams > 0 else None


def _fallback_price(lines: List[str]) -> int:
    """Unlabelled price, only when written with a currency word and not on a cargo/delivery line."""
    for line in lines:
        lower = line.lower()
        if any(word in lower for word in _NON_PRICE_WORDS):
            continue
        m = _SOM_AMOUNT_RE.search(line)
        if m:
            amount = parse_amount(m.group(1))
            if amount:
                return amount
    return 0


def clean_slug(tag: str) -> str:
    return tag.lower()[:MAX_SLUG_LEN]


def parse_product_post(text: Optional[str]) -> ParsedPost:
    raw = (text or "").strip()
    lines = [_normalize(l) for l in raw.splitlines() if l.strip()]

    tags = [clean_slug(t) for t in _HASHTAG_RE.findall(raw)]
    is_review = any(t in REVIEW_TAGS for t in tags)
    category = next((t for t in tags if t not in REVIEW_TAGS), None)

    title: Optional[str] = None
    price = 0
    sizes: Tuple[str, ...] = ()
    colors: Tuple[str, ...] = ()
    weight: Optional[int] = None

    for line in lines:
        body = _strip_decor(line)
        if not body:
            continue
        if not price and (value := _match_label(body, _PRICE_LABELS)) is not None:
            price = parse_amount(value)
        elif not title and (value := _match_label(body, _TITLE_LABELS, require_colon=True)):
            title = value
        elif not sizes and (value := _match_label(body, _SIZE_LABELS)) is not None:
            sizes = _split_list(value)
        elif not colors and (value := _match_label(body, _COLOR_LABELS)) is not None:
            colors = _split_list(value)
        elif weight is None and (value := _match_label(body, _WEIGHT_LABELS)) is not None:
            weight = _parse_weight(value)

    if not price:
        price = _fallback_price(lines)

    if not title:
        title = _title_from_lines(lines)

    return ParsedPost(
        category=category,
        title=title[:MAX_TITLE_LEN] if title else None,
        price=price,
        sizes=sizes,
        colors=colors,
        weight_grams=weight,
        description=raw,
        is_review=is_review,
    )


def _title_from_lines(lines: List[str]) -> Optional[str]:
    """
    Title written next to the hashtag ('#jempir Pushti jempir') or on a '✨ ...' line,
    which is how the bot's own channel posts carry it.
    """
    for line in lines:
        if line.startswith("#"):
            rest = _strip_decor(_HASHTAG_RE.sub("", line))
            if rest:
                return rest
        if line.startswith("✨"):
            rest = _strip_decor(line)
            if rest:
                return rest
    return None
