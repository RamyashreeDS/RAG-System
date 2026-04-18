#!/usr/bin/env python3
"""Start the MediGuide local web server.

Usage:
  python run_app.py            # default: http://localhost:8080
  python run_app.py --port 3000
"""
import argparse
import subprocess
import sys
import webbrowser
import time
import threading

def open_browser(port: int, delay: float = 1.5):
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediGuide local server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    print(f"\n{'='*52}")
    print(f"  🏥  MediGuide — Your Discharge Companion")
    print(f"{'='*52}")
    print(f"  Local URL:  http://localhost:{args.port}")
    print(f"  Network:    http://0.0.0.0:{args.port}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*52}\n")

    if not args.no_browser:
        threading.Thread(target=open_browser, args=(args.port,), daemon=True).start()

    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.server:app",
        "--host", "0.0.0.0",
        "--port", str(args.port),
    ]
    if args.reload:
        cmd.append("--reload")

    subprocess.run(cmd)
