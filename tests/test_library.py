import pytest

from psn.client import PSNClient
from psn.duration import parse_play_duration
from psn.library_utils import merge_library_entries, pick_display_name


class StubPSNClient(PSNClient):
    def __init__(self):
        pass

    async def get_purchased_games(self):
        return [
            {"titleId": "CUSA12345_00", "name": "Test Game One", "source": "purchased"},
            {"titleId": "CUSA67890_00", "name": "Test Game Two", "source": "purchased"},
        ]

    async def get_played_games(self):
        return [
            {
                "titleId": "CUSA67890_00",
                "name": "Worse Name",
                "localizedName": "Test Game Two (Played)",
                "source": "played",
            },
            {
                "titleId": "CUSA11111_00",
                "name": "Played Only Game",
                "localizedName": "Played Only Game",
                "source": "played",
            },
        ]

    async def get_trophy_library_games(self):
        return [
            {
                "titleId": "NPWR01234_00",
                "name": "PS3 Classic",
                "source": "trophy",
            }
        ]


@pytest.mark.asyncio
async def test_get_all_library_titles_merges_and_dedupes():
    client = StubPSNClient()
    client._trophy_title_index = {
        "NPWR01234_00": {
            "npCommunicationId": "NPWR01234_00",
            "npServiceName": "trophy",
            "name": "PS3 Classic",
            "platform": "PS3",
        }
    }
    titles = await client.get_all_library_titles()

    assert len(titles) == 4
    title_ids = {title["titleId"] for title in titles}
    assert title_ids == {
        "CUSA12345_00",
        "CUSA67890_00",
        "CUSA11111_00",
        "NPWR01234_00",
    }
    merged = {title["titleId"]: title["name"] for title in titles}
    assert merged["CUSA67890_00"] == "Test Game Two (Played)"


def test_pick_display_name_prefers_localized():
    assert pick_display_name("Short", "Longer Localized Name") == "Longer Localized Name"


def test_merge_library_entries_skips_unknown_without_name():
    merged = merge_library_entries(
        [
            {"titleId": "CUSA99999_00", "category": "unknown"},
            {"titleId": "CUSA88888_00", "name": "Real Game"},
        ]
    )
    assert len(merged) == 1
    assert merged[0]["titleId"] == "CUSA88888_00"


@pytest.mark.parametrize(
    "duration,minutes",
    [
        ("PT1H30M", 90),
        ("PT228H56M33S", 228 * 60 + 56 + 1),
        ("P1DT2H", 26 * 60),
        (None, None),
        ("invalid", None),
    ],
)
def test_parse_play_duration(duration, minutes):
    assert parse_play_duration(duration) == minutes
