import math
import re
from html import escape
from typing import Optional, List, Dict, Any


def format_price(price: int) -> str:
    """
    Format integer price with dot as thousands separator plus 'so'm'.
    Example: 99000 -> '99.000 so\'m'
             1250000 -> '1.250.000 so\'m'
             0 -> '0 so\'m'
    """
    if price is None:
        return "0 so'm"
    formatted = f"{int(price):,}".replace(",", ".")
    return f"{formatted} so'm"


def calculate_cargo(weight_grams: Optional[int], rate_per_100g: int = 12000) -> int:
    """
    Calculate cargo estimate from weight: ceil(weight / 100) * rate_per_100g.
    Example: 350g -> ceil(3.5) = 4 -> 4 * 12000 = 48.000 so'm
             180g -> ceil(1.8) = 2 -> 2 * 12000 = 24.000 so'm
             None or 0 -> 0 so'm
    """
    if not weight_grams or weight_grams <= 0:
        return 0
    hundred_gram_units = math.ceil(weight_grams / 100.0)
    return hundred_gram_units * rate_per_100g


def build_channel_caption(
    category_slug: str,
    price: int,
    cargo_rate: int = 12000,
    delivery_days: str = "10–15 kun",
    delivery_scope: str = "O'zbekiston bo'ylab",
    contact_username: str = "fkhrdnvvvva",
    title: Optional[str] = None,
) -> str:
    """
    Build exact channel post caption matching channel style:
    #{category} 🌸
    💰 Narxi: 45.000 so'm
    📦 Kargo: 12.000 so'm / 100g
    ⏳ 10–15 kun
    🚚 Dastavka: O'zbekiston bo'ylab
    Buyurtma berish uchun @fkhrdnvvvva ga yozing 💌
    """
    clean_cat = category_slug.replace("#", "").strip()
    tag_line = f"#{clean_cat} 🌸"
    if title:
        header_line = f"{tag_line}\n✨ {escape(title.strip())}"
    else:
        header_line = tag_line

    lines = [
        header_line,
        f"💰 Narxi: {format_price(price)}",
        f"📦 Kargo: {format_price(cargo_rate)} / 100g",
        f"⏳ {delivery_days}",
        f"🚚 Dastavka: {delivery_scope}",
        f"Buyurtma berish uchun @{contact_username.replace('@', '')} ga yozing 💌",
    ]
    return "\n".join(lines)


def parse_channel_post(text: str) -> Dict[str, Any]:
    """
    Magic shortcut parser: when admin forwards a channel post,
    extracts hashtag category, price, and details.
    """
    result: Dict[str, Any] = {
        "category": "jempir",
        "price": 0,
        "title": "",
        "sizes": [],
        "colors": [],
        "weight_grams": None,
    }

    if not text:
        return result

    # 1. Extract hashtag (e.g. #scarf, #jempir, #wig, #sumka)
    match_tag = re.search(r"#([a-zA-Z0-9_]+)", text)
    if match_tag:
        result["category"] = match_tag.group(1).lower()

    # 2. Extract price (e.g. "Narxi: 45.000 so'm" or "45 000 so'm" or "45.000" or "99000")
    match_price = re.search(r"(?:Narxi:?\s*)?(\d{1,3}(?:[.\s]\d{3})*|\d+)\s*(?:so['’`]?m)?", text, re.IGNORECASE)
    if match_price:
        raw_price = match_price.group(1).replace(".", "").replace(" ", "")
        try:
            val = int(raw_price)
            if val >= 1000:  # Reasonable minimum price in so'm
                result["price"] = val
        except ValueError:
            pass

    # 3. Extract title if present
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines:
        if line.startswith("#"):
            cleaned = re.sub(r"^#[a-zA-Z0-9_]+\s*", "", line).strip()
            if cleaned:
                result["title"] = cleaned
            break

    return result


def build_order_summary(
    order_id: int,
    user_id: int,
    customer_name: str,
    customer_username: Optional[str],
    items: List[Dict[str, Any]],
    total: int,
    estimated_cargo: int = 0,
    contact_username: str = "fkhrdnvvvva",
) -> Dict[str, str]:
    """
    Build neat order summary for admin and customer.
    """
    username_display = f"@{customer_username}" if customer_username else "username yo'q"
    user_profile_link = f"<a href='tg://user?id={user_id}'>{escape(customer_name)}</a>"

    item_lines: List[str] = []
    copyable_item_lines: List[str] = []

    for idx, item in enumerate(items, 1):
        title = item.get("title", "Mahsulot")
        qty = item.get("qty", 1)
        price = item.get("price", 0)
        size = item.get("size")
        color = item.get("color")

        attrs = []
        if size:
            attrs.append(f"O'lcham: {size}")
        if color:
            attrs.append(f"Rang: {color}")
        attr_str = f" ({', '.join(attrs)})" if attrs else ""

        subtotal = price * qty
        item_lines.append(f"  {idx}. <b>{escape(str(title))}</b>{escape(attr_str)}\n     {qty} x {format_price(price)} = {format_price(subtotal)}")
        copyable_item_lines.append(f"  {idx}. {title}{attr_str} — {qty} dona ({format_price(subtotal)})")

    items_block = "\n".join(item_lines)
    copyable_items_block = "\n".join(copyable_item_lines)

    cargo_text = f"📦 Taxminiy kargo: <b>{format_price(estimated_cargo)}</b>\n" if estimated_cargo > 0 else ""
    copy_cargo_text = f"📦 Taxminiy kargo: {format_price(estimated_cargo)}\n" if estimated_cargo > 0 else ""

    admin_text = (
        f"🛍️ <b>Yangi buyurtma #{order_id}</b> 🌸\n\n"
        f"👤 <b>Mijoz:</b> {user_profile_link} ({username_display})\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n\n"
        f"📋 <b>Tanlangan mahsulotlar:</b>\n{items_block}\n\n"
        f"💰 <b>Jami mahsulotlar:</b> <b>{format_price(total)}</b>\n"
        f"{cargo_text}"
        f"💳 100% oldindan to'lov sharti bilan"
    )

    copyable_block = (
        f"🌸 Sakura shop — Buyurtma #{order_id}\n"
        f"Mijoz: {customer_name} ({username_display})\n\n"
        f"{copyable_items_block}\n\n"
        f"Jami: {format_price(total)}\n"
        f"{copy_cargo_text}"
    )

    customer_text = (
        f"🌸 <b>Rahmat, {escape(customer_name)}!</b> 💗\n\n"
        f"Sizning buyurtmangiz (#{order_id}) qabul qilindi. Admin tez orada siz bilan bog'lanadi!\n\n"
        f"📋 <b>Buyurtma tafsilotlari:</b>\n{items_block}\n\n"
        f"💰 <b>Jami summa:</b> <b>{format_price(total)}</b>\n"
        f"{cargo_text}\n"
        f"💌 <b>Tezroq buyurtma berish uchun quyidagi matnni nusxalab @{contact_username.replace('@', '')} ga yuborishingiz mumkin:</b>\n\n"
        f"<code>{escape(copyable_block)}</code>"
    )

    return {
        "admin_text": admin_text,
        "customer_text": customer_text,
        "copyable_block": copyable_block,
    }
