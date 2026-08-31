from fastapi import APIRouter, Depends

from api.auth_dependencies import require_roles

from api.runtime import (
    MONITOR_DEFINITIONS,
    latest_run_for_monitor,
)


router = APIRouter()


@router.get("/dashboard")
def dashboard(
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):

    monitors = []
    active_alerts = []

    for definition in MONITOR_DEFINITIONS:
        last = latest_run_for_monitor(
            definition["id"]
        )

        if last is None:
            monitor = {
                **definition,
                "status": "PENDING",
                "progress": 0,
                "records": None,
                "alerts": [],
                "last_run_id": None,
            }

        else:
            monitor = {
                **definition,
                "status": last["status"],
                "progress": last["progress"],
                "records": last.get("records"),
                "alerts": last.get("alerts", []),
                "last_run_id": last["run_id"],
                "last_run_type": last["run_type"],
                "duration_seconds":
                    last.get("duration_seconds"),
            }

            for alert in last.get("alerts", []):
                active_alerts.append({
                    "monitor": definition["name"],
                    "message": alert,
                    "run_id": last["run_id"],
                })

        monitors.append(monitor)

    statuses = {
        item["status"]
        for item in monitors
    }

    if "ERROR" in statuses:
        overall = "ERROR"
    elif "WARNING" in statuses:
        overall = "WARNING"
    elif "RUNNING" in statuses:
        overall = "RUNNING"
    elif statuses and statuses <= {"OK"}:
        overall = "OK"
    else:
        overall = "PENDING"

    return {
        "overall_status": overall,
        "monitors": monitors,
        "active_alerts": active_alerts,
    }
