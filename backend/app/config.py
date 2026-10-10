import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

def _load_dotenv():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

_load_dotenv()

HTTP_HOST = os.environ.get("FROSTGUARD_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("FROSTGUARD_PORT", "8000"))
TCP_HOST = os.environ.get("FROSTGUARD_TCP_HOST", "0.0.0.0")
TCP_PORT = int(os.environ.get("FROSTGUARD_TCP_PORT", "8081"))
DB_PATH = Path(os.environ.get("FROSTGUARD_DB", str(BASE_DIR / "backend" / "frostguard.db")))
FRONTEND_DIR = BASE_DIR / "frontend"
DEVICE_OFFLINE_AFTER = int(os.environ.get("FROSTGUARD_OFFLINE_AFTER", "10"))
