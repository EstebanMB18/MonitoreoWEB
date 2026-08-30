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
DATA = BASE / "data"
SALIDA = DATA / "salida"
DESCARGAS = DATA / "temporal_descargas"

EXCEL_RESULTADO = SALIDA / "resumen_verticales_ultimo.xlsx"


class PasarelasMonitor(BaseMonitor):
    name = "PASARELAS"

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

        self.stdout = ""
        self.stderr = ""
        self.excel_path: Path | None = None
        self.dashboard_path: Path | None = None
        self.df: pd.DataFrame | None = None

    def precheck(self) -> bool:
        script = SRC / "ejecutar_paralelo.py"

        if not script.exists():
            self.result.errors.append(
                f"No existe orquestador Pasarelas: {script}"
            )
            return False

        config_path = BASE / "config" / "verticales.csv"

        if not config_path.exists():
            self.result.errors.append(
                f"No existe configuración de verticales: {config_path}"
            )
            return False

        SALIDA.mkdir(parents=True, exist_ok=True)
        DESCARGAS.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            "Precheck Pasarelas completado."
        )

        return True

    def execute(self) -> None:
        corte = self._resolve_cut()

        self.logger.progress(
            20,
            f"Preparando Pasarelas para corte {corte}",
        )

        cmd = [
            sys.executable,
            str(SRC / "ejecutar_paralelo.py"),
            "--modo",
            "actual",
            "--corte",
            corte,
            "--no-publicar",
        ]

        self.logger.info(
            "Modo operator: publicación oficial deshabilitada."
        )

        self.logger.progress(
            25,
            "Iniciando PayU y consultas eCollect",
        )

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.run(
            cmd,
            cwd=str(BASE),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.stdout = process.stdout or ""
        self.stderr = process.stderr or ""

        self._publish_output(
            self.stdout,
            warning=False,
        )

        self._publish_output(
            self.stderr,
            warning=True,
        )

        if process.returncode != 0:
            raise RuntimeError(
                "Pasarelas terminó con código "
                f"{process.returncode}. "
                f"{self._last_error_message()}"
            )

        self.logger.progress(
            75,
            "Validando consolidado de Pasarelas",
        )

        if not EXCEL_RESULTADO.exists():
            raise RuntimeError(
                "Pasarelas terminó sin generar "
                f"{EXCEL_RESULTADO}"
            )

        self.excel_path = EXCEL_RESULTADO.resolve()

        self.df = pd.read_excel(
            self.excel_path
        )

        self.result.records = int(
            len(self.df)
        )

        self.dashboard_path = (
            self._detect_dashboard()
        )

        self._build_metadata(corte)

        self.result.outputs = MonitorOutput(
            dashboard=(
                str(self.dashboard_path)
                if self.dashboard_path
                else None
            ),
            excel=str(self.excel_path),
            folder=str(SALIDA.resolve()),
        )

        self.logger.info(
            f"Registros consolidados Pasarelas: "
            f"{self.result.records}"
        )

        if self.dashboard_path:
            self.logger.info(
                f"Dashboard Pasarelas: "
                f"{self.dashboard_path}"
            )

        self.logger.info(
            f"Excel Pasarelas: {self.excel_path}"
        )

    def validate(self) -> RunStatus:
        if self.result.errors:
            return RunStatus.ERROR

        if self.df is None:
            return RunStatus.ERROR

        if self.result.records == 0:
            return RunStatus.NO_DATA

        if self._has_process_warnings():
            self.result.alerts.append(
                "Uno o más procesos de Pasarelas "
                "reportaron advertencias durante la ejecución."
            )
            return RunStatus.WARNING

        if self._has_business_alerts():
            return RunStatus.WARNING

        return RunStatus.OK

    def _resolve_cut(self) -> str:
        raw = str(
            self.context.cut or "09"
        ).strip()

        mapping = {
            "9": "09",
            "09": "09",
            "09:00": "09",
            "1": "09",

            "13": "13",
            "13:00": "13",
            "2": "13",

            "17": "17",
            "17:00": "17",
            "3": "17",
        }

        if raw not in mapping:
            raise ValueError(
                f"Corte Pasarelas no válido: {raw}"
            )

        return mapping[raw]

    def _detect_dashboard(
        self,
    ) -> Path | None:
        candidates = [
            SALIDA / "dashboard_verticales.html",
            BASE / "reportes" / "dashboard_verticales.html",
        ]

        for path in candidates:
            if path.exists():
                return path.resolve()

        htmls = sorted(
            BASE.rglob("*.html"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for path in htmls:
            name = path.name.lower()

            if (
                "dashboard" in name
                and "vertical" in name
            ):
                return path.resolve()

        return None

    def _build_metadata(
        self,
        corte: str,
    ) -> None:
        assert self.df is not None

        df = self.df

        metadata = {
            "corte": corte,
            "installation_mode":
                self.context.installation_mode,
            "filas_consolidadas": int(len(df)),
            "columnas": list(df.columns),
        }

        if "vertical" in df.columns:
            metadata["verticales"] = int(
                df["vertical"]
                .dropna()
                .astype(str)
                .nunique()
            )

        if "codigo" in df.columns:
            metadata["codigos"] = sorted(
                df["codigo"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

        if "cantidad_ok" in df.columns:
            metadata["cantidad_ok_total"] = int(
                pd.to_numeric(
                    df["cantidad_ok"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        if "cantidad_total" in df.columns:
            metadata["cantidad_total"] = int(
                pd.to_numeric(
                    df["cantidad_total"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        if "cantidad_fallida" in df.columns:
            metadata["cantidad_fallida"] = int(
                pd.to_numeric(
                    df["cantidad_fallida"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        self.result.metadata.update(
            metadata
        )

    def _has_process_warnings(
        self,
    ) -> bool:
        text = (
            self.stdout
            + "\n"
            + self.stderr
        ).lower()

        patterns = [
            "advertencia - procesos con error",
            "adverten",
            "falló",
            "fallo",
        ]

        return any(
            pattern in text
            for pattern in patterns
        )

    def _has_business_alerts(
        self,
    ) -> bool:
        if self.df is None:
            return False

        for column in [
            "alerta",
            "nivel_alerta",
            "estado_alerta",
        ]:
            if column not in self.df.columns:
                continue

            values = (
                self.df[column]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
            )

            active = values[
                ~values.isin(
                    [
                        "",
                        "OK",
                        "NORMAL",
                        "VERDE",
                        "SIN ALERTA",
                    ]
                )
            ]

            if not active.empty:
                self.result.alerts.extend(
                    sorted(
                        active.unique().tolist()
                    )
                )
                return True

        return False

    def _publish_output(
        self,
        text: str,
        *,
        warning: bool,
    ) -> None:
        for raw in text.splitlines():
            line = raw.strip()

            if not line:
                continue

            if warning:
                self.logger.warning(line)
            else:
                self.logger.info(line)

    def _last_error_message(
        self,
    ) -> str:
        text = (
            self.stderr
            or self.stdout
        )

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        if not lines:
            return "Sin detalle adicional."

        return lines[-1]
