"""Runtime configuration from environment variables."""
import os
import re
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # worker/
REPO = ROOT.parent
ASSETS = Path(os.environ.get("STUDIO_ASSETS", REPO / "assets"))
FONTS = ASSETS / "style" / "fonts"
WORK = Path(os.environ.get("STUDIO_WORK", ROOT / "work"))
WORK.mkdir(parents=True, exist_ok=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://xkbgusqmdeocjwxaknjx.supabase.co").rstrip("/")
# keys only use these characters; anything else is a paste artefact (CR, bracketed-paste bytes, spaces)
SUPABASE_KEY = re.sub(r"[^A-Za-z0-9_.-]", "", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
MASTER_KEY = os.environ.get("MASTER_KEY", "")
WORKER_ID = os.environ.get("WORKER_ID", socket.gethostname())
CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "2"))      # parallel jobs
RENDER_PROCS = int(os.environ.get("RENDER_PROCS", str(max(1, (os.cpu_count() or 2) - 1))))
DRY_RUN = os.environ.get("STUDIO_DRY_RUN", "0") == "1"           # never call TikTok when set
