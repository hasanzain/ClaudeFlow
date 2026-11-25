from dataclasses import dataclass, asdict
import json
import time
from pathlib import Path
from config import ACCOUNTS_FILE, DEFAULT_COOLDOWN_SECONDS, PROFILES_DIR

STATUS_READY = "READY"
STATUS_BUSY = "BUSY"
STATUS_COOLDOWN = "COOLDOWN"
STATUS_EXHAUSTED = "EXHAUSTED"

@dataclass
class Account:
    id: str
    email: str
    profile_dir: str
    status: str = STATUS_READY
    cooldown_until: float = 0.0
    last_used: float = 0.0
    credits: int | None = None
    credits_updated_at: float = 0.0
    proxy: str | None = None
    cookies: dict | None = None  # Dict of cookie_name -> cookie_value

class AccountManager:
    def __init__(self, filepath: Path = ACCOUNTS_FILE):
        self.filepath = filepath
        self.accounts: list[Account] = []
        self.load()

    def load(self):
        if not self.filepath.exists():
            self.accounts = []
            return
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.accounts = [Account(**acc) for acc in data]

    def save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump([asdict(acc) for acc in self.accounts], f, indent=2)

    def add_account(self, acc_id: str, email: str, proxy: str | None = None) -> Account:
        profile_path = str(PROFILES_DIR / acc_id)
        Path(profile_path).mkdir(parents=True, exist_ok=True)
        acc = Account(id=acc_id, email=email, profile_dir=profile_path, proxy=proxy)
        self.accounts.append(acc)
        self.save()
        return acc

    def get_ready_account(self, required_credits: int | None = None) -> Account | None:
        now = time.time()
        # Reset accounts past cooldown
        for acc in self.accounts:
            if acc.status in (STATUS_COOLDOWN, STATUS_EXHAUSTED) and now >= acc.cooldown_until:
                acc.status = STATUS_READY
                acc.cooldown_until = 0.0

        # Filter akun yang siap
        ready = [acc for acc in self.accounts if acc.status == STATUS_READY]
        if not ready:
            return None

        # Jika required_credits diberikan, prioritaskan akun yang saldonya cukup (atau belum diketahui)
        if required_credits is not None:
            sufficient = [acc for acc in ready if acc.credits is None or acc.credits >= required_credits]
            if sufficient:
                ready = sufficient
            else:
                # Tidak ada akun dengan kredit cukup
                return None

        # Pick least recently used
        ready.sort(key=lambda a: a.last_used)
        chosen = ready[0]
        chosen.status = STATUS_BUSY
        chosen.last_used = now
        self.save()
        return chosen

    def update_credits(self, acc_id: str, credits: int):
        for acc in self.accounts:
            if acc.id == acc_id:
                acc.credits = credits
                acc.credits_updated_at = time.time()
                self.save()
                return

    def mark_ready(self, acc_id: str):
        for acc in self.accounts:
            if acc.id == acc_id:
                acc.status = STATUS_READY
                self.save()
                return

    def mark_cooldown(self, acc_id: str, duration: float = DEFAULT_COOLDOWN_SECONDS):
        for acc in self.accounts:
            if acc.id == acc_id:
                acc.status = STATUS_COOLDOWN
                acc.cooldown_until = time.time() + duration
                self.save()
                return

    def update_cookies(self, acc_id: str, cookies: dict):
        for acc in self.accounts:
            if acc.id == acc_id:
                acc.cookies = cookies
                self.save()
                return

if __name__ == "__main__":
    test_file = Path("test_accounts_tmp.json")
    mgr = AccountManager(test_file)
    a1 = mgr.add_account("acc1", "a1@gmail.com")
    a2 = mgr.add_account("acc2", "a2@gmail.com")

    selected = mgr.get_ready_account()
    assert selected.id == "acc1"
    assert selected.status == STATUS_BUSY

    mgr.mark_cooldown("acc1", 10)
    assert mgr.accounts[0].status == STATUS_COOLDOWN

    selected2 = mgr.get_ready_account()
    assert selected2.id == "acc2"

    test_file.unlink(missing_ok=True)
    print("AccountManager self-check passed.")
