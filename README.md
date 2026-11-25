# ClaudeFlow

Automasi dan jembatan (bridge) Google Flow untuk orkestrasi generasi media AI (gambar & video) berbasis multi-akun, manajemen proyek kanvas, variasi output batch, dan referensi aset konsisten (zero-upload anti-duplikasi).

---

## Fitur Utama

- **Multi-Account Rotation & Pooling**: Manajemen akun Google Flow dengan isolasi sesi browser (`profiles/`), auto-cooldown saat limit, dan fallback siap pakai.
- **Project Canvas Management**: Buat proyek cerita baru atau gunakan proyek yang sudah ada untuk mengisolasi kanvas tiap alur cerita.
- **Batch Output Count (`x1` - `x4`)**: Pengaturan otomatis jumlah variasi output media per prompt melalui drawer `Setelan agen` Google Flow.
- **Zero-Upload Reference Consistency**: Menggunakan CDN hash Google ASB (`flow.google.com/asb/...`) untuk memilih aset kanvas langsung via modal `Tambahkan bahan` (`detail-add-to-prompt-btn`), menjaga konsistensi karakter antar-scene tanpa menduplikasi aset di kanvas.
- **Project-Based Output Organization**: Hasil generasi (`.webp` / `.mp4`) otomatis dirapikan ke subdirektori berdasarkan nama proyek (`outputs/<Project_Name>/...`).
- **File-Based Job Queue**: Antrean asinkron berbasis file JSON (`jobs/`), diproses oleh background worker daemon.

---

## Struktur Folder

```text
ClaudeFlow/
├── accounts.py          # Logika rotasi, status, cooldown akun Google
├── client.py            # Playwright automation driver untuk Google Flow
├── config.py            # Konfigurasi path & interval
├── daemon.py            # Queue worker pemroses job antrean
├── login_helper.py      # Script bantuan login interaktif akun Google
├── manage.py            # CLI management tool
├── project_manager.py   # Registry proyek lokal (projects.json)
├── requirements.txt     # Dependensi Python
└── .gitignore           # Filter session, credentials, dan output media
```

---

## Instalasi

1. **Clone repository:**
   ```bash
   git clone https://github.com/hasanzain/ClaudeFlow.git
   cd ClaudeFlow
   ```

2. **Install dependensi & browser Playwright:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

---

## Panduan Penggunaan

### 1. Registrasi & Login Akun Google

Tambahkan profil akun dan jalankan login interaktif sekali untuk menyimpan session:

```bash
# Tambah data akun
python manage.py add-account acc1 email@gmail.com

# Buka browser untuk login Google Flow
python login_helper.py acc1
```

### 2. Jalankan Queue Worker

Buka satu terminal untuk menjalankan background worker:

```bash
python manage.py run-worker
```

### 3. Buat Job Generasi Media

#### A. Generasi Dasar (Mode Interaktif Pilihan Proyek)
```bash
python manage.py create-job "Cyberpunk city with neon lights" --type image --interactive
```

#### B. Generasi Batch Multi-Output (1 s/d 4 Gambar Sekaligus)
```bash
python manage.py create-job "Futuristic samurai portrait" --aspect-ratio 16:9 --count 3 --project-name "Cyber City"
```

#### C. Generasi Adegan Konsisten dengan Referensi Aset
Gunakan `--ref` dengan ASB ID gambar dari adegan sebelumnya:
```bash
python manage.py create-job "Close-up warrior in neon balcony" --ref ANqvLOZYEF1Cs... --project-name "Cyber City"
```

---

## Lisensi

Private & Educational Research.
