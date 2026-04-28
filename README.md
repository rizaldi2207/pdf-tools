# PDF Tools

Aplikasi web untuk mengkonversi dan memproteksi file PDF, dijalankan via Docker.

**Fitur:**
- Konversi PDF ke gambar (PNG / JPEG) dengan pilihan DPI
- Konversi PDF ke DOCX
- Tambahkan password ke PDF (AES-128 / AES-256)
- Mendukung PDF yang sudah terproteksi password

## Prasyarat

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (sudah termasuk di Docker Desktop)

## Cara Menjalankan

**1. Clone repository**

```bash
git clone <url-repository>
cd pdf-convert
```

**2. Build dan jalankan container**

```bash
docker compose up -d --build
```

Tunggu hingga build selesai (pertama kali butuh beberapa menit). Setelah itu buka browser dan akses:

```
http://localhost:5000
```

Container akan otomatis berjalan ulang saat sistem restart (`restart: always`).

## Penggunaan

### Halaman Converter (`/`)

- **PDF → Images**: Upload PDF, pilih format (PNG/JPEG) dan DPI (72/150/300), klik **Convert**. Hasil bisa diunduh satu per satu atau sekaligus dalam satu file ZIP.
- **PDF → DOCX**: Ganti output ke **DOCX**, upload PDF, klik **Convert**. File `.docx` langsung terunduh otomatis.
- Jika PDF dilindungi password, isi field **PDF password** sebelum convert.

### Halaman Protect (`/protect`)

- Upload PDF, isi **Open password** (wajib), isi **Owner password** (opsional), pilih enkripsi (AES-128 atau AES-256), klik **Protect PDF**.
- Jika PDF sudah punya password sebelumnya, isi field **Current password**.
- File yang sudah terproteksi langsung terunduh otomatis.

## Konfigurasi

Ubah nilai environment variable di `docker-compose.yml` jika diperlukan:

| Variable | Default | Keterangan |
|---|---|---|
| `MAX_CONTENT_LENGTH` | `52428800` | Ukuran maksimum file upload (bytes). Default = 50 MB |
| `OUTPUT_DPI` | `150` | DPI default saat tidak dipilih oleh pengguna |

Setelah mengubah konfigurasi, restart container:

```bash
docker compose restart pdf-converter
```

## Perintah Berguna

```bash
# Lihat log aplikasi secara realtime
docker logs pdf-converter -f

# Stop aplikasi
docker compose down

# Rebuild setelah mengubah kode
docker compose up -d --build

# Restart tanpa rebuild (misal setelah ubah konfigurasi)
docker compose restart pdf-converter

# Cek status container
docker compose ps

# Health check
curl http://localhost:5000/health
```

## Struktur Proyek

```
pdf-convert/
├── docker-compose.yml
├── Dockerfile
└── app/
    ├── app.py              # Backend Flask
    ├── requirements.txt
    ├── templates/
    │   ├── base.html       # Layout bersama (nav, header)
    │   ├── index.html      # Halaman converter
    │   └── protect.html    # Halaman protect
    └── static/
        ├── css/style.css
        └── js/
            ├── main.js     # JS untuk halaman converter
            └── protect.js  # JS untuk halaman protect
```
