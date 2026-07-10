from urllib.parse import urlencode

from psn.constants import (
    TROPHY_API_BASE,
    USER_GAMES_API_BASE,
    USER_PROFILE_API_BASE,
)


def _build(base: str, path: str, params: dict) -> str:
    query = urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{base}/{path.lstrip('/')}"
    return f"{url}?{query}" if query else url


def played_games_url(
    account_id: str = "me",
    *,
    limit: int = 200,
    offset: int = 0,
    categories: str = "ps4_game,ps5_native_game,pspc_game",
) -> str:
    return _build(
        USER_GAMES_API_BASE,
        f"{account_id}/titles",
        {"limit": limit, "offset": offset, "categories": categories},
    )


def trophy_titles_url(
    account_id: str = "me",
    *,
    limit: int = 800,
    offset: int = 0,
) -> str:
    return _build(
        TROPHY_API_BASE,
        f"v1/users/{account_id}/trophyTitles",
        {"limit": limit, "offset": offset},
    )


def user_trophies_for_titles_url(
    account_id: str = "me",
    *,
    np_title_ids: str,
) -> str:
    return _build(
        TROPHY_API_BASE,
        f"v1/users/{account_id}/titles/trophyTitles",
        {"npTitleIds": np_title_ids},
    )


def user_trophies_earned_url(
    account_id: str = "me",
    *,
    np_communication_id: str,
    np_service_name: str = "trophy",
) -> str:
    return _build(
        TROPHY_API_BASE,
        f"v1/users/{account_id}/npCommunicationIds/{np_communication_id}/trophyGroups/all/trophies",
        {"npServiceName": np_service_name},
    )


def title_trophies_url(
    np_communication_id: str,
    *,
    np_service_name: str = "trophy",
) -> str:
    return _build(
        TROPHY_API_BASE,
        f"v1/npCommunicationIds/{np_communication_id}/trophyGroups/all/trophies",
        {"npServiceName": np_service_name},
    )


def friends_url(account_id: str = "me", *, limit: int = 2000, offset: int = 0) -> str:
    return _build(
        USER_PROFILE_API_BASE,
        f"{account_id}/friends",
        {"limit": limit, "offset": offset},
    )


def profile_url(account_id: str) -> str:
    return _build(USER_PROFILE_API_BASE, f"{account_id}/profiles", {})
