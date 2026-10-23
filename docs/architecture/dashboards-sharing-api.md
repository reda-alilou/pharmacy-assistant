# Dashboards and collaboration — Checkpoint 4

Express exclusively owns this domain in `platform`; it never reads the private
Python schemas. React routes are `/tableaux`, `/tableaux/nouveau` and
`/tableaux/:id`. The existing assistant stays independent at `/assistant`.
Administration screens and dataset suspension remain Checkpoint 5.

## Permission model

| Access | Permitted behavior |
| --- | --- |
| Dataset owner | Import versions, edit/archive/delete subject to dependencies, explore, analyse, grant dataset access and authorize onward results |
| Dataset recipient | Explore every existing/future version and create personal analyses/dashboards; cannot modify the original, its versions or grants |
| Analysis/dashboard recipient | Read only the saved result configuration and execute its permitted queries; no implicit dataset exploration or arbitrary analytics API access |
| Administrator | Same ownership/grant boundaries here; no implicit access to another owner's content |

Grants are separate relational rows. Owners enter an existing active account's
exact email; no account-search directory is exposed. Sharing is explicit and
read-only; saving does not grant access. Dataset archive retains existing access
and pinned results. Disabled owners lose login/sessions, but active recipients'
explicit grants remain unless revoked. API requests check current sessions and
permissions, without a permission cache.

A configuration using another owner's data needs the original dataset owner's
authorization before sharing its results. That authorization names the saved
analysis/dashboard **and its exact revision**. The owner reviews named source
versions, columns, measures, base search/filters, chart settings and permitted
interactive scopes. Only that owner's source configuration is disclosed. Approval
permits the configuration owner to choose registered recipients of that revision;
it does not grant those recipients dataset access. Updating the configuration
removes old approvals and requires renewed authorization. Revocation of either
the source grant or onward authorization blocks dependent shared execution.
Shared dashboard access is refused if any required source authority is missing.

Copies require separate dataset access to **every** underlying source. They keep
immutable version/configuration references, get a new owner/resource ID, inherit
no grants/approvals, and require their own original-owner approval for onward
sharing. Revoking source access preserves a personal configuration but blocks
its execution. Modifying/deleting an original analysis does not alter a dashboard
widget's copied definition.

## HTTP routes

Gateway prefix `/platform-api`. All routes require an active account. Every
POST/PATCH/DELETE also requires exact Origin and session-bound X-CSRF-Token,
including read calculations. Strict schemas reject unknown properties. JSON is
limited to 128 KiB. There is no anonymous/public dashboard endpoint.

| Method and route | Contract |
| --- | --- |
| GET `/dashboards?page=1` | Own/shared titles, access, revision, widget count; 25/page and `hasMore` |
| GET `/dashboards/:id` | Authorized saved configuration and owner/shared access; no implicit calculation |
| POST `/dashboards` | `{title, description?, configuration}`; independently validates/calculates before transactional creation; 201 |
| PATCH `/dashboards/:id` | Same full body plus `revision`; owner-only, atomic replacement; stale revision 409 |
| DELETE `/dashboards/:id` | `{revision}`; owner-only; removes grants/dependencies, preserves datasets and analyses |
| POST `/dashboards/preview` | `{configuration, widgetId, values?}`; previews a draft using the caller's actual dataset rights |
| POST `/dashboards/:id/widgets/:widgetId/execute` | `{revision, values?}`; derives the query from the saved widget; rejects arbitrary definitions, columns or search |
| POST `/dashboards/:id/copy` | `{title}`; authorized resource plus actual dataset permissions required; new private dashboard, 201 |
| POST `/analyses/:id/execute` | `{revision, page?, pageSize?}`; executes the exact saved definition with current grant/onward checks |
| POST `/analyses/:id/copy` | `{title}`; new private analysis subject to all source permissions |
| GET `/{datasets,analyses,dashboards}/:id/shares?page=1` | Owner-only recipient list, 25/page, `hasMore`, source authorization states |
| POST `/{datasets,analyses,dashboards}/:id/shares` | `{email}`; owner-only, idempotent exact-recipient grant, 201 |
| DELETE `/{datasets,analyses,dashboards}/:id/shares/:grantId` | `{}`; owner-only immediate revocation, 204 |
| GET `/datasets/:id/onward?page=1` | Original owner only; human-readable dependent configurations, 10/page, `hasMore` |
| POST `/datasets/:id/onward` | `{kind: 'analysis'|'dashboard', resourceId, revision, allow}`; original owner only, stale review 409, 204 |

Dashboard calculations/saves/copies share a 300/account/15-minute throttle;
sharing creation has 30/account/15 minutes. Existing account and analytics limits
remain unchanged. At most two heavy calculations run per Express process across
analytics and dashboards. Browser widget requests use a two-slot queue and a
350 ms debounce. SQL retains 10-second statement/3-second lock limits; request
deadlines stay 60 seconds. Errors remove obsolete results and offer explicit retry.

## Saved configurations and mapped filters

`configuration` is `{algorithm: 'cp4-v1', widgets, filters}`. At most 20 widgets and
10 filters; IDs are UUIDs unique within their respective arrays. Array order is
the reading/layout order. Each widget retains an independent cp3-v1 aggregate,
histogram or scatter definition, title/description, width 4/6/12 grid columns,
height 3–12 grid units, and standard/horizontal/donut presentation. KPI, grouped
tables, horizontal rankings, temporal lines, histograms, pie/donut and scatter
use the existing engine and exact table alternatives. Advanced inspection results
remain in the analysis workspace; recommendations can create chart definitions
that can be saved and added to dashboards.

Filters name their label, kind (category/numeric/date/presence), explicit
`mappings: [{widgetId, column}]`, allowed categories or min/max, default values,
and `readerEditable`. Up to 20 mappings/filter. There is no name-based matching
across datasets. Column existence/type and all defaults are validated on save.
Changing source/version requires explicit validation; sources are never silently
replaced by a latest version. Base search/filters always remain in the query.

Execution `values` is an array of `{filterId, values: string[]}`. Category values
are OR within the configured allowed list; mappings and different filters combine
with AND. Numeric/date ranges contain lower and upper strings, with an empty
bound where allowed. Dates on timestamps include the entire last UTC day through
six fractional digits. Presence accepts `missing` or `present`. Unknown/duplicate
IDs, unauthorized categories, out-of-bounds/reversed ranges, invalid dates and
reader changes to fixed filters are rejected. At most 20 effective conditions
per widget. Empty/reset selections retain the full **authorized perimeter**;
they never remove allowed-category or configured min/max restrictions. Reader
adjustments stay local and never update the owner's saved defaults.

Read execution uses a repeatable-read snapshot. Writes lock the active account,
resource and sorted source datasets/grants, independently validate calculations,
and register relational source/deletion dependencies transactionally. Parallel
saves cannot overwrite one another; an approval racing an edit cannot authorize
the new revision. Original datasets remain protected from recipient mutations.

Analysis result sharing also supports advanced summaries. Without separate
dataset access to all sources, affected/original rows and comparison row details
are omitted; comparison schema metadata is limited to mapped columns. With
explicit dataset access, the recipient can inspect the selected rows. The saved
query still cannot be altered through the result-execution endpoint. Dashboard
responses include metadata only for referenced chart/filter columns.

## React behavior

Separate view/edit modes, explicit save/discard, dirty indicator, browser unload
warning and in-app navigation confirmation. Pending saves lock editing controls;
errors preserve drafts. Desktop pointer drag/reorder and resizing are complemented
by keyboard move controls and explicit width/height choices. Mobile uses a single
column in the same DOM order. Duplicating a widget retains its explicit filter
mappings; deleting one removes its mappings and any filters left without targets.
Changing a widget to another dataset removes that widget's interactive mappings,
even if column identifiers match. Remap explicitly or remove a filter left without
targets before saving. Changing versions within the same dataset retains settings
for explicit server validation.
Widget source, loading, empty/error state, omissions and exact tables remain visible.
Repeated chart/table landmarks have widget-specific accessible names.

The router uses the data-router API so the documented
[React Router navigation blocker](https://reactrouter.com/api/hooks/useBlocker)
can cover internal navigation. Drag handles use
[Pointer Events and capture/cancellation](https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events).
No chart/grid dependency was added. See [current evidence](../validation/platform-checkpoint-4.md).
