# Tenara

Marketplace tenun Nusantara dengan galeri budaya interaktif, katalog kain, dan studio baju custom.

## Memindahkan pengalaman lengkap ke komputer lain

Gunakan **snapshot portabel** untuk membawa database yang sudah terisi, file upload, musik,
gambar, font, cerita, dan kode aplikasi saat ini. Seed demo biasa hanya membuat data dasar.

```bash
# Di komputer sumber, dari root proyek. Hentikan API dan worker selama ekspor.
python3 scripts/portable.py export
```

Pindahkan file `backups/tenara-*.tar.gz` dan `scripts/portable.py` ke komputer tujuan, lalu:

```bash
python3 portable.py unpack tenara-YYYYMMDD-HHMMSS.tar.gz --destination tenara
```

Buka terminal di folder `tenara` hasil ekstraksi:

```bash
docker compose up -d db
python3 scripts/portable.py restore
```

Restore membuat `.env` lokal. Setelah itu, di `services/api`:

```bash
uv sync --locked
uv run uvicorn app.main:app --port 8000
# Terminal lain, masih di services/api:
uv run python worker.py
```

Di `web`, jalankan:

```bash
npm ci
npm run dev
```

Buka **http://localhost:3000**. Login memakai akun dan password yang sama dengan komputer sumber.
Favorit, progres jelajah, dan preferensi browser dimulai dari awal pada browser baru.

Prasyarat: **Python 3.12+**, Docker Compose, [uv](https://docs.astral.sh/uv/), dan Node.js 20.9+.
Instalasi dependensi pertama memerlukan internet.

- [Panduan snapshot, restore, dan verifikasi lengkap](docs/PORTABLE.md)
- [Kontrak API dan alur aplikasi](docs/HANDOFF.md)

## Database baru dengan data demo dasar

Untuk pengembangan tanpa snapshot, salin `.env.example` ke `.env`, jalankan Docker Compose,
lalu dari `services/api`:

```bash
uv sync --locked
uv run alembic upgrade head
DEMO_PASSWORD=demo-pass-123 uv run python -m scripts.seed_demo
uv run python -m scripts.seed_catalog
```

Langkah ini **tidak mereplikasi** seluruh isi database atau aset upload dari komputer sumber.
