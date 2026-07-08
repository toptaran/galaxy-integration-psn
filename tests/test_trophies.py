import pytest

from psn.trophies import extract_store_title_mappings, format_achievement_id, merge_earned_with_definitions


def test_extract_store_title_mappings(load_fixture):
    response = load_fixture("trophy_title_mapping.json")
    mappings = extract_store_title_mappings(response)

    assert set(mappings) == {"PPSA07632_00", "CUSA03283_00"}
    assert mappings["PPSA07632_00"][0]["npCommunicationId"] == "NPWR29410_00"
    assert mappings["PPSA07632_00"][0]["npServiceName"] == "trophy2"


def test_format_achievement_id():
    assert format_achievement_id("NPWR37398_00", 0) == "NPWR37398_00_0"
    assert format_achievement_id("NPWR19930_00", "14") == "NPWR19930_00_14"


def test_merge_earned_with_definitions():
    earned = {
        "trophies": [
            {
                "trophyId": 0,
                "earned": True,
                "earnedDateTime": "2008-07-02T05:37:40Z",
            },
            {"trophyId": 1, "earned": False},
        ]
    }
    definitions = {
        "trophies": [
            {"trophyId": 0, "trophyName": "Hero of Lave"},
            {"trophyId": 1, "trophyName": "Hidden"},
        ]
    }

    achievements = merge_earned_with_definitions(earned, definitions, "NPWR01234_00")

    assert len(achievements) == 1
    assert achievements[0].achievement_id == "NPWR01234_00_0"
    assert achievements[0].achievement_name == "Hero of Lave"
    assert achievements[0].unlock_time == 1214977060
