from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.events import EventBus
from core.models import RunContext
from core.platform import config_manager
from api.storage import list_saved_runs, save_run
from monitores.aws.adapter import AWSMonitor
from monitores.hercules.adapter import HerculesMonitor
from monitores.pasarelas.adapter import PasarelasMonitor

from core.execution_window import (
    resolve_general_execution_windows,
)


EVENT_BUS = EventBus()


def _configured_output_root() -> Path | None:
    """Ruta final seleccionada por el usuario."""
    try:
        config = config_manager.load()
        value = str(
            config.get("output_directory")
            or ""
        ).strip()

        if not value:
            return None

        path = Path(value).expanduser()
        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        return path.resolve()

    except Exception:
        # La ejecuci?n conserva los fallbacks internos
        # si la configuraci?n local no est? disponible.
        return None

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
    execution_window: dict[str, Any] | None = None,
) -> dict[str, Any]:

    key = monitor_id.lower()

    if key not in MONITOR_REGISTRY:
        raise KeyError(key)

    run_id = str(uuid4())

    is_official = run_type == "OFFICIAL"

    context = RunContext(
        run_id=run_id,
        cut=cut,

        window_mode=(
            execution_window.get("mode")
            if execution_window
            else None
        ),

        execution_date=(
            execution_window.get(
                "execution_date"
            )
            if execution_window
            else None
        ),

        data_date=(
            execution_window.get(
                "data_date"
            )
            if execution_window
            else None
        ),

        window_start=(
            execution_window.get(
                "window_start"
            )
            if execution_window
            else None
        ),

        window_end=(
            execution_window.get(
                "window_end"
            )
            if execution_window
            else None
        ),

        installation_mode="operator",
        output_root=_configured_output_root(),
        metadata={
            "run_type": run_type,
            "reason": reason,
            "official": is_official,
            "historical": is_official,
            "publish_allowed": False,
            "api_execution": True,
            "execution_window":
                execution_window or {},
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
        "window_mode": (
            execution_window.get("mode")
            if execution_window
            else None
        ),
        "execution_date": (
            execution_window.get(
                "execution_date"
            )
            if execution_window
            else None
        ),
        "data_date": (
            execution_window.get(
                "data_date"
            )
            if execution_window
            else None
        ),
        "window_start": (
            execution_window.get(
                "window_start"
            )
            if execution_window
            else None
        ),
        "window_end": (
            execution_window.get(
                "window_end"
            )
            if execution_window
            else None
        ),
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



GENERAL_MONITORS = (
    "aws",
    "pasarelas",
    "hercules",
)

GENERAL_TERMINAL_STATUSES = {
    "OK",
    "WARNING",
    "ERROR",
    "TIMEOUT",
    "CANCELLED",
    "NO_DATA",
    "STALE",
}


def _general_status(
    children: list[dict[str, Any]],
) -> str:

    if not children:
        return "NO_DATA"

    statuses = {
        str(
            item.get("status")
            or "NO_DATA"
        ).upper()
        for item in children
    }

    if statuses & {
        "ERROR",
        "TIMEOUT",
        "CANCELLED",
    }:
        return "ERROR"

    if "WARNING" in statuses:
        return "WARNING"

    if "STALE" in statuses:
        return "WARNING"

    if "NO_DATA" in statuses:
        return "NO_DATA"

    if statuses == {"OK"}:
        return "OK"

    return "WARNING"


def create_general_run(
    *,
    run_type: str,
    window_mode: str,
    data_date: str | None = None,
    cut: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    last_n_hours: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:

    normalized_mode = str(
        window_mode
    ).upper()

    allowed_general_modes = {
        "CUT",
        "TODAY_TO_NOW",
        "YESTERDAY",
        "DATE",
    }

    if normalized_mode not in allowed_general_modes:
        raise ValueError(
            "GENERAL solo admite: "
            "CUT, TODAY_TO_NOW, "
            "YESTERDAY o DATE."
        )

    windows = (
        resolve_general_execution_windows(
            mode=window_mode,
            data_date=data_date,
            cut=cut,
            window_start=window_start,
            window_end=window_end,
            last_n_hours=last_n_hours,
        )
    )

    run_id = str(uuid4())

    is_official = (
        run_type == "OFFICIAL"
    )

    first_window = next(
        iter(windows.values())
    )

    item = {
        "run_id": run_id,
        "monitor": "GENERAL",
        "run_type": run_type,
        "cut": first_window.cut,
        "reason": reason,

        "window_mode":
            first_window.mode,
        "execution_date":
            first_window.execution_date,
        "data_date":
            first_window.data_date,

        # GENERAL no tiene una ?nica ventana f?sica,
        # porque cada monitor puede resolver horas
        # distintas. Las ventanas reales viven
        # dentro de details.windows.
        "window_start": None,
        "window_end": None,

        "status": "PENDING",
        "progress": 0,

        "official": is_official,
        "historical": False,
        "publish_allowed": False,

        "installation_mode":
            "operator",

        "created_at":
            datetime.now().isoformat(),
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

        "metadata": {
            "scope": "GENERAL",
        },

        "details": {
            "windows": {
                monitor:
                    window.to_dict()
                for monitor, window
                in windows.items()
            },
            "children": {},
        },
    }

    with LOCK:
        RUNS[run_id] = item

    save_run(item)

    thread = threading.Thread(
        target=_execute_general_run,
        args=(
            run_id,
            windows,
            run_type,
            reason,
        ),
        daemon=True,
        name=(
            f"general-{run_id[:8]}"
        ),
    )

    thread.start()

    return get_run(run_id)


def _execute_general_run(
    run_id: str,
    windows: dict[str, Any],
    run_type: str,
    reason: str | None,
) -> None:

    started = datetime.now()

    with LOCK:
        RUNS[run_id][
            "status"
        ] = "RUNNING"

        RUNS[run_id][
            "started_at"
        ] = started.isoformat()

        saved = dict(
            RUNS[run_id]
        )

    save_run(saved)

    child_ids: dict[str, str] = {}

    try:
        # Por ahora se crean los tres hijos usando
        # el runtime nuevo. No se utiliza
        # core/orchestrator.py heredado.
        for monitor in GENERAL_MONITORS:
            window = windows[
                monitor.upper()
            ]

            child = create_run(
                monitor_id=monitor,
                run_type=run_type,
                cut=window.cut,
                reason=reason,
                execution_window=
                    window.to_dict(),
            )

            child_ids[
                monitor.upper()
            ] = child["run_id"]

            with LOCK:
                details = (
                    RUNS[run_id]
                    .setdefault(
                        "details",
                        {},
                    )
                )

                details.setdefault(
                    "children",
                    {},
                )[
                    monitor.upper()
                ] = {
                    "run_id":
                        child["run_id"],
                    "status":
                        child.get(
                            "status"
                        ),
                    "progress":
                        child.get(
                            "progress",
                            0,
                        ),
                }

                saved = dict(
                    RUNS[run_id]
                )

            save_run(saved)

        while True:
            children = []

            for monitor, child_id in (
                child_ids.items()
            ):
                child = get_run(
                    child_id
                )

                if child is None:
                    continue

                children.append(
                    child
                )

                with LOCK:
                    RUNS[run_id][
                        "details"
                    ][
                        "children"
                    ][monitor] = {
                        "run_id":
                            child_id,
                        "status":
                            child.get(
                                "status"
                            ),
                        "progress":
                            child.get(
                                "progress",
                                0,
                            ),
                        "records":
                            child.get(
                                "records"
                            ),
                    }

            progresses = [
                int(
                    item.get(
                        "progress"
                    )
                    or 0
                )
                for item in children
            ]

            progress = (
                int(
                    sum(progresses)
                    / len(
                        GENERAL_MONITORS
                    )
                )
                if progresses
                else 0
            )

            with LOCK:
                RUNS[run_id][
                    "progress"
                ] = progress

            all_finished = (
                len(children)
                == len(
                    GENERAL_MONITORS
                )
                and all(
                    str(
                        item.get(
                            "status"
                        )
                    ).upper()
                    in GENERAL_TERMINAL_STATUSES
                    for item in children
                )
            )

            if all_finished:
                break

            time.sleep(1)

        final_status = (
            _general_status(
                children
            )
        )

        finished = datetime.now()

        records = sum(
            int(
                item.get(
                    "records"
                )
                or 0
            )
            for item in children
        )

        with LOCK:
            RUNS[run_id].update({
                "status":
                    final_status,
                "progress": 100,
                "finished_at":
                    finished.isoformat(),
                "duration_seconds":
                    round(
                        (
                            finished
                            - started
                        ).total_seconds(),
                        2,
                    ),
                "records":
                    records,
            })

            saved = dict(
                RUNS[run_id]
            )

        save_run(saved)

    except Exception as exc:

        finished = datetime.now()

        with LOCK:
            RUNS[run_id].update({
                "status": "ERROR",
                "progress": 100,
                "finished_at":
                    finished.isoformat(),
                "duration_seconds":
                    round(
                        (
                            finished
                            - started
                        ).total_seconds(),
                        2,
                    ),
                "errors": [
                    (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                ],
            })

            saved = dict(
                RUNS[run_id]
            )

        save_run(saved)



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
