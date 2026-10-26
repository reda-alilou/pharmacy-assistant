# Approved unsaved-change specification — warning only

Status: approved policy, proposed production integration. The Phase 0 prototypes are isolated demonstrations; no production guard has been implemented.

## Contract

Keep edited values only in the current editor's memory. Do not add sessionStorage, localStorage, IndexedDB, files, URL-encoded drafts, background synchronization, automatic saves or backend endpoints for drafts. Do not cache a discarded editor for later recovery. This restriction does not remove the application's existing saved resources/import receipts or independent temporary assistant-conversation token and server transcript behavior.

When leaving would destroy unsaved input, interrupt before changing route/tab, replacing the editor, advancing browser history or invalidating the session through ordinary logout. A safe step change within one mounted logical editor may retain its in-memory state without prompting; this must be tested rather than assumed.

## State and action matrix

| State/event | Required presentation and behavior |
| --- | --- |
| Clean → ordinary exit | Navigate normally. No spurious warning. |
| Dirty → internal link, local tab that destroys input, Back/Forward or logout | Show “Quitter sans enregistrer ?” with the affected editor/resource named. Choices: **Rester** (initial focus) and **Quitter et abandonner**. No automatic Save action. |
| Rester / Escape / dialog cancel | Do not navigate, log out, reset values or clear the dirty flag. Restore focus to the initiating control or sensible editor location. |
| Quitter et abandonner | Perform the requested navigation/logout once. Destroy that editor's unsaved input. Returning reads existing saved/server state; no Restore banner appears. |
| Failed save | Keep current input and dirty state. Show actionable server validation/error; do not claim success. A retry is explicit. |
| Successful save | Update baseline only from the confirmed response; clear dirty if no later edits exist. Keep success feedback stable across resource refresh/remount. Do not auto-share or publish. |
| Revision conflict | Keep entered values in the current editor; explain saved resource changed. Offer inspection/current-state verification and deliberate correction. No auto-merge, overwrite or draft restoration after leaving. |
| Request pending → exit | Explain “Une opération peut encore se terminer côté serveur. Quitter ne l’annule pas.” Staying keeps the editor. An explicit exit follows existing permitted behavior; never promise to cancel or undo a request by closing a view. No duplicate request on return. |
| Response outcome unknown | Keep current input while mounted, explain uncertainty, verify the existing saved resource/receipt with its current API. Never replay a POST automatically. Leaving can lose unsaved input. |
| Reload/close while dirty | Native beforeunload warning where browser supports it and user activation requirements are met. Browser controls text/button wording. Cancel keeps the document/input; accept may lose unsaved input. |
| Accepted reload, discarded exit or crash | No recovery promise, storage restoration, cross-route cache or background draft. Existing last-confirmed saved resource/server receipt remains authoritative. |
| Authentication expiry, revocation or forced access loss | Follow current backend security, clear/lock unauthorized UI as appropriate; a warning cannot preserve access. Do not stash values for another account or promise later recovery. |

## Surfaces and dirty baselines

- **Dataset metadata:** title, description, category, source and declared observation date against loaded revision. Local dataset view changes are guarded if they unmount the form. Archive/delete retain their existing review and dependency requirements.
- **Import:** options, selected column interpretations and metadata against current server-accepted import configuration and in-memory state. The File/Interpret/Describe/Validate stage controller may preserve values within the same editor. No re-upload or publication on Next/Back. An expired receipt does not revive on cancellation of navigation.
- **Analysis:** definition, selected sources/versions, filters, calculation/chart settings, title and description. Calculating is not saving. Changing settings removes outdated results. Dirty baseline updates after confirmed explicit save only.
- **Dashboard:** title, description, widgets/order/size/definitions and filter mappings/defaults. Reader filter adjustments are local exploration, not an owner draft and must not trigger misleading owner save prompts. Explicit edit discard remains distinct from resetting reader filters.
- **Profile:** displayed name and password inputs are current-editor memory only. Preserve password-change session invalidation and clear sensitive inputs after the appropriate success/logout. Never persist passwords.
- **Assistant:** typed but unsent input remains current-page memory. Destructive conversation reset retains its existing separate confirmation/server invalidation semantics. Existing server restoration retrieves accepted conversation content, not unsent drafts. Do not introduce patient draft persistence as a side effect.

## Confirmation accessibility

Use a native accessible dialog or existing Radix pattern with a clear title/description, two text-labeled actions, focus containment, Escape as Stay, and focus restoration. Keep the underlying editor mounted. Announce failure/status in context without reading the entire form repeatedly. Do not show a stack of native/custom confirmations for one event. The browser reload warning is a distinct native path.

## Later Phase 1 acceptance matrix

For analysis, dataset metadata, import and dashboard, exercise internal links, destructive local view changes, history and logout: change a recognizable synthetic value → attempt exit → Stay → value unchanged → attempt exit → Discard → return → original server state. Confirm Back/Forward moves only once. Clean navigation must not prompt.

Exercise failed validation, 503, delayed response, 409 and outcome-unknown states. Keep values without duplicates. Confirm successful save followed by exit does not warn unless a new edit occurs. Check storage/network logs for **no new draft persistence/synchronization**. Test native reload cancel and accept manually where headless automation cannot establish reliable browser behavior. A crash test validates the absence of a recovery claim, not guaranteed recovery. Existing assistant sessionStorage is not itself a regression; distinguish it from prohibited new draft writes.

## Phase 0 limitation

Prototype dialogs illustrate intent using local in-memory edits only. They do not validate React Router history, real logout, real conflicts, native reload interception or backend request outcomes. Those remain Phase 1 work after explicit authorization.
