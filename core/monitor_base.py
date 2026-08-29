from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from core.events import EventBus
from core.logger import MonitorLogger
from core.models import MonitorResult, RunContext, RunStatus


class BaseMonitor(ABC):
    name: str = "UNKNOWN"

    def __init__(
        self,
        *,
        context: RunContext,
        event_bus: EventBus,
    ) -> None:
        self.context = context
        self.event_bus = event_bus

        self.result = MonitorResult(
            monitor=self.name,
            status=RunStatus.PENDING,
        )

        self.logger = MonitorLogger(
            run_id=context.run_id,
            monitor=self.name,
            event_bus=event_bus,
        )

    def run(self) -> MonitorResult:
        self.result.started_at = datetime.now()
        self.result.status = RunStatus.PREPARING

        self.logger.progress(
            5,
            f"Preparando monitor {self.name}",
        )

        try:
            precheck_ok = self.precheck()

            if not precheck_ok:
                self.result.errors.append(
                    "El precheck del monitor no fue satisfactorio."
                )

                self.result.finish(RunStatus.ERROR)

                self.logger.error(
                    "Precheck fallido",
                    event_type="STATUS",
                    progress=100,
                )

                return self.result

            self.result.status = RunStatus.RUNNING

            self.logger.progress(
                15,
                f"Iniciando ejecución de {self.name}",
            )

            self.execute()

            self.result.status = RunStatus.PROCESSING

            self.logger.progress(
                85,
                f"Validando resultados de {self.name}",
            )

            validation_status = self.validate()

            if validation_status is None:
                validation_status = RunStatus.OK

            self.result.finish(validation_status)

            self.logger.progress(
                100,
                f"{self.name} finalizado: {self.result.status.value}",
            )

            return self.result

        except TimeoutError as exc:
            self.result.errors.append(str(exc))
            self.result.finish(RunStatus.TIMEOUT)

            self.logger.error(
                f"Timeout en {self.name}: {exc}",
                event_type="STATUS",
                progress=100,
            )

            return self.result

        except Exception as exc:
            self.result.errors.append(
                f"{type(exc).__name__}: {exc}"
            )

            self.result.finish(RunStatus.ERROR)

            self.logger.error(
                f"Error en {self.name}: {exc}",
                event_type="STATUS",
                progress=100,
            )

            return self.result

    def precheck(self) -> bool:
        return True

    @abstractmethod
    def execute(self) -> None:
        raise NotImplementedError

    def validate(self) -> RunStatus:
        if self.result.errors:
            return RunStatus.ERROR

        if self.result.alerts:
            return RunStatus.WARNING

        if self.result.records == 0:
            return RunStatus.NO_DATA

        return RunStatus.OK
