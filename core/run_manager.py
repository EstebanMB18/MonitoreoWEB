from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Dict
import itertools
import socket

from core.models import RunContext, RunStatus


@dataclass
class RunRecord:
    context: RunContext
    status: RunStatus = RunStatus.PENDING

    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    message: str | None = None
    cancelled: bool = False

    def start(self) -> None:
        self.status = RunStatus.RUNNING
        self.started_at = datetime.now()

    def finish(
        self,
        status: RunStatus,
        message: str | None = None,
    ) -> None:
        self.status = status
        self.message = message
        self.finished_at = datetime.now()

    def cancel(self) -> None:
        self.cancelled = True
        self.status = RunStatus.CANCELLED
        self.finished_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "run_id": self.context.run_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "message": self.message,
            "cancelled": self.cancelled,
            "context": self.context.to_dict(),
        }


class RunManager:
    def __init__(self) -> None:
        self._runs: Dict[str, RunRecord] = {}
        self._lock = Lock()
        self._counter = itertools.count(1)

    def create_run(
        self,
        *,
        cut: str | None = None,
        execution_date: str | None = None,
        user: str | None = None,
        installation_mode: str = "operator",
    ) -> RunRecord:

        now = datetime.now()
        sequence = next(self._counter)

        run_id = (
            f"RUN-{now:%Y%m%d-%H%M}-{sequence:03d}"
        )

        context = RunContext(
            run_id=run_id,
            cut=cut,
            execution_date=execution_date,
            user=user,
            computer=socket.gethostname(),
            installation_mode=installation_mode,
        )

        record = RunRecord(context=context)

        with self._lock:
            self._runs[run_id] = record

        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(self) -> list[RunRecord]:
        with self._lock:
            return list(self._runs.values())

    def start(self, run_id: str) -> RunRecord:
        run = self._require(run_id)
        run.start()
        return run

    def finish(
        self,
        run_id: str,
        status: RunStatus,
        message: str | None = None,
    ) -> RunRecord:
        run = self._require(run_id)
        run.finish(status=status, message=message)
        return run

    def cancel(self, run_id: str) -> RunRecord:
        run = self._require(run_id)
        run.cancel()
        return run

    def is_cancelled(self, run_id: str) -> bool:
        run = self._require(run_id)
        return run.cancelled

    def _require(self, run_id: str) -> RunRecord:
        run = self.get(run_id)

        if not run:
            raise KeyError(f"Run no encontrado: {run_id}")

        return run
