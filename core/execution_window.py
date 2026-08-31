from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = "America/Bogota"

ALLOWED_CUTS = {
    "09:00": time(9, 0),
    "13:00": time(13, 0),
    "17:00": time(17, 0),
}


class ExecutionWindowMode(
    str,
    Enum,
):
    CUT = "CUT"
    TODAY_TO_NOW = "TODAY_TO_NOW"
    YESTERDAY = "YESTERDAY"
    DATE = "DATE"
    CUSTOM = "CUSTOM"
    LAST_HOUR = "LAST_HOUR"
    LAST_N_HOURS = "LAST_N_HOURS"


@dataclass(frozen=True)
class ExecutionWindow:
    mode: str
    execution_date: str
    data_date: str
    window_start: str
    window_end: str
    cut: str | None
    timezone: str

    def to_dict(self) -> dict:
        return asdict(self)


def _timezone(
    name: str,
) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception as exc:
        raise ValueError(
            f"Zona horaria invalida: {name}"
        ) from exc


def _parse_date(
    value: str | None,
    *,
    field: str,
) -> date:
    if not value:
        raise ValueError(
            f"{field} es obligatorio."
        )

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field} debe usar YYYY-MM-DD."
        ) from exc


def _parse_datetime(
    value: str | None,
    *,
    field: str,
    tz: ZoneInfo,
) -> datetime:
    if not value:
        raise ValueError(
            f"{field} es obligatorio."
        )

    try:
        parsed = datetime.fromisoformat(
            value
        )
    except ValueError as exc:
        raise ValueError(
            f"{field} debe ser fecha/hora ISO."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=tz
        )
    else:
        parsed = parsed.astimezone(tz)

    return parsed


def _day_start(
    value: date,
    tz: ZoneInfo,
) -> datetime:
    return datetime.combine(
        value,
        time.min,
        tzinfo=tz,
    )


def _day_end(
    value: date,
    tz: ZoneInfo,
) -> datetime:
    return datetime.combine(
        value,
        time.max,
        tzinfo=tz,
    )


def resolve_execution_window(
    *,
    mode: str,
    data_date: str | None = None,
    cut: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    last_n_hours: int | None = None,
    timezone: str = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> ExecutionWindow:

    tz = _timezone(timezone)

    current = (
        now.astimezone(tz)
        if now is not None
        and now.tzinfo is not None
        else (
            now.replace(tzinfo=tz)
            if now is not None
            else datetime.now(tz)
        )
    )

    try:
        resolved_mode = (
            ExecutionWindowMode(
                str(mode).upper()
            )
        )
    except ValueError as exc:
        allowed = ", ".join(
            item.value
            for item
            in ExecutionWindowMode
        )

        raise ValueError(
            "mode invalido. "
            f"Permitidos: {allowed}"
        ) from exc

    resolved_cut = None

    if (
        resolved_mode
        == ExecutionWindowMode.TODAY_TO_NOW
    ):
        target = current.date()
        start = _day_start(
            target,
            tz,
        )
        end = current

    elif (
        resolved_mode
        == ExecutionWindowMode.YESTERDAY
    ):
        target = (
            current.date()
            - timedelta(days=1)
        )
        start = _day_start(
            target,
            tz,
        )
        end = _day_end(
            target,
            tz,
        )

    elif (
        resolved_mode
        == ExecutionWindowMode.DATE
    ):
        target = _parse_date(
            data_date,
            field="data_date",
        )

        start = _day_start(
            target,
            tz,
        )
        end = _day_end(
            target,
            tz,
        )

    elif (
        resolved_mode
        == ExecutionWindowMode.CUT
    ):
        target = (
            _parse_date(
                data_date,
                field="data_date",
            )
            if data_date
            else current.date()
        )

        if cut not in ALLOWED_CUTS:
            raise ValueError(
                "cut invalido. "
                "Permitidos: "
                + ", ".join(
                    ALLOWED_CUTS
                )
            )

        resolved_cut = cut

        start = _day_start(
            target,
            tz,
        )

        end = datetime.combine(
            target,
            ALLOWED_CUTS[cut],
            tzinfo=tz,
        )

        if (
            target == current.date()
            and end > current
        ):
            raise ValueError(
                "No se puede ejecutar "
                "un corte futuro."
            )

    elif (
        resolved_mode
        == ExecutionWindowMode.CUSTOM
    ):
        start = _parse_datetime(
            window_start,
            field="window_start",
            tz=tz,
        )

        end = _parse_datetime(
            window_end,
            field="window_end",
            tz=tz,
        )

        if end <= start:
            raise ValueError(
                "window_end debe ser "
                "posterior a window_start."
            )

        target = start.date()

    elif (
        resolved_mode
        == ExecutionWindowMode.LAST_HOUR
    ):
        end = current
        start = (
            current
            - timedelta(hours=1)
        )
        target = start.date()

    elif (
        resolved_mode
        == ExecutionWindowMode.LAST_N_HOURS
    ):
        if (
            last_n_hours is None
            or last_n_hours < 1
            or last_n_hours > 168
        ):
            raise ValueError(
                "last_n_hours debe estar "
                "entre 1 y 168."
            )

        end = current
        start = (
            current
            - timedelta(
                hours=last_n_hours
            )
        )
        target = start.date()

    else:
        raise ValueError(
            "Modo no soportado."
        )

    if end > current:
        raise ValueError(
            "La ventana no puede "
            "terminar en el futuro."
        )

    return ExecutionWindow(
        mode=resolved_mode.value,
        execution_date=(
            current.date().isoformat()
        ),
        data_date=target.isoformat(),
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        cut=resolved_cut,
        timezone=timezone,
    )



MONITOR_IDS = {
    "AWS",
    "PASARELAS",
    "HERCULES",
}


@dataclass(frozen=True)
class MonitorExecutionWindow:
    monitor: str
    mode: str
    execution_date: str
    data_date: str
    window_start: str
    window_end: str
    cut: str | None
    timezone: str

    def to_dict(self) -> dict:
        return asdict(self)


def resolve_monitor_execution_window(
    *,
    monitor: str,
    mode: str,
    data_date: str | None = None,
    cut: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    last_n_hours: int | None = None,
    timezone: str = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> MonitorExecutionWindow:

    monitor_key = str(
        monitor
    ).upper()

    if monitor_key not in MONITOR_IDS:
        raise ValueError(
            "Monitor invalido. "
            "Permitidos: "
            + ", ".join(
                sorted(MONITOR_IDS)
            )
        )

    base = resolve_execution_window(
        mode=mode,
        data_date=data_date,
        cut=cut,
        window_start=window_start,
        window_end=window_end,
        last_n_hours=last_n_hours,
        timezone=timezone,
        now=now,
    )

    start = datetime.fromisoformat(
        base.window_start
    )
    end = datetime.fromisoformat(
        base.window_end
    )

    if base.mode == ExecutionWindowMode.CUT.value:

        target_date = date.fromisoformat(
            base.data_date
        )

        tz = _timezone(
            base.timezone
        )

        if monitor_key == "AWS":

            if base.cut == "09:00":
                previous_day = (
                    target_date
                    - timedelta(days=1)
                )

                start = datetime.combine(
                    previous_day,
                    time(18, 0),
                    tzinfo=tz,
                )

                end = datetime.combine(
                    target_date,
                    time(9, 0),
                    tzinfo=tz,
                )

            elif base.cut == "13:00":
                start = datetime.combine(
                    target_date,
                    time(9, 0),
                    tzinfo=tz,
                )

                end = datetime.combine(
                    target_date,
                    time(13, 0),
                    tzinfo=tz,
                )

            elif base.cut == "17:00":
                start = datetime.combine(
                    target_date,
                    time(13, 0),
                    tzinfo=tz,
                )

                end = datetime.combine(
                    target_date,
                    time(17, 0),
                    tzinfo=tz,
                )

        elif monitor_key in {
            "PASARELAS",
            "HERCULES",
        }:
            # Monitores guiados por fecha.
            # Nexus NO impone estas horas a
            # sus fuentes; data_date + cut
            # son el contrato operativo.
            start = datetime.combine(
                target_date,
                time.min,
                tzinfo=tz,
            )

            end = datetime.combine(
                target_date,
                ALLOWED_CUTS[base.cut],
                tzinfo=tz,
            )

    return MonitorExecutionWindow(
        monitor=monitor_key,
        mode=base.mode,
        execution_date=
            base.execution_date,
        data_date=base.data_date,
        window_start=
            start.isoformat(),
        window_end=
            end.isoformat(),
        cut=base.cut,
        timezone=base.timezone,
    )


def resolve_general_execution_windows(
    *,
    mode: str,
    data_date: str | None = None,
    cut: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    last_n_hours: int | None = None,
    timezone: str = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> dict[str, MonitorExecutionWindow]:

    result = {}

    for monitor in (
        "AWS",
        "PASARELAS",
        "HERCULES",
    ):
        result[monitor] = (
            resolve_monitor_execution_window(
                monitor=monitor,
                mode=mode,
                data_date=data_date,
                cut=cut,
                window_start=window_start,
                window_end=window_end,
                last_n_hours=
                    last_n_hours,
                timezone=timezone,
                now=now,
            )
        )

    return result
