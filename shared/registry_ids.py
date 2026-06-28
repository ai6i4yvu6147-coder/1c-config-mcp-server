"""Hub-owned identifier validation (Admin Hub protocol v1.0.2 §3.1)."""

from __future__ import annotations

import re
from typing import Optional

UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def is_uuid_v4(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return UUID_V4_PATTERN.match(value.lower()) is not None


def validate_hub_id(field_name: str, value: str) -> Optional[str]:
    """Return error message if value is not a strict UUID v4, else None."""
    if not value:
        return f"{field_name} is required"
    if not is_uuid_v4(value):
        return f"{field_name} must be a strict UUID v4: {value!r}"
    return None
