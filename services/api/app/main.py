from fastapi import FastAPI

from app.core.config import assert_production_safe, settings
from app.core.errors import register_error_handlers
from app.routers import admin_gallery, auth, files, gallery, health, jobs

assert_production_safe(settings)

app = FastAPI(title="Tenara API", version="0.1.0")
register_error_handlers(app)
for router in (health.router, auth.router, files.router, jobs.router, gallery.router,
               admin_gallery.router):
    app.include_router(router, prefix="/api/v1")
