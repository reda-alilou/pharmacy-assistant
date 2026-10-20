"""Explicit isolated Docker verification. Never touches the user's demo volume.

The user invokes --run-isolated to authorize this temporary stack's lifecycle.
All test credentials are generated, inference egress is blocked, and the test
project/volume are removed afterward. No production-provider credentials are read.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import subprocess
import time
import uuid

import httpx

from pharmacy_assistant.compose_setup import write_environment
from pharmacy_assistant.paths import ROOT


def verify():
    project = "pharmacy-checkpoint4-test-" + uuid.uuid4().hex
    assert project.startswith("pharmacy-checkpoint4-test-") and len(project) == 58
    work = ROOT / ".runtime"
    work.mkdir(exist_ok=True)
    env_file, overlay = work / (project + ".env"), work / (project + ".yaml")
    diagnostic = work / (project + ".log")
    result = {"project": project, "verified_at_utc": datetime.now(timezone.utc).isoformat(),
              "live_inference_performed": False, "user_application_volume_modified": False, "checks": {}}
    credentials = [secrets.token_urlsafe(32) for _ in range(3)]
    values = dict(POSTGRES_DB="pharmacy_assistant", POSTGRES_USER="verification_admin", POSTGRES_PASSWORD=credentials[0],
        CORE_DB_PASSWORD=credentials[1], LANGUAGE_DB_PASSWORD=credentials[2], WEB_PORT="0",
        INFERENCE_PROVIDER="groq", GROQ_API_KEY="offline-verification-key", INFERENCE_QUOTA_SCOPE="verification")
    for key, role, password in (("MIGRATION_DATABASE_URL", "verification_admin", credentials[0]),
                              ("CORE_DATABASE_URL", "pharmacy_core", credentials[1]),
                              ("LANGUAGE_DATABASE_URL", "pharmacy_language", credentials[2])):
        values[key] = f"postgresql+psycopg://{role}:{password}@postgres:5432/pharmacy_assistant"
    write_environment(env_file, values)
    overlay.write_text("""services:
  language:
    networks: [inference-test]
  postgres:
    networks: [default, inference-test]
  core:
    networks: [default, inference-test]
networks:
  inference-test:
    internal: true
""", encoding="utf-8")
    command = ["docker", "compose", "-p", project, "--env-file", str(env_file),
               "-f", str(ROOT / "deploy/compose.yaml"), "-f", str(overlay)]
    stage = "configuration"

    def run(arguments, *, stdin=None, timeout=180):
        completed = subprocess.run(arguments, cwd=ROOT, input=stdin, text=True, encoding="utf-8",
            capture_output=True, timeout=timeout)
        with diagnostic.open("a", encoding="utf-8") as handle:
            handle.write(completed.stdout + completed.stderr)
        if completed.returncode:
            raise RuntimeError(f"Docker command failed during {stage}; see ignored diagnostic log.")
        return completed.stdout.strip()

    def compose(*args, **kwargs):
        return run(command + list(args), **kwargs)

    def inside(service, script, payload=None):
        text = compose("exec", "-T", service, "python", "-c", script,
                       stdin=json.dumps(payload) if payload is not None else None)
        return json.loads(text)

    def mark(name):
        result["checks"][name] = True
        print(f"Verified: {name}", flush=True)

    quota_script = """import json
from pharmacy_assistant.config import LanguageSettings
from pharmacy_assistant.language.quota import AttemptControl
c=AttemptControl.from_settings(LanguageSettings.from_env())
try:
    MODE
    print(json.dumps(c.store.status(c.scope)))
finally:
    c.close()
"""
    try:
        compose("--profile", "tools", "config", "--quiet")
        stage = "explicit fresh-database bootstrap"
        compose("up", "-d", "--wait", "postgres")
        for action in ("migrate", "grant", "import", "verify"):
            compose("--profile", "tools", "run", "--rm", "--no-deps", "database-setup", action)
        mark("explicit_migrations_import_and_round_trip")
        stage = "four-service startup"
        compose("up", "-d", "--wait", "--wait-timeout", "120")
        address = compose("port", "web", "8080")
        origin = "http://" + address
        with httpx.Client(base_url=origin, timeout=20, trust_env=False, follow_redirects=False) as client:
            def request(method, path, *, status=200, **kwargs):
                response = client.request(method, "/api" + path, **kwargs)
                assert response.status_code in (status if isinstance(status, tuple) else (status,)), (stage, path, response.status_code)
                return response.json() if response.content else None

            def wait_ready():
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    try:
                        if client.get("/api/ready").status_code == 200:
                            return
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.5)
                raise RuntimeError("Core did not become ready through web after restart.")

            health = request("GET", "/health")
            assert health["catalog_record_count"] == 9936 and health["storage_backend"] == "postgres"
            assert health["language_service_status"] == "available"
            assert client.get("/").status_code == 200 and client.get("/healthz").status_code == 200
            assert "/api/openapi.json" in client.get("/api/docs").text
            assert request("GET", "/openapi.json")["servers"] == [{"url": "/api"}]
            mark("web_static_page_and_core_forwarding")
            core_check = inside("core", """import importlib.util,json,os
assert importlib.util.find_spec('groq') is None
assert importlib.util.find_spec('pharmacy_assistant.language') is None
assert not any(k in os.environ for k in ['GROQ_API_KEY','LANGUAGE_DATABASE_URL','MIGRATION_DATABASE_URL'])
assert not os.path.exists('/app/.env') and not os.path.exists('/app/.runtime')
print(json.dumps({'ok':True}))""")
            assert core_check["ok"]
            language_check = inside("language", """import importlib.util,json,os
assert importlib.util.find_spec('pharmacy_assistant.core') is None
assert not any(k in os.environ for k in ['CORE_DATABASE_URL','MIGRATION_DATABASE_URL'])
assert not os.path.exists('/app/.env') and not os.path.exists('/app/.runtime')
print(json.dumps({'ok':True}))""")
            assert language_check["ok"]
            for service in ("postgres", "core", "language"):
                identifier = compose("ps", "-q", service)
                ports = json.loads(run(["docker", "inspect", "--format", "{{json .NetworkSettings.Ports}}", identifier]))
                assert not ports or all(binding is None for binding in ports.values())
            mark("independent_images_runtime_credentials_and_internal_ports")
            stage = "synthetic clarification seed"
            initial = request("POST", "/conversation")
            seed = (ROOT / "deploy/verification_seed.py").read_text(encoding="utf-8")
            state = inside("core", seed, {"session_id": initial["session_id"], "request_id": uuid.uuid4().hex})
            quota = inside("language", quota_script.replace("MODE", "c.store.reserve(c.scope, 0)"))
            assert quota["local_attempts_reserved"] == 1
            stage = "language outage"
            compose("stop", "language")
            failure = request("POST", "/chat", status=(503, 504), json={"text": "Et deux boites ?", "session_id": state["session_id"],
                "request_id": uuid.uuid4().hex})
            assert failure["detail"]["code"] in {"language_unavailable", "language_timeout"}
            restored = request("GET", "/conversation", headers={"Authorization": "Bearer " + state["session_id"]})
            assert restored["messages"][-1]["outcome"] == "failed"
            selected = request("POST", "/chat", json={"continuation_id": restored["response"]["continuation_id"],
                "selections": [{"mention_index": 0, "record_id": "9080"}]})
            assert not selected["inference_performed"] and "372.00 MAD" in selected["answer"]
            mark("language_outage_failed_message_restore_and_inference_free_selection")
            compose("up", "-d", "--wait", "--no-deps", "language")
            assert inside("language", quota_script.replace("MODE", "pass"))["local_attempts_reserved"] == 1
            stage = "core outage"
            compose("stop", "core")
            failure = request("GET", "/ready", status=503)
            assert failure["detail"]["code"] == "core_unavailable"
            assert client.get("/healthz").status_code == 200
            compose("up", "-d", "--wait", "--force-recreate", "--no-deps", "core")
            wait_ready()
            request("GET", "/conversation", headers={"Authorization": "Bearer " + selected["session_id"]})
            mark("core_outage_safe_gateway_error_and_dns_recovery")
            stage = "database outage"
            compose("stop", "postgres")
            failure = request("GET", "/ready", status=503)
            assert failure["detail"]["code"] == "storage_unavailable"
            compose("up", "-d", "--wait", "--force-recreate", "postgres")
            wait_ready()
            restored = request("GET", "/conversation", headers={"Authorization": "Bearer " + selected["session_id"]})
            assert any(message["outcome"] == "failed" for message in restored["messages"])
            assert request("GET", "/health")["catalog_record_count"] == 9936
            assert inside("language", quota_script.replace("MODE", "pass"))["local_attempts_reserved"] == 1
            mark("database_container_replacement_preserves_catalogue_transcript_and_quota")
            stage = "cooldown forwarding"
            inside("language", quota_script.replace("MODE", "c.store.cooldown(c.scope, 120, 'provider_rate_limited')"))
            response = client.post("/api/interpret", json={"text": "ABIP"})
            assert response.status_code == 429 and int(response.headers["retry-after"]) > 0
            assert response.json()["detail"]["code"] == "provider_rate_limited"
            assert inside("language", quota_script.replace("MODE", "pass"))["local_attempts_reserved"] == 1
            mark("proxy_preserves_cooldown_body_and_retry_after_without_inference")
            stage = "whole-stack replacement"
            compose("up", "-d", "--wait", "--force-recreate", "--wait-timeout", "120")
            address = compose("port", "web", "8080")
            client.base_url = "http://" + address
            wait_ready()
            request("GET", "/conversation", headers={"Authorization": "Bearer " + restored["session_id"]})
            assert request("GET", "/health")["catalog_record_count"] == 9936
            assert inside("language", quota_script.replace("MODE", "pass"))["local_attempts_reserved"] == 1
            mark("whole_stack_replacement_preserves_named_volume")
        result["passed"] = True
    except Exception as error:
        result.update(passed=False, failed_stage=stage, error_type=type(error).__name__,
                      diagnostic_log=str(diagnostic.relative_to(ROOT)))
        try:
            compose("logs", "--no-color", "--tail", "100")
        except Exception:
            pass  # Preserve the original failed stage even if logs are unavailable.
    finally:
        # Resource deletion is scoped to this freshly generated test project.
        assert project.startswith("pharmacy-checkpoint4-test-") and len(project) == 58
        try:
            compose("--profile", "tools", "down", "--volumes", "--remove-orphans")
            result["isolated_resources_removed"] = True
            env_file.unlink()
            overlay.unlink()
        except Exception:
            result["isolated_resources_removed"] = False
        output = ROOT / "reports/architecture_checkpoint4_container_validation.json"
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2), flush=True)
    return 0 if result.get("passed") and result.get("isolated_resources_removed") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-isolated", action="store_true",
        help="Explicitly start, stop, replace, and remove only a temporary test stack and its fresh volume")
    args = parser.parse_args()
    if not args.run_isolated:
        parser.error("Pass --run-isolated to explicitly control the temporary verification stack lifecycle.")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
