# Phase 1 — editing safety and feedback

Status: implementation complete, awaiting user acceptance. Branch: `feature/ui-ux-redesign`. Direction B — Traverse with the agreed green V2 refinements is the approved foundation. Phase 0 is closed; no V2 prototype was created. **Phase 2 has not started.**

## Result

Core editors now warn before ordinary route changes, destructive local tabs/resets, Back/Forward and logout can discard unsaved input. Stay and Escape keep the current editor mounted with its values intact. Explicit discard permits the requested action. Native browser reload/close warnings are registered only while edits or operations require protection; supported reload cancel/accept behavior was exercised in Edge.

There is no persisted draft store, automatic background save, new endpoint or recovery claim after accepted loss. The assistant's existing temporary accepted-message restoration is unchanged. Confirmation uses one native accessible dialog with initial focus on Stay, keyboard containment, cancellation and focus return. Its green actions follow Traverse; the surrounding screen compositions retain their existing layout until their respective phases.

## Routes and implementation decisions

| Surface | Changes and preserved behavior |
| --- | --- |
| `/analyses/nouvelle`, `/analyses/:id` | Guard complete in-memory definitions, source selections, title and description. Calculate does not clear unsaved state. Failed saves retain current values/results. Confirmed creates preserve success feedback across the saved-resource redirect. Existing algorithms, execution requests, source pins, save prerequisites and revisions remain unchanged. |
| Shared analysis | The original remains read-only. Guard an entered private-copy title and pending requests; copy permissions and request contract remain server-controlled. |
| `/donnees/:id` | Guard metadata exits and destructive local-view changes. Clone query parameters before proposing a route change so Stay cannot mutate the active view indirectly. Use the validated PATCH response to update metadata/revision without unmounting the editor; success feedback survives. Explicit reset uses the same confirmation. Dependency/title deletion checks and archive behavior remain. |
| `/donnees/importer`, `/donnees/imports/:id` | Guard selected files, interpretation changes, unsent metadata and pending operations. Accepted validation updates the receipt/configuration baseline but never pretends unsent metadata was published. Publication/cancellation remain explicit. Success handoff is not blocked by a false warning. Existing receipt expiry, validation and atomic-publication contracts remain. |
| `/tableaux/nouveau`, `/tableaux/:id` | Replace the separate native-confirm guard with the shared dialog. Preserve view/edit/save/discard and revision behavior. Reader filters are not owner edits; a private-copy title is protected independently. Confirmed creates/copies carry only success feedback across navigation. |
| `/profil` and logout | Track name/password input in current-editor state and disable edits during submission. Saving a name does not clear an unsent password. Password change warns if it would destroy a separate unsaved name and preserves session invalidation/relogin feedback. Logout does not send its request until discard is accepted. A failed logout keeps the editor and re-arms protection. |
| `/assistant` | Protect an unsent question and warn for pending work when leaving. No conversation state machine, matching, prices, clinical limitations, retry, token storage or provider behavior changed. Composition and duplicate-medication cleanup remain Phase 6. |

The shared guard has no network or storage code. A narrowly scoped navigation bypass covers confirmed save/publication/deletion handoffs, not future arbitrary exits. Late saves cannot redirect a user who already discarded navigation. A stale profile response cannot restore an expired account session. Protected content remounts when the authenticated account identity changes, preventing a different account from inheriting the former editor's input.

Conflicts and unknown mutation outcomes distinguish uncertainty from ordinary validation errors, retain current input, and offer inspection in a separate tab using existing routes. No mutation is replayed automatically. Server revision protection is retained; there is no automatic merge or overwrite. After a pending operation completes while confirmation is open, the dialog reports that the operation ended instead of claiming nonexistent unsaved work or a continuing request.

Save feedback crossing a create redirect uses a consumed navigation-state message only. It contains no editor input or definition and is not draft persistence. Metadata success lives in the still-mounted editor; relevant edits clear it.

## Verification

Final run: **54 passed, 0 skipped, 0 unexpected failures, 0 flaky**. See [browser-tests.json](browser-tests.json).

```powershell
# Run from apps/web; installed dependencies only.
npm run build
npm run lint
node node_modules/@playwright/test/cli.js test --config playwright.editing.config.ts
```

The dedicated config starts/reuses a frontend-only Vite server at loopback port 5190 and uses installed headless Microsoft Edge. Test helpers intercept platform and assistant calls locally. They do not start a backend, create a test database, contact hosted inference or mutate private resources. Traces are disabled. Fixture identities and submitted values are synthetic; CP6 data is the existing functional-review fixture.

Coverage includes existing account/dataset/assistant regressions plus editing-specific tests for:

- Stay, Escape, deliberate discard, focus return, ordinary links and Back/Forward.
- Metadata tabs surviving cancellation and a later session refresh; stable successful-save feedback.
- Failed 503, conflict 409 and unknown/network outcomes retaining input with no automatic replay.
- File selection, validation retaining unsent metadata, explicit publication and guarded cancellation.
- Analysis Calculate versus Save, pinned source references and successful create redirects.
- Dashboard editing, create/discard, conflicts and private-copy input.
- Logout cancellation, failed logout, forced expiry, changed accounts and late profile responses.
- Pending mutation departure without a late navigation hijack; truthful dialog updates when the request finishes.
- Native reload cancellation preserving input and accepted reload returning to saved state without a recovery store.
- Mobile assistant unsent input, dialog accessibility, 320px bounds, 200% root-text sizing and keyboard operation.

Build passes. Lint exits successfully with only the two existing Fast Refresh warnings in `shared/ui/button.tsx` and `shared/ui/badge.tsx`; no new lint warning remains. Targeted Impeccable source checks found no deterministic issues, but are regex-only checks, not rendered accessibility certification. Axe checks on the tested open-dialog desktop/mobile states passed.

Rendered React application evidence, visually inspected:

- [Analysis confirmation — 1440×1000](screenshots/analysis-warning-desktop.png).
- [Assistant confirmation — 390×844](screenshots/assistant-warning-mobile.png).
- [Metadata confirmation — 320×720](screenshots/metadata-warning-320.png).

These are current React screens with intercepted responses, not standalone visual prototypes. Review-only fixtures do not establish actual backend authorization or analytical execution.

## Limits and remaining gates

No known failing frontend check remains in Phase 1. Real-backend integration suites were not run: the existing real suites start backend processes/create test databases, which would exceed the standing lifecycle restriction. Actual backend permission/revocation and calculation correctness were not newly certified. Backend code/contracts, domain algorithms, package manifests and the PRODUCT/DESIGN baseline are unchanged; see [scope-verification.json](scope-verification.json).

Native reload was tested in headless Edge; browser-close/crash behavior, Firefox/Safari, physical mobile keyboards and real screen-reader use remain unverified. Crash recovery is explicitly not offered. 200% root-text sizing is a targeted dialog reflow check, not a complete application zoom audit.

The larger Traverse navigation, chart/dashboard density, source presentation and assistant composition remain in their assigned Phases 2–6. Administration/sharing composition and cross-application accessibility convergence remain later-phase work. This phase does not imply the entire legacy UI is redesigned or certified.

## Exact implementation file list

Modified frontend files:

- `apps/web/src/features/accounts/pages.tsx`
- `apps/web/src/features/analytics/pages.tsx`
- `apps/web/src/features/analytics/shared.tsx`
- `apps/web/src/features/chat/components/chat.tsx`
- `apps/web/src/features/dashboards/pages.tsx`
- `apps/web/src/features/datasets/api.ts`
- `apps/web/src/features/datasets/import.tsx`
- `apps/web/src/features/datasets/pages.tsx`

Created frontend/test files:

- `apps/web/src/shared/editing/unsaved-changes.tsx`
- `apps/web/src/shared/editing/editing-feedback.tsx`
- `apps/web/src/shared/editing/unsaved-changes.css`
- `apps/web/playwright.editing.config.ts`
- `apps/web/tests/support/editing-api.ts`
- `apps/web/tests/browser/editing.spec.ts`

Updated documents: `REDESIGN_PLAN.md` and `artifacts/redesign/phase-0/REVIEW.md`. Phase 1 evidence contains this review, the verification helper/report, browser results and the three named screenshots; Playwright also writes its test-output attachments under `results/`. Build updates ignored `apps/web/dist/` and existing tool caches only.

No dependency install, backend/container lifecycle, credential/environment edit, Git command, commit, push or deployment was performed. Existing unrelated `services/platform/README.md` changes were preserved. Rollback remains a user-controlled review/reversal of these listed frontend/document changes, without changing stored resources or data. No destructive Git operation is needed or authorized by this review.

**Stop:** user acceptance of Phase 1 is required before starting Phase 2.
