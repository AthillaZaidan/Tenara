from sqlalchemy import func, select

from app.models import (
    FabricListing,
    GalleryEntry,
    GarmentTemplate,
    MerchantProfile,
    TailorCapability,
    TailorProfile,
)
from scripts.seed_demo import ALL_TEMPLATES, seed_demo

API = "/api/v1"


def test_demo_fixtures_cover_the_prd_checklist(client, session, storage, embedder):
    result = seed_demo(session, storage, embedder, "demo-pass-123")
    assert result["merchants"] == 3 and result["tailors"] == 4 and result["new_listings"] == 3
    assert session.scalar(select(func.count()).select_from(GarmentTemplate)) == 5
    # several verified merchants offer the same Gallery entry, for comparison
    sumba = session.scalar(select(GalleryEntry).where(GalleryEntry.name == "Tenun Ikat Sumba"))
    items = client.get(f"{API}/gallery/{sumba.slug}/listings").json()["data"]["items"]
    assert len({i["merchant"]["shop_name"] for i in items}) == 2
    # both selling units exist, with actual specs
    units = {u for (u,) in session.execute(select(FabricListing.selling_unit))}
    assert units == {"meter", "piece"}
    # tailors cover T01-T05, and at least one is incompatible with the demo cotton fabrics
    covered = {c for (c,) in session.execute(select(TailorCapability.template_code))}
    assert covered == set(ALL_TEMPLATES)
    narrow = session.scalar(select(TailorProfile).where(TailorProfile.shop_name.like("Butik Sutra%")))
    caps = list(session.scalars(select(TailorCapability).where(TailorCapability.tailor_id == narrow.id)))
    assert [c.template_code for c in caps] == ["T03"] and caps[0].materials == ["sutra"]


def test_demo_login_and_public_catalog_work(client, session, storage, embedder):
    seed_demo(session, storage, embedder, "demo-pass-123")
    for who in ("admin", "buyer", "merchant-sumba", "tailor-bandung"):
        r = client.post(f"{API}/auth/login", json={"email": f"{who}@tenara.demo", "password": "demo-pass-123"})
        assert r.status_code == 200, who
    token = client.post(f"{API}/auth/login", json={"email": "tailor-bandung@tenara.demo",
                                                   "password": "demo-pass-123"}).json()["data"]["access_token"]
    caps = client.get(f"{API}/tailor/capabilities", headers={"Authorization": f"Bearer {token}"}).json()["data"]
    assert {c["template_code"] for c in caps} == set(ALL_TEMPLATES)


def test_seeding_twice_changes_nothing(session, storage, embedder):
    seed_demo(session, storage, embedder, "demo-pass-123")
    counts = [session.scalar(select(func.count()).select_from(m))
              for m in (FabricListing, MerchantProfile, TailorProfile, TailorCapability, GalleryEntry)]
    again = seed_demo(session, storage, embedder, "demo-pass-123")
    assert again["new_listings"] == 0
    assert counts == [session.scalar(select(func.count()).select_from(m))
                      for m in (FabricListing, MerchantProfile, TailorProfile, TailorCapability, GalleryEntry)]


def test_demo_tailors_are_filtered_by_material_for_a_real_design(client, session, storage, embedder):
    from app.services import customization as cust_svc
    from app.services import matching

    seed_demo(session, storage, embedder, "demo-pass-123")
    buyer = client.post(f"{API}/auth/login", json={"email": "buyer@tenara.demo", "password": "demo-pass-123"})
    assert buyer.status_code == 200
    hinggi = session.scalar(select(FabricListing).where(FabricListing.title.like("Hinggi%")))
    from app.models import User

    user = session.scalar(select(User).where(User.email == "buyer@tenara.demo"))
    cust = cust_svc.create_customization(session, user, hinggi.id, "T03")
    address = {"city": "Jakarta", "province": "DKI Jakarta"}
    names = [t["shop_name"] for t in matching.recommendations(session, cust, address)]
    assert "Butik Sutra Eksklusif" not in names  # sutra-only tailor cannot work cotton
    assert "Atelier Nusantara Jakarta" in names
