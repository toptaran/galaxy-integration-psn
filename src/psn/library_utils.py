import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

VALID_TITLE_ID = re.compile(
    r"^(CUSA|PPSA|PCSE|PCSA|NPWR|NPUA|NPUZ|NPHB|NPHG|NPHX|NPEA|NPEB|NPEZ|NPUF|NPUJ|NPUK|NPUH|NPUC|NPUV|NPUW|NPUY|NPUQ|NPUB|NPUG|NPUX|NPUZ)\d{5}_\d{2}$"
)

GENERIC_NAMES = frozenset(
    {
        "",
        "unknown",
        "unknown game",
        "untitled",
        "title",
    }
)


def is_valid_title_id(title_id: str) -> bool:
    return bool(title_id and VALID_TITLE_ID.match(title_id))


def pick_display_name(*candidates: Optional[str]) -> str:
    best = ""
    best_score = -1
    for candidate in candidates:
        if not candidate:
            continue
        name = candidate.strip()
        if name.lower() in GENERIC_NAMES:
            continue
        score = len(name)
        if score > best_score:
            best = name
            best_score = score
    return best


def should_skip_played_entry(entry: Dict) -> bool:
    if entry.get("category") != "unknown":
        return False
    return not pick_display_name(
        entry.get("name"),
        entry.get("localizedName"),
        (entry.get("concept") or {}).get("name"),
    )


def merge_library_entries(entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}
    for entry in entries:
        title_id = entry.get("titleId")
        if not title_id or not is_valid_title_id(title_id):
            continue
        if should_skip_played_entry(entry):
            continue

        name = pick_display_name(
            entry.get("name"),
            entry.get("localizedName"),
            (entry.get("concept") or {}).get("name"),
        )
        if not name:
            continue

        existing = merged.get(title_id)
        if existing:
            existing["name"] = pick_display_name(existing.get("name"), name)
            if entry.get("conceptId"):
                existing["conceptId"] = entry["conceptId"]
        else:
            merged[title_id] = {
                "titleId": title_id,
                "name": name,
                "conceptId": entry.get("conceptId"),
            }
    return list(merged.values())


def enrich_purchased_concept_ids(
    purchased_games: List[Dict[str, str]],
    played_games: List[Dict],
) -> None:
    """Attach conceptId to purchased rows so CUSA/PPSA siblings dedupe and alias."""
    concept_by_title: Dict[str, str] = {}
    for title in played_games:
        if not isinstance(title, dict):
            continue
        concept = title.get("concept") or {}
        concept_id = concept.get("id")
        if concept_id is None:
            continue
        concept_key = str(concept_id)
        title_id = title.get("titleId")
        if title_id:
            concept_by_title[title_id] = concept_key
        for alt_id in concept.get("titleIds") or []:
            if alt_id:
                concept_by_title[alt_id] = concept_key

    for game in purchased_games:
        if game.get("conceptId"):
            continue
        concept_id = concept_by_title.get(game.get("titleId", ""))
        if concept_id:
            game["conceptId"] = concept_id


def build_concept_siblings(played_games: List[Dict]) -> Dict[str, List[str]]:
    groups: Dict[str, set] = {}
    for title in played_games:
        if not isinstance(title, dict):
            continue
        concept = title.get("concept") or {}
        concept_id = concept.get("id")
        if concept_id is None:
            continue
        key = str(concept_id)
        group = groups.setdefault(key, set())
        title_id = title.get("titleId")
        if title_id:
            group.add(title_id)
        for alt_id in concept.get("titleIds") or []:
            if alt_id:
                group.add(alt_id)

    siblings: Dict[str, List[str]] = {}
    for ids in groups.values():
        ordered = sorted(ids)
        for title_id in ordered:
            siblings[title_id] = [other for other in ordered if other != title_id]
    return siblings


def _canonical_score(entry: Dict[str, str]) -> int:
    title_id = entry.get("titleId") or ""
    score = len(entry.get("name") or "")
    if title_id.startswith("PPSA"):
        score += 100
    elif title_id.startswith("CUSA"):
        score += 50
    elif title_id.startswith("NPWR"):
        score -= 25
    if entry.get("source") == "purchased":
        score += 10
    return score


STORE_SKU_PREFIXES = ("CUSA", "PPSA", "PCSE", "PCSA")


def expand_concept_sibling_skus(
    entries: List[Dict[str, str]],
    siblings: Dict[str, List[str]],
) -> List[Dict[str, str]]:
    """Re-add CUSA/PPSA sibling SKUs so Galaxy can match GOG catalog IDs."""
    known = {entry["titleId"] for entry in entries if entry.get("titleId")}
    expanded = list(entries)
    for entry in entries:
        title_id = entry.get("titleId")
        if not title_id:
            continue
        for sibling_id in siblings.get(title_id, []):
            if sibling_id in known or not sibling_id.startswith(STORE_SKU_PREFIXES):
                continue
            expanded.append(
                {
                    "titleId": sibling_id,
                    "name": entry.get("name") or "",
                    "conceptId": entry.get("conceptId"),
                    "source": entry.get("source"),
                }
            )
            known.add(sibling_id)
    return expanded


def dedupe_library_by_concept(entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Keep one library row per PSN concept to avoid duplicate CUSA/PPSA pairs."""
    by_concept: Dict[str, List[Dict[str, str]]] = {}
    standalone: List[Dict[str, str]] = []
    for entry in entries:
        concept_id = entry.get("conceptId")
        if concept_id is None:
            standalone.append(entry)
            continue
        by_concept.setdefault(str(concept_id), []).append(entry)

    deduped = list(standalone)
    for group in by_concept.values():
        deduped.append(max(group, key=_canonical_score))
    return deduped


def alias_context_by_siblings(
    context: dict,
    game_ids: List[str],
    siblings: Dict[str, List[str]],
    *,
    has_data=None,
):
    """Copy stats from a sibling SKU when the requested title id has no data."""
    if has_data is None:
        has_data = bool
    for game_id in game_ids:
        if game_id in context and has_data(context[game_id]):
            continue
        for sibling_id in siblings.get(game_id, []):
            sibling_value = context.get(sibling_id)
            if sibling_value and has_data(sibling_value):
                context[game_id] = sibling_value
                break


def parse_iso_datetime(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())
