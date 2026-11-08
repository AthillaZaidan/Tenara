import json

import pytest
from PIL import Image
from sqlalchemy import select

from app.ml.vision.photo_match import FakePhotoEmbedder
from app.models import File, ReferencePhoto
from app.services import gallery as g
from scripts.seed_reference_photos import _admin, approve_pending, collect, folder_items, load


def _photo(path, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 60), color).save(path)


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "tenun_datasets"
    _photo(root / "museum/met-1.jpg", (200, 40, 40))
    _photo(root / "museum/met-2.jpg", (40, 200, 40))
    (root / "museum/manifest.json").write_text(json.dumps([
        {"file": "met-1.jpg", "label": "Tenun Ikat Sumba", "source": "The Met", "url": "https://met/1",
         "license": "CC0", "title": "Hinggi"},
        {"file": "met-2.jpg", "label": "Tradisi Tak Dikenal", "source": "The Met", "license": "CC0"},
    ]))
    _photo(root / "mendeley_sikka_v3/extracted/sikka_motif_512/merak/a.jpg", (40, 40, 200))
    return root


def test_collect_labels_styles_and_licences(data):
    items = {i["external_id"]: i for i in collect(data)}
    met = items["museum:met-1.jpg"]
    assert (met["style"], met["display_allowed"], met["license"], met["source_url"]) == \
        ("archival", True, "CC0", "https://met/1")
    sikka = items["mendeley-sikka:merak/a.jpg"]
    assert (sikka["label"], sikka["style"], sikka["license"]) == ("Tenun Ikat Sikka", "modern", "CC BY 4.0")


def test_load_skips_unknown_traditions_stays_pending_and_is_idempotent(session, storage, data, make_user,
                                                                      tmp_path):
    owner = make_user("curator@example.com", roles=(("admin", "active"),))
    for name in ("Tenun Ikat Sumba", "Tenun Ikat Sikka"):
        g.create_entry(session, None, name=name, technique="Tenun ikat", region="NTT")
    _photo(tmp_path / "own/IMG_1.jpg", (210, 50, 50))
    items = collect(data) + folder_items(tmp_path / "own", "Tenun Ikat Sumba", "Tim Tenara", None, None, False)
    stats = load(session, storage, FakePhotoEmbedder(), owner, items)
    assert stats == {"loaded_archival": 1, "loaded_modern": 2, "skipped_unknown_tradition": 1}
    refs = list(session.scalars(select(ReferencePhoto)))
    assert {r.approval_status for r in refs} == {"pending"}
    own = next(r for r in refs if r.source_label == "Tim Tenara")
    assert own.style == "modern" and not own.display_allowed
    assert session.get(File, own.file_id).visibility == "private"
    assert load(session, storage, FakePhotoEmbedder(), owner, items)["skipped_already_loaded"] == 3

    assert approve_pending(session, _admin(session, "curator@example.com")) == 3
    assert {r.approval_status for r in session.scalars(select(ReferencePhoto))} == {"approved"}
    make_user("buyer@example.com")
    with pytest.raises(SystemExit):
        _admin(session, "buyer@example.com")
