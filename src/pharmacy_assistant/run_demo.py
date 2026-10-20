"""Start language API, core API, and retained Streamlit; clean up owned processes."""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit

import httpx

from pharmacy_assistant.demo_client import DemoClient, DemoError
from pharmacy_assistant.config import CoreSettings
from pharmacy_assistant.contracts.language_service import LanguageHealth


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


def language_health(url):
    try:
        with httpx.Client(trust_env=False, timeout=2, follow_redirects=False) as client:
            response = client.get(url + "/health")
            response.raise_for_status()
            return LanguageHealth.model_validate_json(response.content)
    except (httpx.HTTPError, ValueError):
        raise RuntimeError("Language service is unavailable or incompatible. Check its URL and logs.") from None


def wait_for(process, check, label):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{label} failed to start. See its output above.")
        try:
            return check()
        except (DemoError, RuntimeError):
            time.sleep(0.3)
    raise RuntimeError(f"{label} startup timed out.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-port", type=int, default=8501)
    parser.add_argument("--language-port", type=int, default=None)
    args = parser.parse_args()
    config = CoreSettings.from_env()
    language_url = f"http://127.0.0.1:{args.language_port}" if args.language_port is not None else config.language_service_url
    origin = urlsplit(language_url)
    language_port = origin.port or (443 if origin.scheme == "https" else 80)
    ports = (args.api_port, args.ui_port, language_port)
    if not all(1024 <= port <= 65535 for port in ports) or len(set(ports)) != 3:
        parser.error("Choose three different ports between 1024 and 65535")
    if not port_available(args.ui_port):
        parser.error("The UI port is already occupied. Stop that service or choose --ui-port.")
    backend, frontend, language = None, None, None
    client = DemoClient(f"http://127.0.0.1:{args.api_port}")
    try:
        api_free = port_available(args.api_port)
        if not api_free:
            try:
                health = client.health()
            except DemoError:
                raise RuntimeError("The API port is occupied by an incompatible or unavailable service.") from None
            if health.storage_backend != config.storage_backend:
                raise RuntimeError("The running API uses a different storage backend. Stop it yourself or choose another --api-port.")
            if health.language_service_url != language_url:
                raise RuntimeError("The running API uses an older architecture or different language URL. Stop it yourself or choose another --api-port.")
        local_language = origin.scheme == "http" and origin.hostname in {"127.0.0.1", "localhost"}
        if local_language and port_available(language_port):
            environment = dict(os.environ)
            # Runtime settings also filter root .env by service ownership.
            environment.pop("CORE_DATABASE_URL", None)
            environment.pop("MIGRATION_DATABASE_URL", None)
            language = subprocess.Popen([
                sys.executable, "-m", "uvicorn", "pharmacy_assistant.language.api:app",
                "--host", "127.0.0.1", "--port", str(language_port),
            ], cwd=ROOT, env=environment)
            language_status = wait_for(language, lambda: language_health(language_url), "Language API")
        else:
            language_status = language_health(language_url)
            print("Reusing the running language service; it will be left running on exit.", flush=True)
        if language_status.storage_backend != config.storage_backend:
            raise RuntimeError("The language service uses a different storage backend. Stop it yourself or choose another --language-port.")
        if api_free:
            environment = dict(os.environ, LANGUAGE_SERVICE_URL=language_url)
            for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENCODE_API_KEY", "LANGUAGE_DATABASE_URL", "MIGRATION_DATABASE_URL"):
                environment.pop(key, None)
            backend = subprocess.Popen([
                sys.executable, "-m", "uvicorn", "pharmacy_assistant.api:app",
                "--host", "127.0.0.1", "--port", str(args.api_port),
            ], cwd=ROOT, env=environment)
            wait_for(backend, client.health, "Core API")
        else:
            print("Reusing the running FastAPI service; it will be left running on exit.", flush=True)
        environment = dict(os.environ, PHARMACY_API_URL=client.base_url)
        for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENCODE_API_KEY", "CORE_DATABASE_URL",
                    "LANGUAGE_DATABASE_URL", "MIGRATION_DATABASE_URL", "DATABASE_ENV_FILE"):
            environment.pop(key, None)
        frontend = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", str(ROOT / "src/pharmacy_assistant/demo.py"),
            "--server.address", "127.0.0.1", "--server.port", str(args.ui_port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false",
        ], cwd=ROOT, env=environment)
        print(f"Open http://127.0.0.1:{args.ui_port} | API: {client.base_url} | Ctrl+C to stop", flush=True)
        while frontend.poll() is None:
            if backend is not None and backend.poll() is not None:
                raise RuntimeError("FastAPI stopped. See its output above.")
            # Keep core/UI usable for inference-free choices if language exits.
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
        stop_owned(language)


if __name__ == "__main__":
    raise SystemExit(main())
