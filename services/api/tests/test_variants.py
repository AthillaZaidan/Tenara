def test_variant_listing_filter_and_entry_validation(client, published_entry, make_partner, make_user, make_file, auth_header):
    first = published_entry("Kain Pertama")
    second = published_entry("Kain Kedua")
    admin = make_user("variant-admin@example.com", roles=(("admin", "active"),))
    merchant, _ = make_partner()
    admin_headers = auth_header(admin)
    merchant_headers = auth_header(merchant)

    response = client.post(f"/api/v1/admin/gallery/{first.id}/variants", json={"name": "Kuda"}, headers=admin_headers)
    assert response.status_code == 201
    variant = response.json()["data"]
    assert client.get(f"/api/v1/gallery/{first.id}/variants").json()["data"][0]["id"] == variant["id"]
    reference = make_file(admin, visibility="public")
    reference.kind = "reference_image"
    image = client.post(f"/api/v1/admin/gallery/variants/{variant['id']}/images",
                        json={"file_id": str(reference.id), "caption": "Contoh motif"}, headers=admin_headers)
    assert image.status_code == 201
    variants = client.get(f"/api/v1/gallery/{first.id}/variants").json()["data"]
    assert variants[0]["images"][0]["caption"] == "Contoh motif"
    changed = client.patch(f"/api/v1/admin/gallery/variants/{variant['id']}",
                           json={"name": "Motif Kuda", "description": "Referensi"}, headers=admin_headers)
    assert changed.status_code == 200
    assert client.get(f"/api/v1/gallery/{first.id}/variants").json()["data"][0]["name"] == "Motif Kuda"
    assert client.patch(f"/api/v1/admin/gallery/variants/{variant['id']}",
                        json={"name": "Lain"}, headers=merchant_headers).status_code == 403
    entry_image = client.post(f"/api/v1/admin/gallery/{first.id}/images",
                              json={"file_id": str(reference.id), "caption": "Referensi kain"}, headers=admin_headers)
    assert entry_image.status_code == 201
    entry_images = client.get(f"/api/v1/admin/gallery/{first.id}/images", headers=admin_headers)
    assert entry_images.status_code == 200
    assert entry_images.json()["data"][0]["caption"] == "Referensi kain"
    assert client.get(f"/api/v1/admin/gallery/{first.id}/images", headers=merchant_headers).status_code == 403
    gallery_image_id = entry_images.json()["data"][0]["id"]
    assert client.delete(f"/api/v1/admin/gallery/{first.id}/images/{gallery_image_id}", headers=merchant_headers).status_code == 403
    assert client.delete(f"/api/v1/admin/gallery/{first.id}/images/{gallery_image_id}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/v1/admin/gallery/{first.id}/images", headers=admin_headers).json()["data"] == []
    body = {"entry_id": str(first.id), "variant_id": variant["id"], "title": "Kain Kuda",
            "selling_unit": "meter", "price_idr": 100000}
    listing = client.post("/api/v1/listings", json=body, headers=merchant_headers)
    assert listing.status_code == 201
    assert listing.json()["data"]["variant_id"] == variant["id"]
    listing_id = listing.json()["data"]["id"]
    photo = make_file(merchant, visibility="public")
    assert client.post(f"/api/v1/listings/{listing_id}/images", json={"file_id": str(photo.id)}, headers=merchant_headers).status_code == 201
    first_photo_id = client.get(f"/api/v1/merchant/listings/{listing_id}", headers=merchant_headers).json()["data"]["images"][0]["id"]
    assert client.post(f"/api/v1/listings/{listing_id}/publish", headers=merchant_headers).status_code == 200
    assert client.delete(f"/api/v1/listings/{listing_id}/images/{first_photo_id}", headers=merchant_headers).status_code == 409
    second_photo = make_file(merchant, visibility="public")
    assert client.post(f"/api/v1/listings/{listing_id}/images", json={"file_id": str(second_photo.id)}, headers=merchant_headers).status_code == 201
    assert client.delete(f"/api/v1/listings/{listing_id}/images/{first_photo_id}", headers=merchant_headers).status_code == 200
    matches = client.get(f"/api/v1/gallery/{first.id}/listings", params={"variant_id": variant["id"]}).json()["data"]["items"]
    assert [item["id"] for item in matches] == [listing_id]
    assert client.delete(f"/api/v1/admin/gallery/variants/{variant['id']}", headers=admin_headers).status_code == 409
    other = client.post(f"/api/v1/admin/gallery/{first.id}/variants", json={"name": "Andung"}, headers=admin_headers).json()["data"]
    assert client.get(f"/api/v1/gallery/{first.id}/listings", params={"variant_id": other["id"]}).json()["data"]["items"] == []
    revision = listing.json()["data"]["revision"] + 1  # publishing advances the listing revision
    cleared = client.patch(f"/api/v1/listings/{listing_id}", json={"expected_revision": revision, "variant_id": None}, headers=merchant_headers)
    assert cleared.status_code == 200
    assert cleared.json()["data"]["variant_id"] is None
    assert client.get(f"/api/v1/gallery/{first.id}/listings", params={"variant_id": variant["id"]}).json()["data"]["items"] == []
    assert client.delete(f"/api/v1/admin/gallery/variants/{variant['id']}", headers=merchant_headers).status_code == 403
    assert client.delete(f"/api/v1/admin/gallery/variants/{variant['id']}", headers=admin_headers).status_code == 200
    remaining = client.get(f"/api/v1/gallery/{first.id}/variants").json()["data"]
    assert [item["id"] for item in remaining] == [other["id"]]
    body["entry_id"] = str(second.id)
    assert client.post("/api/v1/listings", json=body, headers=merchant_headers).status_code == 422
    assert client.get(f"/api/v1/gallery/{second.id}/listings", params={"variant_id": variant["id"]}).status_code == 422
    assert client.post(f"/api/v1/admin/gallery/{first.id}/variants", json={"name": "Lain"}, headers=merchant_headers).status_code == 403
