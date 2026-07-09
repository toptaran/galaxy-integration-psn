import json
from typing import Any, Dict
from urllib.parse import urlencode

GRAPHQL_BASE_URL = "https://web.np.playstation.com/api/graphql/v1/op"

PURCHASED_GAMES_HASH = (
    "827a423f6a8ddca4107ac01395af2ec0eafd8396fc7fa204aaf9b7ed2eefa168"
)
PLAYED_GAMES_HASH = (
    "e780a6d8b921ef0c59ec01ea5c5255671272ca0d819edb61320914cf7a78b3ae"
)


def build_graphql_url(operation_name: str, variables: Dict[str, Any], sha256_hash: str) -> str:
    query = urlencode(
        {
            "operationName": operation_name,
            "variables": json.dumps(variables, separators=(",", ":")),
            "extensions": json.dumps(
                {"persistedQuery": {"version": 1, "sha256Hash": sha256_hash}},
                separators=(",", ":"),
            ),
        }
    )
    return f"{GRAPHQL_BASE_URL}?{query}"


def purchased_games_url(start: int, size: int) -> str:
    return build_graphql_url(
        "getPurchasedGameList",
        {
            "isActive": True,
            "platform": ["ps4", "ps5"],
            "start": start,
            "size": size,
            "sortBy": "ACTIVE_DATE",
            "sortDirection": "desc",
        },
        PURCHASED_GAMES_HASH,
    )


def played_games_url(limit: int) -> str:
    return build_graphql_url(
        "getUserGameList",
        {"categories": "ps4_game,ps5_native_game", "limit": limit},
        PLAYED_GAMES_HASH,
    )
