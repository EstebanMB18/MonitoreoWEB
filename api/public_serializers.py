from __future__ import annotations

import re


_LOCAL_PATH_RE = re.compile(
    r"^[A-Za-z]:[\\/]"
)


def _is_local_path(value: object) -> bool:
    if not isinstance(value, str):
        return False

    text = value.strip()

    if not text:
        return False

    return bool(
        _LOCAL_PATH_RE.match(text)
        or text.startswith("\\\\")
        or text.lower().startswith("file://")
    )


def _sanitize_public_value(value):
    if isinstance(value, dict):
        clean = {}

        for key, item in value.items():
            if _is_local_path(item):
                continue

            clean[key] = _sanitize_public_value(item)

        return clean

    if isinstance(value, list):
        return [
            _sanitize_public_value(item)
            for item in value
            if not _is_local_path(item)
        ]

    if isinstance(value, tuple):
        return [
            _sanitize_public_value(item)
            for item in value
            if not _is_local_path(item)
        ]

    return value


def public_outputs(item: dict) -> dict:
    outputs = item.get("outputs") or {}

    return {
        "dashboard": {
            "output_id": "dashboard",
            "available": bool(
                outputs.get("dashboard")
            ),
        },
        "excel": {
            "output_id": "excel",
            "available": bool(
                outputs.get("excel")
            ),
        },
    }


def public_run(item: dict) -> dict:
    public = _sanitize_public_value(
        dict(item)
    )

    public["outputs"] = public_outputs(
        item
    )

    return public
