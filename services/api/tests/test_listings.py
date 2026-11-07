import pytest

API = "/api/v1"


@pytest.fixture
def merchant(make_partner):
    return make_partner("merchant", shop="Toko Sumba", city="Waingapu", province="NTT")


@pytest.fixture
def entry(published_entry):
    return published_entry()


def _body(entry, **extra):
    body = {"entry_id": str(entry.id), "title": "Hinggi merah 2m", "selling_unit": "meter",
            "price_idr": 450000, "material": "katun", "usable_width_cm": 110}
    body.update(extra)
    return body


def _create(client, headers, entry, **extra):
    r = client.post(f"{API}/listings", headers=headers, json=_body(entry, **extra))
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _publish(client, session, make_file, user, headers, entry, **extra):
    listing = _create(client, headers, entry, **extra)
    photo = make_file(user, visibility="public")
    r = client.post(f"{API}/listings/{listing['id']}/images", headers=headers,
                    json={"file_id": str(photo.id), "caption": "Foto asli"})
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/listings/{listing['id']}/publish", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_only_active_merchants_can_create(client, make_user, auth_header, entry):
    buyer = make_user("b@example.com")
    r = client.post(f"{API}/listings", headers=auth_header(buyer), json=_body(entry))
    assert r.status_code == 403


def test_create_defaults_location_from_merchant(client, merchant, auth_header, entry):
    user, _ = merchant
    listing = _create(client, auth_header(user), entry)
    assert listing["city"] == "Waingapu" and listing["province"] == "NTT"
    assert listing["status"] == "draft"


def test_listing_requires_published_gallery_entry(client, session, merchant, auth_header, make_user):
    from app.services import gallery as g

    user, _ = merchant
    admin = make_user("a@example.com", roles=(("admin", "active"),))
    draft = g.create_entry(session, admin, name="Masih Draft")
    r = client.post(f"{API}/listings", headers=auth_header(user), json=_body(draft))
    assert r.status_code == 422 and r.json()["error"]["field"] == "entry_id"


def test_piece_listings_need_whole_pieces(client, merchant, auth_header, entry):
    user, _ = merchant
    r = client.post(f"{API}/listings", headers=auth_header(user),
                    json=_body(entry, selling_unit="piece", quantity_increment="0.5"))
    assert r.status_code == 422
    ok = client.post(f"{API}/listings", headers=auth_header(user),
                     json=_body(entry, selling_unit="piece", quantity_increment="1",
                                piece_length_cm=200, piece_width_cm=110))
    assert ok.status_code == 201


def test_invalid_price_is_rejected(client, merchant, auth_header, entry):
    user, _ = merchant
    r = client.post(f"{API}/listings", headers=auth_header(user), json=_body(entry, price_idr=0))
    assert r.status_code == 422


def test_publish_requires_photo(client, merchant, auth_header, entry):
    user, _ = merchant
    listing = _create(client, auth_header(user), entry)
    r = client.post(f"{API}/listings/{listing['id']}/publish", headers=auth_header(user))
    assert r.status_code == 422 and r.json()["error"]["field"] == "images"


def test_photos_must_be_own_public_files(client, merchant, make_user, make_file, auth_header, entry):
    user, _ = merchant
    listing = _create(client, auth_header(user), entry)
    private = make_file(user)
    other = make_file(make_user("o@example.com"), visibility="public")
    url = f"{API}/listings/{listing['id']}/images"
    assert client.post(url, headers=auth_header(user), json={"file_id": str(private.id)}).status_code == 422
    assert client.post(url, headers=auth_header(user), json={"file_id": str(other.id)}).status_code == 404


def test_published_listing_is_public_with_merchant_identity(client, session, merchant, make_file, auth_header, entry):
    user, _ = merchant
    listing = _publish(client, session, make_file, user, auth_header(user), entry)
    data = client.get(f"{API}/listings/{listing['id']}").json()["data"]
    assert data["merchant"]["shop_name"] == "Toko Sumba"
    assert data["merchant"]["verified"] is True
    assert data["gallery_entry"]["id"] == str(entry.id)
    assert data["images"][0]["url"].startswith("/api/v1/files/")
    assert data["origin"]["curator_verified_origin"] is None  # a merchant badge is not provenance


def test_draft_listing_is_not_public(client, merchant, auth_header, entry):
    user, _ = merchant
    listing = _create(client, auth_header(user), entry)
    assert client.get(f"{API}/listings/{listing['id']}").status_code == 404
    assert client.get(f"{API}/merchant/listings/{listing['id']}", headers=auth_header(user)).status_code == 200


def test_gallery_to_listings_sorted_and_filtered(client, session, make_partner, make_file, auth_header, entry):
    cheap, _ = make_partner("merchant", shop="Murah", city="Kupang", province="NTT")
    pricey, _ = make_partner("merchant", shop="Mahal", city="Bandung", province="Jawa Barat")
    _publish(client, session, make_file, cheap, auth_header(cheap), entry, price_idr=200000)
    _publish(client, session, make_file, pricey, auth_header(pricey), entry, price_idr=900000)
    items = client.get(f"{API}/gallery/{entry.slug}/listings").json()["data"]["items"]
    assert [i["price_idr"] for i in items] == [200000, 900000]
    only_bandung = client.get(f"{API}/gallery/{entry.slug}/listings?city=bandung").json()["data"]["items"]
    assert [i["merchant"]["shop_name"] for i in only_bandung] == ["Mahal"]
    cap = client.get(f"{API}/gallery/{entry.slug}/listings?max_price=300000").json()["data"]["items"]
    assert [i["merchant"]["shop_name"] for i in cap] == ["Murah"]


def test_gallery_without_providers_is_still_reachable(client, entry):
    data = client.get(f"{API}/gallery/{entry.slug}/listings").json()["data"]
    assert data["items"] == [] and data["gallery_entry"]["name"] == "Tenun Ikat Sumba"


def test_gallery_detail_exposes_availability(client, session, merchant, make_file, auth_header, entry):
    user, _ = merchant
    before = client.get(f"{API}/gallery/{entry.slug}").json()["data"]["availability"]
    assert before == {"listing_count": 0, "min_price_idr": None}
    _publish(client, session, make_file, user, auth_header(user), entry, price_idr=321000)
    after = client.get(f"{API}/gallery/{entry.slug}").json()["data"]["availability"]
    assert after == {"listing_count": 1, "min_price_idr": 321000}


def test_suspended_merchant_listings_are_hidden(client, session, merchant, make_file, auth_header, entry):
    user, profile = merchant
    listing = _publish(client, session, make_file, user, auth_header(user), entry)
    profile.status = "suspended"
    session.flush()
    assert client.get(f"{API}/listings/{listing['id']}").status_code == 404
    assert client.get(f"{API}/gallery/{entry.slug}/listings").json()["data"]["items"] == []


def test_stale_revision_conflicts(client, merchant, auth_header, entry):
    user, _ = merchant
    listing = _create(client, auth_header(user), entry)
    url = f"{API}/listings/{listing['id']}"
    ok = client.patch(url, headers=auth_header(user),
                      json={"expected_revision": listing["revision"], "price_idr": 500000})
    assert ok.status_code == 200 and ok.json()["data"]["price_idr"] == 500000
    stale = client.patch(url, headers=auth_header(user),
                         json={"expected_revision": listing["revision"], "price_idr": 1})
    assert stale.status_code == 409


def test_merchants_cannot_touch_each_others_listings(client, make_partner, auth_header, entry):
    a, _ = make_partner("merchant", shop="A")
    b, _ = make_partner("merchant", shop="B")
    listing = _create(client, auth_header(a), entry)
    assert client.patch(f"{API}/listings/{listing['id']}", headers=auth_header(b),
                        json={"expected_revision": 1, "price_idr": 1}).status_code == 404
    assert client.post(f"{API}/listings/{listing['id']}/publish", headers=auth_header(b)).status_code == 404


def test_custom_order_readiness_flags_missing_data(client, merchant, auth_header, entry):
    user, _ = merchant
    listing = _create(client, auth_header(user), entry, material=None, usable_width_cm=None)
    assert listing["custom_order_ready"] is False
    assert set(listing["missing_for_custom"]) == {"material", "usable_width_cm"}
    assert listing["material"] == "tidak diketahui"  # unknown values are labelled, never invented
    fixed = client.patch(f"{API}/listings/{listing['id']}", headers=auth_header(user),
                         json={"expected_revision": 1, "material": "katun", "usable_width_cm": 110})
    assert fixed.json()["data"]["custom_order_ready"] is True


def test_meter_stock_requires_length_and_summarises_continuous_cuts(client, merchant, auth_header, entry):
    user, _ = merchant
    h = auth_header(user)
    listing = _create(client, h, entry)
    url = f"{API}/listings/{listing['id']}/stock-units"
    assert client.post(url, headers=h, json={"quantity": 2}).status_code == 422
    client.post(url, headers=h, json={"length_m": "3.5", "quantity": 2})
    client.post(url, headers=h, json={"length_m": "1.25", "quantity": 1})
    stock = client.get(f"{API}/merchant/listings/{listing['id']}", headers=h).json()["data"]["stock"]
    assert stock["total_length_m"] == "8.25" or float(stock["total_length_m"]) == 8.25
    assert float(stock["longest_continuous_m"]) == 3.5
    assert stock["pieces"] == 3 and stock["in_stock"] is True


def test_piece_stock_counts_pieces_and_rejects_length(client, merchant, auth_header, entry):
    user, _ = merchant
    h = auth_header(user)
    listing = _create(client, h, entry, selling_unit="piece", piece_length_cm=200, piece_width_cm=110)
    url = f"{API}/listings/{listing['id']}/stock-units"
    assert client.post(url, headers=h, json={"length_m": "2", "quantity": 1}).status_code == 422
    unit = client.post(url, headers=h, json={"quantity": 4}).json()["data"]
    stock = client.get(f"{API}/merchant/listings/{listing['id']}", headers=h).json()["data"]["stock"]
    assert stock == {"unit": "piece", "available_pieces": 4, "in_stock": True}
    client.patch(f"{API}/stock-units/{unit['id']}", headers=h, json={"quantity": 0})
    out = client.get(f"{API}/merchant/listings/{listing['id']}", headers=h).json()["data"]["stock"]
    assert out["in_stock"] is False


def test_stock_is_owner_scoped(client, make_partner, auth_header, entry):
    a, _ = make_partner("merchant", shop="A")
    b, _ = make_partner("merchant", shop="B")
    listing = _create(client, auth_header(a), entry)
    unit = client.post(f"{API}/listings/{listing['id']}/stock-units", headers=auth_header(a),
                       json={"length_m": "2", "quantity": 1}).json()["data"]
    assert client.patch(f"{API}/stock-units/{unit['id']}", headers=auth_header(b),
                        json={"quantity": 99}).status_code == 404
    assert client.post(f"{API}/listings/{listing['id']}/stock-units", headers=auth_header(b),
                       json={"length_m": "2", "quantity": 1}).status_code == 404
    stock = client.get(f"{API}/merchant/stock", headers=auth_header(b)).json()["data"]
    assert stock == []


def test_archived_listing_leaves_public_view(client, session, merchant, make_file, auth_header, entry):
    user, _ = merchant
    listing = _publish(client, session, make_file, user, auth_header(user), entry)
    client.post(f"{API}/listings/{listing['id']}/archive", headers=auth_header(user))
    assert client.get(f"{API}/listings/{listing['id']}").status_code == 404
