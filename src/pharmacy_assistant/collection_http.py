"""Sequential, resumable public-source collection with provenance and backoff."""

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests


USER_AGENT = "pharmacy-assistant-academic/0.1"


class CollectionBudgetReached(RuntimeError):
    """An explicit network-request budget was reached; verified cache is free."""


def atomic_replace(temporary: Path, target: Path):
    """Retain the old checkpoint while Windows readers temporarily deny rename."""
    for attempt in range(12):
        try:
            temporary.replace(target)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 11:
                raise
            time.sleep(min(0.1 * 2 ** attempt, 1.0))


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    atomic_replace(temporary, path)


class SourceClient:
    def __init__(self, origin: str, directory: Path, delay: float = 2,
                 max_requests: int | None = None):
        self.origin = origin.rstrip("/")
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.last_request = None
        self.max_requests = max_requests
        self.request_count = 0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session.close()

    def get(self, url: str, name: str, params: dict | None = None) -> tuple[str, dict]:
        if urlparse(url).netloc != urlparse(self.origin).netloc or not url.startswith("https://"):
            raise ValueError("Collection URL must stay on the configured HTTPS source")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", name):
            raise ValueError("Unsafe cache name")
        html_path = self.directory / f"{name}.html"
        meta_path = self.directory / f"{name}.meta.json"
        safe_params = {key: value for key, value in (params or {}).items()
                       if key.casefold() not in {"api_key", "key", "token", "nonce"}}
        if html_path.exists() and meta_path.exists():
            content = html_path.read_bytes()
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if (meta["requested_url"] != url or meta.get("request_parameters", {}) != safe_params
                    or meta["sha256"] != hashlib.sha256(content).hexdigest()):
                raise ValueError(f"Invalid source cache: {name}")
            return content.decode("utf-8-sig"), meta

        for attempt in range(3):
            if self.max_requests is not None and self.request_count >= self.max_requests:
                raise CollectionBudgetReached("Network request budget reached; rerun to resume")
            if self.last_request is not None:
                time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            self.request_count += 1
            try:
                response = self.session.get(url, params=params, timeout=(10, 45))
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    retry = response.headers.get("Retry-After", "")
                    wait = float(retry) if retry.isdigit() else 2 ** (attempt + 1)
                    if wait > 60:
                        response.raise_for_status()
                    print(f"Retrying {name}: HTTP {response.status_code}, waiting {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                response.raise_for_status()
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))
                continue
            content = response.content
            text = content.decode("utf-8-sig")
            meta = {
                "requested_url": url, "source_url": redact_url(response.url),
                "request_parameters": safe_params,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "status_code": response.status_code, "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            temporary = html_path.with_suffix(".html.tmp")
            temporary.write_bytes(content)
            atomic_replace(temporary, html_path)
            write_json(meta_path, meta)
            return text, meta
        raise RuntimeError("Collection retry limit exceeded")


def redact_url(url: str) -> str:
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query)
             if key.casefold() not in {"api_key", "key", "token", "nonce"}]
    return urlunparse(parsed._replace(query=urlencode(query)))
