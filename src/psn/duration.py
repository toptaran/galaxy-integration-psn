import re
from typing import Optional

_ISO_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def parse_play_duration(duration: Optional[str]) -> Optional[int]:
    """Convert ISO 8601 duration (e.g. PT228H56M33S) to total minutes."""
    if not duration:
        return None
    match = _ISO_DURATION.match(duration.strip())
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    total_minutes = days * 24 * 60 + hours * 60 + minutes
    if seconds >= 30:
        total_minutes += 1
    return total_minutes
