"""Launch the Streamlit app for local use, including the frozen Windows build."""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser

from tax_inventory.tesseract_runtime import configure_tesseract, resource_root

HOST = "127.0.0.1"
PORT = 8501
URL = f"http://{HOST}:{PORT}"


def _open_browser() -> None:
    time.sleep(1.8)
    webbrowser.open(URL)


def main() -> int:
    configure_tesseract()
    root = resource_root()
    os.chdir(root)
    app_path = root / "app.py"
    if not app_path.exists():
        print(f"Could not find app.py at {app_path}", file=sys.stderr)
        return 1

    print("Tax Document Inventory — local POC")
    print("Keep this window open while you use the app. Close it to quit.")
    print(f"Opening {URL} in your browser...")
    threading.Thread(target=_open_browser, daemon=True).start()

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        HOST,
        "--server.port",
        str(PORT),
        "--server.headless",
        "true",
        "--server.fileWatcherType",
        "none",
        "--global.developmentMode",
        "false",
        "--browser.gatherUsageStats",
        "false",
    ]
    return int(stcli.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
