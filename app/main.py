from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.routers import admin, dashboard, exports, hosts

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(hosts.router)
app.include_router(exports.router)
