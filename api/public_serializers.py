from __future__ import annotations


def public_outputs(item: dict) -> dict:
    outputs = item.get("outputs") or {}

    return {
        "dashboard": {
            "output_id": "dashboard",
            "available": bool(outputs.get("dashboard")),
        },
        "excel": {
            "output_id": "excel",
            "available": bool(outputs.get("excel")),
        },
    }


def public_run(item: dict) -> dict:
    public = dict(item)
    public["outputs"] = public_outputs(item)
    return public
