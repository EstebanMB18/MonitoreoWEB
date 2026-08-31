from __future__ import annotations

import threading
from datetime import datetime
from typing import Any
from uuid import uuid4

from core.events import EventBus
from core.models import RunContext
from api.storage import list_saved_runs, save_run
from monitores.aws.adapter import AWSMonitor
from monitores.hercules.adapter import HerculesMonitor
from monitores.pasarelas.adapter import PasarelasMonitor


EVENT_BUS = EventBus()

LOCK = threading.RLock()

RUNS: dict[str, dict[str, Any]] = {
    item["run_id"]: item
    for item in list_saved_runs()
}
MONITOR_OBJECTS: dict[str, Any] = {}


MONITOR_REGISTRY = {
    "aws": AWSMonitor,
    "pasarelas": PasarelasMonitor,
    "hercules": HerculesMonitor,
}


MONITOR_DEFINITIONS = [
    {
        "id": "aws",
        "name": "AWS",
        "enabled": True,
        "supports_manual_run": True,
    },
    {
        "id": "pasarelas",
        "name": "PASARELAS",
        "enabled": True,
        "supports_manual_run": True,
    },
    {
        "id": "hercules",
        "name": "HERCULES",
        "enabled": True,
        "supports_manual_run": True,
    },
]


def create_run(
    *,
    monitor_id: str,
    run_type: str,
    cut: str | None,
    reason: str | None,
) -> dict[str, Any]:

    key = monitor_id.lower()

    if key not in MONITOR_REGISTRY:
        raise KeyError(key)

    run_id = str(uuid4())

    is_official = run_type == "OFFICIAL"

    context = RunContext(
        run_id=run_id,
        cut=cut,
        installation_mode="operator",
        metadata={
            "run_type": run_type,
            "reason": reason,
            "official": is_official,
            "historical": is_official,
            "publish_allowed": False,
            "api_execution": True,
        },
    )

    monitor_class = MONITOR_REGISTRY[key]

    monitor = monitor_class(
        context=context,
        event_bus=EVENT_BUS,
    )

    item = {
        "run_id": run_id,
        "monitor": key.upper(),
        "run_type": run_type,
        "cut": cut,
        "reason": reason,
        "status": "PENDING",
        "progress": 0,
        "official": is_official,
        "historical": is_official,
        "publish_allowed": False,
        "installation_mode": "operator",
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "finished_at": None,
        "duration_seconds": None,
        "records": None,
        "alerts": [],
        "errors": [],
        "outputs": {
            "dashboard": None,
            "excel": None,
            "folder": None,
        },
    }

    with LOCK:
        RUNS[run_id] = item
        MONITOR_OBJECTS[run_id] = monitor

    save_run(item)

    thread = threading.Thread(
        target=_execute_run,
        args=(run_id,),
        daemon=True,
        name=f"monitor-{key}-{run_id[:8]}",
    )

    thread.start()

    return get_run(run_id)


def _execute_run(run_id: str) -> None:
    with LOCK:
        monitor = MONITOR_OBJECTS[run_id]
        RUNS[run_id]["status"] = "PREPARING"
        RUNS[run_id]["started_at"] = datetime.now().isoformat()

    try:
        result = monitor.run()
        result_data = result.to_dict()

        with LOCK:
            RUNS[run_id].update({
                "status": result_data.get("status"),
                "progress": result_data.get("progress", 100),
                "started_at": result_data.get("started_at"),
                "finished_at": result_data.get("finished_at"),
                "duration_seconds": result_data.get("duration_seconds"),
                "records": result_data.get("records"),
                "alerts": result_data.get("alerts", []),
                "errors": result_data.get("errors", []),
                "outputs": result_data.get("outputs", {}),
                "metadata": result_data.get("metadata", {}),
                "details": result_data.get("details", {}),
            })

            saved = dict(RUNS[run_id])

        save_run(saved)

    except Exception as exc:
        with LOCK:
            RUNS[run_id]["status"] = "ERROR"
            RUNS[run_id]["progress"] = 100
            RUNS[run_id]["finished_at"] = datetime.now().isoformat()
            RUNS[run_id]["errors"] = [
                f"{type(exc).__name__}: {exc}"
            ]

            saved = dict(RUNS[run_id])

        save_run(saved)


def _sync_live_state(run_id: str) -> None:
    monitor = MONITOR_OBJECTS.get(run_id)

    if monitor is None:
        return

    result = getattr(monitor, "result", None)

    if result is None:
        return

    data = result.to_dict()
    events = EVENT_BUS.get_events(run_id)

    latest_progress = None
    current_message = None

    for event in events:
        if event.progress is not None:
            latest_progress = event.progress
            current_message = event.message

    with LOCK:
        item = RUNS.get(run_id)

        if item is None:
            return

        item["status"] = data.get(
            "status",
            item.get("status"),
        )

        item["details"] = data.get(
            "details",
            item.get("details", {}),
        )

        if latest_progress is not None:
            item["progress"] = latest_progress
            item["current_message"] = current_message
        else:
            item["progress"] = data.get(
                "progress",
                item.get("progress", 0),
            )

        item["records"] = data.get(
            "records",
            item.get("records"),
        )

        item["alerts"] = data.get(
            "alerts",
            item.get("alerts", []),
        )

        item["errors"] = data.get(
            "errors",
            item.get("errors", []),
        )

        item["outputs"] = data.get(
            "outputs",
            item.get("outputs", {}),
        )

        item["metadata"] = data.get(
            "metadata",
            item.get("metadata", {}),
        )

def get_run(run_id: str) -> dict[str, Any] | None:
    _sync_live_state(run_id)

    with LOCK:
        item = RUNS.get(run_id)

        if item is None:
            return None

        data = dict(item)

    events = EVENT_BUS.get_events(run_id)

    data["events"] = [
        event.to_dict()
        for event in events
    ]

    return data


def list_runs() -> list[dict[str, Any]]:
    with LOCK:
        ids = list(RUNS.keys())

    items = []

    for run_id in ids:
        item = get_run(run_id)

        if item is not None:
            items.append(item)

    items.sort(
        key=lambda item:
            item.get("created_at") or "",
        reverse=True,
    )

    return items


def latest_run_for_monitor(
    monitor_id: str,
) -> dict[str, Any] | None:

    key = monitor_id.upper()

    items = list_runs()

    for item in items:
        if item["monitor"] == key:
            return item

    return None
