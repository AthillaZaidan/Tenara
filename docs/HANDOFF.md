# Tenara: handoff untuk integrasi frontend

Dokumen ini untuk yang akan membangun frontend Tenara dari nol di atas backend yang sudah jadi.
Isinya **kontrak API dan alur bisnis**, bukan desain. Tema, gaya visual, tata letak, komponen,
framework, dan struktur halaman sepenuhnya keputusanmu. Kalau ada bagian yang terdengar seperti
"harus tampil", itu soal **isi** (teks wajib, data yang tidak boleh bocor), bukan soal bentuk.

Status: backend per 14 November 2026, branch `feat/vlm-web-evidence`. Semua fakta di sini diambil
dari kode di `services/api`. Kalau ada yang bertentangan, **kode dan respons API yang benar**,
bukan dokumen ini. Cek dulu responsnya sebelum menebak nama field, status, atau peran.

---

## 1. Tenara dalam satu paragraf

Marketplace kain tenun dengan konteks budaya. Pembeli bisa membeli kain per meter atau per potong,
atau memesan baju custom dari kain itu: pilih pola, ubah desain lewat teks, ukur badan dari foto,
pilih penjahit, lalu penjual mengirim kain ke penjahit dan penjahit mengirim baju ke pembeli.
Penjual memindai foto kain (AI mendeskripsikannya dan memeriksa klaim asal), lalu AI menulis
cerita budaya dari sumber yang sudah disetujui kurator. Kurator/admin mengelola Galeri budaya,
sumber, verifikasi mitra, dan banding klaim. **Pembayaran, ongkir, dan pelacakan kurir semuanya
simulasi.**

---

## 2. Menjalankan backend di laptopmu

Prasyarat: Docker Desktop, [uv](https://docs.astral.sh/uv/), Python 3.13 (uv mengurusnya).

```bash
# dari root repo
cp .env.example .env          # minta isi key LLM ke pemilik repo; jangan pernah commit .env
docker compose up -d          # Postgres 17 + pgvector

cd services/api
uv sync                        # tambah --extra body3d kalau mau ukur badan 3D (lihat catatan)
uv run alembic upgrade head
DEMO_PASSWORD=demo-pass-123 uv run python -m scripts.seed_demo   # akun demo
uv run python -m scripts.seed_catalog                             # katalog tradisi untuk scan & cerita

uv run uvicorn app.main:app --port 8000   # API
uv run python worker.py                   # WAJIB jalan di terminal lain (lihat 3.8)
```

- Swagger interaktif: **http://localhost:8000/docs**. Skema JSON: `/openapi.json`. Pakai ini untuk
  bentuk body request yang persis; dokumen ini menjelaskan alur dan respons yang tidak bertipe.
- Health check: `GET /api/v1/health`.
- **CORS** hanya mengizinkan `http://localhost:3000` dan `http://127.0.0.1:3000`. Kalau frontend-mu
  jalan di port lain, ubah `CORS_ORIGINS` di `.env` (dipisah koma) lalu restart API.
- Satu `.env` di root repo dipakai semua bagian. Variabel yang relevan untuk frontend hanya
  `NEXT_PUBLIC_API_URL=http://localhost:8000` (atau nama lain sesuai framework-mu).

### Fitur yang butuh file atau key tambahan

| Fitur | Butuh | Tanpa itu |
|---|---|---|
| Scan kain, cerita listing, interpreter prompt versi LLM | key OpenRouter di `.env` | scan & cerita mengembalikan error `service_unavailable`; interpreter prompt jatuh ke aturan biasa |
| Ukur badan dari foto | `services/api/models/pose_landmarker_full.task` (MediaPipe) | job ukur gagal dengan pesan "isi ukuran secara manual" |
| Ukur badan 3D (foto depan + samping, 7 ukuran) | `uv sync --extra body3d` + file SMPL-X di `services/api/models/smplx/` | turun ke ukuran dari foto depan saja (hanya sebagian ukuran) |

File model tidak ada di repo (lisensi; SMPL-X khusus non-komersial). Minta ke pemilik repo.
Frontend **harus** tetap bisa jalan tanpa fitur-fitur ini: selalu sediakan jalur isi ukuran manual.

### Akun demo (password `demo-pass-123`)

| Email | Peran |
|---|---|
| `buyer@tenara.demo` | pembeli |
| `merchant-sumba@tenara.demo`, `merchant-kupang@tenara.demo`, `merchant-bali@tenara.demo` | penjual (+ pembeli) |
| `tailor-bandung@`, `tailor-jakarta@`, `tailor-yogya@`, `tailor-sutra@` + `tenara.demo` | penjahit (+ pembeli) |
| `admin@tenara.demo` | admin/kurator |

---

## 3. Aturan umum API (berlaku di semua endpoint)

### 3.1 Base URL dan format respons

Semua endpoint di bawah **`/api/v1`**. Semua respons JSON memakai amplop yang sama:

```json
{ "data": { ... }, "error": null }                                   // sukses
{ "data": null, "error": { "code": "validation_error", "message": "…", "field": "quantity" } }  // gagal
```

`field` hanya ada kalau error menunjuk satu input. Pakai itu untuk menandai field form yang salah.
Pesan error kadang berbahasa Indonesia, kadang Inggris; tampilkan apa adanya atau petakan per `code`.

### 3.2 Kode error

| HTTP | `code` | Arti untuk UI |
|---|---|---|
| 401 | `unauthenticated` | token tidak ada/kedaluwarsa → arahkan ke login |
| 403 | `forbidden` | peran tidak cocok atau bukan pemilik |
| 404 | `not_found` | tidak ada, **atau bukan milikmu** (API sengaja tidak membedakan) |
| 409 | `stale_revision` | data sudah berubah sejak kamu baca → muat ulang lalu coba lagi (lihat 3.6) |
| 409 | `invalid_transition` | aksi tidak berlaku di status sekarang → muat ulang status |
| 409 | `insufficient_stock` | stok tidak cukup |
| 409 | `payment_expired` | hold 15 menit habis → mulai checkout baru |
| 409 | `idempotency_conflict` | key dipakai ulang untuk body berbeda, atau request yang sama masih jalan |
| 422 | `validation_error` | input salah; lihat `field` |
| 503 | `service_unavailable` | layanan AI belum dikonfigurasi/gagal → tawarkan jalur manual atau coba lagi |

### 3.3 Login dan token

```
POST /auth/register  { email, password (min 8), display_name }   → data: user (TANPA token)
POST /auth/login     { email, password }                           → data: { access_token, token_type: "bearer" }
GET  /auth/me                                                      → data: { id, email, display_name, roles: [{role, status}] }
```

- Register **tidak** login otomatis: panggil login setelahnya.
- Kirim `Authorization: Bearer <access_token>` di setiap request yang butuh login. Tidak ada cookie
  dan tidak ada refresh token. Token berlaku **12 jam**; setelah itu 401 → login ulang.
- Endpoint publik (tanpa token): `/health`, `/auth/register`, `/auth/login`, `GET /gallery*`,
  `POST /search/semantic`, `GET /listings/{id}`, `GET /gallery/{ref}/listings`,
  `GET /garment-templates*`, `GET /merchants/{id}`, `GET /tailors/{id}`, `GET /photo-consent-notice`,
  dan file publik.

### 3.4 Peran

Satu akun bisa punya beberapa peran sekaligus: `buyer`, `merchant`, `tailor`, `admin`, masing-masing
dengan `status` `pending` / `active` / `suspended`. Hanya peran **`active`** yang berlaku. Semua akun
baru otomatis `buyer`. Jadi penjual/penjahit adalah pembeli yang aplikasi mitranya disetujui admin.

Beberapa list menerima `?as=buyer|merchant|tailor` untuk memilih sudut pandang
(`GET /orders`, `GET /custom-requests`). Kalau user punya beberapa peran, UI perlu cara memilih
peran mana yang sedang dilihat. **Isi respons berbeda per peran** (lihat 3.10).

### 3.5 Pagination

List besar memakai cursor: `?limit=20&cursor=…` (limit maks 100), respons
`{ items: [...], next_cursor: "…" | null }`. Urutan selalu terbaru dulu. `next_cursor: null` berarti
habis. Beberapa list kecil mengembalikan array biasa tanpa pagination (misalnya `/addresses`,
`/body-photos`, revisi desain); cek bentuk `data`.

### 3.6 Revisi (optimistic locking)

Objek yang bisa diedit punya `revision`. Saat mengubah, kirim revisi yang kamu baca:
`expected_revision` (listing, entri galeri, set ukuran), `expected_design_revision` (desain),
`expected_quote_revision` (menerima penawaran), `expected_total_idr` (konfirmasi checkout).
Kalau orang lain/tab lain sudah mengubahnya, API menjawab 409 `stale_revision`.
Jangan kirim ulang otomatis: muat ulang data, tunjukkan perubahannya, biarkan user memutuskan.

### 3.7 Idempotency-Key (untuk aksi uang)

Tiga endpoint **wajib** header `Idempotency-Key`:

- `POST /fabric-checkouts/{id}/confirm`
- `POST /demo-payments/{id}/complete`
- `POST /quotes/{id}/accept`

Buat satu key acak (misalnya UUID) **per niat user**, lalu pakai key yang sama kalau request diulang
karena jaringan putus atau tombol diklik dua kali. Server akan memutar ulang respons pertama, bukan
memproses dua kali. Key baru = aksi baru.

### 3.8 Pekerjaan async (job) dan polling

Beberapa proses berjalan di **worker** (`worker.py`), bukan di request. Kalau worker mati, statusnya
tertahan di `queued` selamanya.

Status job: `queued` → `processing` → `completed` | `completed_with_warnings` | `failed`.

| Proses | Mulai | Pantau | Waktu kira-kira |
|---|---|---|---|
| Ukur badan | `POST /body-measurements/estimate` → `{ job_id, status }` (202) | `GET /body-measurements/{job_id}` | beberapa detik; 3D bisa lebih lama |
| Preview produk | `POST /customizations/{id}/product-previews` → preview (202) | `GET /previews/{preview_id}` | detik |
| Ilustrasi di foto (try-on) | `POST /customizations/{id}/photo-try-ons` → preview (202) | `GET /previews/{preview_id}` | detik |
| Cerita listing | `POST /listings/{id}/story` → `{ job }` (202) | `GET /listings/{id}/story` | **30–60 detik** |
| Umum | — | `GET /jobs/{job_id}` | — |

Polling tiap 1–3 detik sampai status final, lalu berhenti. Kalau `failed`, tampilkan `error`
(pesannya sudah ditulis untuk manusia) dan tawarkan jalan lain. Scan kain (`POST /vision/analyze`)
**tidak** async: request-nya menunggu sampai selesai (sekitar 3 detik).

### 3.9 File, gambar, dan URL bertanda tangan

- **Upload umum:** `POST /files`, `multipart/form-data` dengan field `file` dan `kind`.
  `kind` salah satu dari:
  - `listing_photo`: foto kain, **publik**, hanya penjual aktif
  - `claim_evidence`: bukti klaim, **privat**, gambar atau PDF
  - `verification_doc`: dokumen aplikasi mitra, **privat**, gambar atau PDF
  - `reference_image`: gambar referensi galeri, publik, hanya admin

  Gambar: JPEG/PNG/WebP, maks 8 MB. Server membuang metadata EXIF/GPS. Respons: `{ id, url, ... }`.
  Pakai `id` untuk menempelkan file ke objek lain (listing, klaim, aplikasi).
- **Foto badan punya endpoint sendiri** (`POST /body-photos`, lihat 5.5), bukan `/files`.
- **URL di respons itu relatif**, misalnya `/api/v1/files/<id>`. Tambahkan base URL API di depannya.
- **File privat** datang dengan `?token=…` yang **kedaluwarsa 5 menit**. Jangan simpan URL-nya
  (localStorage, cache lama, link yang dibagikan). Ambil ulang objeknya untuk mendapat URL baru.
  Kalau gambar privat gagal dimuat setelah lama terbuka, muat ulang datanya.
- File publik (foto listing, gambar galeri) tidak kedaluwarsa.

### 3.10 Privasi: API menyaring data per peran, UI jangan menambah

Backend sudah menyaring, jadi UI cukup menampilkan apa yang diterima. Tetapi jangan pernah mencoba
mengakali, menyimpan, atau meneruskan data ini ke pihak lain:

- **Foto badan dan ilustrasi try-on** hanya pernah terlihat oleh pemiliknya (pembeli).
- **Penjahit** menerima desain, preview produk, ukuran (cm), kebutuhan kain, dan alamat untuk
  permintaan yang ditujukan kepadanya. **Tidak** menerima foto badan.
- **Penjual** dalam pesanan custom hanya menerima jumlah dan potongan kain. **Tidak** menerima
  ukuran, desain, atau alamat (field-nya memang tidak ada di respons).
- Hasil **cek klaim foto** (sinyal untuk kurator) tidak ada di tampilan publik listing.
- Jangan log isi foto, ukuran badan, atau bukti klaim ke analytics/console di produksi.

### 3.11 Tipe data

- ID = UUID (string). Waktu = ISO 8601 dengan zona waktu (UTC).
- Uang = **integer rupiah** (`*_idr`), tanpa desimal.
- Jumlah kain/panjang (`quantity`, `purchase_quantity`, `min_quantity`, dll.) bisa datang sebagai
  **angka atau string desimal** ("2.00") tergantung endpoint. Parse keduanya. Kirim sebagai angka.
- Ukuran badan dalam **cm**, kunci: `chest_circumference`, `waist_circumference`,
  `hip_circumference`, `shoulder_width`, `back_length`, `sleeve_length`, `neck_circumference`.

---

## 4. Daftar layar yang perlu ada (fungsi, bukan desain)

Ini cakupan fitur yang sudah didukung backend. Cara mengelompokkan, menamai, dan menata layar
terserah kamu.

**Publik:** beranda, jelajah Galeri budaya + filter + pencarian, detail entri Galeri (+ "paspor"
sumber), daftar kain per entri, detail listing kain (+ cerita budaya kalau ada), profil penjual,
profil penjahit, daftar pola baju, login, daftar.

**Pembeli:** alamat pengiriman, checkout kain, pembayaran demo, daftar & detail pesanan (+ konfirmasi
terima), rancang baju custom (desain → ukur → kain → ilustrasi → pilih penjahit), daftar & detail
permintaan custom (+ terima penawaran), chat, klaim & banding, kelola foto badan & izin, ajukan
menjadi mitra.

**Penjual:** aplikasi mitra, daftar listing, buat/ubah listing + foto + stok, scan foto kain,
cerita listing (minta, tinjau, terbitkan), pesanan masuk (+ ubah status), permintaan custom masuk
(konfirmasi/tolak kain), settlement.

**Penjahit:** aplikasi mitra, kapabilitas per pola, permintaan masuk (tolak/minta revisi, buat
spesifikasi, terbitkan penawaran), pesanan custom (terima kain, inspeksi, produksi, kirim),
amendment, settlement.

**Admin/kurator:** aplikasi mitra (tinjau/setujui/tolak), suspend/reinstate mitra, Galeri (entri,
gambar, terbit/arsip), sumber budaya + potongan teks, cerita Galeri (tulis/AI/setujui), foto
referensi + cakupan, cek klaim listing + verifikasi asal, banding (tinjau/minta bukti/putusan),
eksekusi remedi, aturan komisi, log audit, simulasi pengiriman tiba.

---

## 5. Alur per fitur

Format: urutan panggilan, field respons yang penting, dan hal yang mudah salah. Body request
lengkap ada di `/docs`.

### 5.1 Galeri budaya (publik)

```
GET  /gallery?region=&technique=&kind=textile|motif|tradition&limit=&cursor=
GET  /gallery/{ref}               ref = slug atau id
GET  /gallery/{ref}/passport      cerita yang disetujui + daftar sumber + kutipan
GET  /gallery/{ref}/listings      kain yang dijual untuk entri ini
POST /search/semantic             { query, region?, technique?, kind?, limit? }
```

- Item list: `{ id, slug, name, kind, aliases, textile_type, technique, region, community, summary, ... }`.
- Detail menambah `has_story`, `reference_images`, `availability`.
- Paspor: `story` (bisa `null`), `citations[]` (`title`, `publisher`, `url`, `license`, `excerpt`),
  `review`, dan `notice`. **`notice` wajib tampil:** Galeri menjelaskan referensi budaya, bukan
  sertifikat keaslian barang.

### 5.2 Detail listing dan beli kain

```
GET  /listings/{id}
POST /addresses                         { label, recipient_name, phone, line1, city, province, postal_code? }
GET  /addresses
POST /fabric-checkouts                  { listing_id, quantity, delivery_address_id }   → status "review"
POST /fabric-checkouts/{id}/confirm     { expected_total_idr }  + Idempotency-Key       → "payment_pending", stok di-hold 15 menit
POST /demo-payments/{payment_id}/complete  { outcome: "succeeded" | "failed" } + Idempotency-Key → { payment, order }
GET  /orders?as=buyer   GET /orders/{id}
POST /orders/{id}/events                { event, note? }
```

Field listing yang penting: `title`, `price_idr`, `selling_unit` (`meter`|`piece`), `min_quantity`,
`quantity_increment`, `usable_width_cm`, `piece_length_cm`/`piece_width_cm`, `material`,
`images[]` (`url` publik), `stock`, `merchant`, `custom_order_ready` + `missing_for_custom`,
`story` (cerita terbit atau `null`), dan `origin`:

- `origin.merchant_claimed_origin`: klaim penjual. Tampilkan **sebagai klaim** ("menurut penjual").
- `origin.curator_verified_origin`: hanya terisi kalau kurator memverifikasi. Ini satu-satunya yang
  boleh ditampilkan sebagai terverifikasi.
- `origin.visual_match`: deskripsi hasil scan. Bukan sertifikat.

Checkout:
- Jumlah harus ≥ `min_quantity` dan kelipatan `quantity_increment`.
- Ringkasan checkout: `subtotal_idr`, `shipping_idr` (simulasi), `service_fee_idr`, `total_idr`,
  `expires_at`, `payment`.
- Konfirmasi mengirim `expected_total_idr` dari ringkasan. Kalau harga/ongkir berubah → 409; tampilkan
  total baru dan minta konfirmasi lagi.
- Setelah confirm, ada **hitung mundur 15 menit** (`expires_at`). Lewat dari itu → `payment_expired`.
- Pembayaran demo: UI menyediakan tombol "bayar (simulasi)" dan, kalau mau, "gagalkan" untuk demo.

Status pesanan kain dan event (field `event` di `POST /orders/{id}/events`):

| event | siapa | dari → ke |
|---|---|---|
| `start_preparing` | penjual | `confirmed` → `preparing` |
| `dispatch` | penjual | `preparing` → `shipped_to_buyer` |
| `simulate_delivery` | admin | `shipped_to_buyer` → `delivered` |
| `confirm_receipt` | pembeli | `delivered` → `completed` (ditolak kalau masih ada klaim terbuka) |
| `cancel` | penjual/admin | `confirmed`/`preparing` → `cancelled` |

Detail pesanan: `kind` (`fabric`|`custom`), `status`, `total_idr`, `snapshot`, `payment`,
`shipments[]` (`leg`, `status`, `tracking_no`, semuanya `simulated: true`), `events[]` (riwayat),
`simulation_notice`. Rincian uang: `GET /orders/{id}/settlement` (isi berbeda per peran).

### 5.3 Menjadi mitra (penjual/penjahit)

```
POST  /partner-applications            { type: "merchant"|"tailor", data: {...} }   → status "draft"
PATCH /partner-applications/{id}       { data }
POST  /partner-applications/{id}/submit
GET   /partner-applications/mine
```

`data` penjual: `shop_name`, `description`, `city`, `province`, `contact_phone?`,
`evidence_file_ids[]` (upload dulu dengan `kind=verification_doc`). Penjahit menambah
`service_area[]` dan `experience_years`.

Status: `draft` → `submitted` → `under_review` → `approved` | `rejected` | `needs_information`
(kalau `needs_information`, user mengubah `data` lalu submit lagi). Setelah `approved`, peran
`merchant`/`tailor` jadi `active`: panggil `GET /auth/me` lagi untuk memperbarui UI.

Penjahit lalu mengisi kapabilitas per pola (wajib, kalau tidak ia tidak pernah direkomendasikan):
`GET /tailor/capabilities`, `PUT /tailor/capabilities/{T01..T05}`
`{ base_rate_idr, lead_time_days, weekly_capacity, materials[], supported_options }`,
`DELETE /tailor/capabilities/{code}`.

### 5.4 Penjual: listing, scan, dan cerita

```
POST  /listings                         { entry_id, title, selling_unit, price_idr, ... }  → "draft"
PATCH /listings/{id}                    { expected_revision, ...field yang diubah }
POST  /files  (kind=listing_photo)      → file id
POST  /listings/{id}/images             { file_id, caption?, sort_order? }
POST  /listings/{id}/stock-units        { length_m? (meter), quantity }
PATCH /stock-units/{unit_id}            { quantity }
POST  /listings/{id}/publish            /archive
GET   /merchant/listings   GET /merchant/listings/{id}   GET /merchant/stock
```

- `entry_id` = entri Galeri yang **terbit**. Ini **klaim** penjual tentang tradisi kainnya. Pilihan
  diambil dari `GET /gallery`. `merchant_claimed_origin` (teks bebas, misalnya desa asal) opsional.
- Syarat publish: entri Galeri terbit dan minimal **satu foto kain**.
- Supaya bisa dipesan custom: `material` + `usable_width_cm` (meter) atau `piece_length_cm` +
  `piece_width_cm` (potong). Respons memberi tahu lewat `missing_for_custom`.
- Stok "meter" dicatat per potongan utuh (`length_m`), karena kain tidak bisa disambung.

**Scan foto kain** (sinkron, ~3 detik):
```
POST /vision/analyze   { listing_id, file_id? }   (tanpa file_id = foto pertama listing)
```
Respons: `{ id, status, method, result, error, notice }`. `result` berisi deskripsi AI (teknik,
motif, warna, ciri) dan pemeriksaan teknik terhadap klaim. **AI tidak menebak nama tradisi**, hanya
mendeskripsikan dan memeriksa konsistensi. **`notice` wajib tampil:** ini deskripsi otomatis, bukan
sertifikasi asal-usul. Model: Gemma 4 26B via OpenRouter.

**Cerita listing** (async, 30–60 detik, butuh scan dulu):
```
POST /listings/{id}/story                       → { job: { id, status, error } }
GET  /listings/{id}/story                       → { draft, published, job }
POST /listings/{id}/story/{story_id}/publish
```
- Kalau scan belum ada atau teknik di scan "berbeda" dengan klaim, POST langsung ditolak (422).
- Cerita = 3 paragraf. `sentences[]` = tiap kalimat dengan `paragraph` dan `sources` (`"foto"` atau
  id potongan sumber). `citations` memetakan id sumber ke teksnya. Kalimat pertama selalu klaim
  penjual ("Menurut penjual, kain ini …"), ditulis oleh kode, bukan model.
- `notes[]` berisi catatan seperti kalimat yang dibuang karena tidak didukung sumber. Tampilkan ke
  penjual saat meninjau draf.
- Hasil selalu **draf**. Penjual membaca lalu menerbitkan; setelah terbit, cerita muncul di
  `GET /listings/{id}` sebagai `story`.

### 5.5 Baju custom: desain, ukur, kain, ilustrasi

Urutan yang wajar (backend tidak memaksa urutan, tapi syarat "siap diajukan" di bawah harus
terpenuhi):

**a. Mulai dan desain**
```
GET  /listings/{id}/templates             pola yang cocok untuk kain ini
GET  /garment-templates/{code}            definisi pola: options + required_dimensions
POST /customizations                      { listing_id, template_code }   → current_revision 1
GET  /customizations/{id}
```

Pola: `T01` Kemeja lengan pendek, `T02` Blouse, `T03` Rompi, `T04` Outer, `T05` Tunik.
`options` tiap pola berbentuk `{ nama: { type: "enum", values, default } | { type: "number", min, max, unit, default } }`.
Bangun kontrol pilihan dari data ini, jangan di-hardcode. **`notice` pola wajib tampil**: nilai
batas adalah nilai demo, penjahit yang mengonfirmasi.

Mengubah desain, dua cara:
```
# 1) langsung dari kontrol
POST /customizations/{id}/revisions   { expected_design_revision, changes: { collar: "mandarin" } }

# 2) dari teks bebas, dua langkah
POST /customizations/{id}/prompt-changes  { expected_design_revision, prompt: "kerah mandarin, saku kiri" }
   → proposal: { proposal_id, changes[], clarifications[], unsupported_requests[], fallback, ... }
POST /customizations/{id}/revisions   { expected_design_revision, proposal_id, resolutions?: { c0: <pilihan> } }

# kembali ke versi lama
POST /customizations/{id}/revisions   { expected_design_revision, revert_to_revision: 2 }
GET  /customizations/{id}/revisions
```
- Proposal **tidak** langsung diterapkan. Tampilkan `changes` untuk dikonfirmasi pembeli.
- `clarifications[]` (id `c0`, `c1`, …) = permintaan ambigu; pembeli memilih, kirim lewat `resolutions`.
- `unsupported_requests[]` = permintaan yang tidak bisa dilayani pola ini, beserta alasannya.
- `fallback: "structured_controls"` = teks tidak dipahami; arahkan ke kontrol biasa.
- Setiap revisi baru membuat preview, estimasi kain, dan penawaran lama menjadi usang.

**b. Preview produk**
```
POST /customizations/{id}/product-previews   → { id, status: "queued", ... }
GET  /previews/{id}                          → { status, url, label, warnings, design_revision }
```
`status` bisa `stale` kalau desain sudah berubah: minta preview baru. **`label` wajib tampil**
(ilustrasi konseptual, bukan pola potong). Preview produk terbaru dari revisi desain yang diajukan
ikut dikirim ke penjahit.

**c. Foto badan dan ukur otomatis**
```
GET  /photo-consent-notice          teks izin, masa simpan default, panduan foto
POST /photo-consents                { retention_minutes? }   → consent id
POST /body-photos                   multipart: file, consent_id   (depan, lalu samping)
POST /body-measurements/estimate    { body_photo_id, side_photo_id?, gender?: "male"|"female", height_cm, customization_id? }
GET  /body-measurements/{job_id}    poll sampai selesai
```
- **Izin harus diberikan dulu** dan teks `GET /photo-consent-notice` ditampilkan ke user sebelum
  upload. Tampilkan juga `guidance` (cara foto yang benar).
- Foto badan **privat** dan **otomatis terhapus** setelah masa simpan (default 60 menit). User bisa
  menghapus kapan saja (`DELETE /body-photos/{id}`) atau mencabut izin
  (`POST /photo-consents/{id}/revoke`, semua fotonya ikut terhapus). Ukuran yang sudah dibuat tetap ada.
- Dengan foto samping + gender, server memperkirakan 7 ukuran (model 3D). Hanya foto depan →
  sebagian ukuran saja; sisanya `manual_required`.
- Hasil job yang selesai:
  ```
  { status, error, output: { method, supported[], manual_required[], warnings[] },
    measurement_set: { id, values: [{ key, value_cm, source, quality_flag }], ... },
    visual: { front?: View, side?: View } | null }
  ```
  `warnings` ditulis untuk manusia; tampilkan. `quality_flag: "review_required"` artinya pembeli
  harus mengecek.

**Menggambar ukuran di atas foto (opsional tapi sangat membantu).** `visual.front`/`visual.side`:
```
View = {
  photo_url: string,                 // URL bertanda tangan foto pemilik (kedaluwarsa 5 menit)
  frame: [width, height],            // ukuran foto dalam piksel; koordinat di bawah memakai sistem ini
  rings: [{ key, cx, cy, rx, ry }],  // lingkar (dada, pinggang, pinggul, leher) sebagai elips
  lines: [{ key, points: [[x1,y1],[x2,y2]] }]   // panjang (bahu, lengan, punggung)
}
```
Cara termudah: tumpuk elemen SVG dengan `viewBox="0 0 width height"` tepat di atas gambar dengan
ukuran tampil yang sama. Warna, gaya garis, dan label bebas. `visual` jadi `null` setelah foto dihapus.

**d. Set ukuran (selalu bisa manual)**
```
POST  /measurement-sets              { height_cm?, values: { chest_circumference: 96, ... } }   (manual)
PATCH /measurement-sets/{id}         { expected_revision, height_cm?, values }   koreksi
POST  /customizations/{id}/measurement-set     { measurement_set_id }   pasang ke desain
POST  /measurement-sets/{id}/confirm           { customization_id }     pembeli mengonfirmasi
```
- Set hasil ukur otomatis sudah dibuat oleh job; tinggal dikoreksi, dipasang, dan dikonfirmasi.
- `values[].source`: `estimated`, `manual`, `corrected`, `manual_required`, `tailor`. Nilai asli hasil
  estimasi disimpan di `original_value_cm` dan `history`, jadi koreksi tidak menghapus jejak.
- Semua `required_dimensions` pola harus terisi sebelum konfirmasi.
- **`notice` set ukuran wajib tampil**: ukuran badan ≠ ukuran baju jadi; penjahit menetapkan dimensi
  produksi.

**e. Kebutuhan kain**
```
POST /customizations/{id}/material-estimates          → { result, stale, stale_reasons, notice }
GET  /customizations/{id}/material-estimates/current
```
`result` berisi antara lain `required_length_cm`, `purchase_quantity`, `surplus_m`, `fits`. Buat
ulang kalau `stale: true` (desain/ukuran berubah). `notice` wajib tampil.

**f. Ilustrasi di foto sendiri (try-on)**
```
POST /customizations/{id}/photo-try-ons   { body_photo_id }   → preview (kind "on_body"), poll GET /previews/{id}
```
Hanya pemilik foto yang bisa melihatnya. **Tidak pernah** dikirim ke penjahit. `label` wajib tampil.

**g. Siap diajukan?**
`GET /customizations/{id}` → `ready_for_tailor_validation: true` kalau tidak ada klarifikasi
terbuka, set ukuran sudah `confirmed`, dan estimasi kain ada dan tidak usang. Selain itu juga ada
`open_clarifications`, `measurement_set`, `material_estimate` untuk menunjukkan apa yang kurang.

### 5.6 Permintaan custom, penawaran, dan pesanan custom

```
GET  /tailors/recommendations?customization_id=&delivery_address_id=
POST /custom-requests            { customization_id, tailor_id, delivery_address_id }   → "draft"
POST /custom-requests/{id}/submit                                                       → "submitted"
GET  /custom-requests?as=buyer|merchant|tailor     GET /custom-requests/{id}
PATCH /custom-requests/{id}      { tailor_id?, delivery_address_id? }   (ganti penjahit/alamat)
POST /custom-requests/{id}/withdraw
```
- Rekomendasi: `[{ tailor_id, shop_name, city, province, experience_years, base_rate_idr,
  lead_time_days, weekly_capacity, reasons[], verified }]`. Tampilkan `reasons` (kenapa
  direkomendasikan). Pembeli tetap memilih sendiri.
- **Sebelum submit, beri tahu pembeli apa yang dikirim** (wajib, isi bebas bentuknya): penjahit
  menerima desain, preview produk terbaru, ukuran (cm), kebutuhan kain, dan alamat; foto badan dan
  ilustrasi di foto tidak dikirim; penjual hanya menerima jumlah kain.
- Submit mengambil **snapshot** desain + ukuran + estimasi. Mengubah desain/ukuran/penjahit setelahnya
  membatalkan validasi dan penawaran lama.
- Detail untuk pembeli/penjahit memuat `design_state`, `measurements_cm`, `estimate`, `template`,
  `address`, dan `design_preview: { url, label } | null`. Untuk penjual hanya `requested_quantity`,
  `required_continuous_cut_m`, `selling_unit`.

Validasi oleh mitra:
```
POST /custom-requests/{id}/merchant-confirmation   { decision: "confirm"|"reject", reason? }      penjual
POST /custom-requests/{id}/tailor-decision         { action: "return_for_revision"|"reject", reason } penjahit
POST /custom-requests/{id}/production-spec         { fabric_purchase_quantity, finished_dimensions, lead_time_days,
                                                     extra_materials[], surcharges[], motif_notes?, surplus_handling }  penjahit
POST /custom-requests/{id}/quotes                  { spec_id, expires_in_hours? (default 48) }      penjahit
GET  /custom-requests/{id}/quotes   GET /quotes/{id}
```
- Penjual harus konfirmasi kain **lebih dulu**; baru penjahit bisa membuat spesifikasi.
- Spesifikasi baru membatalkan penawaran terbuka sebelumnya.

Status permintaan: `draft` → `submitted` → `validating` (penjual sudah konfirmasi) →
`ready_for_quote` (spesifikasi ada) → `awaiting_buyer` (penawaran terbit) → `converted_to_order`.
Cabang: `needs_revision` (penjual menolak atau penjahit minta revisi → pembeli memperbaiki lalu
submit ulang), `rejected`, `withdrawn`.

Penawaran: `{ id, revision, status, total_idr, expires_at, lines[] (kind, description, amount_idr,
owner), specification, stale_reasons[], acceptable, changes_from_request, surplus_fabric,
simulation_notice }`. Tombol terima hanya aktif kalau `acceptable: true`. Kalau `stale_reasons`
berisi `design_revision_changed`/`measurements_changed`, jelaskan bahwa penawaran itu untuk versi lama.
`changes_from_request` menunjukkan beda jumlah kain yang diminta vs yang ditawarkan penjahit;
tampilkan supaya pembeli sadar.

Terima dan bayar:
```
POST /quotes/{id}/accept   { expected_quote_revision, acknowledged_visual_reference: true, delivery_address_id }
                           + Idempotency-Key   → { payment: { id, status, amount_idr }, quote }
POST /demo-payments/{payment_id}/complete   { outcome } + Idempotency-Key   → { payment, order }
```
`acknowledged_visual_reference` wajib `true`: pembeli mencentang bahwa preview hanya referensi
visual, bukan jaminan hasil. Kain di-hold 15 menit seperti checkout biasa.

Pesanan custom (`POST /orders/{id}/events`):

| event | siapa | dari → ke |
|---|---|---|
| `start_preparing` | penjual | `confirmed` → `fabric_preparing` |
| `dispatch_to_tailor` | penjual | `fabric_preparing` → `shipped_to_tailor` (leg 1) |
| `receive_fabric` | penjahit | `shipped_to_tailor` → `received_by_tailor` |
| *(inspeksi, endpoint sendiri)* | penjahit | `received_by_tailor` → `inspection_passed` / `inspection_issue` |
| `begin_production` | penjahit | `inspection_passed` → `in_production` |
| `complete_production` | penjahit (+ `note` wajib) | `in_production` → `quality_check` |
| `dispatch_finished` | penjahit | `quality_check` → `shipped_to_buyer` (leg 2) |
| `simulate_delivery` | admin | `shipped_to_buyer` → `delivered` |
| `confirm_receipt` | pembeli | `delivered` → `completed` |
| `resolve_issue` / `fail_fulfillment` | admin (+ `note`) | `inspection_issue` → `received_by_tailor` / `failed_fulfillment` |
| `cancel` | penjual/penjahit/admin (+ `note`) | `confirmed`/`fabric_preparing` → `cancelled` |

```
POST /orders/{id}/fabric-inspection   { passed, condition, measured_width_cm?, measured_length_m?, notes? }   penjahit
POST /orders/{id}/amendments          { reason, changes, price_delta_idr }    perubahan setelah pesanan jalan
GET  /orders/{id}/amendments
POST /orders/{id}/amendments/{aid}/decision   { decision: "approve"|"reject" }
```

### 5.7 Chat

```
POST /conversations                { order_id? | request_id?, with: "merchant"|"tailor" }
GET  /conversations
GET  /conversations/{id}/messages
POST /conversations/{id}/messages  { body (maks 2000) }
```
Chat terikat konteks (pesanan, permintaan, atau klaim). Tidak ada push/websocket: ambil ulang pesan
secara berkala atau saat user membuka percakapan. `viewer_id` di percakapan membantu membedakan
pesan milik sendiri.

### 5.8 Klaim, banding, dan remedi

```
POST /orders/{id}/claims         { target: "merchant"|"tailor", component: "fabric"|"garment"|"shipping"|"service",
                                   description, evidence_file_ids[] }          pembeli
GET  /claims    GET /claims/{id}
POST /claims/{id}/evidence       { file_id, note? }
POST /claims/{id}/responses      { kind: "discussion"|"proposal"|"rejection", reason, proposal? }   mitra
POST /claims/{id}/proposals/{response_id}/decision   { decision: "accept"|"reject" }            pembeli
POST /claims/{id}/withdraw                                                                       pembeli
POST /claims/{id}/appeals        { partner_rejection_id, reason, evidence_ids[] }   pembeli, setelah mitra menolak
POST /claims/{id}/escalate       { reason }   pembeli, kalau mitra tidak merespons melewati batas waktu
```
- Bukti diunggah dulu lewat `POST /files` dengan `kind=claim_evidence`.
- Klaim bisa dibuka sampai 14 hari setelah pesanan sampai. Mitra punya 48 jam untuk merespons.
  Detail klaim memuat `policy` (`claim_window_ends_at`, `partner_response_due_at`,
  `partner_overdue`, `note`): pakai ini, jangan hitung sendiri. `policy.note` menjelaskan bahwa
  ini kebijakan demo.
- `roles` di detail klaim memberi tahu peran user ini dalam klaim tersebut. **Pakai `roles`**
  untuk memutuskan tombol mana yang tampil (pihak yang diklaim adalah `target`, bukan
  merchant/tailor secara umum).
- Klaim terbuka memblokir `confirm_receipt`.

Status klaim: `opened`, `partner_discussion`, `resolution_proposed`, `partner_rejected`,
`appealed`, `internal_review`, `decision_issued`, `resolved`, `withdrawn`.
Status banding: `pending`, `under_review`, `decided`.

Admin:
```
GET  /admin/appeals    GET /admin/appeals/{id}   (detail baru bisa dibuka setelah start-review)
POST /admin/appeals/{id}/start-review
POST /admin/appeals/{id}/request-evidence   { message }
POST /appeals/{id}/decision    { outcome: "upheld_rejection"|"overturned"|"partial", remedy_type, amount_idr?, reasoning }
POST /claims/{id}/remedy-events   { action: "rework"|"replacement"|"refund_partial"|"refund_full", amount_idr?, note? }
```
Putusan dan eksekusi remedi itu dua langkah terpisah (`decision.requires_execution`). Semua refund
adalah simulasi.

### 5.9 Admin dan kurator

- **Mitra:** `GET /admin/partner-applications`, `GET …/{id}`,
  `POST …/{id}/decision { action: "start_review"|"approve"|"reject"|"request_information", reason? }`,
  `POST /admin/partners/suspend` & `/reinstate` `{ user_id, role, reason? }`.
- **Galeri:** `POST/GET /admin/gallery`, `GET/PATCH /admin/gallery/{id}` (dengan
  `expected_revision`), `POST …/publish`, `…/archive`, `…/images`. Status entri: `draft`,
  `in_review`, `published`, `archived`. Entri harus punya cerita yang disetujui untuk terbit.
- **Sumber budaya:** `POST/GET /admin/sources`, `POST …/{id}/decision` (`approval_status`:
  `pending`/`approved`/`rejected`), `POST …/{id}/chunks` (potongan teks). Hanya sumber `approved`
  yang dipakai AI dan boleh dikutip cerita.
- **Cerita Galeri:** `POST/GET /admin/gallery/{id}/stories`, `POST …/story/generate` (AI, hasil
  draf), `POST /admin/stories/{id}/submit`, `POST /admin/stories/{id}/decision`. Status: `draft`,
  `in_review`, `approved`, `rejected`, `superseded`.
- **Foto referensi:** `GET /admin/reference-photos`, `GET …/coverage` (tradisi mana yang sudah bisa
  dinilai), `POST …/decision`.
- **Cek klaim listing & verifikasi asal:** `GET /admin/listings/{id}/claim-check`,
  `POST /admin/listings/{id}/verify-origin { text, add_as_reference }`. Hasil cek klaim:
  `konsisten`, `perlu_dicek`, `belum_ada_referensi`, `gagal`. Ini sinyal untuk kurator, bukan vonis.
- **Lain-lain:** `GET/POST /admin/commission-rules`, `GET /admin/audit-events`,
  `POST /admin/garment-templates/sync`.

---

## 6. Ringkasan status (untuk label UI)

Semua nilai status dikirim sebagai string bahasa Inggris. Terjemahan dan label tampilan urusan
frontend. Jangan membandingkan dengan teks terjemahan; bandingkan dengan nilai mentah.

| Objek | Nilai |
|---|---|
| Pesanan | `confirmed`, `preparing`, `shipped_to_buyer`, `delivered`, `completed`, `cancelled`, `issue_reported`, `on_hold`, `failed_fulfillment`, `fabric_preparing`, `shipped_to_tailor`, `received_by_tailor`, `inspection_passed`, `inspection_issue`, `in_production`, `quality_check` |
| Checkout kain | `review`, `payment_pending`, `paid`, `expired`, `cancelled`, `failed` |
| Pembayaran demo | `not_started`, `pending`, `succeeded`, `failed`, `expired`, `refund_recorded` |
| Pengiriman | leg `merchant_to_buyer` / `merchant_to_tailor` / `tailor_to_buyer`; status `pending`, `shipped`, `delivered` |
| Permintaan custom | `draft`, `submitted`, `validating`, `ready_for_quote`, `awaiting_buyer`, `converted_to_order`, `needs_revision`, `rejected`, `withdrawn` |
| Penawaran | `issued`, `accepted`, `superseded`, `expired`, `declined` |
| Amendment | `proposed`, `approved`, `rejected` |
| Listing | `draft`, `published`, `archived` |
| Cerita listing | `draft`, `published`, `superseded` |
| Aplikasi mitra | `draft`, `submitted`, `under_review`, `approved`, `needs_information`, `rejected` |
| Set ukuran | `draft`, `confirmed` |
| Preview | `queued`, `processing`, `completed`, `completed_with_warnings`, `failed`, `stale` |
| Job | `queued`, `processing`, `completed`, `completed_with_warnings`, `failed` |
| Klaim / banding | lihat 5.8 |

---

## 7. Teks yang wajib sampai ke user

Bentuk dan penempatan bebas. Yang penting isinya terlihat di momen yang tepat. Semua teks ini
sudah dikirim API, jadi tampilkan dari respons, jangan tulis ulang sendiri.

| Di mana | Field | Isi singkat |
|---|---|---|
| Checkout, pesanan, penawaran, settlement, klaim | `simulation_notice` | pembayaran, ongkir, pelacakan, dan dana adalah simulasi |
| Paspor Galeri | `notice` | Galeri bukan sertifikat keaslian barang |
| Scan kain | `notice` | deskripsi otomatis, bukan sertifikasi asal-usul |
| Pola baju | `notice` | nilai batas adalah nilai demo |
| Preview & try-on | `label` / `warnings` | ilustrasi konseptual, bukan pola potong atau jaminan |
| Set ukuran | `notice` | ukuran badan ≠ ukuran baju jadi |
| Estimasi kain | `notice` | estimasi awal, penjahit memvalidasi |
| Sebelum upload foto badan | `GET /photo-consent-notice` → `text`, `guidance` | izin, masa simpan, cara foto |
| Sebelum mengajukan ke penjahit | (teks frontend) | apa yang diterima penjahit dan penjual, foto badan tidak dikirim |
| Klaim | `policy.note` | kebijakan demo |
| Listing | `origin` | klaim penjual ditampilkan sebagai klaim; hanya `curator_verified_origin` yang boleh disebut terverifikasi |

---

## 8. Hal yang sering bikin bug

1. **Nama status/peran ditebak.** Dua bug di frontend lama berasal dari sini (peran klaim `target`,
   status banding `pending`/`under_review`). Selalu cek respons asli.
2. **Worker tidak jalan** → ukur badan, preview, dan cerita tertahan di `queued`.
3. **URL file privat disimpan** → gambar rusak setelah 5 menit.
4. **Lupa base URL** di depan URL file relatif (`/api/v1/files/...`).
5. **Klik ganda di tombol bayar/terima** tanpa Idempotency-Key yang sama → ditolak atau dobel.
6. **Mengirim ulang otomatis setelah 409 `stale_revision`** → harus muat ulang dan tanya user.
7. **Menganggap 404 = tidak ada**: bisa juga berarti bukan milik user ini.
8. **Desimal sebagai string** (`"2.00"`) → parse sebelum dihitung.
9. **Peran baru tidak muncul** setelah aplikasi mitra disetujui → panggil `GET /auth/me` lagi.
10. **Klaim terbuka** memblokir konfirmasi terima pesanan; tampilkan alasannya dari error.

---

## 9. Batasan yang perlu diketahui

- Pembayaran, ongkir, kurir, refund, dan settlement: **simulasi**, diberi label di respons.
- Akurasi ukur badan **belum** diuji terhadap meteran. Selalu perlakukan sebagai estimasi yang
  dicek pembeli, dan selalu sediakan input manual.
- Cek klaim foto belum bisa memberi vonis untuk tradisi mana pun (foto referensi modern masih
  kurang). Hasil yang wajar saat ini: `belum_ada_referensi`.
- Hanya entri Galeri berstatus `published` yang bisa dipilih penjual; isinya bergantung pada data
  yang sudah disetujui kurator di database-mu.
- Tidak ada notifikasi push, email, websocket, atau refresh token. Semua pembaruan lewat polling
  atau muat ulang.
- Tidak ada upload video.

Kalau menemukan respons yang tidak sesuai dokumen ini, atau butuh field/endpoint baru, catat
endpoint, body, dan respons aslinya lalu kabari pemilik backend.
