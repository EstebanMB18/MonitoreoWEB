from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.auth import router as auth_router
from api.routes.dashboard import router as dashboard_router
from api.routes.health import router as health_router
from api.routes.history import router as history_router
from api.routes.monitors import router as monitors_router
from api.routes.runs import router as runs_router
from api.routes.settings import router as settings_router


app = FastAPI(
    title="Centro de Monitoreo V2",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(monitors_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
