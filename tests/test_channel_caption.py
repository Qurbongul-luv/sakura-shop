from api.services.formatters import build_channel_caption, parse_channel_post


def test_build_channel_caption_format():
    caption = build_channel_caption(
        category_slug="scarf",
        price=45000,
        cargo_rate=12000,
        delivery_days="10–15 kun",
        delivery_scope="O'zbekiston bo'ylab",
        contact_username="fkhrdnvvvva",
    )

    expected = (
        "#scarf 🌸\n"
        "💰 Narxi: 45.000 so'm\n"
        "📦 Kargo: 12.000 so'm / 100g\n"
        "⏳ 10–15 kun\n"
        "🚚 Dastavka: O'zbekiston bo'ylab\n"
        "Buyurtma berish uchun @fkhrdnvvvva ga yozing 💌"
    )
    assert caption == expected


def test_parse_channel_post_shortcut():
    sample_post = (
        "#jempir 🌸\n"
        "💰 Narxi: 99.000 so'm\n"
        "📦 Kargo: 12.000 so'm / 100g\n"
        "⏳ 10–15 kun\n"
        "🚚 Dastavka: O'zbekiston bo'ylab\n"
        "Buyurtma berish uchun @fkhrdnvvvva ga yozing 💌"
    )

    parsed = parse_channel_post(sample_post)
    assert parsed["category"] == "jempir"
    assert parsed["price"] == 99000
