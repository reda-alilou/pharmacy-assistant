# Improvement Step 1: quota control and resumable evaluation

**Current behavior:** at the user's request, the artificial message delay is
disabled by default (`INFERENCE_MIN_INTERVAL_SECONDS=0`). Disabling it also ignores
pending local-spacing timestamps from an earlier process. Provider-issued
cooldowns and evaluation budgets remain active. Positive local spacing is an
optional configuration choice. The 30-second policy described below is historical.

Implemented and verified offline. No live provider requests or demo servers were
started for this step. Stop here for user validation before the evaluation-data step.

## Shared request gate

The API and the interpretation evaluator use the same SQLite ledger at
`.runtime/inference_quota.sqlite3`. Factory-created Gemini, Groq and OpenCode
interpreters reserve a slot before every outbound attempt, including retries.
SQLite transactions serialize concurrent callers, including separate processes.
Restarting the application preserves spacing and provider cooldowns.

The default local spacing is **30 seconds between attempt starts**. This is a
conservative application policy, not a claim about the account's provider quota.
Interactive API requests return HTTP 429 with `Retry-After` when a slot is not
available; the existing UI displays the wait and offers a manual retry. The
budgeted evaluator waits for local spacing, up to 60 seconds per attempt, and
checkpoints if it cannot proceed. It does not sleep through provider cooldowns.

Configuration is optional; defaults apply without changing the existing `.env`:

```dotenv
INFERENCE_MIN_INTERVAL_SECONDS=30
INFERENCE_QUOTA_SCOPE=default
# Optional shared absolute path for another checkout on this machine:
# INFERENCE_QUOTA_DB=C:/absolute/path/to/inference_quota.sqlite3
```

The scope is `<scope>:<provider>:<model>`, independent of the API key. All local
clients using the same Google project/model must keep the same scope and database.
Separate machines/checkouts with different ledgers and external applications are
not coordinated. This is a local request-start limiter; it does not count input
tokens, discover account quotas, or guarantee avoidance of provider RPM/TPM/RPD limits.

## Provider quota responses

- HTTP 429 is never automatically retried, even with a short advertised delay.
- `Retry-After` and Gemini's typed `RetryInfo` set a shared cooldown. When neither
  is supplied, the local default is 60 seconds.
- A Gemini `QuotaFailure` containing a daily `quotaId` is classified as daily
  exhaustion. Requests stay blocked until the next midnight in Pacific time, or
  longer if the provider specifies a longer delay. If Pacific timezone data is
  unavailable, a conservative 24-hour cooldown is used instead.
- Unknown quota types remain generic rate-limit responses; no daily diagnosis is
  inferred from arbitrary provider message text.
- Other transient errors still allow at most one retry, subject to the same gate
  and evaluation budget. An interactive retry can instead return local spacing.
- Missing/corrupt/locked quota state prevents dispatch rather than bypassing the gate.

Google documents project-level quotas, their daily reset, and account-specific
limits in its [rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits).
This feature does not increase those limits or enable paid fallback.

## Budgeted interpretation evaluation

Start a new run with a maximum of four outbound attempts:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_interpretation --max-requests 4
```

Continue the same report later, authorizing at most four additional attempts:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_interpretation --resume --max-requests 4
```

The default report is `reports/interpretation_budgeted_gemini.json` for Gemini;
other providers have their own filename. `--output reports/another-run.json`
selects a separate run. Existing files cannot be silently overwritten. Historical
live reports remain unchanged.

The budget is **per command invocation**, and counts every reserved outbound
attempt, including failed responses and retries. Local spacing/cooldown rejections
do not consume it. A reservation committed immediately before a crash is retained
conservatively, even if dispatch or response completion is uncertain.

Each successful case is saved immediately. Provider errors leave the case pending;
budget/quota pauses do not count as completed cases. Resuming skips completed
cases, including completed cases whose predictions were incorrect. It does not
rerun them until they happen to pass. A completed report resumes with zero calls.

Resume requires matching model, output mode, output-token limit, prompt content,
prompt version, schema, examples and annotations. Changed evaluation inputs require
a new report. API keys and pacing settings are not fingerprinted. Reports are
locked against concurrent writers; OS locks release after interruption. Request
counters survive in SQLite, and a report cannot resume with missing or reduced
ledger counters. Keep the ledger alongside reports you intend to resume.

`--interval` adds an optional delay between cases; shared pacing still applies.
The default four-attempt run may complete fewer than four cases if retries occur.
Exit code 0 means completed/passed, 1 means incomplete or failed (including a normal
budget pause), 2 indicates an invalid configuration/report, and 130 is interruption.

The old chat and Streamlit smoke utilities still exercise the API's shared gate;
their flow checks do not use this evaluator's per-invocation budget. Use the
budgeted interpretation command for development extraction runs. No saved
interpretations are substituted into normal chat or a fresh live evaluation.

## Verify without spending quota

Show local pacing/cooldown state; no inference:

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.quota
```

The recorded CLI check used zero requests. Resume it with zero again to verify
the command without spending quota (a normal `paused_budget` exits with code 1):

```powershell
.\.venv\Scripts\python.exe -m pharmacy_assistant.evaluate_interpretation --resume --max-requests 0 --output reports/quota_zero_request_check.json
```

Run all offline regressions:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

**119 tests passed**, including 22 new quota/resume tests. Coverage includes
concurrent connections, a separate Python process, persistent cooldowns,
daily reset across daylight-saving changes, retry budgets, interruptions,
resume identity checks, missing ledgers and API `Retry-After` handling.

An [offline control-flow demonstration](../reports/quota_resume_offline_demo.json)
shows budgets of 1, then 2, then 0 producing 1, then 3, then 3 saved cases, with
no repeated completed cases. Its inference is explicitly mocked; it is not a
model-accuracy measurement. The [zero-request CLI report](../reports/quota_zero_request_check.json)
and [step checkpoint](../reports/improvement_step1_quota.json) record verification.

## Validation boundary

The existing demo was accepted by the user. This step changes quota handling,
not medication matching or conversational capability. The next step creates the
80-example evaluation dataset. Restart your existing demo yourself to load the
new gate; no services were started or stopped during this step. The new `.runtime`
ledger and report lock files are ignored by Git and contain no credentials or
patient messages.
