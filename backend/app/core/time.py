from datetime import datetime, timezone
from typing import Any

UTC_MIN = datetime.min.replace(tzinfo=timezone.utc)


def parse_iso_timestamp(val: Any) -> datetime:
    if not val or not isinstance(val, str):
        return UTC_MIN
    s = val.strip()
    if not s:
        return UTC_MIN
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return UTC_MIN
