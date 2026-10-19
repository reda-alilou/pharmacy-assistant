"""Start the local FastAPI + Streamlit demo and clean up owned processes."""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from pharmacy_assistant.demo_client import DemoClient, DemoError


ROOT = Path(__file__).resolve().parents[2]


def port_available(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def stop_owned(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-port", type=int, default=8501)
    args = parser.parse_args()
    if not all(1024 <= port <= 65535 for port in (args.api_port, args.ui_port)) or args.api_port == args.ui_port:
        parser.error("Choose two different ports between 1024 and 65535")
    if not port_available(args.ui_port):
        parser.error("The UI port is already occupied. Stop that service or choose --ui-port.")
    backend, frontend = None, None
    client = DemoClient(f"http://127.0.0.1:{args.api_port}")
    try:
        if port_available(args.api_port):
            backend = subprocess.Popen([
                sys.executable, "-m", "uvicorn", "pharmacy_assistant.api:app",
                "--host", "127.0.0.1", "--port", str(args.api_port),
            ], cwd=ROOT)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if backend.poll() is not None:
                    raise RuntimeError("FastAPI failed to start. See its output above.")
                try:
                    client.health()
                    break
                except DemoError:
                    time.sleep(0.3)
            else:
                raise RuntimeError("FastAPI startup timed out.")
        else:
            try:
                client.health()
            except DemoError:
                raise RuntimeError("The API port is occupied by an incompatible or unavailable service.") from None
            print("Reusing the running FastAPI service; it will be left running on exit.", flush=True)
        environment = dict(os.environ, PHARMACY_API_URL=client.base_url)
        frontend = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", str(ROOT / "src/pharmacy_assistant/demo.py"),
            "--server.address", "127.0.0.1", "--server.port", str(args.ui_port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false",
        ], cwd=ROOT, env=environment)
        print(f"Open http://127.0.0.1:{args.ui_port} | API: {client.base_url} | Ctrl+C to stop", flush=True)
        while frontend.poll() is None:
            if backend is not None and backend.poll() is not None:
                raise RuntimeError("FastAPI stopped. See its output above.")
            time.sleep(0.5)
        return frontend.returncode
    except KeyboardInterrupt:
        return 0
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        stop_owned(frontend)
        stop_owned(backend)


if __name__ == "__main__":
    raise SystemExit(main())
