from typing import Dict, List, Optional

from galaxy.api.types import Achievement

from psn.library_utils import parse_iso_datetime


def format_achievement_id(np_communication_id: str, trophy_id) -> str:
    """GOG GamesDB matches PSN trophies as ``NPWR12345_00_3``."""
    return f"{np_communication_id}_{trophy_id}"


def extract_store_title_mappings(response: dict) -> Dict[str, List[dict]]:
    """Map store title IDs (CUSA/PPSA) to trophy-set metadata."""
    mappings: Dict[str, List[dict]] = {}
    for block in response.get("titles") or []:
        np_title_id = block.get("npTitleId")
        if not np_title_id:
            continue
        sets = []
        for trophy_title in block.get("trophyTitles") or []:
            np_comm_id = trophy_title.get("npCommunicationId")
            if not np_comm_id:
                continue
            platform = trophy_title.get("trophyTitlePlatform") or ""
            np_service = trophy_title.get("npServiceName") or (
                "trophy2" if "PS5" in platform else "trophy"
            )
            sets.append(
                {
                    "npCommunicationId": np_comm_id,
                    "npServiceName": np_service,
                }
            )
        if sets:
            mappings[np_title_id] = sets
    return mappings


def merge_earned_with_definitions(
    earned_response: dict,
    title_response: dict,
    np_communication_id: str,
) -> List[Achievement]:
    names = {
        str(trophy.get("trophyId")): trophy.get("trophyName")
        for trophy in (title_response.get("trophies") or [])
    }
    achievements: List[Achievement] = []
    for trophy in earned_response.get("trophies") or []:
        if not trophy.get("earned"):
            continue
        trophy_id = str(trophy.get("trophyId"))
        unlock_time = parse_iso_datetime(trophy.get("earnedDateTime"))
        if unlock_time is None:
            continue
        achievements.append(
            Achievement(
                unlock_time=unlock_time,
                achievement_id=format_achievement_id(np_communication_id, trophy_id),
                achievement_name=names.get(trophy_id) or trophy.get("trophyName"),
            )
        )
    return achievements


def parse_rarest_trophies(
    trophy_titles: List[dict],
    np_communication_id: Optional[str] = None,
) -> List[Achievement]:
    """Fallback when only summary data is available."""
    achievements: List[Achievement] = []
    for trophy_set in trophy_titles or []:
        np_comm_id = np_communication_id or trophy_set.get("npCommunicationId") or ""
        for trophy in trophy_set.get("rarestTrophies") or []:
            if not trophy.get("earned"):
                continue
            unlock_time = parse_iso_datetime(trophy.get("earnedDateTime"))
            if unlock_time is None:
                continue
            trophy_id = str(trophy.get("trophyId"))
            achievements.append(
                Achievement(
                    unlock_time=unlock_time,
                    achievement_id=format_achievement_id(np_comm_id, trophy_id)
                    if np_comm_id
                    else trophy_id,
                    achievement_name=trophy.get("trophyName"),
                )
            )
    return achievements
