import time
import json
from pathlib import Path
from config import JOBS_DIR, OUTPUTS_DIR, POLL_INTERVAL_SECONDS
from accounts import AccountManager
from client import FlowRpcClient, AuthError, RateLimitError, RpcError, InsufficientCreditsError

class QueueDaemon:
    def __init__(self, account_mgr: AccountManager | None = None):
        self.account_mgr = account_mgr or AccountManager()
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    def process_once(self) -> int:
        """Proses satu putaran antrean jobs/*.json. Mengembalikan jumlah job yang diproses."""
        job_files = sorted(JOBS_DIR.glob("*.json"))
        processed_count = 0

        for job_file in job_files:
            # Lewati file hasil / internal
            if job_file.stem.endswith(".done") or job_file.stem.endswith(".failed"):
                continue

            done_file = JOBS_DIR / f"{job_file.stem}.done"
            failed_file = JOBS_DIR / f"{job_file.stem}.failed"
            if done_file.exists() or failed_file.exists():
                continue

            # Baca job
            try:
                with open(job_file, "r", encoding="utf-8") as f:
                    job_data = json.load(f)
            except Exception as e:
                failed_file.write_text(f"Invalid JSON: {e}", encoding="utf-8")
                continue

            job_id = job_data.get("id", job_file.stem)
            prompt = job_data.get("prompt", "")
            media_type = job_data.get("type", "image")
            aspect_ratio = job_data.get("aspect_ratio")
            model = job_data.get("model")
            count = job_data.get("count")
            reference_asb_ids = job_data.get("reference_asb_ids")
            project_name = job_data.get("project_name")
            project_id = job_data.get("project_id")
            ext = "mp4" if media_type == "video" else "webp"

            # Tentukan direktori output: subfolder berdasarkan nama project jika ada
            if project_name:
                import re
                safe_folder = re.sub(r'[\\/*?:"<>|]', '_', project_name).strip()
                target_dir = OUTPUTS_DIR / safe_folder
            else:
                target_dir = OUTPUTS_DIR

            target_dir.mkdir(parents=True, exist_ok=True)
            dest_file = target_dir / f"{job_id}.{ext}"

            # Coba proses dengan akun yang siap (auto-switch jika saldo kurang / limit)
            job_completed = False
            while True:
                account = self.account_mgr.get_ready_account()
                if not account:
                    # Tidak ada akun yang siap / saldo cukup saat ini
                    break

                print(f"[Queue] Processing job {job_id} using account {account.id}...")
                client = FlowRpcClient(
                    account_id=account.id,
                    profile_dir=account.profile_dir,
                    cookies=account.cookies,
                    proxy=account.proxy,
                    mock=(account.cookies is None)
                )

                try:
                    res = client.generate(
                        prompt=prompt,
                        media_type=media_type,
                        aspect_ratio=aspect_ratio,
                        model=model,
                        count=count,
                        reference_asb_ids=reference_asb_ids,
                        project_name=project_name,
                        project_id=project_id,
                        dest_file=dest_file
                    )
                    self.account_mgr.mark_ready(account.id)
                    saved_outputs = [str(p) for p in res.output_paths] if res.output_paths else [str(dest_file)]
                    done_file.write_text(json.dumps({
                        "id": job_id,
                        "status": "COMPLETED",
                        "account_used": account.id,
                        "output": str(saved_outputs[0]),
                        "outputs": saved_outputs,
                        "media_assets": res.media_assets,
                        "completed_at": time.time()
                    }, indent=2), encoding="utf-8")
                    print(f"[Queue] Job {job_id} COMPLETED -> {saved_outputs}")
                    processed_count += 1
                    job_completed = True
                    break

                except InsufficientCreditsError as e:
                    print(f"[Queue] Akun {account.id} saldo kredit tidak cukup: {e}. Mengalihkan ke akun berikutnya...")
                    # Set cooldown 12 jam (sampai jadwal reset harian)
                    self.account_mgr.mark_cooldown(account.id, duration=43200)
                    # Lanjut mencoba akun berikutnya di pool tanpa menunggu gagal
                    continue

                except RateLimitError as e:
                    print(f"[Queue] Account {account.id} rate limited: {e}. Cooldown activated.")
                    self.account_mgr.mark_cooldown(account.id)
                    # Lanjut mencoba akun berikutnya
                    continue

                except AuthError as e:
                    print(f"[Queue] Account {account.id} auth expired: {e}")
                    self.account_mgr.mark_cooldown(account.id, duration=86400)
                    continue

                except Exception as e:
                    print(f"[Queue] Job {job_id} failed: {e}")
                    self.account_mgr.mark_ready(account.id)
                    failed_file.write_text(json.dumps({"error": str(e)}, indent=2), encoding="utf-8")
                    break

        return processed_count

    def run(self):
        """Loop daemon utama."""
        print("[Queue] ClaudeFlow Daemon running. Menunggu job di folder jobs/...")
        while True:
            try:
                self.process_once()
                time.sleep(POLL_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                print("[Queue] Daemon stopped by user.")
                break

if __name__ == "__main__":
    from accounts import AccountManager
    test_mgr_file = Path("test_daemon_accounts.json")
    mgr = AccountManager(test_mgr_file)
    mgr.add_account("test_acc_daemon", "daemon@example.com")

    # Buat job uji coba
    test_job = JOBS_DIR / "job_selfcheck_tmp.json"
    test_job.write_text(json.dumps({
        "id": "job_selfcheck_tmp",
        "prompt": "a sunset over mountain",
        "type": "image"
    }), encoding="utf-8")

    daemon = QueueDaemon(mgr)
    count = daemon.process_once()
    assert count >= 1
    done_file = JOBS_DIR / "job_selfcheck_tmp.done"
    assert done_file.exists()

    # Bersihkan file uji coba
    test_job.unlink(missing_ok=True)
    done_file.unlink(missing_ok=True)
    (OUTPUTS_DIR / "job_selfcheck_tmp.png").unlink(missing_ok=True)
    test_mgr_file.unlink(missing_ok=True)
    print("QueueDaemon self-check passed.")
