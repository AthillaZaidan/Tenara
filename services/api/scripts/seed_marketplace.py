"""Marketplace fixtures that match the web catalog (web/lib/catalog-data.ts): the eleven catalog
traditions as published Gallery entries, their 21 motifs as variants, regional merchants offering
each motif with the catalog photos, more tailors, and buyers with complete addresses.

Runs after seed_demo (it reuses the demo admin and accounts) and is idempotent. Cultural text comes
from data/tenun_catalog.json (web research, cited); entries are labelled as demo seed because a
curator still has to review that research.

Usage (from services/api):
    DEMO_PASSWORD=... uv run python -m scripts.seed_demo   # runs this too
"""
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ml.text.embedding import Embedder
from app.models import (
    CulturalSource,
    DeliveryAddress,
    FabricListing,
    FabricStockUnit,
    GalleryEntry,
    GalleryVariant,
    GalleryVariantImage,
    ListingImage,
    MerchantProfile,
    SourceChunk,
    TailorCapability,
    TailorProfile,
    User,
)
from app.services import gallery as gallery_svc
from app.services.files import create_file
from app.services.storage import Storage
from scripts.seed_catalog import CATALOG, TECHNIQUE_TEXT, dossier_title, load_catalog

ROOT = Path(__file__).resolve().parents[3]
PHOTOS = ROOT / "web" / "public" / "assets" / "katalog-tenun" / "mvp"
VIEWS = (("utama", "Tampak utama"), ("lipatan-datar", "Lipatan datar"), ("detail-tekstur", "Detail tekstur"))
PLACEHOLDER_STORY = "adalah entri demo"
REVIEW_NOTE = "Disetujui untuk data demo; riset web perlu ditinjau kurator sebelum dipakai di produksi"

# web catalog tradition -> (tenun_catalog.json name, API names the web looks for)
TRADITIONS = {
    "hinggi-sumba": ("Tenun Ikat Sumba", ["Hinggi Sumba"]),
    "sikka": ("Tenun Ikat Sikka", []),
    "sasak": ("Tenun Sasak Lombok", ["Tenun Sasak"]),
    "endek": ("Endek Bali", ["Tenun Endek"]),
    "gringsing": ("Gringsing Tenganan", ["Tenun Gringsing"]),
    "troso": ("Tenun Ikat Troso", ["Tenun Troso"]),
    "lurik": ("Lurik", ["Tenun Lurik"]),
    "ulos": ("Ulos Batak Toba", ["Ulos", "Ulos Batak"]),
    "songket": ("Songket Palembang", []),
    "pandai-sikek": ("Songket Minangkabau (Pandai Sikek dan Silungkang)", ["Songket Pandai Sikek"]),
    "donggala": ("Tenun Donggala", []),
    # not a web catalog card, but seed_demo publishes it with a placeholder story
    "songket-bali": ("Songket Bali", []),
}

# catalog sample code -> (tradition, motif = variant name, what the photo shows)
MOTIFS = {
    "SUM-01": ("hinggi-sumba", "Kuda", "barisan kuda, rusa, dan burung berwarna krem di atas biru tua, diselingi pita merah bata"),
    "SUM-02": ("hinggi-sumba", "Andung", "figur andung dan manusia berwarna krem di atas dasar cokelat tua dengan pita oranye"),
    "BAL-01": ("endek", "Mekepung", "adegan balap kerbau mekepung di bagian bawah kain merah marun"),
    "BAL-02": ("endek", "Jalak Bali", "burung jalak putih dan bunga kecil di atas biru terang dengan pinggiran bermotif"),
    "BAL-03": ("gringsing", "Wayang Kebo", "bidang segi empat berisi figur wayang dalam warna cokelat, hitam, dan krem"),
    "BAL-04": ("gringsing", "Pat Likur Isi", "pola bintang empat sudut berulang dalam cokelat dan krem"),
    "LOM-01": ("sasak", "Subahnale", "segi enam berwarna-warni di atas dasar hitam dengan pinggiran kuning"),
    "LOM-02": ("sasak", "Rangrang", "pola zig-zag kuning, putih, dan hijau tua di atas magenta"),
    "SIK-01": ("sikka", "Utan Ruha", "deretan rusa dan tanaman krem di atas biru tua, diapit lajur merah"),
    "SIK-02": ("sikka", "Manu Hutu", "lajur geometris hitam dan krem di antara bidang merah bata"),
    "JTG-01": ("troso", "Ampel", "bunga kecil dan lengkung daun berwarna lembut di atas hitam dengan rumbai"),
    "JTG-02": ("troso", "Kedawung", "bunga kecil merah muda di atas hijau tua dengan pinggiran bermotif"),
    "JTG-03": ("lurik", "Telupat", "garis-garis memanjang biru, merah, dan kuning"),
    "JTG-04": ("lurik", "Tumbar Pecah", "kotak-kotak kecil biru muda dan putih"),
    "BTK-01": ("ulos", "Ragi Hotang", "garis halus cokelat kemerahan dengan rumbai di kedua ujung"),
    "BTK-02": ("ulos", "Sadum", "belah ketupat dan garis cerah merah dan oranye"),
    "MIN-01": ("pandai-sikek", "Tidak dibedakan per motif", "anyaman benang emas di atas merah dan oranye"),
    "PLB-01": ("songket", "Nago Besaung", "ragam hias benang perak di atas merah muda dengan tumpal di ujung kain"),
    "PLB-02": ("songket", "Bungo Cino", "bunga-bunga emas rapat di atas merah tua dengan lajur emas"),
    "DGL-01": ("donggala", "Bunga Bomba", "bunga putih di atas merah muda dan bidang kotak merah tua"),
    "DGL-02": ("donggala", "Bunga Ketupat", "taburan motif ketupat perak di atas krem"),
}


@dataclass
class Shop:
    slug: str
    shop: str
    owner: str
    city: str
    province: str
    phone: str
    about: str


MERCHANTS = [
    Shop("merchant-sumba", "Toko Tenun Sumba", "Yohana Rambu Kahi", "Waingapu", "Nusa Tenggara Timur",
         "0812-3790-4415", "Kain hinggi dan lau dari kelompok penenun di Kambera, Sumba Timur. Pewarna alam "
         "dari akar mengkudu dan nila."),
    Shop("merchant-kupang", "Galeri Tenun Kupang", "Agustina Ndun", "Kupang", "Nusa Tenggara Timur",
         "0813-3922-1874", "Galeri kurasi tenun ikat dari Sumba, Flores, dan Timor. Mengirim ke seluruh "
         "Indonesia dari Kota Kupang."),
    Shop("merchant-bali", "Rumah Songket Bali", "I Gusti Ayu Ratna", "Klungkung", "Bali",
         "0819-3640-2271", "Endek dan songket dari sentra tenun Gelgel, Klungkung. Bisa dibeli per meter."),
    Shop("merchant-tenganan", "Rumah Gringsing Tenganan", "I Wayan Sudarma", "Karangasem", "Bali",
         "0817-4721-0936", "Gringsing ikat ganda dari Tenganan Pegringsingan. Tiap lembar dikerjakan "
         "berbulan-bulan, stok terbatas."),
    Shop("merchant-lombok", "Tenun Sasak Sukarara Lestari", "Baiq Nurhayati", "Lombok Tengah",
         "Nusa Tenggara Barat", "0818-0365-7724", "Songket dan tenun Sasak dari Desa Sukarara, Jonggat."),
    Shop("merchant-maumere", "Lepo Tenun Maumere", "Maria Goreti Nona", "Maumere", "Nusa Tenggara Timur",
         "0812-4677-3109", "Tenun ikat Sikka dari penenun di sekitar Maumere, dipintal dan dicelup sendiri."),
    Shop("merchant-jepara", "Tenun Troso Lestari", "Siti Maemunah", "Jepara", "Jawa Tengah",
         "0821-3804-5562", "Tenun ikat Troso dari Desa Troso, Pecangaan. Melayani pembelian per meter."),
    Shop("merchant-klaten", "Lurik Pedan Asli", "Sri Lestari", "Klaten", "Jawa Tengah",
         "0857-2611-9083", "Lurik alat tenun bukan mesin dari Pedan, Klaten. Cocok untuk kemeja dan outer."),
    Shop("merchant-toba", "Ulos Tao Toba", "Rosmawati Siahaan", "Balige", "Sumatera Utara",
         "0813-7044-8290", "Ulos tenunan tangan dari Balige dan sekitar Danau Toba."),
    Shop("merchant-palembang", "Songket Limas Palembang", "Cek Ayu Fitriani", "Palembang", "Sumatera Selatan",
         "0811-7810-4426", "Songket Palembang benang emas dan perak dari pengrajin di Seberang Ulu."),
    Shop("merchant-minang", "Songket Rumah Gadang", "Nurhasanah", "Tanah Datar", "Sumatera Barat",
         "0812-6658-3301", "Songket Pandai Sikek dari nagari di kaki Gunung Singgalang."),
    Shop("merchant-donggala", "Buya Sabe Donggala", "Hasnah Lamarauna", "Donggala", "Sulawesi Tengah",
         "0852-4155-7368", "Tenun Donggala (buya sabe) dari Watusampu dan sekitarnya."),
]


@dataclass
class Offer:
    code: str
    merchant: str
    title: str
    unit: str  # meter | piece
    price: int
    material: str
    width_cm: int  # usable width (meter) or piece width
    length_cm: int | None  # piece length
    stock: list  # meter: [(length_m, qty)], piece: [qty]
    origin: str


OFFERS = [
    Offer("SUM-01", "merchant-sumba", "Hinggi Kombu motif kuda", "piece", 2_400_000, "katun", 118, 240, [3],
          "Ditenun kelompok penenun di Kambera, Sumba Timur."),
    Offer("SUM-01", "merchant-kupang", "Ikat Sumba motif kuda (per meter)", "meter", 285_000, "katun", 110, None,
          [(Decimal(4), 2), (Decimal(3), 1)], "Dikurasi dari penenun di Sumba Timur."),
    Offer("SUM-02", "merchant-sumba", "Hinggi motif andung", "piece", 2_750_000, "katun", 120, 245, [2],
          "Ditenun di Kambera, Sumba Timur."),
    Offer("BAL-01", "merchant-bali", "Endek Mekepung merah marun", "meter", 165_000, "katun", 110, None,
          [(Decimal(5), 3)], "Ditenun di Gelgel, Klungkung."),
    Offer("BAL-02", "merchant-bali", "Endek Jalak Bali biru", "meter", 175_000, "katun", 110, None,
          [(Decimal(5), 2), (Decimal(3), 1)], "Ditenun di Gelgel, Klungkung."),
    Offer("BAL-03", "merchant-tenganan", "Gringsing Wayang Kebo", "piece", 6_500_000, "katun", 55, 210, [1],
          "Ditenun di Tenganan Pegringsingan, Karangasem."),
    Offer("BAL-04", "merchant-tenganan", "Gringsing Pat Likur Isi", "piece", 4_800_000, "katun", 52, 200, [2],
          "Ditenun di Tenganan Pegringsingan, Karangasem."),
    Offer("LOM-01", "merchant-lombok", "Songket Subahnale", "piece", 1_350_000, "songket", 65, 200, [4],
          "Ditenun di Desa Sukarara, Lombok Tengah."),
    Offer("LOM-02", "merchant-lombok", "Tenun Sasak Rangrang", "meter", 145_000, "katun", 100, None,
          [(Decimal(4), 3)], "Ditenun di Desa Sukarara, Lombok Tengah."),
    Offer("SIK-01", "merchant-maumere", "Ikat Sikka Utan Ruha", "piece", 1_200_000, "katun", 70, 200, [3],
          "Ditenun di sekitar Maumere, Kabupaten Sikka."),
    Offer("SIK-01", "merchant-kupang", "Ikat Sikka motif rusa (per meter)", "meter", 230_000, "katun", 105, None,
          [(Decimal(4), 2)], "Dikurasi dari penenun di Kabupaten Sikka."),
    Offer("SIK-02", "merchant-maumere", "Ikat Sikka Manu Hutu", "piece", 1_100_000, "katun", 68, 195, [2],
          "Ditenun di sekitar Maumere, Kabupaten Sikka."),
    Offer("JTG-01", "merchant-jepara", "Troso Ampel hitam", "meter", 135_000, "katun", 110, None,
          [(Decimal(5), 4)], "Ditenun di Desa Troso, Pecangaan, Jepara."),
    Offer("JTG-02", "merchant-jepara", "Troso Kedawung hijau", "meter", 150_000, "katun", 110, None,
          [(Decimal(5), 3)], "Ditenun di Desa Troso, Pecangaan, Jepara."),
    Offer("JTG-03", "merchant-klaten", "Lurik Telupat", "meter", 65_000, "katun", 105, None,
          [(Decimal(10), 5)], "Ditenun dengan ATBM di Pedan, Klaten."),
    Offer("JTG-04", "merchant-klaten", "Lurik Tumbar Pecah biru", "meter", 60_000, "katun", 105, None,
          [(Decimal(10), 4)], "Ditenun dengan ATBM di Pedan, Klaten."),
    Offer("BTK-01", "merchant-toba", "Ulos Ragi Hotang", "piece", 950_000, "katun", 90, 200, [3],
          "Ditenun di Balige, Toba."),
    Offer("BTK-02", "merchant-toba", "Ulos Sadum", "piece", 850_000, "katun", 80, 180, [4],
          "Ditenun di sekitar Danau Toba."),
    Offer("MIN-01", "merchant-minang", "Songket Pandai Sikek benang emas", "piece", 3_200_000, "songket", 100,
          200, [2], "Ditenun di Pandai Sikek, Tanah Datar."),
    Offer("PLB-01", "merchant-palembang", "Songket Nago Besaung", "piece", 3_500_000, "songket", 90, 200, [2],
          "Ditenun pengrajin di Seberang Ulu, Palembang."),
    Offer("PLB-02", "merchant-palembang", "Songket Bungo Cino", "piece", 2_900_000, "songket", 90, 200, [2],
          "Ditenun pengrajin di Seberang Ulu, Palembang."),
    Offer("DGL-01", "merchant-donggala", "Buya Sabe Bunga Bomba", "meter", 185_000, "sutra", 100, None,
          [(Decimal(4), 3)], "Ditenun di Watusampu, Donggala."),
    Offer("DGL-02", "merchant-donggala", "Buya Sabe Bunga Ketupat", "meter", 175_000, "sutra", 100, None,
          [(Decimal(4), 2)], "Ditenun di Watusampu, Donggala."),
]

# seed_demo listings that still carry a drawn placeholder photo -> the catalog photo set they get
DEMO_LISTING_PHOTOS = {"Hinggi merah motif kuda": "SUM-01", "Ikat biru indigo": "SIK-01"}
DEMO_PHOTO_CAPTION = "Foto demo"

ALL_TEMPLATES = ("T01", "T02", "T03", "T04", "T05")
TAILORS = [  # (slug, shop, city, province, phone, years, areas, templates, rate, lead, materials, bio)
    ("tailor-denpasar", "Rumah Jahit Kertha Denpasar", "Denpasar", "Bali", "0819-1622-4038", 11,
     ["Bali", "Nusa Tenggara Barat"], ALL_TEMPLATES, 350_000, 12, ["katun", "tenun", "songket"],
     "Spesialis kemeja dan outer dari endek serta songket Bali."),
    ("tailor-medan", "Penjahit Boru Medan", "Medan", "Sumatera Utara", "0813-6270-1159", 9,
     ["Sumatera Utara", "Sumatera Barat"], ("T01", "T02", "T04"), 260_000, 14, ["katun", "tenun", "songket"],
     "Menjahit kemeja dan blouse dari ulos dan songket untuk acara adat."),
]
TAILOR_DETAILS = {  # existing seed_demo tailors: phone, bio, areas
    "tailor-bandung": ("0812-2140-7781", ("Kemeja, blouse, dan rompi dari tenun; teliti mencocokkan motif di "
                       "sambungan."), ["Jawa Barat", "DKI Jakarta"]),
    "tailor-jakarta": ("0811-1904-3362", "Atelier busana etnik modern; terbiasa dengan songket dan sutra.",
                       ["DKI Jakarta", "Banten", "Jawa Barat"]),
    "tailor-yogya": ("0857-4381-2290", "Blouse dan tunik dari lurik serta tenun Jawa.",
                     ["DI Yogyakarta", "Jawa Tengah"]),
    "tailor-sutra": ("0821-3118-6604", "Butik sutra; hanya mengerjakan rompi dari bahan sutra.",
                     ["Jawa Timur"]),
}

TAILOR_OWNERS = {"tailor-bandung": "Rina Kurniasih", "tailor-jakarta": "Dimas Arya Wicaksana",
                 "tailor-yogya": "Sri Wahyuni", "tailor-sutra": "Lenny Hartono",
                 "tailor-denpasar": "Ni Made Sukarini", "tailor-medan": "Tiurma Br. Sitorus"}

BUYERS = [  # (slug, name, [(label, recipient, phone, line1, city, province, postal)])
    ("buyer", "Nadia Putri Rahmawati", [
        ("Rumah", "Nadia Putri Rahmawati", "0812-8841-2093",
         "Jl. Tebet Barat Dalam VI No. 14, RT 5/RW 2, Tebet Barat", "Jakarta Selatan", "DKI Jakarta", "12810"),
        ("Kantor", "Nadia Putri Rahmawati", "0812-8841-2093",
         "Jl. Jend. Sudirman No. 28, Lantai 9, Karet Tengsin, Tanah Abang", "Jakarta Pusat", "DKI Jakarta",
         "10220")]),
    ("buyer-bandung", "Raka Aditya Pratama", [
        ("Rumah", "Raka Aditya Pratama", "0813-2207-6614",
         "Jl. Taman Sari No. 71, Lebak Siliwangi, Coblong", "Bandung", "Jawa Barat", "40132")]),
    ("buyer-surabaya", "Sekar Ayu Lestari", [
        ("Rumah", "Sekar Ayu Lestari", "0838-5012-7740",
         "Jl. Manyar Kertoarjo V No. 22, Mojo, Gubeng", "Surabaya", "Jawa Timur", "60285")]),
    ("buyer-medan", "Daniel Hasudungan Simanjuntak", [
        ("Rumah", "Daniel Hasudungan Simanjuntak", "0822-7613-0958",
         "Jl. Setia Budi Gg. Sejahtera No. 9, Tanjung Sari, Medan Selayang", "Medan", "Sumatera Utara", "20132")]),
    ("buyer-makassar", "Andi Nurul Fadhilah", [
        ("Rumah", "Andi Nurul Fadhilah", "0852-9930-4471",
         "Jl. Boulevard Panakkukang Blok F No. 5, Masale, Panakkukang", "Makassar", "Sulawesi Selatan", "90231"),
        ("Rumah orang tua", "Hj. Andi Rahmatia", "0811-4410-2386",
         "Jl. Poros Bone Km. 3 No. 40, Watampone", "Bone", "Sulawesi Selatan", "92712")]),
]


def _photo(code: str, view: str) -> bytes:
    return (PHOTOS / f"{code.lower()}-{view}.webp").read_bytes()


def _story_body(t: dict) -> str:
    """Three paragraphs, in the order the gallery panels read them: culture, weaving, textiles."""
    place = ", ".join(p for p in (t.get("region"), t["province"]) if p)
    weaving = f"{TECHNIQUE_TEXT[t['technique']]} dari {place}"
    if t.get("community"):
        weaving += f", dikerjakan masyarakat {t['community']}"
    return "\n".join((t["culture"], weaving + ".", t["visual"]))


def _publish_tradition(session: Session, admin: User, embedder: Embedder | None, t: dict,
                       aliases: list[str]) -> GalleryEntry:
    entry = session.scalar(select(GalleryEntry).where(GalleryEntry.name == t["name"]))
    entry.aliases = sorted(set(entry.aliases or []) | set(aliases))
    entry.region = entry.region or t["province"]
    source = session.scalar(select(CulturalSource).where(CulturalSource.title == dossier_title(t["name"])))
    if source.approval_status != "approved":
        gallery_svc.decide_source(session, admin, source, "approve", REVIEW_NOTE)
    story = gallery_svc.approved_story(session, entry.id)
    if story is None or PLACEHOLDER_STORY in story.body:
        chunks = session.scalars(select(SourceChunk).where(SourceChunk.source_id == source.id)).all()
        story = gallery_svc.create_story(
            session, admin, entry, body=_story_body(t),
            citations=[{"source_id": source.id, "chunk_id": c.id, "locator": c.locator} for c in chunks],
            unresolved=[*(t.get("uncertain") or []), "Ringkasan riset web; perlu ditinjau kurator dan komunitas"])
        gallery_svc.submit_story(session, admin, story)
        gallery_svc.decide_story(session, admin, story, "approve", REVIEW_NOTE, embedder)
    if entry.status != "published":
        entry.is_demo_seed = True
        gallery_svc.publish_entry(session, admin, entry, embedder, action="gallery.demo_seeded")
    else:
        gallery_svc.reindex(session, entry, embedder)
    return entry


def _variant(session: Session, storage: Storage, admin: User, entry: GalleryEntry, code: str,
             name: str, shows: str) -> GalleryVariant:
    variant = session.scalar(select(GalleryVariant).where(GalleryVariant.entry_id == entry.id,
                                                          GalleryVariant.name == name))
    if variant is None:
        variant = GalleryVariant(entry_id=entry.id, name=name, description="")
        session.add(variant)
        session.flush()
    variant.description = f"Motif {name}: {shows}." if name != MOTIFS["MIN-01"][1] else (
        f"Songket ini tidak dibedakan per motif: {shows}.")
    catalog_caption = f"Foto katalog Tenara · {code}"
    have = session.scalars(select(GalleryVariantImage).where(GalleryVariantImage.variant_id == variant.id)).all()
    if not any((i.caption or "").startswith(catalog_caption) for i in have):
        # drop drawn placeholders (seed_demo) once real catalog photos exist
        session.execute(delete(GalleryVariantImage).where(GalleryVariantImage.variant_id == variant.id))
        for order, (view, label) in enumerate(VIEWS):
            file = create_file(session, storage, owner_id=admin.id, kind="reference_image", data=_photo(code, view),
                               content_type="image/webp", visibility="public")
            session.add(GalleryVariantImage(variant_id=variant.id, file_id=file.id, sort_order=order,
                                            caption=f"{catalog_caption} · {label}", credit="Tenara",
                                            license="Foto produk katalog"))
    session.flush()
    return variant


def _listing_photos(session: Session, storage: Storage, listing: FabricListing, owner_id, code: str,
                    title: str) -> None:
    for order, (view, label) in enumerate(VIEWS):
        file = create_file(session, storage, owner_id=owner_id, kind="listing_photo", data=_photo(code, view),
                           content_type="image/webp", visibility="public")
        session.add(ListingImage(listing_id=listing.id, file_id=file.id, sort_order=order,
                                 caption=f"{title} · {label.lower()}"))


def seed_marketplace(session: Session, storage: Storage, embedder: Embedder | None, password: str) -> dict:
    from scripts.seed_demo import _user  # one account helper for every seed

    admin = session.scalar(select(User).where(User.email == "admin@tenara.demo"))
    catalog = json.loads(CATALOG.read_text())
    load_catalog(session, embedder, catalog)
    by_name = {t["name"]: t for t in catalog["traditions"]}
    entries = {key: _publish_tradition(session, admin, embedder, by_name[name], aliases)
               for key, (name, aliases) in TRADITIONS.items()}
    variants = {code: _variant(session, storage, admin, entries[trad], code, motif, shows)
                for code, (trad, motif, shows) in MOTIFS.items()}

    merchants: dict[str, MerchantProfile] = {}
    for m in MERCHANTS:
        user = _user(session, m.slug, m.owner, password, ("merchant",))
        user.display_name = m.owner
        profile = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
        if profile is None:
            profile = MerchantProfile(user_id=user.id, shop_name=m.shop, city=m.city, province=m.province)
            session.add(profile)
        profile.shop_name, profile.city, profile.province = m.shop, m.city, m.province
        profile.contact_phone, profile.description = m.phone, m.about
        session.flush()
        merchants[m.slug] = profile

    new_listings = 0
    for o in OFFERS:
        merchant = merchants[o.merchant]
        trad, _motif, shows = MOTIFS[o.code]
        listing = session.scalar(select(FabricListing).where(FabricListing.merchant_id == merchant.id,
                                                             FabricListing.title == o.title))
        if listing is not None:
            continue
        meter = o.unit == "meter"
        listing = FabricListing(
            merchant_id=merchant.id, entry_id=entries[trad].id, variant_id=variants[o.code].id, title=o.title,
            description=f"Kain {o.material} dengan {shows}. Warna dapat sedikit berbeda dari foto karena "
                        "pencahayaan; setiap lembar tenunan tangan punya variasi kecil.",
            material=o.material, selling_unit=o.unit, price_idr=o.price,
            min_quantity=Decimal(1), quantity_increment=Decimal("0.5") if meter else Decimal(1),
            usable_width_cm=o.width_cm if meter else None,
            piece_width_cm=None if meter else o.width_cm, piece_length_cm=None if meter else o.length_cm,
            city=merchant.city, province=merchant.province, dispatch_days=3, status="published",
            merchant_claimed_origin=o.origin)
        session.add(listing)
        session.flush()
        _listing_photos(session, storage, listing, merchant.user_id, o.code, o.title)
        for unit in o.stock:
            length, qty = (unit if meter else (None, unit))
            session.add(FabricStockUnit(listing_id=listing.id, length_m=length, quantity=qty))
        new_listings += 1

    # seed_demo's drawn placeholders: real catalog photos for the Sumba/Sikka ones, the rest are hidden
    for listing in session.scalars(select(FabricListing).join(ListingImage).where(
            ListingImage.caption == DEMO_PHOTO_CAPTION)).unique().all():
        code = DEMO_LISTING_PHOTOS.get(listing.title)
        session.execute(delete(ListingImage).where(ListingImage.listing_id == listing.id,
                                                   ListingImage.caption == DEMO_PHOTO_CAPTION))
        if code is None:
            listing.status = "archived"
            continue
        trad = MOTIFS[code][0]
        listing.entry_id, listing.variant_id = entries[trad].id, variants[code].id
        listing.description = f"Kain katun dengan {MOTIFS[code][2]}."
        listing.merchant_claimed_origin = "Dikurasi dari penenun di Nusa Tenggara Timur."
        merchant = session.get(MerchantProfile, listing.merchant_id)
        _listing_photos(session, storage, listing, merchant.user_id, code, listing.title)

    for slug, (phone, bio, areas) in TAILOR_DETAILS.items():
        profile = session.scalar(select(TailorProfile).join(User, User.id == TailorProfile.user_id).where(
            User.email == f"{slug}@tenara.demo"))
        if profile is not None:
            profile.contact_phone, profile.bio, profile.service_area = phone, bio, areas
    for slug, shop, city, province, phone, years, areas, templates, rate, lead, materials, bio in TAILORS:
        user = _user(session, slug, shop, password, ("tailor",))
        profile = session.scalar(select(TailorProfile).where(TailorProfile.user_id == user.id))
        if profile is None:
            profile = TailorProfile(user_id=user.id, shop_name=shop, city=city, province=province)
            session.add(profile)
        profile.contact_phone, profile.bio, profile.service_area = phone, bio, areas
        profile.experience_years = years
        session.flush()
        for code in templates:
            if session.scalar(select(TailorCapability.id).where(
                    TailorCapability.tailor_id == profile.id, TailorCapability.template_code == code)) is None:
                session.add(TailorCapability(tailor_id=profile.id, template_code=code, base_rate_idr=rate,
                                             lead_time_days=lead, weekly_capacity=4, materials=materials))

    for slug, owner in TAILOR_OWNERS.items():
        user = session.scalar(select(User).where(User.email == f"{slug}@tenara.demo"))
        if user is not None:
            user.display_name = owner
    for slug, name, addresses in BUYERS:
        user = _user(session, slug, name, password, ())
        user.display_name = name
        existing = {a.label: a for a in session.scalars(select(DeliveryAddress).where(
            DeliveryAddress.user_id == user.id))}
        for label, recipient, phone, line1, city, province, postal in addresses:
            address = existing.get(label) or DeliveryAddress(user_id=user.id, label=label)
            address.recipient_name, address.phone, address.line1 = recipient, phone, line1
            address.city, address.province, address.postal_code = city, province, postal
            session.add(address)
    session.flush()
    return {"published_traditions": len(entries), "variants": len(variants), "merchants": len(merchants),
            "new_listings": new_listings, "buyers": len(BUYERS), "tailors_added": len(TAILORS)}
