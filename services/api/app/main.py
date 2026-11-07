from fastapi import FastAPI

from app.core.config import assert_production_safe, settings
from app.core.errors import register_error_handlers
from app.routers import (
    admin_gallery,
    admin_partners,
    auth,
    chat,
    claims,
    commerce,
    custom,
    customizations,
    files,
    gallery,
    health,
    jobs,
    listings,
    measurements,
    partners,
    templates,
)

assert_production_safe(settings)

app = FastAPI(title="Tenara API", version="0.1.0")
register_error_handlers(app)
for router in (custom.router, health.router, auth.router, files.router, jobs.router, gallery.router,
               admin_gallery.router, partners.router, admin_partners.router, listings.router,
               commerce.router, templates.router, customizations.router, measurements.router, chat.router, claims.router):
    app.include_router(router, prefix="/api/v1")
