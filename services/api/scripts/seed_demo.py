"""Demo fixtures (PRD 11.4): templates, verified merchants and tailors, listings with stock and fabric
photos, a buyer with an address, and an admin. Idempotent; every account is labelled as a demo.

Usage (from services/api):
    DEMO_PASSWORD=... uv run python -m scripts.seed_demo
"""
import io
import os
import uuid
from decimal import Decimal

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.ml.text.embedding import Embedder, get_embedder
from app.models import (
    DeliveryAddress,
    FabricListing,
    FabricStockUnit,
    GalleryEntry,
    ListingImage,
    MerchantProfile,
    RoleAssignment,
    TailorCapability,
    TailorProfile,
    User,
)
from app.services import gallery as gallery_svc
from app.services import templates as templates_svc
from app.services.files import create_file
from app.services.storage import Storage, get_storage
from scripts.seed_admin import seed_admin

DOMAIN = "tenara.demo"
ALL_TEMPLATES = ("T01", "T02", "T03", "T04", "T05")

MERCHANTS = [
    ("merchant-sumba", "Toko Tenun Sumba", "Waingapu", "NTT", "Tenun Ikat Sumba"),
    ("merchant-kupang", "Galeri Tenun Kupang", "Kupang", "NTT", "Tenun Ikat Sumba"),
    ("merchant-bali", "Rumah Songket Bali", "Klungkung", "Bali", "Songket Bali"),
]
TAILORS = [  # (slug, shop, city, province, templates, rate, lead days, materials)
    ("tailor-bandung", "Penjahit Rina Bandung", "Bandung", "Jawa Barat", ALL_TEMPLATES, 300_000, 14,
     ["katun", "tenun", "songket"]),
    ("tailor-jakarta", "Atelier Nusantara Jakarta", "Jakarta", "DKI Jakarta", ALL_TEMPLATES, 420_000, 10,
     ["katun", "tenun", "songket", "sutra"]),
    ("tailor-yogya", "Jahit Kebaya Yogya", "Yogyakarta", "DI Yogyakarta", ("T02", "T05"), 280_000, 12,
     ["katun", "tenun"]),
    # deliberately incompatible with cotton/ikat fabrics: demonstrates hard filtering
    ("tailor-sutra", "Butik Sutra Eksklusif", "Surabaya", "Jawa Timur", ("T03",), 500_000, 7, ["sutra"]),
]
FABRICS = [  # (slug, merchant slug, title, unit, price, width/piece dims, stock, colours)
    ("hinggi-merah", "merchant-sumba", "Hinggi merah motif kuda", "meter", 185_000, 110,
     [(Decimal(3), 2), (Decimal(5), 1)], ((150, 40, 40), (230, 190, 60))),
    ("ikat-biru", "merchant-kupang", "Ikat biru indigo", "meter", 210_000, 115,
     [(Decimal(4), 2)], ((30, 50, 110), (235, 235, 225))),
    ("songket-emas", "merchant-bali", "Songket benang emas (potongan)", "piece", 650_000, 110,
     [(None, 5)], ((90, 20, 60), (225, 175, 50))),
]


def _fabric_png(base, accent) -> bytes:
    img = Image.new("RGB", (400, 400), base)
    d = ImageDraw.Draw(img)
    for x in range(0, 400, 40):
        d.rectangle((x, 0, x + 14, 400), fill=accent)
    for y in range(20, 400, 80):
        d.polygon([(0, y), (40, y - 18), (80, y), (40, y + 18)], fill=accent)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _user(session: Session, slug: str, name: str, password: str, roles: tuple[str, ...]) -> User:
    email = f"{slug}@{DOMAIN}"
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(password), display_name=name)
        session.add(user)
        session.flush()
    have = {r.role for r in user.roles}
    for role in ("buyer", *roles):
        if role not in have:
            session.add(RoleAssignment(user_id=user.id, role=role, status="active"))
    session.flush()
    session.refresh(user)
    return user


def _entry(session: Session, admin: User, embedder: Embedder | None, name: str) -> GalleryEntry:
    entry = session.scalar(select(GalleryEntry).where(GalleryEntry.name == name,
                                                      GalleryEntry.status == "published"))
    if entry is not None:
        return entry
    source = gallery_svc.create_source(session, admin, title="Sumber demo Tenara", license="Demo")
    gallery_svc.decide_source(session, admin, source, "approve", "demo fixture",
                              action_prefix="gallery.demo_seeded")
    entry = gallery_svc.create_entry(session, admin, name=name, summary=f"{name} (entri demo).",
                                     is_demo_seed=True)
    story = gallery_svc.create_story(
        session, admin, entry, body=f"{name} adalah entri demo; isi budaya sungguhan berasal dari "
                                    "dataset yang disetujui kurator.",
        citations=[{"source_id": source.id}], unresolved=["Seluruh narasi budaya perlu verifikasi kurator"])
    gallery_svc.submit_story(session, admin, story)
    gallery_svc.decide_story(session, admin, story, "approve", "demo fixture", embedder)
    gallery_svc.publish_entry(session, admin, entry, embedder, action="gallery.demo_seeded")
    return entry


def seed_demo(session: Session, storage: Storage, embedder: Embedder | None, password: str) -> dict:
    templates_svc.sync_templates(session)
    admin = seed_admin(session, f"admin@{DOMAIN}", password, "Admin Demo")
    merchants: dict[str, MerchantProfile] = {}
    for slug, shop, city, province, _entry_name in MERCHANTS:
        user = _user(session, slug, shop, password, ("merchant",))
        profile = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
        if profile is None:
            profile = MerchantProfile(user_id=user.id, shop_name=shop, city=city, province=province,
                                      description="Merchant demo terverifikasi platform.")
            session.add(profile)
            session.flush()
        merchants[slug] = profile
    tailors = 0
    for slug, shop, city, province, templates, rate, lead, materials in TAILORS:
        user = _user(session, slug, shop, password, ("tailor",))
        profile = session.scalar(select(TailorProfile).where(TailorProfile.user_id == user.id))
        if profile is None:
            profile = TailorProfile(user_id=user.id, shop_name=shop, city=city, province=province,
                                    bio="Penjahit demo terverifikasi platform.", experience_years=8)
            session.add(profile)
            session.flush()
        for code in templates:
            if session.scalar(select(TailorCapability.id).where(
                    TailorCapability.tailor_id == profile.id, TailorCapability.template_code == code)) is None:
                session.add(TailorCapability(tailor_id=profile.id, template_code=code, base_rate_idr=rate,
                                             lead_time_days=lead, weekly_capacity=3, materials=materials))
        tailors += 1
    listings = 0
    entries = {name: _entry(session, admin, embedder, name) for name in {m[4] for m in MERCHANTS}}
    entry_of = {m[0]: entries[m[4]] for m in MERCHANTS}
    for slug, merchant_slug, title, unit, price, width, stock, colours in FABRICS:
        merchant = merchants[merchant_slug]
        if session.scalar(select(FabricListing.id).where(FabricListing.merchant_id == merchant.id,
                                                         FabricListing.title == title)):
            continue
        listing = FabricListing(
            merchant_id=merchant.id, entry_id=entry_of[merchant_slug].id, title=title,
            description="Listing demo dengan foto ilustrasi.", material="katun" if unit == "meter" else "songket",
            selling_unit=unit, price_idr=price, min_quantity=Decimal(1),
            quantity_increment=Decimal("0.5") if unit == "meter" else Decimal(1),
            usable_width_cm=width if unit == "meter" else None,
            piece_width_cm=width if unit == "piece" else None,
            piece_length_cm=220 if unit == "piece" else None, city=merchant.city,
            province=merchant.province, status="published", dispatch_days=3,
            merchant_claimed_origin="Data demo; bukan klaim asal-usul sungguhan.")
        session.add(listing)
        session.flush()
        photo = create_file(session, storage, owner_id=merchant.user_id, kind="listing_photo",
                            data=_fabric_png(*colours), content_type="image/png", visibility="public")
        session.add(ListingImage(listing_id=listing.id, file_id=photo.id, caption="Foto demo"))
        for length, qty in stock:
            session.add(FabricStockUnit(listing_id=listing.id, length_m=length, quantity=qty))
        listings += 1
    buyer = _user(session, "buyer", "Pembeli Demo", password, ())
    if session.scalar(select(DeliveryAddress.id).where(DeliveryAddress.user_id == buyer.id)) is None:
        session.add(DeliveryAddress(user_id=buyer.id, label="Rumah", recipient_name="Pembeli Demo",
                                    phone="081200000000", line1="Jl. Demo No. 1", city="Jakarta",
                                    province="DKI Jakarta", postal_code="10110"))
    session.flush()
    return {"accounts": f"*@{DOMAIN}", "merchants": len(merchants), "tailors": tailors,
            "new_listings": listings, "published_entries": len(entries)}


def main() -> None:
    password = os.environ.get("DEMO_PASSWORD") or f"demo-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as session:
        result = seed_demo(session, get_storage(), get_embedder(), password)
        session.commit()
    print(result)
    print(f"Demo accounts (admin@, buyer@, merchant-sumba@, tailor-bandung@ ... {DOMAIN}) "
          f"password: {password if not os.environ.get('DEMO_PASSWORD') else '(from DEMO_PASSWORD)'}")


if __name__ == "__main__":
    main()
