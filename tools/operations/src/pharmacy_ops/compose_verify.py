"""Explicit isolated Docker verification. Never touches the user's demo volume.

The user invokes --run-isolated to authorize this temporary stack's lifecycle.
All test credentials are generated, inference egress is blocked, and the test
project/volume are removed afterward. No production-provider credentials are read.
"""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

import httpx
from sqlalchemy.engine import make_url

from pharmacy_ops.compose_setup import write_environment
from pharmacy_infrastructure.paths import ROOT


def verify(*, frontend=False, output=None):
    project = "pharmacy-checkpoint4-test-" + uuid.uuid4().hex
    assert project.startswith("pharmacy-checkpoint4-test-") and len(project) == 58
    work = ROOT / ".runtime"
    work.mkdir(exist_ok=True)
    env_file, overlay = work / (project + ".env"), work / (project + ".yaml")
    host_env = work / (project + "-host.env")
    host_overlay = work / (project + "-host.yaml")
    diagnostic = work / (project + ".log")
    result = {"project": project, "verified_at_utc": datetime.now(timezone.utc).isoformat(),
              "live_inference_performed": False, "user_application_volume_modified": False, "checks": {}}
    credentials = [secrets.token_urlsafe(32) for _ in range(4)]
    values = dict(POSTGRES_DB="pharmacy_assistant", POSTGRES_USER="verification_admin", POSTGRES_PASSWORD=credentials[0],
        CORE_DB_PASSWORD=credentials[1], LANGUAGE_DB_PASSWORD=credentials[2], PLATFORM_DB_PASSWORD=credentials[3], WEB_PORT="0",
        INFERENCE_PROVIDER="groq", GROQ_API_KEY="offline-verification-key", INFERENCE_QUOTA_SCOPE="verification")
    for key, role, password in (("MIGRATION_DATABASE_URL", "verification_admin", credentials[0]),
                              ("CORE_DATABASE_URL", "pharmacy_core", credentials[1]),
                              ("LANGUAGE_DATABASE_URL", "pharmacy_language", credentials[2]),
                              ("PLATFORM_DATABASE_URL", "pharmacy_platform", credentials[3])):
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

    def run(arguments, *, stdin=None, timeout=180, env=None):
        completed = subprocess.run(arguments, cwd=ROOT, input=stdin, text=True, encoding="utf-8",
            capture_output=True, timeout=timeout, env=env)
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
from pharmacy_language.config import LanguageSettings
from pharmacy_language.quota.control import AttemptControl
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
        for action in ("migrate", "grant", "migrate", "grant"):
            compose("--profile", "tools", "run", "--rm", "--no-deps", "platform-setup", action)
        mark("explicit_platform_migrations_and_grants")
        stage = "five-service startup"
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
            assert client.get('/platform-api/ready').status_code == 200
            anonymous = client.get('/platform-api/auth/session')
            assert anonymous.status_code == 200 and anonymous.json()['user'] is None
            # The isolated web port is assigned dynamically; HTTPX deliberately
            # supplies the exact configured platform origin for this API probe.
            registered = client.post('/platform-api/auth/register',
                headers={'Origin': 'http://127.0.0.1:8080', 'X-CSRF-Token': anonymous.json()['csrfToken']},
                json={'email': 'isolated-platform@example.test', 'displayName': 'Isolated analyst',
                      'password': 'isolated-verification-password'})
            assert registered.status_code == 201 and registered.json()['user']['role'] == 'analyst'
            platform_user_id = registered.json()['user']['id']
            assert client.get('/platform-api/users/' + platform_user_id).status_code == 200
            assert client.get('/platform-api/admin/access').status_code == 403
            assert client.post('/platform-api/auth/logout', json={},
                               headers={'Origin': 'https://invalid.example'}).status_code == 403
            mark('platform_gateway_account_cookie_csrf_and_role_boundary')
            platform_headers = {'Origin': 'http://127.0.0.1:8080',
                                'X-CSRF-Token': registered.json()['csrfToken']}
            csv_text = 'code,amount,label,observed_at\n' + '\n'.join(
                f'{index:06d},{index},' + 'synthetic-private-dataset-row-' * 2 + ',2026-10-18T16:17:23.815325+00:00' for index in range(1000)) + '\n'
            assert len(csv_text.encode()) > 32768
            staged = client.post('/platform-api/imports', content=csv_text.encode(),
                headers={**platform_headers, 'Content-Type': 'application/octet-stream', 'X-Filename': 'isolated.csv'})
            assert staged.status_code == 201
            import_id = staged.json()['id']
            preview = client.get('/platform-api/imports/' + import_id)
            assert preview.status_code == 200 and preview.json()['rowCount'] == 1000
            configuration = preview.json()['configuration']
            validation = client.post('/platform-api/imports/' + import_id + '/validate', headers=platform_headers,
                json={'revision': preview.json()['revision'],
                      'options': {key: value for key, value in configuration.items() if key != 'columns'},
                      'columns': configuration['columns']})
            assert validation.status_code == 200 and validation.json()['validation']['valid']
            published = client.post('/platform-api/imports/' + import_id + '/publish', headers=platform_headers,
                json={'revision': validation.json()['revision'], 'metadata': {'title': 'Isolated dataset', 'source': 'Synthetic verification'}})
            assert published.status_code == 201
            dataset_path = '/platform-api/datasets/' + published.json()['datasetId'] + '/versions/' + published.json()['versionId']
            rows = client.post(dataset_path + '/rows', json={'pageSize': 25}, headers=platform_headers)
            assert rows.status_code == 200 and rows.json()['total'] == 1000 and len(rows.json()['rows']) == 25
            timestamp_column = next(column['id'] for column in configuration['columns'] if column['originalName'] == 'observed_at')
            assert rows.json()['rows'][0]['values'][timestamp_column] == '2026-10-18T16:17:23.815325Z'
            mark('platform_csv_gateway_validation_atomic_import_and_pagination')
            stage = 'platform analytics correctness and saved configuration'
            amount_column = next(column['id'] for column in configuration['columns'] if column['originalName'] == 'amount')
            code_column = next(column['id'] for column in configuration['columns'] if column['originalName'] == 'code')
            analytics_source = {'datasetId': published.json()['datasetId'], 'versionId': published.json()['versionId']}
            analytics_definition = {'kind': 'aggregate', 'source': analytics_source,
                'measures': [{'operation': operation, 'column': amount_column} for operation in ['sum', 'mean', 'median', 'q1', 'q3']]}
            calculation = client.post('/platform-api/analytics/execute', headers=platform_headers, json={'definition': analytics_definition})
            assert calculation.status_code == 200
            assert [Decimal(metric['value']) for metric in calculation.json()['rows'][0]['metrics']] == [Decimal('499500'), Decimal('499.5'), Decimal('499.5'), Decimal('249.75'), Decimal('749.25')]
            for definition in [
                {'kind': 'missing', 'source': analytics_source, 'columns': [amount_column]},
                {'kind': 'outliers', 'source': analytics_source, 'column': amount_column},
                {'kind': 'recommend', 'source': analytics_source, 'columns': [amount_column]},
                {'kind': 'compare', 'source': analytics_source, 'right': analytics_source,
                 'mappings': [{'left': amount_column, 'right': amount_column}], 'keys': [{'left': code_column, 'right': code_column}]},
            ]:
                feature_response = client.post('/platform-api/analytics/execute', headers=platform_headers, json={'definition': definition})
                assert feature_response.status_code == 200 and feature_response.json()['kind'] == definition['kind']
            saved_analysis = client.post('/platform-api/analyses', headers=platform_headers,
                json={'title': 'Isolated pinned analysis', 'definition': analytics_definition})
            assert saved_analysis.status_code == 201
            analysis_path = '/platform-api/analyses/' + saved_analysis.json()['analysis']['id']
            dependencies = client.get('/platform-api/datasets/' + analytics_source['datasetId'] + '/dependencies')
            assert dependencies.status_code == 200 and not dependencies.json()['canDelete']
            mark('platform_analytics_exact_statistics_four_features_and_saved_dependencies')
            core_check = inside("core", """import importlib.util,json,os
assert importlib.util.find_spec('groq') is None
assert importlib.util.find_spec('pharmacy_language') is None
assert not any(k in os.environ for k in ['GROQ_API_KEY','LANGUAGE_DATABASE_URL','MIGRATION_DATABASE_URL'])
assert not os.path.exists('/app/.env') and not os.path.exists('/app/.runtime')
print(json.dumps({'ok':True}))""")
            assert core_check["ok"]
            language_check = inside("language", """import importlib.util,json,os
assert importlib.util.find_spec('pharmacy_core') is None
assert not any(k in os.environ for k in ['CORE_DATABASE_URL','MIGRATION_DATABASE_URL'])
assert not os.path.exists('/app/.env') and not os.path.exists('/app/.runtime')
print(json.dumps({'ok':True}))""")
            assert language_check["ok"]
            for service in ("postgres", "core", "language", "platform"):
                identifier = compose("ps", "-q", service)
                ports = json.loads(run(["docker", "inspect", "--format", "{{json .NetworkSettings.Ports}}", identifier]))
                assert not ports or all(binding is None for binding in ports.values())
            mark("independent_images_runtime_credentials_and_internal_ports")
            stage = "synthetic clarification seed"
            initial = request("POST", "/conversation")
            seed = (ROOT / "tests/support/compose_seed.py").read_text(encoding="utf-8")
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
            assert client.get('/platform-api/users/' + platform_user_id).status_code == 200
            rows = client.post(dataset_path + '/rows', json={'pageSize': 25}, headers=platform_headers)
            assert rows.status_code == 200 and rows.json()['total'] == 1000
            persisted_analysis = client.get(analysis_path)
            assert persisted_analysis.status_code == 200
            assert persisted_analysis.json()['analysis']['definition']['source']['versionId'] == analytics_source['versionId']
            recalculated = client.post('/platform-api/analytics/execute', headers=platform_headers,
                json={'definition': persisted_analysis.json()['analysis']['definition']})
            assert recalculated.status_code == 200 and Decimal(recalculated.json()['rows'][0]['metrics'][1]['value']) == Decimal('499.5')
            mark("whole_stack_replacement_preserves_named_volume")
            if frontend:
                stage = "real frontend integration"
                fresh = request("POST", "/conversation")
                browser_state = inside("core", seed, {"session_id": fresh["session_id"], "request_id": uuid.uuid4().hex})
                inside("language", quota_script.replace("MODE", "c.store.cooldown(c.scope, 120, 'provider_rate_limited')"))
                environment = dict(os.environ, DEPLOYMENT_ORIGIN="http://" + address,
                                   DEPLOYMENT_TOKEN=browser_state["session_id"],
                                   DEPLOYMENT_SCREENSHOT_PATH=str(ROOT / "artifacts/compose" / (project + "-frontend.png")))
                (ROOT / "artifacts/compose").mkdir(parents=True, exist_ok=True)
                run(["node", str(ROOT / "apps/web/node_modules/@playwright/test/cli.js"), "test",
                     "tests/browser/deployment.spec.ts", "--config", str(ROOT / "apps/web/playwright.config.ts"),
                     "--reporter=list"], env=environment, timeout=120)
                assert inside("language", quota_script.replace("MODE", "pass"))["local_attempts_reserved"] == 1
                mark("real_frontend_restore_quota_selection_refresh_reset_without_inference")
                stage = "real frontend dataset lifecycle"
                # Browser writes must use the actual dynamically allocated origin.
                # Only this disposable test environment is amended; no credentials
                # or application configuration are regenerated or printed.
                with env_file.open('a', encoding='utf-8') as handle:
                    handle.write("PLATFORM_ORIGIN='http://" + address + "'\n")
                compose('up', '-d', '--wait', '--force-recreate', '--no-deps', 'platform')
                environment = dict(os.environ, DEPLOYMENT_ORIGIN='http://' + address)
                run(['node', str(ROOT / 'apps/web/node_modules/@playwright/test/cli.js'), 'test',
                     'tests/browser/real-datasets.spec.ts', '--config', str(ROOT / 'apps/web/playwright.datasets.config.ts'),
                     '--reporter=list'], env=environment, timeout=240)
                mark('real_frontend_csv_versions_ownership_archive_delete_and_validation_recovery')
                stage = 'real frontend analytics and advanced features'
                run(['node', str(ROOT / 'apps/web/node_modules/@playwright/test/cli.js'), 'test',
                     'tests/browser/real-analytics.spec.ts', '--config', str(ROOT / 'apps/web/playwright.analytics.config.ts'),
                     '--reporter=list'], env=environment, timeout=420)
                mark('real_frontend_analytics_four_features_saved_versions_charts_and_permissions')
        # Only the temporary verification database is exposed, on a random
        # localhost port, after the normal internal-port checks have passed.
        stage = "owned PostgreSQL concurrency, backup and evaluation checks"
        host_overlay.write_text(json.dumps({"services":{"postgres":{"ports":[{
            "target":5432,"published":"0","host_ip":"127.0.0.1","protocol":"tcp"}]}}}),encoding="utf-8")
        host_command = command + ["-f",str(host_overlay)]
        run(host_command + ["up","-d","--no-deps","--wait","postgres"])
        binding = run(host_command + ["port","postgres","5432"])
        host, port = binding.rsplit(":",1)
        assert host == "127.0.0.1" and port.isdecimal()
        host_values = dict(values)
        for key in ("MIGRATION_DATABASE_URL","CORE_DATABASE_URL","LANGUAGE_DATABASE_URL"):
            host_values[key] = make_url(values[key]).set(host=host,port=int(port)).render_as_string(hide_password=False)
        write_environment(host_env,host_values)
        environment = dict(os.environ,PHARMACY_ISOLATED_TEST_PROJECT=project,
                           PHARMACY_PG_TEST_ENV=str(host_env),PYTHONPATH=str(ROOT))
        postgres = json.loads(run([sys.executable,"-m","pharmacy_ops.postgres_checks"],env=environment,timeout=300))
        assert postgres["passed"] and postgres["skipped"] == 0
        result["postgres_tests"] = postgres
        mark("postgres_concurrency_backup_and_evaluation_resume_without_inference")
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
            for temporary in (env_file,overlay,host_env,host_overlay):
                temporary.unlink(missing_ok=True)
        except Exception:
            result["isolated_resources_removed"] = False
        report_path = ROOT / output if output else ROOT / "artifacts/compose" / (project + ".json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2), flush=True)
    return 0 if result.get("passed") and result.get("isolated_resources_removed") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-isolated", action="store_true",
        help="Explicitly start, stop, replace, and remove only a temporary test stack and its fresh volume")
    parser.add_argument("--frontend", action="store_true", help="Also verify the real React interface against the isolated APIs/database")
    parser.add_argument("--output", type=Path, help="Write a new verification report here; defaults to ignored artifacts/compose (preserves historical checkpoint reports)")
    args = parser.parse_args()
    if not args.run_isolated:
        parser.error("Pass --run-isolated to explicitly control the temporary verification stack lifecycle.")
    return verify(frontend=args.frontend, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
