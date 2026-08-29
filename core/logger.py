from __future__ import annotations

import logging
from pathlib import Path

from core.events import EventBus


class MonitorLogger:
    def __init__(
        self,
        *,
        run_id: str,
        monitor: str,
        event_bus: EventBus,
        log_root: str | Path = "runtime/logs",
    ) -> None:

        self.run_id = run_id
        self.monitor = monitor.upper()
        self.event_bus = event_bus

        log_root = Path(log_root)
        log_root.mkdir(parents=True, exist_ok=True)

        self.log_file = log_root / f"{run_id}.log"

        logger_name = f"monitor.{run_id}.{self.monitor}"

        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        if not self._logger.handlers:
            handler = logging.FileHandler(
                self.log_file,
                encoding="utf-8",
            )

            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s"
            )

            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def _emit(
        self,
        level: str,
        message: str,
        *,
        event_type: str = "LOG",
        progress: int | None = None,
        data: dict | None = None,
    ) -> None:

        getattr(self._logger, level.lower())(message)

        self.event_bus.publish(
            run_id=self.run_id,
            monitor=self.monitor,
            level=level,
            event_type=event_type,
            message=message,
            progress=progress,
            data=data,
        )

    def debug(self, message: str, **kwargs) -> None:
        self._emit("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self._emit("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self._emit("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self._emit("ERROR", message, **kwargs)

    def progress(
        self,
        value: int,
        message: str,
        *,
        data: dict | None = None,
    ) -> None:

        value = max(0, min(100, value))

        self._emit(
            "INFO",
            message,
            event_type="PROGRESS",
            progress=value,
            data=data,
        )
