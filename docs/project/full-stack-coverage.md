# Full Stack CdC — implemented technical coverage

Reviewed 2026-10-24 against [CdC_Application_Full_Stack.md](../../CdC_Application_Full_Stack.md)
and approved D021–D034 in [DECISION_LOG.md](../../DECISION_LOG.md). This covers the
new pharmaceutical analysis platform. The older `requirements-audit.md` concerns
the previous assistant challenge and is not evidence for this CdC.

The user narrowed CP6 to the actual project and technical documentation; no
presentation, submission package, rehearsal or demonstration script is prepared.
This map records implemented behavior and verification, not external submission
or group-contribution claims. API paths below are Express paths behind the
same-origin `/platform-api` gateway.

| CdC area | Implemented screen / workflow | API / technical contract | Evidence |
| --- | --- | --- | --- |
| §3 visitor | Introduction `/`, registration `/inscription`, login `/connexion`; separate visitor assistant `/assistant` | Public bootstrap plus `/auth/register`, `/auth/login`; visitor guards on protected routes | [CP1](../validation/platform-checkpoint-1.md), [installed CP6](../validation/platform-checkpoint-6-installed.json) |
| §3 analyst/profile | `/espace`, `/profil`; name/password updates and logout | Own-user GET/PATCH, `/auth/password`, `/auth/logout`; analyst-only public registration | [Account contract](../architecture/platform-api.md), [CP1](../validation/platform-checkpoint-1.md) |
| §4 dataset management | `/donnees`, `/donnees/importer`, guided preview/full validation/publication; title/description/category/source, archive and reviewed deletion | `/imports/*`, `/datasets/*`; private owner, immutable versions, atomic publication, bounded reports | [Dataset contract](../architecture/datasets-api.md), [CP2](../validation/platform-checkpoint-2.md) |
| §5 exploration | Version-pinned table, full-data search/filter/sort/pagination, original cells, dimensions/types/completeness | `/datasets/:id/versions/:version` and POST `.../rows`; server-side bounded queries | [Dataset contract](../architecture/datasets-api.md), [CP2](../validation/platform-checkpoint-2.md) |
| §6 analysis/business indicators | `/analyses/nouvelle` and dataset analysis entry; exact aggregates, distributions/rankings/time grouping and pharmaceutical templates with field prerequisites | `/analytics/execute`, `/analytics/templates`; source versions, conventions and missing denominators explicit | [Analytics contract](../architecture/analytics-api.md), [CP3](../validation/platform-checkpoint-3.md) |
| §7 visualizations | KPI, bar, line, histogram, pie and scatter with exact tables/text alternatives | Saved chart/style in analytical definitions; bounded normalized drawing coordinates preserve exact numeric results | [Analytics contract](../architecture/analytics-api.md), [CP3](../validation/platform-checkpoint-3.md) |
| §7 interactive dashboards | `/tableaux`, `/tableaux/nouveau`, `/tableaux/:id`; multiple widgets, accessible order/size controls and explicitly mapped filters | Dashboard save/preview/widget execution; filters apply only to mapped compatible sources | [Dashboard contract](../architecture/dashboards-sharing-api.md), [CP4](../validation/platform-checkpoint-4.md) |
| §8 saved analyses | `/analyses`, reopen/edit/delete; explicit save, immutable dataset/version references, filters/indicators/chart/algorithm retained | `/analyses/*`; source dependencies and optimistic revisions; no silent save or version substitution | [Analytics contract](../architecture/analytics-api.md), [CP3](../validation/platform-checkpoint-3.md) |
| §8 private/sharable results | Separate dataset, analysis and dashboard grants; read-only recipients, immediate revocation, original-owner onward approval and constrained copies | Resource `/shares`, dataset `/onward`, saved-result execution and copy endpoints; result access grants no raw-dataset access | [Sharing contract](../architecture/dashboards-sharing-api.md), [CP4](../validation/platform-checkpoint-4.md), [CP5](../validation/platform-checkpoint-5.md) |
| §9 at least three advanced data features | Four implemented: missing-value analysis, IQR outliers, editable chart recommendations, explicit dataset/version comparison | Versioned analytical definitions/algorithms executed by Express, including both source permission checks for comparisons | [Analytics conventions](../architecture/analytics-api.md), [CP3](../validation/platform-checkpoint-3.md) |
| §§3/10 administration | `/administration`: global indicators, users, dataset metadata/suspension, explicitly confirmed content inspection, filtered activity | `/admin/overview`, `/admin/users`, `/admin/datasets`, `/admin/activity`; last-admin safeguard, logged inspection and immediate invalidation | [Administration contract](../architecture/administration-api.md), [CP5](../validation/platform-checkpoint-5.md) |
| §11 React/Router/Hooks/REST and Node/Express | One TypeScript React app with routed workspaces, account hooks and REST; Express owns all platform domains, Python services retain assistant | Independent images and schema-restricted PostgreSQL roles, same-origin Nginx gateway, no Express access to Python private tables | [Architecture](../architecture/overview.md), [CP5](../validation/platform-checkpoint-5.md), [installed CP6](../validation/platform-checkpoint-6-installed.json) |
| §12 authentication/security/errors | Server-managed PostgreSQL sessions, scrypt passwords, HttpOnly cookie, CSRF, throttling, strict validation and safe failures; backend roles/ownership/current permissions | Account and domain guards, transaction locks, immediate disable/permission enforcement, private data and runtime least privilege | [Account contract](../architecture/platform-api.md), [Administration contract](../architecture/administration-api.md), [CP1](../validation/platform-checkpoint-1.md), [CP5](../validation/platform-checkpoint-5.md) |
| §13 technical source/database/architecture/API deliverables | Source and lockfiles, five explicit platform migrations plus unchanged Python histories, setup/upgrade/backup and API references | No startup migrations/imports; explicit admin provisioning; verified private backup/restore; source facts/nulls/prices/provenance preserved | [Fresh setup](../operations/setup.md), [Safe upgrade](../operations/local-upgrade.md), [CP6](../validation/platform-checkpoint-6.md) |

Optional JSON/Excel/API imports, public dashboards, correlation/forecasting/ML
are not implemented and are not required for the approved CSV/four-feature MVP.
They must not be presented as working functionality. Production hosting/TLS and
external submission/presentation are not claimed delivered by these local checks.

The final CP5 disposable production stack passed 20 named checks and all 18
assistant PostgreSQL tests, including complete dataset/analytics/dashboard/sharing/
admin browser workflows and backup/persistence regressions. CP6 independently
verified the real normal-volume backup, unchanged fingerprints for all 14 original
persistent assistant tables, all five migrations/runtime boundaries and 41 installed
assertions. Public desktop/mobile screens and deployed auth centering were also
checked against real Nginx/API. The user reports workspace/profile/administration
look correct and confirms the centering fix; other minor tweaks are deferred.
This distinguishes full isolated workflow evidence from basic manual installed
review. No exhaustive manual test of every normal-volume workflow is claimed.
The user-requested installed review is now complete within the agreed focused
scope: listed CSV/analytics checks, version pinning/comparison, dashboard mapped
filters/save/reopen, result-only sharing/revocation and suspension/restoration
passed by user reports/screenshots. The
[phased review record](../validation/platform-checkpoint-6-functional-review.md)
distinguishes these observations from detailed cases covered only by retained
isolated tests. Engineering implementation/verification is ready for checkpoint
review; minor tweaks are deferred and publication remains user-controlled.
