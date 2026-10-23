# Analytics and private saved configurations — Checkpoint 3

Express owns these routes and tables exclusively in `platform`. The frontend
provides `/analyses`, `/analyses/nouvelle` and `/analyses/:id`; the dataset's
Analysis tab links to a builder with an explicit immutable version. Protected
deep links retain their local path and query through login. The assistant remains
independent at `/assistant`. Dashboard construction and all sharing are future work.

## HTTP contract

Same-origin gateway prefix: `/platform-api`. All routes require an active account;
all POST/PATCH/DELETE requests also require exact Origin and X-CSRF-Token. JSON
is bounded to 128 KiB. Unknown properties and unsupported algorithm versions are
rejected. Administrators receive no implicit access to other owners' analyses or
dataset contents. Missing/foreign resources return 404.

| Method and Express route | Body / result |
| --- | --- |
| POST `/analytics/execute` | `{definition, page?, pageSize?}`; typed result and original definition, source/version descriptors and calculation conventions |
| POST `/analytics/templates` | A source object; four templates with a valid definition or a reason the required fields are unavailable |
| GET `/analyses?page=1` | Own saved configurations, 25/page, `hasMore` |
| GET `/analyses/:id` | Own complete configuration and metadata, no implicit execution |
| POST `/analyses` | `{title, description?, definition}`; validates and executes before transactional creation, returns `{analysis}`, 201 |
| PATCH `/analyses/:id` | Full save body plus current `revision`; atomic replacement and revision increment; stale revision returns 409 |
| DELETE `/analyses/:id` | `{revision}`; removes configuration and its dependency registrations, preserves datasets, 204 |

Execution and saving share a 60/account/15-minute throttle. At most two heavy
analytics operations run per Express process; an occupied service returns 429
with Retry-After: 1. Pools remain bounded; each SQL statement has the existing
10-second timeout and 3-second lock timeout. The existing gateway/client deadline
is 60 seconds. Queries are not retried automatically. An uncertain create/save
requires checking **Mes analyses** before explicitly repeating it.

Read calculations use a repeatable-read, read-only transaction. Both comparison
sources are authorized in that snapshot before results are returned. Save locks
the active account, then involved datasets in stable order; this prevents a
concurrent deletion from racing dependency creation. Ownership, column existence,
types, comparison keys and executable configuration are checked on the server.

## Definition and reproducibility

All definitions retain `algorithm: "cp3-v1"` and a source:

```json
{
  "datasetId": "<uuid>",
  "versionId": "<uuid>",
  "search": "",
  "filters": []
}
```

Filters/search use the [full-version dataset semantics](datasets-api.md), including
AND between filters and OR within selected values, canonical decimal point, ISO
dates and true/false. Changing an import does not change a source reference. A
dataset switch resets filters and calculation settings instead of inferring column
equivalence. A version switch is explicit and requires revalidation of the retained configuration;
absent/incompatible columns are rejected rather than silently remapped.

The builder runs only on explicit **Calculer** and clears old results whenever the
definition changes or a request fails. It disables all configuration/save controls
while processing. Saving is explicit and requires a current preview; the backend
independently verifies executability. Reopening restores settings and offers an
explicit recalculation, without presenting a cached result as current. Dirty state
is visible, with a browser unload warning; the full dashboard edit/navigation
guard and layout workflow remain Checkpoint 4. Failed saves preserve the draft.

## Aggregation and charts

`kind: "aggregate"` adds:

- `measures`: 1–8 `{operation, column, label}` objects. `rows` requires null column;
  present/missing/distinct accept any type. Sum/mean/median/min/max/q1/q3/
  stddev_sample/stddev_population require numeric columns.
- `groupBy`: 0–2 different `{column, interval}` objects. `interval` is value/day/
  month/year; temporal buckets require a date or datetime column.
- `order`: `{by: "measure"|"group", index, direction: "asc"|"desc"}`.
- `limit`: 1–200 groups (default 20). Counts, filtered-row denominator and group
  totals cover the full selection before limiting. Omitted groups are explicit;
  there is no fabricated Other category.
- `chart`: table/kpi/bar/line/pie. KPI requires no groups. Bars require groups;
  line requires exactly one explicit temporal group. A pie requires one grouping,
  additive row/present/missing counts, at most eight groups, and no omitted groups;
  distinct counts cannot be used as additive shares.

Every numerical result is transported as a decimal string or null. Contributing
present/missing counts accompany measures. Row-share percentages use all filtered
rows as their denominator. Missing grouping values remain an explicit group.
Stable sorting uses selected values and group keys, with nulls last. Dates/times
group in UTC using the canonical imported timestamp; date-only values retain their
calendar day. There is no inference of a time series from dataset observation
metadata or a single snapshot.

Chart style retains `xLabel`, `yLabel`, `unit`, `precision` (0–12) and `legend`.
SVG charts have text descriptions and exact table alternatives. Bar/line plots
show the first measure, explicitly identified; tables contain every measure.
Coordinates use numeric normalization on the server to avoid collapsing distinct
large decimals into one floating-point source value. Only bounded normalized
coordinates are converted for drawing; data/result strings stay intact. Temporal
curves space observations by UTC date, order chronologically and break at missing
measures. Missing dates stay in the result table. Plot omissions are declared.

`kind: "histogram"` adds a numeric `column`, `bins` (2–50, default 10) and style.
Bins have equal numeric width, lower bound included and upper excluded, except
the last upper bound is included. Constant data produce one closed interval;
no present values produce no intervals. Missing counts remain visible.

`kind: "scatter"` adds different numeric `x` and `y`, `pointLimit` (1–1000,
default 500) and style. Extents use all complete pairs; constant axes are centered.
Only the first bounded complete pairs in source order are returned, with exact
values and source lines. Paired/excluded/omitted counts are explicit; this is not
a representative random sample and implies no causation.

## Statistical conventions

- Sum uses PostgreSQL numeric arithmetic; no JavaScript floating-price arithmetic.
- Means and sample/population standard deviations cast inputs to numeric(80,24)
  to retain at least 24 fractional places in derived calculations even at large
  magnitudes. Nonterminating means and irrational deviations remain finite-precision
  numeric results, not mathematically exact real numbers. Source input is unchanged.
- Quartiles/median use Hyndman–Fan type 7: sort present values, set zero-based rank
  `(n−1)×p`, then linearly interpolate adjacent values using numeric arithmetic.
  Q1 uses p=.25, median .5, Q3 .75. This avoids PostgreSQL percentile_cont's double
  precision input coercion. Empty selections return null; one present value is its
  own quartile. Sample deviation uses n−1 and is null below two present values;
  population deviation uses n and is zero for a singleton.
- Missing cells are excluded from numerical statistics, never replaced with zero.
  Null is displayed as undefined/missing, separately from zero, false and empty text.
- Chart labels round separately using decimal-string/BigInt logic; exact returned
  strings remain in tables. Cross-product price averages are descriptive statistics,
  not therapeutic value or live offers.

New import profiles use the same higher-scale mean. Previously published immutable
profiles are retained without backfill; cp3-v1 analyses recalculate from their
unchanged typed cells using the documented conventions. A difference from an older
rounded profile is a calculation convention, not a change in source price.

## Four advanced features

**Missingness**, `kind: "missing"`: select 1–20 different columns, optional
`groupBy`, and `groupLimit` (1–200, default 50). Results contain global and group
present/missing counts/rates, column meters, grouped completeness and affected
rows with interpreted/original cells. A row is affected if any selected column is
missing. A rate's denominator is its group's row count; zero rows give null rate.
Every group contributes to global counts and inspection even if group details
are limited. Declared import missing markers are distinct from invalid input,
which would have prevented publication.

**Outliers**, `kind: "outliers"`: numeric `column`, optional `groupBy`, `factor`
as string `"1.5"` or `"3"`, fixed `minimumGroupSize: 4`, and groupLimit. Flags are strictly below
Q1−k×IQR or above Q3+k×IQR. Bounds themselves are not flagged. Groups with fewer
than four present values are not evaluated; their counts remain visible. Zero IQR
uses the same strict fence, so different tails may be flagged and constant groups
have no flags. Group thresholds are materialized once, and null-safe hashable
group joins avoid repeated array work on large fixtures. Paginated inspection
covers all flagged rows, with their own group thresholds, regardless of the group
detail limit. No value is corrected/deleted or declared clinically wrong.

**Recommendations**, `kind: "recommend"`: select 1–3 different columns. Filtered
types/cardinalities determine histogram/KPI for a number, bar counts for a
category, pie only for at most eight complete groups, means by category,
two-number scatter, and monthly time series only with at least two observed months.
Reasons and limitations are visible. Applying a recommendation creates a valid
editable definition; running/saving it is separate and uses the same engine.
No hosted model is used.

**Comparison**, `kind: "compare"`: adds a second complete `right` source and up
to ten explicit `{left, right}` column mappings. All column schemas and filtered
row counts are reported; mapped columns receive completeness/distinct and numeric
summary comparisons. Unmapped columns and type changes are explicit. Same names
do not create equivalence. Both sources may be separate datasets or any owned
immutable versions, with separate saved filters.

Optional `keys` contains up to three explicit pairs. Each filtered side must have
complete unique keys. Integer/decimal keys are compatible; text-to-number or date-
to-datetime coercion is rejected. When keys are used, mapped values must also have
compatible types. Exact interpreted values identify added/removed/changed/unchanged
rows; only selected mapped columns define a changed row. Original values remain
stored and source lines are included. Duplicates/missing keys reject the operation;
there is no fuzzy medication matching. Difference examples use the requested page
(25 default, maximum 100); totals cover all pairs. Without keys only schema and
statistics are compared, with no implied row identity.

## Pharmaceutical templates and persistence

Exact expected field names enable presentations by `form`, missing
`ppv_price_mad`, price histogram in declared MAD, and positive `recorded_conflicts`
by source where present. No field equivalence is guessed. Missing required fields
disable a template with an explanation. Templates preserve source filters and
add only their visible condition. They are ordinary executable definitions.

Migration `0003_analyses.sql` adds `analyses`, `analysis_sources` and analysis
activity actions/resource kind. It does not rewrite account/dataset/Python
revisions. Saved definitions are versioned JSON with relational version FKs.
Transactions maintain real `dataset_dependencies` registrations, including both
comparison sources. Dataset deletion is blocked until dependent configurations
are explicitly deleted or migrated. Metadata, source references and dependencies
change atomically with optimistic revisions; archive preserves executions.
No sharing, copies or dashboard grant is created by saving.

Explicit runtime grants permit these new owned tables and dependency registry
DML; published rows/columns/versions remain immutable and peer schemas forbidden.
Maintained backup/restore includes analyses, settings and source/dependency
relationships while retaining the existing staging/session/patient exclusions.

Technical references checked during implementation:
[PostgreSQL numeric aggregates](https://www.postgresql.org/docs/17/functions-aggregate.html),
[date/time semantics](https://www.postgresql.org/docs/17/functions-datetime.html), and
[R's primary type-7 quantile definition](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/quantile.html).
