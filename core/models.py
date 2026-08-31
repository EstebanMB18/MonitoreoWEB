from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class RunStatus(str, Enum):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    PROCESSING = "PROCESSING"
    PUBLISHING = "PUBLISHING"
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    NO_DATA = "NO_DATA"
    STALE = "STALE"


@dataclass
class MonitorOutput:
    dashboard: str | None = None
    excel: str | None = None
    folder: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MonitorResult:
    monitor: str
    status: RunStatus = RunStatus.PENDING
    progress: int = 0

    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None

    records: int | None = None

    alerts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    outputs: MonitorOutput = field(default_factory=MonitorOutput)

    metadata: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def finish(self, status: RunStatus) -> None:
        self.status = status
        self.finished_at = datetime.now()

        if self.started_at:
            self.duration_seconds = round(
                (self.finished_at - self.started_at).total_seconds(),
                2,
            )

        self.progress = 100

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        data["status"] = self.status.value

        for key in ("started_at", "finished_at"):
            value = getattr(self, key)
            data[key] = value.isoformat() if value else None

        return data


@dataclass
class RunContext:
    run_id: str

    cut: str | None = None
    window_mode: str | None = None

    execution_date: str | None = None
    data_date: str | None = None

    window_start: str | None = None
    window_end: str | None = None

    user: str | None = None
    computer: str | None = None

    installation_mode: str = "operator"

    output_root: Path | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        if self.output_root:
            data["output_root"] = str(self.output_root)

        return data
