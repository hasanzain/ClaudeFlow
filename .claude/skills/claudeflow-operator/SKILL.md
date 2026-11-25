---
name: claudeflow-operator
description: Operator antarmuka manajemen akun, kanvas proyek, eksekusi job, dan pelacakan aset referensi ClaudeFlow untuk Google Flow
---

# ClaudeFlow Operator Skill

Skill ini bertindak sebagai antarmuka (CLI & Workflow Bridge) antara user/skill lain dengan mesin otomasi **ClaudeFlow** (`manage.py`, `daemon.py`, `client.py`).

Tugas utama skill ini:
1. **Manajemen Akun**: Memandu pendaftaran akun Google, login interaktif browser, pengecekan status limit/cooldown, dan rotasi.
2. **Manajemen Proyek**: Melihat, memilih, atau membuat kanvas proyek Google Flow baru.
3. **Eksekusi Generasi**: Menerima prompt mentah dari user atau skill cerita, menjalankan parameter (`--count`, `--aspect-ratio`, `--model`, `--ref`), dan menunggu hasil.
4. **Registri & Pelacakan Aset**: Menampilkan thumbnail hasil generasi kepada user, mencatat ASB ID terpilih untuk adegan berikutnya tanpa duplikasi aset di kanvas.

---

## 1. Panduan Tindakan (Action Commands)

Ketika user memanggil perintah atau meminta bantuan operasional, jalankan alur berikut menggunakan tool `Bash`:

### A. Cek Status Sistem & Akun
Jalankan pemeriksaan status akun terdaftar:
```bash
python manage.py list-accounts
```
- Jika belum ada akun: Pandu user dengan alur **Tambah Akun**.
- Jika ada akun `COOLDOWN`: Beritahukan estimasi waktu cooldown atau sarankan akun cadangan.

### B. Tambah & Login Akun Baru
Jika user ingin menambah akun Google baru:
1. Minta ID akun singkat (misal: `acc2`) dan email Google.
2. Daftarkan akun ke sistem:
   ```bash
   python manage.py add-account <id> <email>
   ```
3. Buka jendela browser interaktif agar user login sekali:
   ```bash
   python login_helper.py <id>
   ```
4. Setelah user menyelesaikan login di browser dan menekan Enter di terminal, verifikasi kembali status akun.

---

## 2. Manajemen Proyek Kanvas

Untuk menjaga kerapian aset antar-alur cerita:
1. Cek daftar proyek yang tersimpan:
   ```bash
   python manage.py list-projects
   ```
2. Pilihan proyek:
   - Gunakan `--project-name "<Nama Proyek>"` untuk mengarahkan prompt ke kanvas tertentu. Jika belum ada di Google Flow, sistem akan membuatnya secara otomatis.
   - Hasil generasi akan disimpan terstruktur di folder: `outputs/<Nama_Proyek>/`.

---

## 3. Eksekusi Generasi Media

Saat menerima permintaan generasi (dari user atau skill lain):

1. **Jalankan Daemon** (pastikan daemon berjalan di background jika belum aktif):
   - Jika belum berjalan di terminal terpisah, proses job dapat dipicu via daemon run/process.

2. **Buat Job**:
   Gunakan `python manage.py create-job` dengan parameter pendukung:
   - `--type`: `image` atau `video` (default: `image`)
   - `--aspect-ratio`: `16:9`, `4:3`, `1:1`, `3:4`, atau `9:16`
   - `--model`: Nama model (misal: `"Nano Banana 2.1"`, `"Veo 3.1 - Lite"`)
   - `--count`: `1`, `2`, `3`, atau `4` (variasi output batch)
   - `--project-name`: Nama proyek cerita
   - `--ref`: Satu atau lebih ASB ID gambar referensi kanvas terdahulu (anti-duplikasi)

   Contoh eksekusi:
   ```bash
   python manage.py create-job "<prompt_teks>" --count 3 --aspect-ratio 16:9 --project-name "Nama_Proyek"
   ```

3. **Monitor Selesai**:
   Pantau file `.done` atau `.failed` di direktori `jobs/<job_id>.done`.

---

## 4. Presentasi Hasil & Registri ASB ID

Setelah job selesai:
1. Baca metadata dari `jobs/<job_id>.done`.
2. Tampilkan file path gambar lokal (`outputs/...`) ke user.
3. Catat dan tampilkan pemetaan daftar aset:
   - **File**: `outputs/<project>/<job_id>_X.webp`
   - **ASB ID**: Hash CDN Google Flow (`ANqvLOZ...`)
4. Berikan panduan kepada user/skill pemanggil:
   *"Jika salah satu gambar ini ingin dijadikan referensi karakter/lingkungan untuk prompt berikutnya, gunakan ASB ID tersebut pada parameter `--ref`."*
