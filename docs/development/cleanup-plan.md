# Reviewed repository cleanup

Approved scope: separate installable services, an organized React application,
PostgreSQL-only service startup, maintained import/evaluation tools, and an
isolated historical archive. This is a production-style structure for the local
challenge/learning project, not a claim of production readiness.

The saved starting point is commit
`b1bca1693c6b351edd95f40aed4ced7e19e78520` on `refactor/web-architecture`:
"Complete checkpoint 5: React chat and phone testing". Architecture checkpoints
1–5 passed user review. Cleanup checkpoints R1–R7 govern the remaining work;
the final validation and Streamlit retirement from D018 were included in this plan.

## Checkpoints and review gates

Complete one checkpoint, report its changes and evidence, and stop for user
review before the next. Stop earlier if a new architecture/retention decision
is needed. The instruction to begin R1 does not authorize R2–R7 automatically.

| Checkpoint | Deliverable | Review gate |
| --- | --- | --- |
| **R1: baseline and inventory** | Saved commit/contracts/data hashes, file destinations, dependency/path hazards, test migration map, finalized cleanup policy | Review the inventories; no application files moved or removed |
| **R2: backend packages** | Independently installable core/language, contracts/infrastructure packages, service settings/migrations/images | Independent builds/imports and existing HTTP behavior pass |
| **R3: frontend organization** | React under `apps/web`, feature/shared folders, updated fixtures/contracts/build paths | Browser checks pass; laptop and phone experience preserved |
| **R4: PostgreSQL-only runtime** | Required service-owned database settings; no file/SQLite runtime selection; explicit offline fixture injection | Startup fails clearly without PostgreSQL; offline tests still work |
| **R5: tools and coverage** | Organized operations/evaluation tools, new documented entry points, useful legacy scenarios ported | No useful coverage/tooling depends on compatibility modules or Streamlit |
| **R6: archive and removal** | Hash-verified archive, current documentation, obsolete code/config/tests/dependencies removed | Representative flows pass before UI retirement; every removal satisfies its gate |
| **R7: complete validation** | Independent builds, fresh/existing-revision setup, real isolated stack, backup/restore, final documentation | User reviews complete laptop/phone demo and handoff |

Temporary compatibility imports may remain between R2 and R5 to keep intermediate
checkpoints usable. They must not remain in the completed R6 tree. The inventory
is a destination/deletion plan, not authorization to delete files during R1.

## Final layout

```text
/
├── README.md
├── PROJECT_CONTEXT.md
├── DECISION_LOG.md
├── pyproject.toml                 # uv workspace coordination
├── uv.lock
├── .env.example                  # placeholders only
├── apps/web/
│   ├── package.json, package-lock.json, Dockerfile, Vite/TS configuration
│   ├── public/, contracts/
│   ├── src/
│   │   ├── app/                  # entry point, application shell and styles
│   │   ├── features/chat/        # components and temporary conversation state
│   │   ├── features/results/     # factual cards, sources and presentation
│   │   └── shared/               # api/, ui/, lib/
│   └── tests/                    # browser/, fixtures/, support/
├── services/
│   ├── core/
│   │   ├── pyproject.toml, Dockerfile, alembic.ini, migrations/
│   │   ├── src/pharmacy_core/
│   │   │   ├── api/              # lifecycle, dependencies, route groups
│   │   │   ├── conversation/     # orchestration, context, response models
│   │   │   ├── medications/      # catalogue, matching, normalization, pricing
│   │   │   ├── pharmacies/       # directory, models, normalization
│   │   │   ├── storage/postgres/ # owned tables, persistence and state codec
│   │   │   ├── clients/          # HTTP language-service client
│   │   │   └── config.py
│   │   └── tests/                # unit/, integration/
│   └── language/
│       ├── pyproject.toml, Dockerfile, alembic.ini, migrations/
│       ├── src/pharmacy_language/
│       │   ├── api/, extraction/, providers/, quota/, storage/postgres/
│       │   └── config.py
│       └── tests/                # unit/, integration/
├── packages/
│   ├── contracts/                # pyproject, src/pharmacy_contracts/, tests/
│   └── infrastructure/           # pyproject, src/pharmacy_infrastructure/, tests/
├── tools/
│   ├── operations/               # pyproject, Dockerfile, src/pharmacy_ops/, tests/
│   └── evaluation/               # pyproject, src/pharmacy_evaluation/, tests/
├── deploy/                       # Compose configurations and nginx/
├── data/
│   ├── imports/                  # the two authoritative JSONL import inputs
│   └── evaluation/               # active annotations/regression datasets
├── tests/                        # architecture/, integration/, support/
├── docs/                         # architecture/, development/, operations/,
│                                 # project/, validation/
├── archive/
│   ├── README.md, manifest.json
│   └── historical/               # preserves original relative subtrees
└── artifacts/                    # ignored generated reports/logs/builds
```

Keep normal repository dotfiles at the root. Create a directory only when it has
an actual responsibility/file. Keep `.runtime`, `.env`, `.venv`, caches and IDE
settings private/ignored; do not move or remove user-specific state as cleanup.

After R6, the user explicitly authorized additional local housekeeping: remove
verified obsolete ignored scratch/build/log/bytecode files, including nested
leftovers. Preserve private runtime/environment/editor state and current
validation evidence. Previously ignored raw downloads/staging data remain
preserved with hashes in ignored `archive/local/`, outside the public manifest.

## Ownership and interfaces

- Python members have their own dependency manifests and source/test packages,
  coordinated by one uv workspace and lockfile. Preserve dependency versions
  where compatible; do not introduce another package manager or test framework.
- Running services never import each other's implementation or access each
  other's tables. Core has no provider SDK or in-process inference fallback.
- Contracts own shared schemas/protocols/errors, not application logic or tables.
  Infrastructure owns connection/environment/path helpers, not business logic or
  service settings/secrets. Maintenance/evaluation tools may explicitly depend
  on service packages; they never become runtime dependencies of those services.
- Preserve endpoint URLs, request/response fields, error codes, continuation
  semantics, cooldown propagation, provider/model/prompt behavior and the accepted
  frontend. Health reports PostgreSQL after R4. Regenerate frontend types only
  from reviewed core schema changes; package moves alone must not change the wire
  contract.
- Preserve migration revision IDs, SQL semantics, Compose service/project names,
  named-volume identity, localhost defaults, phone/debug overlays and runtime
  credential locations. No schema reset, data re-import or credential regeneration
  is part of normal startup or package relocation.
- Replace old Python imports/commands without final compatibility shims.
  Operations provide entry points for database setup, backup, Compose setup/
  verification and contract export, retaining relevant existing arguments.
  Evaluation retains scoring, explicit live-request budgets, resume protection
  and evidence checks under the new package namespace.
- Replace fixed `parents[2]` assumptions with explicit project-root configuration
  or workspace discovery. Runtime images must work without the original checkout
  layout or ignored source caches.

## What stays, is archived, or is retired

Keep the active medication/pharmacy import files, evaluation annotations and
regression datasets. Keep migrations, grants, import/reconstruction validation,
quota import, backup/restore, contract export, fixture generation and isolated
verification. Supported provider adapters remain; historical duplicate modules
and launchers do not.

Archive raw snapshots, historical secondary datasets, reports, screenshots,
ledgers that are already public evidence, superseded drafts and walkthroughs.
Preserve their contents, embedded paths and hashes. Private ledgers/backups stay
untouched in their private locations. The future archive manifest maps original
paths to archived locations; current tools must resolve historical dependencies
through that mapping rather than rewriting old reports/freezes. New fingerprints
describe the reorganized workspace; old freezes do not silently become valid.

Retire collection/scraping, expansion/enrichment/activation, the Streamlit UI and
launcher, compatibility modules, unused CLI stub and overlapping old smoke
commands only after meaningful scenarios/helpers have been migrated. Remove
tests only when they exclusively exercise a retired capability. In particular,
preserve concurrency/cooldown/budget semantics against PostgreSQL, source/price
integrity through import/round-trip checks, and UI behavior through React tests.
Do not carry forward obsolete automatic request replay or combined secret-bearing
settings merely to preserve an old test assertion.

## Evidence and completion

R1 inventory: [file dispositions](../validation/cleanup-r1-inventory.json),
[per-method test map](../validation/cleanup-r1-test-map.json),
[dependency/path hazards](../validation/cleanup-r1-dependencies.json), and
[baseline](../validation/cleanup-r1-baseline.json). Read the
[R1 review guide](../validation/cleanup-r1.md) before R2. These are snapshots and
planned destinations, not claims that later work is implemented. R1 additions
under `docs/development/` and `docs/validation/` stay active and do not belong in
the old-document archive rule for files in the baseline commit.

Completion requires independent package/image checks; preserved matching,
multilingual, pricing, quotas and temporary-conversation scenarios; PostgreSQL
startup/failure checks; and complete comparison of 9,936 medication presentations
and 327 pharmacy records, including identity, prices, missing values, sources and
conflicts. Verify fresh/existing-revision migrations, repeated import, backup/
restore, whole-stack persistence, refresh, expiry, reset, failure recovery and
phone behavior. Preserve useful coverage rather than an arbitrary test count.

The user controls application and isolated Compose startup/shutdown. No hosted
inference, scraping, network changes, Git commits or pushes occur automatically.

## Completion — 2026-10-20

R1–R7 are complete. The final laptop review passed; the user explicitly waived
the final physical-phone check after suspecting restrictions on campus Wi-Fi.
The restriction was not confirmed, and no new physical-phone pass is claimed.
Automated mobile browser checks and the full isolated stack passed. Streamlit
and compatibility code are retired. See [R7 results](../validation/cleanup-r7.md)
for the complete evidence, clean-export scope and remaining submission work.
Changes remain uncommitted; publication is a separate user-controlled step.
