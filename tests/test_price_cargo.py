from api.services.formatters import format_price, calculate_cargo


def test_format_price_dots_and_som():
    assert format_price(99000) == "99.000 so'm"
    assert format_price(45000) == "45.000 so'm"
    assert format_price(125000) == "125.000 so'm"
    assert format_price(1250000) == "1.250.000 so'm"
    assert format_price(0) == "0 so'm"
    assert format_price(None) == "0 so'm"


def test_calculate_cargo_formula():
    # 350 grams -> ceil(3.5) = 4 units -> 4 * 12000 = 48000 so'm
    assert calculate_cargo(350, 12000) == 48000

    # 180 grams -> ceil(1.8) = 2 units -> 2 * 12000 = 24000 so'm
    assert calculate_cargo(180, 12000) == 24000

    # Exactly 100 grams -> 1 unit -> 12000 so'm
    assert calculate_cargo(100, 12000) == 12000

    # Exactly 200 grams -> 2 units -> 24000 so'm
    assert calculate_cargo(200, 12000) == 24000

    # 0 grams or None -> 0 so'm
    assert calculate_cargo(0, 12000) == 0
    assert calculate_cargo(None, 12000) == 0
