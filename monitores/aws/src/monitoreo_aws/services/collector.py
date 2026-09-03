from __future__ import annotations

from datetime import timedelta

from monitoreo_aws.core.aws import (
    contar,
    crear_cliente,
    ejecutar_query,
)
from monitoreo_aws.services.queries import (
    COUNT_QUERIES,
    DETAIL_QUERIES,
)


def _load_dynamic_config() -> dict | None:
    try:
        from core.aws_monitor_config import (
            ensure_aws_monitor_config_seeded,
        )

        config = ensure_aws_monitor_config_seeded()

        if not isinstance(config, dict):
            return None

        services = config.get("services")

        if not isinstance(services, list):
            return None

        if not services:
            return None

        return config

    except Exception as exc:
        print(
            "AWS dynamic config no disponible; "
            f"se usara fallback legacy: {exc}"
        )
        return None


def _active_services(
    config: dict,
) -> list[dict]:
    return [
        service
        for service in config.get(
            "services",
            [],
        )
        if (
            isinstance(service, dict)
            and service.get(
                "activo",
                True,
            )
        )
    ]


def _query_map(
    service: dict,
) -> dict[str, dict]:
    result = {}

    for query in service.get(
        "queries",
        [],
    ):
        if not isinstance(query, dict):
            continue

        if not query.get(
            "activo",
            True,
        ):
            continue

        query_id = str(
            query.get("id")
            or ""
        ).strip()

        if not query_id:
            continue

        result[query_id] = query

    return result


def _find_service(
    services: list[dict],
    service_id: str,
) -> dict | None:
    key = service_id.strip().lower()

    for service in services:
        current = str(
            service.get("id")
            or ""
        ).strip().lower()

        if current == key:
            return service

    return None


def _get_client(
    *,
    cache: dict,
    profile: str,
    region: str,
    legacy_profiles: dict,
):
    profile = str(
        profile
        or ""
    ).strip()

    if not profile:
        raise ValueError(
            "Servicio AWS sin profile."
        )

    if profile not in cache:
        resolved_profile = (
            legacy_profiles.get(
                profile,
                profile,
            )
        )

        cache[profile] = crear_cliente(
            resolved_profile,
            region,
        )

    return cache[profile]


def _recolectar_dynamic(
    cfg: dict,
    ventana,
    dynamic: dict,
) -> dict:
    region = str(
        dynamic.get("region")
        or cfg["app"]["region"]
    ).strip()

    legacy_profiles = dict(
        cfg.get("profiles", {})
        or {}
    )

    services = _active_services(
        dynamic
    )

    if not services:
        raise RuntimeError(
            "Configuracion AWS dinamica "
            "sin servicios activos."
        )

    ini = ventana.inicio
    fin = ventana.fin

    result = {
        "metricas": {},
        "detalles": {},
        "errores_consulta": [],
        "config_source": "dynamic",
    }

    clients = {}

    # --------------------------------------------------------
    # QUERIES GENERICAS
    # --------------------------------------------------------

    for service in services:
        service_id = str(
            service.get("id")
            or ""
        ).strip()

        profile = str(
            service.get("profile")
            or ""
        ).strip()

        group = str(
            service.get("log_group")
            or ""
        ).strip()

        if not profile:
            result[
                "errores_consulta"
            ].append(
                f"{service_id}: "
                "profile vacio"
            )
            continue

        if not group:
            result[
                "errores_consulta"
            ].append(
                f"{service_id}: "
                "log_group vacio"
            )
            continue

        try:
            client = _get_client(
                cache=clients,
                profile=profile,
                region=region,
                legacy_profiles=(
                    legacy_profiles
                ),
            )
        except Exception as exc:
            result[
                "errores_consulta"
            ].append(
                f"{service_id}: {exc}"
            )
            continue

        for query in service.get(
            "queries",
            [],
        ):
            if not isinstance(
                query,
                dict,
            ):
                continue

            if not query.get(
                "activo",
                True,
            ):
                continue

            query_id = str(
                query.get("id")
                or ""
            ).strip()

            query_type = str(
                query.get("tipo")
                or ""
            ).strip().upper()

            query_text = str(
                query.get("query")
                or ""
            ).strip()

            if (
                not query_id
                or not query_text
            ):
                continue

            try:
                if query_type == "COUNT":
                    print(
                        f"  - {query_id}"
                    )

                    result[
                        "metricas"
                    ][query_id] = contar(
                        client,
                        group,
                        query_text,
                        ini,
                        fin,
                    )

                elif query_type == "DETAIL":
                    result[
                        "detalles"
                    ][query_id] = (
                        ejecutar_query(
                            client,
                            group,
                            query_text,
                            ini,
                            fin,
                        )
                    )

            except Exception as exc:
                if query_type == "COUNT":
                    result[
                        "metricas"
                    ][query_id] = None

                else:
                    result[
                        "detalles"
                    ][query_id] = []

                result[
                    "errores_consulta"
                ].append(
                    f"{query_id}: {exc}"
                )

    # --------------------------------------------------------
    # DERIVADO MENSAJERIA
    # --------------------------------------------------------

    if "mens_report" in result[
        "metricas"
    ]:
        result["metricas"][
            "mens_total_send"
        ] = result[
            "metricas"
        ].get(
            "mens_report"
        )

    # --------------------------------------------------------
    # SERVICIOS RED - LOGICA ESPECIAL
    # --------------------------------------------------------

    sr_service = _find_service(
        services,
        "serviciosred",
    )

    if sr_service:
        sr_queries = _query_map(
            sr_service
        )

        resumen = sr_queries.get(
            "serviciosred_resumen"
        )

        buckets = sr_queries.get(
            "serviciosred_10m"
        )

        if resumen:
            try:
                sr_client = _get_client(
                    cache=clients,
                    profile=sr_service[
                        "profile"
                    ],
                    region=region,
                    legacy_profiles=(
                        legacy_profiles
                    ),
                )

                sr_ini = max(
                    ini,
                    fin
                    - timedelta(
                        minutes=60
                    ),
                )

                sr_rows = ejecutar_query(
                    sr_client,
                    sr_service[
                        "log_group"
                    ],
                    resumen["query"],
                    sr_ini,
                    fin,
                )

                sr = (
                    sr_rows[0]
                    if sr_rows
                    else {}
                )

                try:
                    sr_count = int(
                        float(
                            sr.get(
                                "count",
                                0,
                            )
                            or 0
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    sr_count = 0

                result["metricas"][
                    "serviciosred_ultima_hora"
                ] = sr_count

                result["detalles"][
                    "serviciosred_ultima_hora"
                ] = [
                    {
                        "count": sr_count,
                        "ultima_notificacion": (
                            sr.get(
                                "ultima_notificacion",
                                "",
                            )
                        ),
                        "desde": (
                            sr_ini.isoformat()
                        ),
                        "hasta": (
                            fin.isoformat()
                        ),
                    }
                ]

                if buckets:
                    try:
                        result[
                            "detalles"
                        ][
                            "serviciosred_10m_ultima_hora"
                        ] = ejecutar_query(
                            sr_client,
                            sr_service[
                                "log_group"
                            ],
                            buckets[
                                "query"
                            ],
                            sr_ini,
                            fin,
                        )

                    except Exception as exc:
                        result[
                            "detalles"
                        ][
                            "serviciosred_10m_ultima_hora"
                        ] = []

                        result[
                            "errores_consulta"
                        ].append(
                            "serviciosred_10m_"
                            "ultima_hora: "
                            f"{exc}"
                        )

            except Exception as exc:
                result["metricas"][
                    "serviciosred_ultima_hora"
                ] = None

                result["detalles"][
                    "serviciosred_ultima_hora"
                ] = []

                result["detalles"][
                    "serviciosred_10m_ultima_hora"
                ] = []

                result[
                    "errores_consulta"
                ].append(
                    "serviciosred_ultima_hora: "
                    f"{exc}"
                )

    # --------------------------------------------------------
    # TUP - LOGICA ESPECIAL ULTIMOS 60 MIN / 10 MIN
    # --------------------------------------------------------

    tup_service = _find_service(
        services,
        "tarjetatup",
    )

    if tup_service:
        tup_queries = _query_map(
            tup_service
        )

        total_10m = tup_queries.get(
            "tup_total_10m"
        )

        errores_10m = tup_queries.get(
            "tup_errores_10m"
        )

        if total_10m or errores_10m:
            try:
                tup_client = _get_client(
                    cache=clients,
                    profile=tup_service[
                        "profile"
                    ],
                    region=region,
                    legacy_profiles=(
                        legacy_profiles
                    ),
                )

                tup_ini = max(
                    ini,
                    fin
                    - timedelta(
                        minutes=60
                    ),
                )

                if total_10m:
                    result["detalles"][
                        "tup_total_10m_ultima_hora"
                    ] = ejecutar_query(
                        tup_client,
                        tup_service[
                            "log_group"
                        ],
                        total_10m[
                            "query"
                        ],
                        tup_ini,
                        fin,
                    )

                if errores_10m:
                    result["detalles"][
                        "tup_errores_10m_ultima_hora"
                    ] = ejecutar_query(
                        tup_client,
                        tup_service[
                            "log_group"
                        ],
                        errores_10m[
                            "query"
                        ],
                        tup_ini,
                        fin,
                    )

            except Exception as exc:
                result["detalles"][
                    "tup_total_10m_ultima_hora"
                ] = []

                result["detalles"][
                    "tup_errores_10m_ultima_hora"
                ] = []

                result[
                    "errores_consulta"
                ].append(
                    "tup_10m_ultima_hora: "
                    f"{exc}"
                )

    return result


def _recolectar_legacy(
    cfg: dict,
    ventana,
) -> dict:
    region = cfg["app"]["region"]
    profiles = cfg["profiles"]
    groups = cfg["services"]

    clientes = {
        "interopprod": crear_cliente(
            profiles["interopprod"],
            region,
        ),
        "cscprod": crear_cliente(
            profiles["cscprod"],
            region,
        ),
        "corporativoprod": crear_cliente(
            profiles["corporativoprod"],
            region,
        ),
    }

    i = clientes["interopprod"]
    c = clientes["cscprod"]
    p = clientes["corporativoprod"]

    ini = ventana.inicio
    fin = ventana.fin

    result = {
        "metricas": {},
        "detalles": {},
        "errores_consulta": [],
        "config_source": "legacy",
    }

    jobs = [
        *(
            (
                key,
                i,
                groups[
                    "interopprod"
                ][
                    "apiorqpagos"
                ],
            )
            for key in [
                "aprob_creacion_payu",
                "aprob_creacion_ecollect",
                "aprob_estado_payu",
                "aprob_estado_ecollect",
                "aprob_receiver",
                "err_creacion_payu",
                "err_creacion_ecollect",
                "err_estado_payu",
                "err_estado_ecollect",
                "err_receiver",
                "err_log",
                "err_mongodb_update",
            ]
        ),
        (
            "seg_consulta_persona",
            i,
            groups[
                "interopprod"
            ][
                "apimoduloseguridad"
            ],
        ),
        (
            "error_cx",
            i,
            groups[
                "interopprod"
            ][
                "apisubsidios"
            ],
        ),
        (
            "tup_error",
            i,
            groups[
                "interopprod"
            ][
                "tarjetatup"
            ],
        ),
        (
            "serviciosred_total",
            i,
            groups[
                "interopprod"
            ][
                "serviciosred"
            ],
        ),
        (
            "csc_task_timed",
            c,
            groups[
                "cscprod"
            ][
                "apiorqpagos_proxy"
            ],
        ),
        (
            "csc_504",
            c,
            groups[
                "cscprod"
            ][
                "apiorqpagos_proxy"
            ],
        ),
        *(
            (
                key,
                p,
                groups[
                    "corporativoprod"
                ][
                    "apimensajeria"
                ],
            )
            for key in [
                "mens_timeout",
                "mens_503",
                "mens_502",
                "mens_report",
                "mens_cannot",
                "mens_sms_failed",
                "mens_error_400_total",
                "mens_exitos_200_total",
                "otp_408",
            ]
        ),
        (
            "replicador",
            p,
            groups[
                "corporativoprod"
            ][
                "replicador"
            ],
        ),
        (
            "otp_500",
            p,
            groups[
                "corporativoprod"
            ][
                "validarotp"
            ],
        ),
    ]

    for key, client, group in jobs:
        try:
            print(f"  - {key}")

            result["metricas"][key] = (
                contar(
                    client,
                    group,
                    COUNT_QUERIES[key],
                    ini,
                    fin,
                )
            )

        except Exception as exc:
            result["metricas"][
                key
            ] = None

            result[
                "errores_consulta"
            ].append(
                f"{key}: {exc}"
            )

    result["metricas"][
        "mens_total_send"
    ] = result["metricas"].get(
        "mens_report"
    )

    detail_jobs = [
        (
            "consulta_persona",
            i,
            groups[
                "interopprod"
            ][
                "apimoduloseguridad"
            ],
        ),
        (
            "mensajeria_errores",
            p,
            groups[
                "corporativoprod"
            ][
                "apimensajeria"
            ],
        ),
        (
            "mensajeria_exitos",
            p,
            groups[
                "corporativoprod"
            ][
                "apimensajeria"
            ],
        ),
        (
            "mensajeria_400_por_hora",
            p,
            groups[
                "corporativoprod"
            ][
                "apimensajeria"
            ],
        ),
        (
            "mensajeria_errores_por_hora",
            p,
            groups[
                "corporativoprod"
            ][
                "apimensajeria"
            ],
        ),
        (
            "mensajeria_200_por_hora",
            p,
            groups[
                "corporativoprod"
            ][
                "apimensajeria"
            ],
        ),
        (
            "tup_por_hora",
            i,
            groups[
                "interopprod"
            ][
                "tarjetatup"
            ],
        ),
        (
            "tup_total_por_hora",
            i,
            groups[
                "interopprod"
            ][
                "tarjetatup"
            ],
        ),
        (
            "tup_resumen",
            i,
            groups[
                "interopprod"
            ][
                "tarjetatup"
            ],
        ),
        (
            "pagos_errores_por_hora",
            i,
            groups[
                "interopprod"
            ][
                "apiorqpagos"
            ],
        ),
        (
            "replicador_por_hora",
            p,
            groups[
                "corporativoprod"
            ][
                "replicador"
            ],
        ),
        (
            "serviciosred_resumen",
            i,
            groups[
                "interopprod"
            ][
                "serviciosred"
            ],
        ),
        (
            "serviciosred_por_hora",
            i,
            groups[
                "interopprod"
            ][
                "serviciosred"
            ],
        ),
    ]

    for (
        key,
        client,
        group,
    ) in detail_jobs:
        try:
            result["detalles"][
                key
            ] = ejecutar_query(
                client,
                group,
                DETAIL_QUERIES[key],
                ini,
                fin,
            )

        except Exception as exc:
            result["detalles"][
                key
            ] = []

            result[
                "errores_consulta"
            ].append(
                f"{key}: {exc}"
            )

    try:
        sr_ini = max(
            ini,
            fin
            - timedelta(
                minutes=60
            ),
        )

        sr_rows = ejecutar_query(
            i,
            groups[
                "interopprod"
            ][
                "serviciosred"
            ],
            DETAIL_QUERIES[
                "serviciosred_resumen"
            ],
            sr_ini,
            fin,
        )

        sr = (
            sr_rows[0]
            if sr_rows
            else {}
        )

        try:
            sr_count = int(
                float(
                    sr.get(
                        "count",
                        0,
                    )
                    or 0
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            sr_count = 0

        result["metricas"][
            "serviciosred_ultima_hora"
        ] = sr_count

        result["detalles"][
            "serviciosred_ultima_hora"
        ] = [
            {
                "count": sr_count,
                "ultima_notificacion": (
                    sr.get(
                        "ultima_notificacion",
                        "",
                    )
                ),
                "desde": (
                    sr_ini.isoformat()
                ),
                "hasta": (
                    fin.isoformat()
                ),
            }
        ]

        result["detalles"][
            "serviciosred_10m_ultima_hora"
        ] = ejecutar_query(
            i,
            groups[
                "interopprod"
            ][
                "serviciosred"
            ],
            DETAIL_QUERIES[
                "serviciosred_10m"
            ],
            sr_ini,
            fin,
        )

    except Exception as exc:
        result["metricas"][
            "serviciosred_ultima_hora"
        ] = None

        result["detalles"][
            "serviciosred_ultima_hora"
        ] = []

        result["detalles"][
            "serviciosred_10m_ultima_hora"
        ] = []

        result[
            "errores_consulta"
        ].append(
            "serviciosred_ultima_hora: "
            f"{exc}"
        )

    try:
        tup_ini = max(
            ini,
            fin
            - timedelta(
                minutes=60
            ),
        )

        result["detalles"][
            "tup_total_10m_ultima_hora"
        ] = ejecutar_query(
            i,
            groups[
                "interopprod"
            ][
                "tarjetatup"
            ],
            DETAIL_QUERIES[
                "tup_total_10m"
            ],
            tup_ini,
            fin,
        )

        result["detalles"][
            "tup_errores_10m_ultima_hora"
        ] = ejecutar_query(
            i,
            groups[
                "interopprod"
            ][
                "tarjetatup"
            ],
            DETAIL_QUERIES[
                "tup_errores_10m"
            ],
            tup_ini,
            fin,
        )

    except Exception as exc:
        result["detalles"][
            "tup_total_10m_ultima_hora"
        ] = []

        result["detalles"][
            "tup_errores_10m_ultima_hora"
        ] = []

        result[
            "errores_consulta"
        ].append(
            "tup_10m_ultima_hora: "
            f"{exc}"
        )

    return result


def recolectar(
    cfg: dict,
    ventana,
) -> dict:
    dynamic = (
        _load_dynamic_config()
    )

    if dynamic is not None:
        try:
            return _recolectar_dynamic(
                cfg,
                ventana,
                dynamic,
            )

        except Exception as exc:
            print(
                "AWS dynamic config fallo "
                "antes de completar la "
                "recoleccion; fallback "
                f"legacy: {exc}"
            )

    return _recolectar_legacy(
        cfg,
        ventana,
    )
