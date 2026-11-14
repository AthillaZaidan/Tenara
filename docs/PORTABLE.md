# Memindahkan Tenara secara lengkap

## Apa yang dibawa

`scripts/portable.py` membuat satu arsip `.tar.gz` berisi:

- Dump PostgreSQL format custom: seluruh tabel, ID, relasi, akun/password hash, status kurasi,
  cerita, listing, stok, aktivitas, embedding, dan versi Alembic yang sudah ada.
- Seluruh file `services/api/storage`, termasuk gambar listing, referensi, dan preview.
- `web/public`: gambar, tekstur, atlas/peta, soundtrack MP3, font lokal, dan atribusinya.
- Kode frontend/backend **dari working directory**, termasuk file aplikasi baru yang belum
  di-commit, migrasi, seed dasar, tes, lockfile, dan panduan menjalankan aplikasi.
- Pengaturan runtime non-rahasia yang diubah melalui `.env`/environment, misalnya model embedding
  atau nama model LLM. URL komputer sumber dan credential tidak disalin.
- Manifest dengan SHA-256 setiap file, jumlah dan fingerprint isi tiap tabel, serta versi PostgreSQL.

Database dan `pg_dump` membaca satu snapshot transaksi yang sama. Hentikan API/worker serta
perubahan kode/aset saat ekspor supaya file upload dan kode juga tetap konsisten.
Ekspor gagal jika file aktif yang dirujuk database hilang atau ukurannya tidak sesuai.

Paket adalah **salinan lengkap**, bukan seed sintetis: status draft tetap draft, akun dan password
tetap sama, cerita hasil AI yang sudah tersimpan tidak dibuat ulang. Password hash bukan password
baru; mengetahui password akun sumber tetap diperlukan untuk login.

`.git`, `.env`, `node_modules`, `.venv`, cache build, browser session, dan dataset eksperimen
tidak masuk paket. Snapshot lengkap disimpan di `backups/` yang diabaikan Git karena memuat akun
dan data lokal. Kode, aset publik, serta tool tetap tersedia di repository.

## 1. Ekspor dari komputer sumber

Prasyarat ekspor: Python 3.12+ dan service `db` Docker Compose yang sedang sehat.
Tidak membutuhkan `uv`, PostgreSQL CLI di host, atau dependensi Python tambahan.

```bash
# Root repository
docker compose up -d db
python3 scripts/portable.py export
# Atau beri nama output:
python3 scripts/portable.py export --output backups/tenara-lengkap.tar.gz
python3 scripts/portable.py verify backups/tenara-lengkap.tar.gz
```

Perintah database selalu memakai service **`db` pada Docker Compose proyek ini**, bukan server
remote dari `DATABASE_URL`. Default nama database adalah `POSTGRES_DB` dari container (`tenara`).
Untuk nama database lain pada container yang sama, gunakan `--database NAMA`.
Storage default adalah `services/api/storage`, atau `STORAGE_DIR` di environment/`.env`.
Path relatif storage ditafsirkan dari `services/api`, sama seperti saat menjalankan API.

```bash
python3 scripts/portable.py export --database tenara --storage-dir /lokasi/storage
```

Model tambahan di `services/api/models` dapat disertakan bila foldernya tersedia:

```bash
python3 scripts/portable.py export --include-models
```

Model embedding yang diunduh oleh library ke cache pengguna tidak otomatis dibundel. Pada komputer
tujuan, model tersebut diunduh saat pertama dipakai. Model MediaPipe/SMPL-X dibawa melalui opsi
di atas atau dipasang terpisah sesuai petunjuk `HANDOFF.md`. Snapshot tidak mengunduh model baru.

## 2. Pindahkan dan ekstrak

Salin arsip dan `scripts/portable.py` melalui media transfer Anda. Pada komputer tujuan:

```bash
python3 portable.py unpack tenara-lengkap.tar.gz --destination tenara
```

Jika sudah clone repository, bisa memakai `python3 scripts/portable.py unpack ...` dari clone
tersebut. Folder tujuan harus baru atau kosong. Arsip membawa kode dan aset sendiri sehingga
kode hasil ekstraksi sesuai dengan snapshot, bukan tergantung versi clone lain.

`unpack` memverifikasi semua checksum sebelum ekstraksi, menolak path keluar direktori,
symlink, serta nama duplikat, lalu memverifikasi kembali hasil ekstraksi.

## 3. Restore database

Buka terminal di root folder hasil ekstraksi:

```bash
docker compose up -d db
docker compose ps
python3 scripts/portable.py restore
```

Tunggu service `db` sehat sebelum restore. Restore membuat database bila belum ada dan hanya
menerima database kosong. Tidak menghapus database yang sudah berisi data. Dump sudah membawa
schema dan migrasinya, jadi **jangan jalankan Alembic atau seed dasar sebelum restore**.

Restore berlangsung dalam satu transaksi. Setelahnya, tool membandingkan jumlah dan fingerprint
seluruh baris per tabel, versi migrasi, serta daftar file dengan manifest. `.env` lokal dibuat
dengan URL localhost, storage lokal, dan signing secret baru. Jika `.env` sudah ada, file itu
dipertahankan: sesuaikan `DATABASE_URL`, `STORAGE_DIR`, dan `NEXT_PUBLIC_API_URL` sendiri.
Generator `.env` menggunakan user/password/port bawaan Compose repository ini; jika konfigurasi
Compose diubah, sesuaikan URL-nya.

Untuk menggunakan database kosong bernama lain:

```bash
python3 scripts/portable.py restore --database tenara_copy
python3 scripts/portable.py verify --database tenara_copy
```

Pastikan API menggunakan database tersebut. Flag global `--compose-project NAMA` tersedia untuk
mengarahkan ke instance Compose yang sengaja diberi nama lain; letakkan sebelum nama perintah.

## 4. Jalankan aplikasi

Pasang uv dan Node.js, lalu di `services/api`:

```bash
uv sync --locked
uv run uvicorn app.main:app --port 8000
```

Terminal kedua di `services/api`:

```bash
uv run python worker.py
```

Terminal ketiga di `web`:

```bash
npm ci
npm run dev
```

- Aplikasi: http://localhost:3000
- API: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

Musik dimulai setelah interaksi masuk galeri, mengikuti aturan audio browser. Visual galeri 3D
memerlukan browser dengan WebGL; performa mengikuti kemampuan GPU dan pengaturan grafis komputer.
Tidak ada favorit, progres, token login, atau preferensi suara dari browser sumber yang diimpor.
Gunakan browser/profil baru untuk pengalaman awal yang bersih.

Cerita, gambar, dan preview yang sudah tersimpan dibawa oleh snapshot. Untuk scan atau pembuatan
cerita AI baru, tambahkan key provider ke `.env` lokal dan jalankan worker. Hasil AI baru bergantung
pada provider. Waktu kedaluwarsa checkout, penawaran, foto sementara, dan job tetap waktu aslinya;
worker akan menjalankan aturan kedaluwarsa normal setelah dinyalakan.

## 5. Pemeriksaan dan pembaruan paket

```bash
# Arsip: cek isi dan hash; tidak memerlukan Docker
python3 scripts/portable.py verify backups/tenara-lengkap.tar.gz

# Folder hasil ekstraksi: cek file sesuai manifest
python3 scripts/portable.py verify

# Tambahkan perbandingan seluruh isi database setelah restore, sebelum dipakai beraktivitas
python3 scripts/portable.py verify --database tenara
```

Setelah aplikasi dipakai, perubahan file atau data membuat perbandingan dengan snapshot lama
gagal; itu memang menunjukkan kondisi sudah berbeda. Ekspor lagi untuk mengambil kondisi terbaru.
Simpan output di `backups/` atau di luar proyek; file output yang sudah ada tidak ditimpa.

## Verifikasi pengembangan tool

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Uji restore penuh memakai database kosong terpisah, lalu `verify --database ...` dan smoke test API
terhadap data hasil restore. Database utama tidak perlu dihapus atau di-reset.

```bash
TENARA_TEST_SNAPSHOT=backups/tenara-lengkap.tar.gz \
TENARA_TEST_API_PYTHON=services/api/.venv/bin/python \
python3 -m unittest discover -s scripts -p 'test_portable_roundtrip.py'
```

Tes ini membuat database bernama acak, menguji backend dan upload dari **folder hasil ekstraksi**,
memastikan restore kedua ditolak, lalu menghapus hanya database uji tersebut. Dependensi backend
harus sudah tersedia pada interpreter `TENARA_TEST_API_PYTHON`.
