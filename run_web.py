"""Launch AniScope AI (final design + analytics):  python run_web.py  → http://127.0.0.1:8000"""
import os
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("ANISCOPE_PORT", "8000"))
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run("server.api:app", host="127.0.0.1", port=port, log_level="info")
