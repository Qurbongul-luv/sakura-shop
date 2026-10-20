import pytest
from fastapi import HTTPException
from api.auth import verify_telegram_init_data
from tests.conftest import generate_test_init_data, TEST_BOT_TOKEN


def test_verify_valid_init_data():
    valid_data = generate_test_init_data(user_id=12345, first_name="Amina", auth_date_offset=0)
    parsed = verify_telegram_init_data(valid_data, TEST_BOT_TOKEN)
    assert "user" in parsed
    assert "auth_date" in parsed


def test_verify_tampered_init_data():
    tampered_data = generate_test_init_data(user_id=12345, first_name="Amina", tampered=True)
    with pytest.raises(HTTPException) as exc_info:
        verify_telegram_init_data(tampered_data, TEST_BOT_TOKEN)
    assert exc_info.value.status_code == 401
    assert "tampered" in exc_info.value.detail.lower() or "signature" in exc_info.value.detail.lower()


def test_verify_expired_init_data():
    # 25 hours ago = -90000 seconds
    expired_data = generate_test_init_data(user_id=12345, first_name="Amina", auth_date_offset=-90000)
    with pytest.raises(HTTPException) as exc_info:
        verify_telegram_init_data(expired_data, TEST_BOT_TOKEN)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_verify_missing_hash():
    invalid_data = "user=12345&auth_date=1234567890"
    with pytest.raises(HTTPException) as exc_info:
        verify_telegram_init_data(invalid_data, TEST_BOT_TOKEN)
    assert exc_info.value.status_code == 401
