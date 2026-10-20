from api.services.formatters import build_order_summary


def test_build_order_summary_content():
    items = [
        {
            "product_id": 1,
            "title": "Aesthetic Vintage Pushti Jempir 🌸",
            "price": 99000,
            "size": "M",
            "color": "Sakura pushti 🌸",
            "qty": 2,
        }
    ]

    summary = build_order_summary(
        order_id=42,
        user_id=12345678,
        customer_name="Madina",
        customer_username="madina_aesthetic",
        items=items,
        total=198000,
        estimated_cargo=48000,
        contact_username="fkhrdnvvvva",
    )

    admin_text = summary["admin_text"]
    customer_text = summary["customer_text"]
    copyable = summary["copyable_block"]

    assert "#42" in admin_text
    assert "Madina" in admin_text
    assert "198.000 so'm" in admin_text
    assert "48.000 so'm" in admin_text
    assert "12345678" in admin_text

    assert "Madina" in customer_text
    assert "#42" in customer_text
    assert "@fkhrdnvvvva" in customer_text
    assert "copyable_block" in summary
    assert "Aesthetic Vintage Pushti Jempir" in copyable
