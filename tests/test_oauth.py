import base64
import json

from psn.constants import OAUTH_LOGIN_REDIRECT_URL, REFRESH_COOKIES_URL
from psn.oauth import (
    _access_code_from_location,
    decode_jwt_payload,
    user_info_from_id_token,
)


def test_access_code_parsed_from_app_redirect_with_leading_question_mark():
    location = (
        "com.scee.psxandroid.scecompcall://redirect/?code=v3.Pk00DB"
        "&cid=5e2dde3c-4cf7-45b0-a36c-57e1ef1c5d95"
    )
    assert _access_code_from_location(location) == "v3.Pk00DB"


def test_refresh_cookies_url_redirects_to_playstation_homepage():
    assert OAUTH_LOGIN_REDIRECT_URL in REFRESH_COOKIES_URL
    assert "ssocookie" not in REFRESH_COOKIES_URL


def test_user_info_from_id_token_reads_account_fields():
    payload = {
        "account_id": "1234567890",
        "online_id": "TestPlayer",
    }
    segment = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    id_token = f"header.{segment}.signature"
    user_id, user_name = user_info_from_id_token(id_token)
    assert user_id == "1234567890"
    assert user_name == "TestPlayer"


def test_decode_jwt_payload_handles_urlsafe_base64():
    payload = {"sub": "abc", "online_id": "player1"}
    segment = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    decoded = decode_jwt_payload(f"x.{segment}.y")
    assert decoded["sub"] == "abc"
