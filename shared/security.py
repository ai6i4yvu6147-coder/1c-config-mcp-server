from __future__ import annotations

import re

_SECRET_PATTERNS = (
    (re.compile(r"(secret_access_key\s*[:=]\s*)(\S+)", re.IGNORECASE), r"\1***"),
    (re.compile(r"(access_key_id\s*[:=]\s*)(\S+)", re.IGNORECASE), r"\1***"),
    (re.compile(r"\bYCO[a-zA-Z0-9]{30,}\b"), "***"),
    (re.compile(r"\bYCA[a-zA-Z0-9]{15,}\b"), "***"),
)


def mask_secrets(text: str) -> str:
    masked = text
    for pattern, replacement in _SECRET_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked
