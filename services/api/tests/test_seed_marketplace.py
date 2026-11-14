from sqlalchemy import func, select

from app.models import (
    DeliveryAddress,
    FabricListing,
    GalleryEntry,
    GalleryVariant,
    GalleryVariantImage,
    ListingImage,
    User,
)
from scripts.seed_demo import seed_demo
from scripts.seed_marketplace import BUYERS, MOTIFS, TRADITIONS, seed_marketplace

API = "/api/v1"


def _seed(session, storage, embedder):
    seed_demo(session, storage, embedder, "demo-pass-123")
    return seed_marketplace(session, storage, embedder, "demo-pass-123")


def test_every_catalog_motif_has_a_published_entry_variant_and_photographed_offer(client, session, storage, embedder):
    _seed(session, storage, embedder)
    published = {e.name: e for e in session.scalars(select(GalleryEntry).where(GalleryEntry.status == "published"))}
    for name, aliases in TRADITIONS.values():
        assert name in published, name
        assert set(aliases) <= set(published[name].aliases)
        passport = client.get(f"{API}/gallery/{published[name].slug}/passport").json()["data"]
        assert passport["story"] and len(passport["story"]["body"].split("\n")) == 3
        assert "entri demo" not in passport["story"]["body"]
    for code, (_trad, motif, _shows) in MOTIFS.items():
        variant = session.scalar(select(GalleryVariant).where(GalleryVariant.name == motif))
        images = session.scalars(select(GalleryVariantImage).where(GalleryVariantImage.variant_id == variant.id)).all()
        assert len(images) == 3 and all(i.caption.startswith(f"Foto katalog Tenara · {code}") for i in images)
        offers = session.scalars(select(FabricListing).where(FabricListing.variant_id == variant.id,
                                                             FabricListing.status == "published")).all()
        assert offers, code
        for offer in offers:
            assert session.scalar(select(func.count()).select_from(ListingImage).where(
                ListingImage.listing_id == offer.id)) == 3


def test_placeholder_listings_get_catalog_photos_or_are_hidden(session, storage, embedder):
    _seed(session, storage, embedder)
    assert session.scalar(select(func.count()).select_from(ListingImage).where(
        ListingImage.caption == "Foto demo")) == 0
    hinggi = session.scalar(select(FabricListing).where(FabricListing.title == "Hinggi merah motif kuda"))
    assert hinggi.status == "published" and hinggi.variant_id is not None
    songket = session.scalar(select(FabricListing).where(FabricListing.title.like("Songket benang emas%")))
    assert songket.status == "archived"


def test_buyers_have_complete_addresses_and_seeding_twice_changes_nothing(session, storage, embedder):
    _seed(session, storage, embedder)
    for slug, name, addresses in BUYERS:
        user = session.scalar(select(User).where(User.email == f"{slug}@tenara.demo"))
        assert user.display_name == name
        saved = session.scalars(select(DeliveryAddress).where(DeliveryAddress.user_id == user.id)).all()
        assert {a.label for a in saved} == {a[0] for a in addresses}
        assert all(a.postal_code and a.phone and a.line1 for a in saved)
    models = (FabricListing, ListingImage, GalleryVariant, GalleryVariantImage, DeliveryAddress, GalleryEntry)
    counts = [session.scalar(select(func.count()).select_from(m)) for m in models]
    again = _seed(session, storage, embedder)
    assert again["new_listings"] == 0
    assert counts == [session.scalar(select(func.count()).select_from(m)) for m in models]
