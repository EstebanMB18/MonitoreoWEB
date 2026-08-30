from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import yaml

from core.events import EventBus
from core.monitor_base import BaseMonitor
from core.models import MonitorOutput, RunContext, RunStatus


BASE = Path(__file__).resolve().parent
SRC = BASE / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from monitoreo_aws.core.alerts import evaluar
from monitoreo_aws.core.aws import asegurar_sso_profiles
from monitoreo_aws.core.windows import obtener_ventana
from monitoreo_aws.reports.excel import generar_excel
from monitoreo_aws.reports.html import generar_html
from monitoreo_aws.services.collector import recolectar


class AWSMonitor(BaseMonitor):
    name = "AWS"

    def __init__(
        self,
        *,
        context: RunContext,
        event_bus: EventBus,
        demo: bool = False,
    ) -> None:
        super().__init__(
            context=context,
            event_bus=event_bus,
        )

        self.demo = demo

        self.cfg: dict = {}
        self.ventana = None
        self.data: dict = {}
        self.alertas: list = []

        self.total_metricas = 0
        self.metricas_validas = 0
        self.metricas_fallidas = 0

        self.output_dir: Path | None = None

    def precheck(self) -> bool:
        config_path = BASE / "config" / "config.yaml"

        if not config_path.exists():
            self.result.errors.append(
                f"No existe configuración AWS: {config_path}"
            )
            return False

        self.cfg = yaml.safe_load(
            config_path.read_text(encoding="utf-8")
        )

        if not isinstance(self.cfg, dict):
            self.result.errors.append(
                "config.yaml AWS no contiene una configuración válida."
            )
            return False

        for section in ("app", "profiles", "services"):
            if section not in self.cfg:
                self.result.errors.append(
                    f"Falta sección AWS requerida: {section}"
                )
                return False

        self.logger.info(
            "Configuración AWS cargada correctamente."
        )

        return True

    def execute(self) -> None:
        cfg = copy.deepcopy(self.cfg)

        corte = self._resolve_cut()

        self.logger.progress(
            20,
            f"Resolviendo ventana AWS para corte {corte}",
        )

        self.ventana = obtener_ventana(
            corte,
            self.context.execution_date,
            cfg["app"]["timezone"],
            "00:00",
            "23:59",
        )

        self.logger.info(
            f"Ventana AWS: {self.ventana.texto}"
        )

        if not self.demo:
            self.logger.progress(
                25,
                "Validando sesiones AWS SSO",
            )

            asegurar_sso_profiles(
                cfg["profiles"],
                cfg["app"]["region"],
            )

        self.logger.progress(
            35,
            "Consultando métricas CloudWatch",
        )

        if self.demo:
            from monitoreo_aws.demo import datos_demo
            self.data = datos_demo()
        else:
            self.data = recolectar(
                cfg,
                self.ventana,
            )

        metricas = dict(
            self.data.get("metricas", {}) or {}
        )

        self.total_metricas = len(metricas)

        self.metricas_validas = sum(
            value is not None
            for value in metricas.values()
        )

        self.metricas_fallidas = sum(
            value is None
            for value in metricas.values()
        )

        errores_consulta = list(
            self.data.get(
                "errores_consulta",
                [],
            ) or []
        )

        self.logger.info(
            "Diagnóstico AWS: "
            f"total={self.total_metricas}, "
            f"válidas={self.metricas_validas}, "
            f"fallidas={self.metricas_fallidas}, "
            f"errores={len(errores_consulta)}"
        )

        self.result.records = self.metricas_validas

        self.result.metadata.update(
            {
                "metricas_totales": self.total_metricas,
                "metricas_validas": self.metricas_validas,
                "metricas_fallidas": self.metricas_fallidas,
                "errores_consulta": errores_consulta,
                "corte": getattr(
                    self.ventana,
                    "corte",
                    None,
                ),
                "rango": getattr(
                    self.ventana,
                    "texto",
                    None,
                ),
            }
        )

        self._validate_collection_health()

        self.logger.progress(
            70,
            "Evaluando alertas AWS",
        )

        self.alertas = evaluar(
            cfg,
            self.ventana,
            self.data,
        )

        self.result.alerts = [
            self._alert_to_text(alert)
            for alert in self.alertas
        ]

        self.result.metadata["cantidad_alertas"] = len(
            self.alertas
        )

        self.result.details = (
            self._build_structured_details()
        )

        self.logger.progress(
            78,
            "Generando reportes AWS",
        )

        self.output_dir = self._resolve_output_dir()

        excel_path = (
            self.output_dir /
            "Monitoreo_AWS.xlsx"
        )

        html_path = (
            self.output_dir /
            "Dashboard_AWS.html"
        )

        excel_tmp = (
            self.output_dir /
            ".Monitoreo_AWS.tmp.xlsx"
        )

        html_tmp = (
            self.output_dir /
            ".Dashboard_AWS.tmp.html"
        )

        generar_excel(
            excel_tmp,
            cfg,
            self.ventana,
            self.data,
            self.alertas,
        )

        generar_html(
            html_tmp,
            cfg,
            self.ventana,
            self.data,
            self.alertas,
        )

        excel_tmp.replace(excel_path)
        html_tmp.replace(html_path)

        self.result.outputs = MonitorOutput(
            dashboard=str(html_path),
            excel=str(excel_path),
            folder=str(self.output_dir),
        )

        self.logger.info(
            f"Dashboard AWS generado: {html_path}"
        )

        self.logger.info(
            f"Excel AWS generado: {excel_path}"
        )

        if (
            self.context.installation_mode.lower()
            == "publisher"
        ):
            self._write_management_json()

    def validate(self) -> RunStatus:
        if self.total_metricas == 0:
            return RunStatus.NO_DATA

        if self.metricas_validas == 0:
            return RunStatus.ERROR

        proporcion_fallo = (
            self.metricas_fallidas /
            max(self.total_metricas, 1)
        )

        if (
            self.total_metricas >= 3
            and proporcion_fallo >= 0.80
        ):
            return RunStatus.ERROR

        if self.result.alerts:
            return RunStatus.WARNING

        errores = self.result.metadata.get(
            "errores_consulta",
            [],
        )

        if errores:
            return RunStatus.WARNING

        return RunStatus.OK

    def _validate_collection_health(self) -> None:
        if self.total_metricas == 0:
            raise RuntimeError(
                "AWS no devolvió métricas."
            )

        if self.metricas_validas == 0:
            raise RuntimeError(
                "AWS NO PUBLICADO: ninguna métrica "
                "pudo consultarse."
            )

        proporcion_fallo = (
            self.metricas_fallidas /
            max(self.total_metricas, 1)
        )

        if (
            self.total_metricas >= 3
            and proporcion_fallo >= 0.80
        ):
            raise RuntimeError(
                "AWS NO PUBLICADO: falló al menos "
                "el 80% de las métricas."
            )

    def _resolve_cut(self) -> str:
        raw = str(
            self.context.cut or "auto"
        ).strip().lower()

        mapping = {
            "09": "1",
            "9": "1",
            "09:00": "1",
            "1": "1",

            "13": "2",
            "13:00": "2",
            "2": "2",

            "17": "3",
            "17:00": "3",
            "3": "3",

            "auto": "auto",
            "dia": "dia",
        }

        return mapping.get(
            raw,
            raw,
        )

    def _resolve_output_dir(self) -> Path:
        mode = (
            self.context.installation_mode
            or "operator"
        ).lower()

        if mode == "publisher":
            configured = str(
                self.cfg["app"].get(
                    "salida_oficial",
                    "",
                )
            ).strip()

            if not configured:
                raise RuntimeError(
                    "AWS publisher requiere "
                    "app.salida_oficial."
                )

            output = Path(configured).expanduser()

        else:
            if self.context.output_root:
                output = (
                    self.context.output_root /
                    "aws"
                )
            else:
                output = (
                    Path("runtime") /
                    "output" /
                    "aws"
                )

        output.mkdir(
            parents=True,
            exist_ok=True,
        )

        return output.resolve()

    def _write_management_json(self) -> None:
        if not self.output_dir:
            return

        general = (
            self.output_dir.parent /
            "GENERAL" /
            "data"
        )

        general.mkdir(
            parents=True,
            exist_ok=True,
        )

        target = (
            general /
            "aws_gerencial.json"
        )

        payload = {
            "fecha": self._json_safe(
                getattr(
                    self.ventana,
                    "fin",
                    None,
                )
            ),
            "corte": getattr(
                self.ventana,
                "corte",
                "",
            ),
            "rango": getattr(
                self.ventana,
                "texto",
                "",
            ),
            "metricas": self._json_safe(
                self.data.get(
                    "metricas",
                    {},
                )
            ),
            "detalles": self._json_safe(
                self.data.get(
                    "detalles",
                    {},
                )
            ),
            "errores_consulta": self._json_safe(
                self.data.get(
                    "errores_consulta",
                    [],
                )
            ),
            "alertas": self._json_safe(
                self.alertas
            ),
        }

        target.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.result.metadata[
            "management_json"
        ] = str(target)

        self.logger.info(
            f"Datos gerenciales AWS publicados: {target}"
        )

    def _build_structured_details(self) -> dict:
        metric_catalog = {
            "aprob_creacion_payu": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Aprobados creacion PayU",
            ),
            "aprob_creacion_ecollect": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Aprobados creacion eCollect",
            ),
            "aprob_estado_payu": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Aprobados estado PayU",
            ),
            "aprob_estado_ecollect": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Aprobados estado eCollect",
            ),
            "aprob_receiver": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Aprobados Receiver",
            ),
            "err_creacion_payu": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Errores creacion PayU",
            ),
            "err_creacion_ecollect": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Errores creacion eCollect",
            ),
            "err_estado_payu": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Errores estado PayU",
            ),
            "err_estado_ecollect": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Errores estado eCollect",
            ),
            "err_receiver": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Errores Receiver",
            ),
            "err_log": (
                "INTEROPPROD",
                "API Orquestador Pagos",
                "Errores log",
            ),
            "err_mongodb_update": (
                "INTEROPPROD",
                "MongoDB",
                "Error Update MongoDB",
            ),
            "seg_consulta_persona": (
                "SEGURIDAD",
                "Modulo de Seguridad",
                "ConsultaPersona",
            ),
            "error_cx": (
                "API SUBSIDIOS",
                "API Subsidios",
                "Error archivo CX",
            ),
            "tup_error": (
                "TARJETA TUP",
                "Tarjeta TUP",
                "Errores Tarjeta TUP",
            ),
            "serviciosred_total": (
                "SERVICIOS RED",
                "Servicios Red",
                "Notificaciones del corte",
            ),
            "serviciosred_ultima_hora": (
                "SERVICIOS RED",
                "Servicios Red",
                "Notificaciones ultima hora",
            ),
            "csc_task_timed": (
                "CSC",
                "Lambda Proxy PaymentsPost",
                "Task timed out",
            ),
            "csc_504": (
                "CSC",
                "Lambda Proxy PaymentsPost",
                "504 Gateway Time-out",
            ),
            "mens_timeout": (
                "MENSAJERIA",
                "API Mensajeria",
                "Timeout",
            ),
            "mens_503": (
                "MENSAJERIA",
                "API Mensajeria",
                "HTTP 503",
            ),
            "mens_502": (
                "MENSAJERIA",
                "API Mensajeria",
                "HTTP 502",
            ),
            "mens_report": (
                "MENSAJERIA",
                "API Mensajeria",
                "REPORT enviados",
            ),
            "mens_total_send": (
                "MENSAJERIA",
                "API Mensajeria",
                "Total enviados",
            ),
            "mens_cannot": (
                "MENSAJERIA",
                "API Mensajeria",
                "Cannot process",
            ),
            "mens_sms_failed": (
                "MENSAJERIA",
                "API Mensajeria",
                "SMS failed",
            ),
            "mens_error_400_total": (
                "MENSAJERIA",
                "API Mensajeria",
                "Errores HTTP 400",
            ),
            "mens_exitos_200_total": (
                "MENSAJERIA",
                "API Mensajeria",
                "Exitos HTTP 200",
            ),
            "otp_408": (
                "MENSAJERIA",
                "API Mensajeria",
                "OTP HTTP 408",
            ),
            "otp_500": (
                "MENSAJERIA",
                "Validar OTP",
                "OTP HTTP 500",
            ),
            "replicador": (
                "MENSAJERIA",
                "Replicador",
                "Replicaciones",
            ),
        }

        metrics = dict(
            self.data.get("metricas", {}) or {}
        )

        raw_errors = list(
            self.data.get(
                "errores_consulta",
                [],
            ) or []
        )

        technical_by_key = {}

        for error in raw_errors:
            text = str(error)
            key = text.split(":", 1)[0].strip()

            if key:
                technical_by_key[key] = text

        business_alerts = []

        for alert in self.alertas:
            if isinstance(alert, dict):
                business_alerts.append(
                    self._json_safe(alert)
                )
            else:
                business_alerts.append({
                    "detalle": str(alert),
                })

        severity_order = {
            "CRITICA": 4,
            "CRITICAL": 4,
            "ALTA": 3,
            "HIGH": 3,
            "MEDIA": 2,
            "MEDIUM": 2,
            "INFORMATIVA": 1,
            "INFO": 1,
        }

        def normalize_severity(value):
            raw = str(value or "").upper()

            if "CR" in raw and "TICA" in raw:
                return "CRITICAL"

            if raw in {"ALTA", "HIGH"}:
                return "HIGH"

            if raw in {"MEDIA", "MEDIUM"}:
                return "MEDIUM"

            if raw in {"INFORMATIVA", "INFO"}:
                return "INFO"

            return raw or None

        groups = {}

        for key, value in metrics.items():
            (
                group_name,
                service_name,
                metric_name,
            ) = metric_catalog.get(
                key,
                (
                    "AWS",
                    "AWS",
                    key.replace("_", " ").title(),
                ),
            )

            technical_error = (
                technical_by_key.get(key)
            )

            query_ok = (
                value is not None
                and technical_error is None
            )

            related_alerts = []

            for alert in business_alerts:
                alert_group = str(
                    alert.get("grupo", "")
                ).upper()

                alert_service = str(
                    alert.get("servicio", "")
                ).upper()

                if (
                    alert_group == group_name.upper()
                    or alert_service == service_name.upper()
                ):
                    related_alerts.append(alert)

            severity = None

            if related_alerts:
                severities = [
                    normalize_severity(
                        item.get("nivel")
                    )
                    for item in related_alerts
                ]

                severities = [
                    item
                    for item in severities
                    if item
                ]

                if severities:
                    severity = max(
                        severities,
                        key=lambda item: severity_order.get(
                            item,
                            0,
                        ),
                    )

            if not query_ok:
                status = "TECHNICAL_ERROR"
            elif severity:
                status = "ALERT"
            else:
                status = "OK"

            detail = None

            if technical_error:
                detail = technical_error
            elif related_alerts:
                detail = related_alerts[0].get(
                    "detalle"
                )

            group = groups.setdefault(
                group_name,
                {
                    "id": group_name,
                    "name": group_name,
                    "services": {},
                },
            )

            service = group["services"].setdefault(
                service_name,
                {
                    "id": (
                        service_name
                        .lower()
                        .replace(" ", "-")
                    ),
                    "name": service_name,
                    "metrics": [],
                },
            )

            service["metrics"].append({
                "id": key,
                "metric": metric_name,
                "value": self._json_safe(value),
                "status": status,
                "severity": severity,
                "detail": detail,
                "query_ok": query_ok,
                "technical_error": technical_error,
            })

        normalized_groups = []

        for group in groups.values():
            services = []

            for service in group["services"].values():
                metrics_list = service["metrics"]

                if any(
                    item["status"] == "TECHNICAL_ERROR"
                    for item in metrics_list
                ):
                    service_status = "TECHNICAL_ERROR"
                elif any(
                    item["status"] == "ALERT"
                    for item in metrics_list
                ):
                    service_status = "ALERT"
                else:
                    service_status = "OK"

                service["status"] = service_status
                services.append(service)

            normalized_groups.append({
                "id": group["id"],
                "name": group["name"],
                "services": services,
            })

        detail_series = {
            key: self._json_safe(value)
            for key, value in (
                self.data.get("detalles", {}) or {}
            ).items()
        }

        return {
            "summary": {
                "total_metrics": self.total_metricas,
                "valid_metrics": self.metricas_validas,
                "failed_metrics": self.metricas_fallidas,
                "business_alerts": len(
                    business_alerts
                ),
                "technical_errors": len(
                    raw_errors
                ),
            },
            "groups": normalized_groups,
            "business_alerts": business_alerts,
            "technical_errors": [
                {
                    "type": "TECHNICAL_ERROR",
                    "detail": str(error),
                }
                for error in raw_errors
            ],
            "series": detail_series,
        }

    @staticmethod
    def _alert_to_text(alert) -> str:
        if isinstance(alert, str):
            return alert

        if isinstance(alert, dict):
            return json.dumps(
                alert,
                ensure_ascii=False,
            )

        return str(alert)

    @staticmethod
    def _json_safe(value):
        if value is None or isinstance(
            value,
            (str, int, float, bool),
        ):
            return value

        if isinstance(value, dict):
            return {
                str(k): AWSMonitor._json_safe(v)
                for k, v in value.items()
            }

        if isinstance(
            value,
            (list, tuple, set),
        ):
            return [
                AWSMonitor._json_safe(v)
                for v in value
            ]

        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass

        return str(value)
