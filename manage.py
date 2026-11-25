import sys
import argparse
import json
import time
from pathlib import Path
from config import JOBS_DIR, OUTPUTS_DIR
from accounts import AccountManager
from daemon import QueueDaemon

def cmd_add_account(args):
    mgr = AccountManager()
    acc = mgr.add_account(args.id, args.email, args.proxy)
    print(f"Akun berhasil ditambahkan: {acc.id} ({acc.email})")

def cmd_list_accounts(args):
    mgr = AccountManager()
    if not mgr.accounts:
        print("Belum ada akun terdaftar. Gunakan: python manage.py add-account <id> <email>")
        return
    print(f"{'ID':<15} {'EMAIL':<30} {'STATUS':<12} {'HAS_COOKIES'}")
    print("-" * 65)
    for a in mgr.accounts:
        has_cookies = "YES" if a.cookies else "NO (Mock mode)"
        print(f"{a.id:<15} {a.email:<30} {a.status:<12} {has_cookies}")

def cmd_set_cookies(args):
    """Import cookies dari format JSON atau file."""
    mgr = AccountManager()
    cookie_file = Path(args.cookie_file)
    if not cookie_file.exists():
        print(f"File {cookie_file} tidak ditemukan.")
        return
    try:
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
            # Jika cookies dalam format list dari browser export [{name: ..., value: ...}]
            if isinstance(cookies, list):
                cookie_dict = {c["name"]: c["value"] for c in cookies if "name" in c and "value" in c}
            elif isinstance(cookies, dict):
                cookie_dict = cookies
            else:
                print("Format cookies tidak dikenali.")
                return

            mgr.update_cookies(args.id, cookie_dict)
            print(f"Cookies untuk akun {args.id} berhasil diperbarui ({len(cookie_dict)} cookies).")
    except Exception as e:
        print(f"Gagal memproses cookies: {e}")

from project_manager import ProjectManager

def cmd_create_job(args):
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = args.id or f"job_{int(time.time())}"
    job_path = JOBS_DIR / f"{job_id}.json"

    project_name = args.project_name
    project_id = args.project_id

    # Mode interaktif jika diminta atau jika parameter project tidak diberikan lewat CLI
    if args.interactive:
        pm = ProjectManager()
        saved = pm.list_projects()
        print("\n=== PENGATURAN PROJECT GOOGLE FLOW ===")
        print("1. Gunakan project yang sudah ada")
        print("2. Buat project baru untuk cerita ini")
        choice = input("Pilih opsi [1/2] (default 1): ").strip() or "1"

        if choice == "2":
            project_name = input("Masukkan nama project cerita baru: ").strip()
            if not project_name:
                project_name = f"Story_{int(time.time())}"
            print(f"-> Akan dibuat project baru: '{project_name}'")
        else:
            if saved:
                print("\nDaftar project tersimpan:")
                keys = list(saved.keys())
                for idx, k in enumerate(keys):
                    print(f"  [{idx+1}] {k} (ID: {saved[k].get('id', 'N/A')})")
                print("  [0] Project default kanvas")
                p_pick = input("Pilih nomor project [0-N] (default 0): ").strip() or "0"
                if p_pick.isdigit() and 1 <= int(p_pick) <= len(keys):
                    chosen = saved[keys[int(p_pick)-1]]
                    project_name = chosen["name"]
                    project_id = chosen.get("id")
                    print(f"-> Memilih project: '{project_name}'")
            else:
                print("Belum ada daftar project tersimpan. Gunakan project default kanvas atau buat baru.")

    job_data = {
        "id": job_id,
        "prompt": args.prompt,
        "type": args.type,
        "aspect_ratio": args.aspect_ratio,
        "model": args.model,
        "count": args.count,
        "reference_asb_ids": args.ref if args.ref else None,
        "project_name": project_name,
        "project_id": project_id,
        "created_at": time.time()
    }
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job_data, f, indent=2, ensure_ascii=False)
    print(f"Job dibuat: {job_path}")

def cmd_list_projects(args):
    pm = ProjectManager()
    projects = pm.list_projects()
    if not projects:
        print("Belum ada project tersimpan di projects.json.")
        return
    print(f"{'NAMA PROJECT':<35} {'PROJECT ID':<40} {'AKUN'}")
    print("-" * 85)
    for name, p in projects.items():
        print(f"{name:<35} {p.get('id', 'N/A'):<40} {p.get('account_id', 'N/A')}")

def cmd_run_worker(args):
    daemon = QueueDaemon()
    daemon.run()

def main():
    parser = argparse.ArgumentParser(description="ClaudeFlow CLI Management Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add-account
    p_add = subparsers.add_parser("add-account", help="Tambah akun Google baru")
    p_add.add_argument("id", help="ID unik akun (misal: acc1)")
    p_add.add_argument("email", help="Email Google")
    p_add.add_argument("--proxy", default=None, help="Proxy opsional (http://user:pass@host:port)")
    p_add.set_defaults(func=cmd_add_account)

    # list-accounts
    p_list = subparsers.add_parser("list-accounts", help="Daftar akun dan status")
    p_list.set_defaults(func=cmd_list_accounts)

    # set-cookies
    p_cookies = subparsers.add_parser("set-cookies", help="Set cookies untuk akun dari file JSON")
    p_cookies.add_argument("id", help="ID akun")
    p_cookies.add_argument("cookie_file", help="Path file cookies JSON")
    p_cookies.set_defaults(func=cmd_set_cookies)

    # create-job
    p_job = subparsers.add_parser("create-job", help="Kirim job prompt baru")
    p_job.add_argument("prompt", help="Teks prompt generasi")
    p_job.add_argument("--type", choices=["image", "video"], default="image", help="Tipe media (image/video)")
    p_job.add_argument("--aspect-ratio", choices=["16:9", "4:3", "1:1", "3:4", "9:16"], default=None, help="Rasio aspek")
    p_job.add_argument("--model", default=None, help="Nama model (misal: 'Nano Banana Pro', 'Veo 3.1 - Lite', dll)")
    p_job.add_argument("--count", type=int, choices=[1, 2, 3, 4], default=None, help="Jumlah variasi output media (1, 2, 3, 4)")
    p_job.add_argument("--ref", nargs="+", default=None, help="Satu atau lebih ASB ID gambar referensi dari library proyek")
    p_job.add_argument("--project-name", default=None, help="Nama project cerita baru atau yang ingin dipakai")
    p_job.add_argument("--project-id", default=None, help="ID project Flow spesifik (opsional)")
    p_job.add_argument("-i", "--interactive", action="store_true", help="Tanyakan pilihan project secara interaktif")
    p_job.add_argument("--id", default=None, help="Custom ID job")
    p_job.set_defaults(func=cmd_create_job)

    # list-projects
    p_proj = subparsers.add_parser("list-projects", help="Daftar project cerita yang tersimpan")
    p_proj.set_defaults(func=cmd_list_projects)

    # run-worker
    p_run = subparsers.add_parser("run-worker", help="Jalankan daemon antrean")
    p_run.set_defaults(func=cmd_run_worker)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
