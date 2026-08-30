from fastapi import FastAPI

from api.routes.dashboard import router as dashboard_router
from api.routes.health import router as health_router
from api.routes.monitors import router as monitors_router
from api.routes.runs import router as runs_router


app = FastAPI(
    title="Centro de Monitoreo V2",
    version="0.1.0",
)

app.include_router(health_router, prefix="/api")
app.include_router(monitors_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
