"""Run the approved collection checkpoint and audit it; never publish datasets."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pharmacy_assistant.collection_http import write_json

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "reports/collection_expansion_run.json"
REPORT = ROOT / "reports/collection_expansion_checkpoint.json"
ACTIVE_NAMES = ("ammps_medications_enriched.jsonl", "medicament_medications.jsonl",
                "saydalia_medications.jsonl", "pharmacies_rabat.jsonl", "pharmacy_duty_observations.jsonl")


def now():
    return datetime.now(timezone.utc).isoformat()


def active_hashes():
    return {name: hashlib.sha256((ROOT / "data/processed" / name).read_bytes()).hexdigest()
            for name in ACTIVE_NAMES}


def review_ready(report: dict, return_codes: dict, audit_return_code: int) -> bool:
    return (all(code == 0 for code in return_codes.values()) and audit_return_code == 0
            and report.get("all_collections_finished") is True
            and report.get("offline_integrity_passed") is True
            and bool(report.get("pharmacies", {}).get("retrieval_checks"))
            and all(c["passed"] for c in report["pharmacies"]["retrieval_checks"]))


def run(max_requests: int | None = None):
    # The OS releases this byte lock when the process exits, including crashes.
    lock_path = ROOT / ".runtime/collection_expansion.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        # Reading a byte already locked by another Windows process is denied.
        # Inspect the length without reading before attempting the actual lock.
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise SystemExit("A collection expansion runner is already active")
        else:
            import fcntl
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise SystemExit("A collection expansion runner is already active")

        state = {"status": "running", "started_at_utc": now(), "pid": os.getpid(),
                 "staging_only": True, "inference_requests": 0, "max_requests_per_source": max_requests,
                 "active_dataset_sha256_before": active_hashes(), "jobs": {}}
        write_json(STATUS, state)
        processes, streams, codes = {}, [], {}
        try:
            for name, module, options in [
                ("medicament", "expand_medications", ["--source", "medicament"]),
                ("saydalia", "expand_medications", ["--source", "saydalia"]),
                ("rabat", "expand_pharmacies", ["--city", "rabat"]),
            ]:
                command = [sys.executable, "-u", "-m", f"pharmacy_assistant.{module}", *options]
                if max_requests is not None:
                    command += ["--max-requests", str(max_requests)]
                log = ROOT / f"reports/collection_{name}.log"
                stream = log.open("a", encoding="utf-8")
                streams.append(stream)
                stream.write(f"\nCollection invocation {state['started_at_utc']}\n")
                stream.flush()
                process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                processes[name] = process
                state["jobs"][name] = {"pid": process.pid, "log": str(log.relative_to(ROOT)), "status": "running"}
                write_json(STATUS, state)
            while len(codes) < len(processes):
                for name, process in processes.items():
                    code = process.poll()
                    if name not in codes and code is not None:
                        codes[name] = code
                        state["jobs"][name].update(status="finished" if code == 0 else "incomplete", return_code=code)
                        state["updated_at_utc"] = now()
                        write_json(STATUS, state)
                if len(codes) < len(processes):
                    time.sleep(1)
            state["status"] = "auditing"
            write_json(STATUS, state)
            with (ROOT / "reports/collection_audit.log").open("a", encoding="utf-8") as audit_log:
                result = subprocess.run([sys.executable, "-u", "-m",
                    "pharmacy_assistant.review_collection_expansion", "--output", str(REPORT)],
                    cwd=ROOT, stdout=audit_log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            report = json.loads(REPORT.read_text(encoding="utf-8")) if result.returncode == 0 and REPORT.exists() else {}
            state["active_dataset_sha256_after"] = active_hashes()
            state["active_datasets_unchanged"] = state["active_dataset_sha256_before"] == state["active_dataset_sha256_after"]
            state["status"] = ("ready_for_review" if review_ready(report, codes, result.returncode)
                               and state["active_datasets_unchanged"] else "needs_attention")
            state.update(finished_at_utc=now(), audit_return_code=result.returncode,
                         report=str(REPORT.relative_to(ROOT)))
            write_json(STATUS, state)
        except BaseException as error:
            for process in processes.values():
                if process.poll() is None:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        process.terminate()
            for process in processes.values():
                process.wait()
            state.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "runner_failed",
                         error_type=type(error).__name__, finished_at_utc=now())
            write_json(STATUS, state)
            raise
        finally:
            for stream in streams:
                stream.close()
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-requests", type=int, default=None)
    args = parser.parse_args()
    if args.max_requests is not None and args.max_requests < 0:
        parser.error("Request budget must be nonnegative")
    state = run(args.max_requests)
    print(json.dumps({"status": state["status"], "report": state.get("report")}))
    raise SystemExit(0 if state["status"] == "ready_for_review" else 2)


if __name__ == "__main__":
    main()
