from unittest.mock import Mock

import pytest
from galaxy.api.types import GameTime


@pytest.fixture()
def played_games_backend_response():
    return {
        "data": {
            "gameLibraryTitlesRetrieve": {
                "__typename": "GameList",
                "games": [
                    {
                        "__typename": "GameLibraryTitle",
                        "lastPlayedDateTime": "2021-03-06T16:29:22.490Z",
                        "name": "Call of Duty®: Modern Warfare®",
                        "platform": "PS4",
                        "titleId": "GAME_ID_1",
                    },
                    {
                        "__typename": "GameLibraryTitle",
                        "lastPlayedDateTime": "1970-01-01T00:00:01.000Z",
                        "name": "Call of Duty®: Modern Warfare®",
                        "platform": "PS4",
                        "titleId": "GAME_ID_2",
                    },
                ],
            }
        }
    }


@pytest.mark.asyncio
async def test_prepare_game_times_context(
    http_get, authenticated_plugin, played_games_backend_response
):
    http_get.return_value = played_games_backend_response

    result = await authenticated_plugin.prepare_game_times_context(Mock(list))
    for title in played_games_backend_response["data"]["gameLibraryTitlesRetrieve"]["games"]:
        game = result[title["titleId"]]
        assert game["name"] is not None
        assert game["name"] == title["name"]
        assert game["titleId"] is not None
        assert game["titleId"] == title["titleId"]
        assert game["lastPlayedDateTime"] is not None
        assert game["lastPlayedDateTime"] == title["lastPlayedDateTime"]


@pytest.mark.asyncio
async def test_getting_game_time(
    http_get, authenticated_plugin, played_games_backend_response
):
    http_get.return_value = played_games_backend_response
    ctx = await authenticated_plugin.prepare_game_times_context(Mock(list))
    assert GameTime("GAME_ID_1", None, 1615048162) == await authenticated_plugin.get_game_time(
        "GAME_ID_1", ctx
    )
    assert GameTime("GAME_ID_2", None, 1) == await authenticated_plugin.get_game_time(
        "GAME_ID_2", ctx
    )