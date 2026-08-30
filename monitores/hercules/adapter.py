from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from core.events import EventBus
from core.monitor_base import BaseMonitor
from core.models import MonitorOutput, RunContext, RunStatus


BASE = Path(__file__).resolve().parent
SRC = BASE / "src"

STORAGE_STATE = BASE / "storage" / "hercules_sesion.json"
DOWNLOADS_DIR = BASE / "downloads"
REPORTS_DIR = BASE / "reports"


class HerculesMonitor(BaseMonitor):
    name = "HERCULES"

    def __init__(
        self,
        *,
        context: RunContext,
        event_bus: EventBus,
    ) -> None:
        super().__init__(
            context=context,
            event_bus=event_bus,
        )

        self.summary_path: Path | None = None
        self.download_path: Path | None = None
        self.stdout: str = ""
        self.stderr: str = ""

    def precheck(self) -> bool:
        if not STORAGE_STATE.exists():
            self.result.errors.append(
                "No existe la sesión local de Hércules."
            )
            return False

        if not SRC.exists():
            self.result.errors.append(
                f"No existe código Hércules: {SRC}"
            )
            return False

        DOWNLOADS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        REPORTS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.logger.info(
            "Precheck Hércules completado."
        )

        return True

    def execute(self) -> None:
        dias_atras = self._resolve_days_back()

        nombre_descarga = (
            f"hercules_v2_{self.context.run_id}.xlsx"
        )

        nombre_resumen = (
            f"resumen_hercules_v2_{self.context.run_id}.xlsx"
        )

        self.logger.progress(
            25,
            f"Ejecutando Hércules. Días atrás={dias_atras}",
        )

        script = f"""
import sys
from pathlib import Path

src = Path(r"{SRC}")
sys.path.insert(0, str(src))

from monitoreo_hercules import main

resultado = main(
    dias_atras={dias_atras},
    nombre_descarga={nombre_descarga!r},
    nombre_resumen={nombre_resumen!r},
)

print("HERCULES_RESULT_PATH=" + str(resultado))
"""

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        process = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
            ],
            cwd=str(BASE),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.stdout = process.stdout or ""
        self.stderr = process.stderr or ""

        self._publish_process_output(
            self.stdout,
            level="INFO",
        )

        self._publish_process_output(
            self.stderr,
            level="WARNING",
        )

        if process.returncode != 0:
            raise RuntimeError(
                "Hércules terminó con código "
                f"{process.returncode}. "
                f"{self._last_error_message()}"
            )

        result_path = self._extract_result_path()

        if not result_path:
            raise RuntimeError(
                "Hércules finalizó pero no devolvió "
                "la ruta del resumen."
            )

        self.summary_path = Path(result_path)

        if not self.summary_path.exists():
            raise RuntimeError(
                "El resumen informado por Hércules "
                f"no existe: {self.summary_path}"
            )

        self.download_path = (
            DOWNLOADS_DIR /
            nombre_descarga
        )

        self.logger.progress(
            75,
            "Validando resumen Hércules",
        )

        records = self._count_records(
            self.summary_path
        )

        self.result.records = records

        self.result.metadata.update(
            {
                "dias_atras": dias_atras,
                "summary_file": str(
                    self.summary_path
                ),
                "download_file": (
                    str(self.download_path)
                    if self.download_path.exists()
                    else None
                ),
                "installation_mode":
                    self.context.installation_mode,
            }
        )

        self.result.outputs = MonitorOutput(
            excel=str(self.summary_path),
            folder=str(REPORTS_DIR.resolve()),
        )

        self.logger.info(
            f"Resumen Hércules generado: {self.summary_path}"
        )

        self.logger.info(
            f"Registros consolidados Hércules: {records}"
        )

    def validate(self) -> RunStatus:
        if self.result.errors:
            status = RunStatus.ERROR

        elif not self.summary_path:
            status = RunStatus.ERROR

        elif not self.summary_path.exists():
            status = RunStatus.ERROR

        elif self.result.records is None:
            status = RunStatus.WARNING

        elif self.result.records == 0:
            status = RunStatus.NO_DATA

        elif self.result.alerts:
            status = RunStatus.WARNING

        else:
            status = RunStatus.OK

        if (
            self.summary_path
            and self.summary_path.exists()
        ):
            self.result.details = (
                self._build_structured_details(
                    self.summary_path
                )
            )

        return status

    def _build_structured_details(
        self,
        path: Path,
    ) -> dict:
        try:
            import unicodedata

            def normalize_name(value: str) -> str:
                value = unicodedata.normalize(
                    "NFKD",
                    str(value),
                )

                return "".join(
                    char
                    for char in value
                    if not unicodedata.combining(char)
                ).strip().lower()

            xls = pd.ExcelFile(path)

            sheet_name = next(
                (
                    name
                    for name in xls.sheet_names
                    if normalize_name(name)
                    == "diagnostico"
                ),
                None,
            )

            if not sheet_name:
                raise ValueError(
                    "No se encontr? hoja Diagnostico."
                )

            df = pd.read_excel(
                path,
                sheet_name=sheet_name,
            )

            normalized_columns = {
                normalize_name(column): column
                for column in df.columns
            }

        except Exception as exc:
            return {
                "summary": {},
                "groups": [],
                "business_alerts": [
                    str(item)
                    for item in self.result.alerts
                ],
                "technical_errors": [
                    {
                        "type": "TECHNICAL_ERROR",
                        "detail": (
                            "No fue posible leer "
                            f"Diagn?stico: {exc}"
                        ),
                    }
                ],
                "series": {},
            }

        def number(value):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return 0

        option_col = normalized_columns.get(
            "opcion"
        )

        if not option_col:
            return {
                "summary": {},
                "groups": [],
                "business_alerts": [
                    str(item)
                    for item in self.result.alerts
                ],
                "technical_errors": [
                    {
                        "type": "TECHNICAL_ERROR",
                        "detail": (
                            "La hoja Diagn?stico "
                            "no contiene columna Opci?n."
                        ),
                    }
                ],
                "series": {},
            }

        option_values = (
            df[option_col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        total_rows = df[
            option_values.str.lower()
            == "total general"
        ]

        total = (
            total_rows.iloc[0]
            if not total_rows.empty
            else None
        )

        option_rows = df[
            option_values.str.lower()
            != "total general"
        ].copy()

        option_rows = option_rows[
            option_rows[option_col]
            .fillna("")
            .astype(str)
            .str.strip()
            != ""
        ]

        services = []
        technical_errors = [
            {
                "type": "TECHNICAL_ERROR",
                "detail": str(error),
            }
            for error in self.result.errors
        ]

        for _, row in option_rows.iterrows():

            option = str(
                row.get(option_col, "")
            ).strip()

            missing = str(
                row.get(
                    normalized_columns.get("columnas faltantes", "Columnas faltantes"),
                    "",
                )
                or ""
            ).strip()

            query_ok = (
                missing == ""
                or missing.upper() == "OK"
            )

            technical_error = (
                None
                if query_ok
                else (
                    "Columnas faltantes: "
                    f"{missing}"
                )
            )

            status = (
                "OK"
                if query_ok
                else "TECHNICAL_ERROR"
            )

            metrics = []

            for metric_id, column in (
                ("filas_base", normalized_columns.get("filas base", "Filas base")),
                ("pago_realizado", normalized_columns.get("pago realizado", "Pago Realizado")),
                ("checkout", normalized_columns.get("checkout", "Checkout")),
                (
                    "pendiente_recaudo",
                    normalized_columns.get("pendiente recaudo", "Pendiente Recaudo"),
                ),
            ):
                metrics.append({
                    "id": (
                        f"{option}-{metric_id}"
                        .lower()
                        .replace(" ", "-")
                    ),
                    "metric": column,
                    "value": number(
                        row.get(column)
                    ),
                    "status": status,
                    "severity": None,
                    "query_ok": query_ok,
                    "technical_error": (
                        technical_error
                    ),
                    "detail": None,
                })

            services.append({
                "id": (
                    option
                    .lower()
                    .replace(" ", "-")
                ),
                "name": option,
                "status": status,
                "metrics": metrics,
            })

            if technical_error:
                technical_errors.append({
                    "type": "TECHNICAL_ERROR",
                    "service": option,
                    "detail": technical_error,
                })

        def total_value(column):
            if total is not None:
                return number(
                    total.get(column)
                )

            return sum(
                number(row.get(column))
                for _, row
                in option_rows.iterrows()
            )

        return {
            "summary": {
                "total_records": total_value(
                    normalized_columns.get("filas base", "Filas base")
                ),
                "pago_realizado": total_value(
                    normalized_columns.get("pago realizado", "Pago Realizado")
                ),
                "checkout": total_value(
                    normalized_columns.get("checkout", "Checkout")
                ),
                "pendiente_recaudo": total_value(
                    normalized_columns.get("pendiente recaudo", "Pendiente Recaudo")
                ),
                "options": int(
                    len(option_rows)
                ),
                "business_alerts": len(
                    self.result.alerts
                ),
                "technical_errors": len(
                    technical_errors
                ),
            },
            "groups": [
                {
                    "id": "HERCULES",
                    "name": "HERCULES",
                    "services": services,
                }
            ],
            "business_alerts": [
                str(item)
                for item in self.result.alerts
            ],
            "technical_errors": technical_errors,
            "series": {},
        }

    def _resolve_days_back(self) -> int:
        execution_date = (
            self.context.execution_date or ""
        ).strip()

        if execution_date:
            from datetime import date

            target = date.fromisoformat(
                execution_date
            )

            today = date.today()

            delta = (
                today - target
            ).days

            if delta < 0:
                raise ValueError(
                    "Hércules no puede consultar "
                    "una fecha futura."
                )

            return delta

        return 0

    def _extract_result_path(
        self,
    ) -> str | None:
        marker = "HERCULES_RESULT_PATH="

        for line in reversed(
            self.stdout.splitlines()
        ):
            if line.startswith(marker):
                return line[
                    len(marker):
                ].strip()

        return None

    def _publish_process_output(
        self,
        text: str,
        *,
        level: str,
    ) -> None:
        for raw in text.splitlines():
            line = raw.strip()

            if not line:
                continue

            if line.startswith(
                "HERCULES_RESULT_PATH="
            ):
                continue

            if level == "WARNING":
                self.logger.warning(line)
            else:
                self.logger.info(line)

    def _last_error_message(
        self,
    ) -> str:
        lines = [
            line.strip()
            for line in (
                self.stderr
                or self.stdout
            ).splitlines()
            if line.strip()
        ]

        if not lines:
            return "Sin detalle adicional."

        return lines[-1]

    @staticmethod
    def _count_records(
        path: Path,
    ) -> int:
        try:
            sheets = pd.read_excel(
                path,
                sheet_name=None,
            )
        except Exception:
            return 0

        preferred = sheets.get(
            "Base_Consolidada"
        )

        if preferred is not None:
            return int(
                preferred.dropna(
                    how="all"
                ).shape[0]
            )

        candidates = [
            df
            for name, df in sheets.items()
            if name.startswith("Base_")
        ]

        if not candidates:
            return 0

        return int(
            sum(
                df.dropna(
                    how="all"
                ).shape[0]
                for df in candidates
            )
        )
