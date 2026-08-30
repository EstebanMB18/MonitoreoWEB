from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]

if str(PROJECT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT),
    )


from core.daily_closure import (
    catch_up_all_monitors,
    catch_up_monitor_closures,
    close_all_monitors,
    close_monitor_day,
)


VALID_MONITORS = {
    "AWS",
    "PASARELAS",
    "HERCULES",
}


def _yesterday() -> str:
    return (
        date.today()
        - timedelta(days=1)
    ).isoformat()


def _monitor(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.upper()

    if normalized not in VALID_MONITORS:
        raise ValueError(
            f"Monitor no valido: {value}"
        )

    return normalized


def _date(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    return date.fromisoformat(
        value
    ).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Cierre diario historico "
            "Centro de Monitoreo V2"
        )
    )

    parser.add_argument(
        "--monitor",
        choices=[
            "AWS",
            "PASARELAS",
            "HERCULES",
            "aws",
            "pasarelas",
            "hercules",
        ],
    )

    parser.add_argument(
        "--date",
        dest="closure_date",
        help="YYYY-MM-DD. Default: ayer.",
    )

    parser.add_argument(
        "--catch-up",
        action="store_true",
        help=(
            "Cierra fechas faltantes "
            "hasta la fecha objetivo."
        ),
    )

    parser.add_argument(
        "--start-date",
        help=(
            "Fecha inicial para catch-up "
            "cuando no existe cierre previo."
        ),
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida JSON.",
    )

    args = parser.parse_args()

    try:
        monitor = _monitor(
            args.monitor
        )

        closure_date = (
            _date(args.closure_date)
            or _yesterday()
        )

        start_date = _date(
            args.start_date
        )

        if (
            closure_date
            >= date.today().isoformat()
        ):
            raise ValueError(
                "El cierre solo puede "
                "realizarse hasta ayer."
            )

        if args.catch_up:
            if monitor:
                result = (
                    catch_up_monitor_closures(
                        monitor=monitor,
                        start_date=start_date,
                        until_date=closure_date,
                    )
                )
            else:
                result = (
                    catch_up_all_monitors(
                        start_date=start_date,
                        until_date=closure_date,
                    )
                )
        else:
            if monitor:
                result = close_monitor_day(
                    monitor=monitor,
                    closure_date=closure_date,
                )
            else:
                result = close_all_monitors(
                    closure_date=closure_date,
                )

        if args.json:
            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(
                "CIERRE DIARIO OK"
            )
            print(
                f"Fecha: {closure_date}"
            )
            print(
                f"Monitor: "
                f"{monitor or 'TODOS'}"
            )
            print(
                f"Catch-up: "
                f"{args.catch_up}"
            )

        return 0

    except Exception as exc:
        print(
            (
                "ERROR CIERRE DIARIO: "
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
