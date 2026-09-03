from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.execution_window import (
    resolve_monitor_execution_window,
)
from core.platform import ensure_user_directories


BOGOTA = ZoneInfo("America/Bogota")

TERMINAL_STATUSES = {
    "OK",
    "WARNING",
    "ERROR",
    "TIMEOUT",
    "CANCELLED",
    "NO_DATA",
    "STALE",
}

ACTIVE_STATUSES = {
    "PENDING",
    "PREPARING",
    "RUNNING",
}


DEFAULT_SCHEDULER_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "enabled": False,
    "timezone": "America/Bogota",
    "poll_seconds": 30,
    "catch_up_enabled": True,
    "schedule": {
        "09": {
            "pasarelas": "08:40",
            "aws": "08:50",
            "hercules": "09:00",
            "general": "09:05",
        },
        "13": {
            "pasarelas": "12:40",
            "aws": "12:50",
            "hercules": "13:00",
            "general": "13:05",
        },
        "17": {
            "pasarelas": "16:40",
            "aws": "16:50",
            "hercules": "17:00",
            "general": "17:05",
        },
    },
}


def _config_path() -> Path:
    paths = ensure_user_directories()

    path = (
        Path(paths["config"])
        / "scheduler.json"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def load_scheduler_config() -> dict[str, Any]:
    path = _config_path()

    if not path.exists():
        config = deepcopy(
            DEFAULT_SCHEDULER_CONFIG
        )

        save_scheduler_config(config)

        return config

    try:
        raw = json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except Exception as exc:
        raise RuntimeError(
            "La configuracion del scheduler "
            "no es valida."
        ) from exc

    if not isinstance(raw, dict):
        raise RuntimeError(
            "scheduler.json debe ser "
            "un objeto JSON."
        )

    config = deepcopy(
        DEFAULT_SCHEDULER_CONFIG
    )

    # Mezcla superficial para opciones generales,
    # pero el schedule se fusiona por corte para
    # conservar configuraciones existentes y a?adir
    # nuevas claves introducidas por versiones nuevas.
    raw_schedule = raw.get(
        "schedule"
    )

    config.update(
        {
            key: value
            for key, value in raw.items()
            if key != "schedule"
        }
    )

    if raw_schedule is not None:
        if not isinstance(
            raw_schedule,
            dict,
        ):
            raise RuntimeError(
                "scheduler.schedule debe ser "
                "un objeto."
            )

        for cut, cut_values in (
            raw_schedule.items()
        ):
            if not isinstance(
                cut_values,
                dict,
            ):
                raise RuntimeError(
                    f"scheduler.schedule.{cut} "
                    "debe ser un objeto."
                )

            if cut not in config["schedule"]:
                config["schedule"][cut] = {}

            config["schedule"][cut].update(
                cut_values
            )

    if not isinstance(
        config.get("schedule"),
        dict,
    ):
        raise RuntimeError(
            "scheduler.schedule debe ser "
            "un objeto."
        )

    return config


def save_scheduler_config(
    config: dict[str, Any],
) -> dict[str, Any]:
    normalized = deepcopy(
        DEFAULT_SCHEDULER_CONFIG
    )

    normalized.update(config)

    poll_seconds = int(
        normalized.get(
            "poll_seconds",
            30,
        )
    )

    if poll_seconds < 5:
        raise ValueError(
            "poll_seconds debe ser >= 5."
        )

    normalized[
        "poll_seconds"
    ] = poll_seconds

    schedule = normalized.get(
        "schedule"
    )

    if not isinstance(schedule, dict):
        raise ValueError(
            "schedule debe ser un objeto."
        )

    for cut in ("09", "13", "17"):
        cut_cfg = schedule.get(cut)

        if not isinstance(
            cut_cfg,
            dict,
        ):
            raise ValueError(
                f"Falta schedule para corte {cut}."
            )

        for monitor in (
            "pasarelas",
            "aws",
            "hercules",
            "general",
        ):
            raw = str(
                cut_cfg.get(monitor)
                or ""
            ).strip()

            try:
                datetime.strptime(
                    raw,
                    "%H:%M",
                )
            except ValueError as exc:
                raise ValueError(
                    f"Horario invalido "
                    f"{cut}/{monitor}: {raw}"
                ) from exc

    path = _config_path()

    tmp = path.with_suffix(".tmp")

    tmp.write_text(
        json.dumps(
            normalized,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tmp.replace(path)

    return normalized


def _official_run_exists(
    *,
    monitor: str,
    data_date: str,
    cut: str,
) -> bool:
    # Import local para evitar ciclo
    # monitor_scheduler -> api.runtime -> ...
    from api.runtime import list_runs

    monitor = monitor.upper()
    cut = str(cut)

    for run in list_runs():
        if str(
            run.get("monitor")
            or ""
        ).upper() != monitor:
            continue

        if str(
            run.get("run_type")
            or ""
        ).upper() != "OFFICIAL":
            continue

        if str(
            run.get("cut")
            or ""
        ) != cut:
            continue

        if str(
            run.get("data_date")
            or ""
        ) != data_date:
            continue

        status = str(
            run.get("status")
            or ""
        ).upper()

        if (
            status in ACTIVE_STATUSES
            or status in TERMINAL_STATUSES
        ):
            return True

    return False


def _create_official_run(
    *,
    monitor: str,
    cut: str,
    now: datetime,
) -> dict[str, Any] | None:
    from api.runtime import create_run

    normalized_cut = {
        "09": "09:00",
        "13": "13:00",
        "17": "17:00",
    }.get(
        str(cut),
        str(cut),
    )

    # Los monitores oficiales comienzan antes de la hora
    # nominal del corte:
    #
    # 08:40 Pasarelas -> corte 09:00
    # 08:50 AWS       -> corte 09:00
    # 09:00 Hercules  -> corte 09:00
    #
    # execution_window protege correctamente contra cortes
    # futuros para ejecuciones manuales. Para el scheduler
    # oficial usamos la hora nominal del corte ?nicamente al
    # resolver la ventana, sin debilitar esa validaci?n global.
    cut_hour, cut_minute = (
        int(part)
        for part in normalized_cut.split(
            ":",
            1,
        )
    )

    resolution_now = now.replace(
        hour=cut_hour,
        minute=cut_minute,
        second=0,
        microsecond=0,
    )

    if now > resolution_now:
        resolution_now = now

    resolved = (
        resolve_monitor_execution_window(
            monitor=monitor,
            mode="CUT",
            data_date=now.date().isoformat(),
            cut=normalized_cut,
            now=resolution_now,
        )
    )

    if _official_run_exists(
        monitor=monitor,
        data_date=resolved.data_date,
        cut=resolved.cut,
    ):
        return None

    return create_run(
        monitor_id=monitor,
        run_type="OFFICIAL",
        cut=resolved.cut,
        reason=(
            "Ejecucion automatica "
            "Nexus Scheduler"
        ),
        execution_window=
            resolved.to_dict(),
    )


def _general_official_exists(
    *,
    data_date: str,
    cut: str,
) -> bool:
    from api.runtime import list_runs

    normalized_cut = {
        "09": "09:00",
        "13": "13:00",
        "17": "17:00",
    }.get(
        str(cut),
        str(cut),
    )

    for run in list_runs():
        if str(
            run.get("monitor")
            or ""
        ).upper() != "GENERAL":
            continue

        if str(
            run.get("run_type")
            or ""
        ).upper() != "OFFICIAL":
            continue

        if str(
            run.get("cut")
            or ""
        ) != normalized_cut:
            continue

        if str(
            run.get("data_date")
            or ""
        ) != data_date:
            continue

        status = str(
            run.get("status")
            or ""
        ).upper()

        if (
            status in ACTIVE_STATUSES
            or status in TERMINAL_STATUSES
        ):
            return True

    return False


def _official_children_exist(
    *,
    data_date: str,
    cut: str,
) -> bool:

    normalized_cut = {
        "09": "09:00",
        "13": "13:00",
        "17": "17:00",
    }.get(
        str(cut),
        str(cut),
    )

    return all(
        _official_run_exists(
            monitor=monitor,
            data_date=data_date,
            cut=normalized_cut,
        )
        for monitor in (
            "AWS",
            "PASARELAS",
            "HERCULES",
        )
    )


def _create_scheduled_general(
    *,
    cut: str,
    now: datetime,
) -> dict[str, Any] | None:

    from api.runtime import (
        create_general_run,
    )

    data_date = (
        now.date().isoformat()
    )

    normalized_cut = {
        "09": "09:00",
        "13": "13:00",
        "17": "17:00",
    }.get(
        str(cut),
        str(cut),
    )

    if _general_official_exists(
        data_date=data_date,
        cut=normalized_cut,
    ):
        return None

    # General solo consolida cuando los tres
    # OFFICIAL del corte ya existen.
    if not _official_children_exist(
        data_date=data_date,
        cut=normalized_cut,
    ):
        return None

    return create_general_run(
        run_type="OFFICIAL",
        window_mode="CUT",
        data_date=data_date,
        cut=normalized_cut,
        reason=(
            "Consolidacion automatica "
            "Nexus Scheduler"
        ),
        reuse_official_children=True,
    )


def _scheduled_datetime(
    *,
    now: datetime,
    hhmm: str,
) -> datetime:
    hour, minute = (
        int(part)
        for part in hhmm.split(
            ":",
            1,
        )
    )

    return now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )


def _close_previous_day_if_needed(
    *,
    now: datetime,
) -> None:
    from core.daily_closure import (
        catch_up_all_monitors,
    )

    yesterday = (
        now.date()
        - timedelta(days=1)
    ).isoformat()

    try:
        catch_up_all_monitors(
            start_date=yesterday,
            until_date=yesterday,
        )
    except Exception as exc:
        print(
            "Nexus Scheduler daily closure "
            f"catch-up error: {exc}"
        )


def run_scheduler_tick(
    *,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cfg = (
        config
        or load_scheduler_config()
    )

    if not cfg.get(
        "enabled",
        False,
    ):
        return []

    current = (
        now.astimezone(BOGOTA)
        if now
        else datetime.now(BOGOTA)
    )

    created = []

    if cfg.get(
        "catch_up_enabled",
        True,
    ):
        _close_previous_day_if_needed(
            now=current,
        )

    schedule = cfg["schedule"]

    for cut in ("09", "13", "17"):
        cut_cfg = schedule[cut]

        for monitor in (
            "pasarelas",
            "aws",
            "hercules",
        ):
            due = _scheduled_datetime(
                now=current,
                hhmm=cut_cfg[monitor],
            )

            # Todavia no llega la hora.
            if current < due:
                continue

            # No se ejecutan horarios futuros
            # de otros cortes.
            cut_hour = int(cut)

            if current.hour > cut_hour:
                # Permitimos catch-up durante
                # el mismo dia, incluso si ya
                # paso la hora del corte.
                pass

            run = _create_official_run(
                monitor=monitor,
                cut=cut,
                now=current,
            )

            if run is not None:
                created.append(run)

        general_due = _scheduled_datetime(
            now=current,
            hhmm=cut_cfg["general"],
        )

        if current >= general_due:
            general_run = (
                _create_scheduled_general(
                    cut=cut,
                    now=current,
                )
            )

            if general_run is not None:
                created.append(
                    general_run
                )

    return created


class NexusScheduler:
    def __init__(self) -> None:
        self._stop_event = (
            threading.Event()
        )

        self._thread: (
            threading.Thread | None
        ) = None

    @property
    def running(self) -> bool:
        return bool(
            self._thread
            and self._thread.is_alive()
        )

    def start(self) -> None:
        if self.running:
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="nexus-scheduler",
        )

        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        thread = self._thread

        if (
            thread
            and thread.is_alive()
        ):
            thread.join(
                timeout=5,
            )

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                cfg = (
                    load_scheduler_config()
                )

                run_scheduler_tick(
                    config=cfg
                )

                poll_seconds = int(
                    cfg.get(
                        "poll_seconds",
                        30,
                    )
                )

            except Exception as exc:
                print(
                    "Nexus Scheduler error: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                poll_seconds = 30

            self._stop_event.wait(
                poll_seconds
            )


scheduler = NexusScheduler()
