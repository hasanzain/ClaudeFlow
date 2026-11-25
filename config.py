from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = BASE_DIR / "jobs"
OUTPUTS_DIR = BASE_DIR / "outputs"
PROFILES_DIR = BASE_DIR / "profiles"
ACCOUNTS_FILE = BASE_DIR / "accounts.json"

DEFAULT_COOLDOWN_SECONDS = 12 * 3600  # 12 jam jika rate limited
POLL_INTERVAL_SECONDS = 3
FLOW_URL = "https://flow.google.com/"
