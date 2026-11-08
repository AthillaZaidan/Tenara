from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import assert_production_safe, settings
from app.core.errors import register_error_handlers
from app.routers import (
    admin_gallery,
    admin_partners,
    ai,
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"], allow_headers=["*"], allow_credentials=False,  # bearer tokens, no cookies
)
for router in (custom.router, health.router, auth.router, files.router, jobs.router, gallery.router,
               admin_gallery.router, partners.router, admin_partners.router, listings.router,
               commerce.router, templates.router, customizations.router, measurements.router, chat.router, claims.router, ai.router):
    app.include_router(router, prefix="/api/v1")
