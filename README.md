# ClaudeFlow

Automasi dan jembatan (bridge) Google Flow untuk orkestrasi generasi media AI (gambar & video) berbasis multi-akun, manajemen proyek kanvas, variasi output batch, dan referensi aset konsisten (zero-upload anti-duplikasi).

Dilengkapi dengan **MCP Server (`server.py`)** dan **Claude Skill (`claudeflow-operator`)** untuk integrasi langsung dengan Claude Desktop dan Claude Code.

---

## Fitur Utama

- **1-Click Installer (`install.py`)**: Setup otomatis virtual environment, instalasi Playwright browser, registrasi MCP Server ke konfigurasi Claude Desktop & Claude Code, serta pemasangan Skill global.
- **MCP Server Native (`server.py`)**: Tool siap pakai untuk `list_accounts`, `add_account`, `list_projects`, `generate_media`, dan `get_job_status`.
- **Operator Skill (`claudeflow-operator`)**: Antarmuka percakapan yang menjembatani user / skill naskah cerita lain dengan mesin eksekutor ClaudeFlow.
- **Multi-Account Rotation & Pooling**: Manajemen banyak akun Google Flow dengan isolasi sesi browser (`profiles/`), auto-cooldown saat limit, dan rotasi otomatis.
- **Batch Output Count (`x1` - `x4`)**: Pengaturan jumlah variasi output media per prompt melalui drawer `Setelan agen` Google Flow.
- **Zero-Upload Reference Consistency**: Menggunakan CDN hash Google ASB (`flow.google.com/asb/...`) untuk memilih aset kanvas langsung via modal `Tambahkan bahan` (`detail-add-to-prompt-btn`), menjaga konsistensi karakter antar-scene tanpa menduplikasi aset di kanvas.
- **Project-Based Output Organization**: Hasil generasi (`.webp` / `.mp4`) otomatis dirapikan ke subdirektori berdasarkan nama proyek (`outputs/<Project_Name>/...`).

---

## Struktur Folder

```text
ClaudeFlow/
├── accounts.py          # Logika rotasi, status, cooldown akun Google
├── client.py            # Playwright automation driver untuk Google Flow
├── config.py            # Konfigurasi path & interval
├── daemon.py            # Queue worker pemroses job antrean
├── install.py           # 1-Click Automated Installer (MCP & Skill)
├── login_helper.py      # Script bantuan login interaktif akun Google
├── manage.py            # CLI management tool
├── project_manager.py   # Registry proyek lokal (projects.json)
├── requirements.txt     # Dependensi Python (curl_cffi, playwright, mcp)
├── server.py            # FastMCP Server (MCP Tools untuk Claude)
├── .claude/skills/      # Skill bundled (claudeflow-operator)
└── .gitignore           # Filter session, credentials, dan output media
```

---

## Instalasi Cepat (1-Click Setup)

Jalankan skrip instalasi otomatis:

```bash
python install.py
```

Skrip ini akan otomatis:
1. Membuat Python virtual environment (`venv/`).
2. Menginstal semua dependensi (`requirements.txt`).
3. Menginstal Chromium Playwright.
4. Mendaftarkan MCP server `claudeflow` ke:
   - Claude Code (`~/.claude.json`)
   - Claude Desktop (`claude_desktop_config.json`)
5. Memasang skill `claudeflow-operator` ke folder global Claude (`~/.claude/skills/claudeflow-operator/`).

> **Catatan**: Setelah instalasi selesai, cukup restart aplikasi Claude Desktop atau buka sesi Claude Code baru.

---

## Dokumentasi MCP Server (`server.py`)

MCP Server menyediakan 5 tool yang dapat dipanggil langsung oleh Claude:

| Tool | Parameter | Deskripsi |
|---|---|---|
| `list_accounts()` | - | Menampilkan daftar akun Google terdaftar, status (READY/COOLDOWN), dan ketersediaan profil session. |
| `add_account(...)` | `account_id`, `email`, `proxy?` | Mendaftarkan akun Google baru ke pool ClaudeFlow. |
| `list_projects()` | - | Melihat daftar kanvas proyek Google Flow yang tersimpan di registry lokal. |
| `generate_media(...)` | `prompt`, `media_type?`, `aspect_ratio?`, `model?`, `count?`, `reference_asb_ids?`, `project_name?`, `wait_for_completion?` | Menjalankan generasi media di Google Flow. Mendukung batch count (1-4) dan referensi ASB ID anti-duplikasi. |
| `get_job_status(...)` | `job_id` | Mengecek status job antrean (`QUEUED`, `COMPLETED`, `FAILED`). |

---

## Dokumentasi Skill (`claudeflow-operator`)

Skill ini bertindak sebagai antarmuka operasional (Command & Control) antara pengguna / Skill Cerita dan mesin ClaudeFlow.

### Cara Memakai Skill

Ketik perintah skill langsung di chat Claude:
```text
/claudeflow-operator
```
Atau berikan instruksi percakapan biasa:
- *"Bantu saya tambah akun Google kedua untuk ClaudeFlow"*
- *"Cek status akun dan proyek yang ada di Google Flow"*
- *"Generate 3 variasi gambar cyber warrior di project Cyber City"*
- *"Gunakan gambar dari adegan 1 tadi sebagai referensi untuk adegan berikutnya"*

### Alur Kerja dengan Skill Cerita (Multi-Skill Pipeline)

```text
[ User / Story Writer Skill ]
       │  (Menghasilkan naskah adegan & deskripsi visual)
       ▼
[ Skill: claudeflow-operator ]
       │  (Memilih kanvas project, mengatur count 1..4, rasio, & ASB ID referensi)
       ▼
[ MCP: claudeflow (server.py) ]
       │  (Memasukkan job & memproses via Playwright Google Flow)
       ▼
[ Canvas Google Flow & outputs/<Project>/ ]
```

1. **Scene 1**: Story Skill meminta gambar pembuka. Operator memanggil `generate_media(count=3, project_name="SciFi_Story")`.
2. **Review & Seleksi**: Operator menampilkan hasil 3 gambar dan ASB ID-nya. User atau Story Skill memilih gambar terbaik (misal Gambar 2, ASB ID: `ANqvLOZ...`).
3. **Scene 2**: Story Skill meminta adegan kelanjutan. Operator memanggil `generate_media(prompt="...", reference_asb_ids=["ANqvLOZ..."], project_name="SciFi_Story")`.
4. **Hasil**: Karakter dan gaya visual tetap konsisten tanpa ada gambar duplikat di kanvas Google Flow.

---

## Penggunaan Manual via CLI (Opsional)

Jika ingin menjalankan tanpa MCP:

```bash
# 1. Tambah akun & login
python manage.py add-account acc1 email@gmail.com
python login_helper.py acc1

# 2. Jalankan antrean worker
python manage.py run-worker

# 3. Kirim job generasi
python manage.py create-job "Cyberpunk city street" --count 3 --project-name "Cyber City"
```

---

## Lisensi

Private & Educational Research.
