# Historical archive

This archive preserves 1,002 files from the reviewed R1 inventory: raw snapshots,
secondary datasets, public collection/evaluation evidence, screenshots, earlier
walkthroughs and superseded design documents. Their bytes and embedded paths are
unchanged. They describe their original versions, not the current application.

`manifest.json` maps each original relative path to `historical/<original-path>`,
with its exact R1 checkout SHA-256, original Git blob identity, committed-content
hash and size. Checkout hashes and Git hashes are separate because some historical
files had Windows line endings. Git attributes disable normalization in this
subtree. Two additional manifest entries map active imports to `data/imports/`.

Verify every preserved file from the workspace root:

```powershell
.\.venv\Scripts\pharmacy-archive.exe
```

Maintained evaluation tools resolve missing original input paths through this
manifest and check the destination hash before reading. They can score historical
predictions without rewriting sources. This resolution is only for inputs;
new output belongs in ignored `artifacts/`. Old freezes and fingerprints do not
become valid for current hosted execution through relocation.

Examples: `reports/qwen_evaluation_freeze.json` now lives at
`historical/reports/qwen_evaluation_freeze.json`; the earlier architectural draft
is `historical/ARCHITECTURE_DECISIONS.txt`. The current finalized choices are
[DECISION_LOG.md](../DECISION_LOG.md), and the current processing explanation is
[the architecture overview](../docs/architecture/overview.md).

Old Markdown links and absolute paths are intentionally preserved as evidence.
Interpret missing original references through the manifest. References to removed
code describe the saved implementation at commit
`b1bca1693c6b351edd95f40aed4ced7e19e78520` or its documented earlier version;
they do not identify current entry points.

The tracked `historical/` subtree contains only reviewed public/tracked material.
Following explicit user authorization, obsolete local scratch files and caches
were removed. Previously ignored raw downloads/staging data were preserved under
ignored `local/`, with an independent `local/manifest.json` and verified hashes.
That local collection is optional, is not committed, and is not included in the
public manifest or `pharmacy-archive` counts. New checkouts need only the tracked
archive and active inputs. Private credentials, ledgers and backups stay untouched.
Source attribution does not imply ownership or a blanket license for third-party
material. See the [data guide](../docs/project/data-and-evidence.md).
