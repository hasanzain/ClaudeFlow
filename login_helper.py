import sys
import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from config import PROFILES_DIR, FLOW_URL
from accounts import AccountManager

def login_account(account_id: str, email: str = ""):
    profile_dir = PROFILES_DIR / account_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[Login Helper] Membuka browser untuk akun '{account_id}'...")
    print(f"[Login Helper] Profile path: {profile_dir}")
    print("[Login Helper] Silakan selesaikan login Google di browser yang terbuka.")

    with sync_playwright() as p:
        launch_args = {
            "user_data_dir": str(profile_dir),
            "headless": False,
            "args": ["--disable-blink-features=AutomationControlled"]
        }
        try:
            context = p.chromium.launch_persistent_context(**launch_args, channel="msedge")
        except Exception:
            context = p.chromium.launch_persistent_context(**launch_args)

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(FLOW_URL)

        print("\n" + "=" * 60)
        print("PETUNJUK:")
        print("1. Login ke akun Google Anda di jendela browser.")
        print("2. Pastikan halaman https://flow.google.com/ sudah terbuka dan aktif.")
        print("3. Kembali ke terminal ini dan tekan ENTER untuk menyimpan session.")
        print("=" * 60)

        input("\nTekan [ENTER] jika sudah selesai login...")

        # Ambil cookies dari browser
        cookies = context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}

        # Simpan ke AccountManager
        mgr = AccountManager()
        acc = next((a for a in mgr.accounts if a.id == account_id), None)
        if not acc:
            acc = mgr.add_account(account_id, email or f"{account_id}@google.com")

        mgr.update_cookies(account_id, cookie_dict)
        context.close()

        print(f"\n[Login Helper] Sukses! {len(cookie_dict)} cookies disimpan untuk akun '{account_id}'.")
        print(f"[Login Helper] Akun '{account_id}' kini berstatus READY untuk worker.")

def main():
    parser = argparse.ArgumentParser(description="Google Flow Interactive Login Helper")
    parser.add_argument("account_id", help="ID unik akun (misal: acc1, akun_utama)")
    parser.add_argument("--email", default="", help="Email akun Google (opsional)")
    args = parser.parse_args()

    login_account(args.account_id, args.email)

if __name__ == "__main__":
    main()
