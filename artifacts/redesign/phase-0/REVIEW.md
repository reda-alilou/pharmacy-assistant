# Phase 0 review — accepted and closed

**Subsequent decision:** the user approved Direction B — Traverse with the agreed green V2 refinements, closed Phase 0, skipped further prototypes, and authorized Phase 1 on `feature/ui-ux-redesign`. See REDESIGN_PLAN.md for the active scope. The review packet below records the original proposal/evidence state; its open-decision labels are historical. Phase 2 still requires acceptance of Phase 1.

Prepared 25 October 2026. Phase 0 artifacts are complete for review; **no visual direction is selected, and no production redesign or Phase 1 work has begun**.

## Start here

Open [index.html](index.html) locally in a browser. Its controls compare all three directions using the same analysis, dashboard and assistant content at 1440px and 390px. Open a full-size capture for exact reading, or a live prototype to resize and inspect local interactions. No server is needed. If the IDE shows HTML source, use its browser/open-file action.

1. [Comparison and recommendation](COMPARISON.md): Registre, Traverse, Cahier; strengths, costs and integration risks.
2. [Interaction blueprint](INTERACTION_BLUEPRINT.md): all principal workflows and shared states.
3. [Capability map](CAPABILITY_MAP.md): every existing capability retained, with composed versus specified-only coverage.
4. [Warning-only policy](UNSAVED_CHANGES.md): the approved no-persistence behavior and later acceptance matrix.
5. Candidate systems: [A](direction-a-system.md), [B](direction-b-system.md), [C](direction-c-system.md); each has matching JSON tokens and a live `?view=system` specimen.
6. [Exact file manifest](FILES.md) and [production integrity report](production-verification.json).

## Decisions faithfully recorded

REDESIGN_PLAN.md now authorizes substantial visual exploration, removes the assumption that the incumbent palette/navigation/components are approved, and preserves the no-gradient/no-decorative-side-strip constraints. It specifies warnings rather than persisted draft recovery. It keeps the Phase 0–7 order and explicit acceptance gates.

Stay preserves the current editor; Discard permits loss. Failed saves retain mounted input. Native reload/close warnings are required where supported; accepted reload, crash and discarded navigation have no recovery promise. Existing saved resources, import receipts and the assistant's temporary accepted-message restoration keep their existing contracts. No new draft store, synchronization or endpoint is proposed.

## Approval still needed

| Decision | What you are approving | What remains separate |
| --- | --- | --- |
| Select A, B or C, or request a concrete revision | Operating model, navigation composition and overall visual character | No automatic implementation or combination of proposals |
| Accept or amend the interaction blueprint/capability mapping | Progressive disclosure, reading order, state/feedback and permission-aware placement across existing capabilities | Existing backend and analytical contracts stay authoritative |
| Accept the selected candidate system | Typography, colors, spacing, components and responsive rules as the basis for later work | DESIGN.md remains the incumbent baseline until a separately authorized implementation records reality |
| Explicitly authorize Phase 1 after Phase 0 acceptance | Warning-only safeguards and feedback in the existing app, within its planned scope | Phases 2–7 remain gated individually |

Particular choices to assess with the direction: persistent expert parameters versus a disclosed question stage; dossier-first versus conversation-first assistant on mobile; full navigation grouping when the remaining routes are integrated. These are consequences of A/B/C, not new product capabilities. No precise analyst persona or future landing-page build default is invented or set.

## Browser evidence

The isolated HTML files were rendered in installed **headless Microsoft Edge using the project's existing Playwright and axe packages**. Navigation used `file://`; HTTP(S) requests were blocked and the review recorded none. No frontend/backend server or container was started, stopped or changed.

- **48 viewport cases:** 3 directions × 4 views (analysis, dashboard, assistant, system) × 4 widths (1440, 390, 320, 768).
- **24 reference captures:** desktop/mobile for all four views. Additional captures show three desktop discard dialogs, three expanded mobile configurations and the comparison gallery: **31 screenshots total**.
- No page-wide horizontal overflow in those cases. Bounded exact-table/document-tab scrolling is intentional. No visible main-content leaf text below 12px in measured initial views; plot labels use CSS text rather than a shrinking SVG viewBox. Essential medication price/date/source remain 14px or larger.
- Automated WCAG A/AA-tagged axe checks on all 24 reference views reported no violations after correcting a missing semantic role on Cahier's missingness graphic. The gallery was also checked at all four widths. This is bounded automated coverage, not accessibility certification.
- Local specimens exercised: dirty navigation → Stay and Discard; Escape retaining the edited value; changed mean to sum/count and explicit Calculate; group B displaying 5 rows, 87.50 MAD and 20% missing; medication identity, 372.00 MAD, 18 October 2026 and AMMPS visible.
- Rendered reference captures and component/state specimens were visually inspected. Obvious issues corrected included the missing chart role, mobile source-selector discoverability/spacing, preview-thumbnail cropping and the public assistant's account wording.

Details: [browser-verification.json](browser-verification.json), [review-verification.json](review-verification.json), reproducible helpers `verify-prototypes.mjs` and `verify-review.mjs`. They use installed packages only and operate on these local artifacts. A helper's exploratory hidden-control selector timed out on the first run; it was corrected before the completed reports were generated.

## What these checks do not establish

- These are compositions and limited in-memory simulations, not a frontend replacement or an alternate analytical engine. Most capabilities are specified in the map rather than implemented in prototypes. Save announces simulation and does not clear the fact that work is unsaved.
- No production runtime, authentication, permissions, real save/publication, revision conflict, logout/history interception, beforeunload behavior or actual backend calculation was exercised during this phase. The prior critique supplies the current-app evidence; this phase verifies proposed static compositions.
- No real screen-reader session, physical mobile keyboard, touch device, Safari/Firefox, browser zoom/reflow session or non-Windows font rendering was verified. 320px and tablet were measured in Edge; they are not substitutes for those tests. The candidate systems specify focus, reduced motion, contrast and readable data, but implementation must verify these in actual components.
- Existing screenshots are supporting historical evidence, not a claim that every backend state was available today. All new compositions use CP6/response fixtures and declare their test status. They do not verify a current medication price or source webpage.
- The assistant's 30-minute behavior is explained, not simulated as a server session. The static prototypes store nothing and cannot prove the real restoration/reset/cooldown paths. Their simplified reset and navigation demonstrations do not supersede the complete blueprint.
- Native dialogs are local examples. Final wording, emphasis and focus behavior must follow the approved policy across actual editors, browser history and forced access loss. No promise of retaining unsaved work after a crash is possible under the approved policy.

## Production and boundary verification

The before/after SHA-256 comparison covers 254 baseline production/context files, including all tracked apps/web files and PRODUCT.md/DESIGN.md; the final report records any differences and source-tree additions. Existing unrelated `services/platform/README.md` work is compared to its starting bytes, not reverted. Artifacts are ignored by the repository's existing rules; this review does not change ignore configuration.

REDESIGN_PLAN.md is modified outside the Phase 0 artifact directory. After the requested hook triage, `.impeccable/config.json` was also created using the skill's validated command, solely for narrowly scoped detector exceptions described below. No production components/styles, backend code/contracts, package manifests, credentials or environment settings were edited. No dependencies were installed, inference called, private data accessed, commit/push/deployment/publication performed. The skill's free reference-metadata lookup is documented in [exploration notes](EXPLORATION_NOTES.md); it was not hosted inference or asset generation.

## Hook triage after delivery

The Stop hook flagged cream/beige backgrounds in B and C. These are intentional isolated comparison studies: Traverse's warm canvas accompanies forest/sage navigation, while Cahier's warm paper accompanies a document/report composition and oxblood actions. They are documented candidate decisions, not evidence that the user selected or approved them. Changing them merely to remove a taste warning would alter the proposals awaiting review.

Following the requested triage, `impeccable hooks ignore-value` persisted `cream-palette=*` **only** for `direction-b.html` and `direction-c.html`. A direct detector check also flagged Cahier's Cambria because it differs from the incumbent DESIGN.md; `design-system-font=cambria` is scoped only to `direction-c.html`. No whole rule or file is disabled, and production files have no exception. Both targeted detector checks then exited successfully. Incumbent color/size/radius advisories are expected for proposed replacement systems; DESIGN.md was not changed. The hover contrast advisory concerns disabled-button text, not an enabled text state.

No HTML, visual composition or screenshot changed during this triage. The added config records review exceptions only; no candidate becomes the approved design system. The manifest and integrity report were refreshed to disclose the additional tooling file.

Phase 0 ends here for your review. Selection, blueprint acceptance and permission to start Phase 1 are explicit next decisions; viewing this packet or accepting the overall phase sequence does not authorize subsequent work.
