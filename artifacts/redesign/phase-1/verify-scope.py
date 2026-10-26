"""Read-only integrity comparison against the pre-redesign baseline. No Git CLI."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json

out = Path(__file__).resolve().parent
root = out.parents[2]
baseline = json.loads((out.parent / 'phase-0/production-before.json').read_text(encoding='utf-8-sig'))
expected = [
    'apps/web/src/features/accounts/pages.tsx',
    'apps/web/src/features/analytics/pages.tsx',
    'apps/web/src/features/analytics/shared.tsx',
    'apps/web/src/features/chat/components/chat.tsx',
    'apps/web/src/features/dashboards/pages.tsx',
    'apps/web/src/features/datasets/api.ts',
    'apps/web/src/features/datasets/import.tsx',
    'apps/web/src/features/datasets/pages.tsx',
]
created = [
    'apps/web/src/shared/editing/unsaved-changes.tsx',
    'apps/web/src/shared/editing/editing-feedback.tsx',
    'apps/web/src/shared/editing/unsaved-changes.css',
    'apps/web/playwright.editing.config.ts',
    'apps/web/tests/support/editing-api.ts',
    'apps/web/tests/browser/editing.spec.ts',
]
changed = [name for name, digest in baseline.items() if not (root / name).is_file() or sha256((root / name).read_bytes()).hexdigest() != digest]
unexpected = sorted(set(changed) - set(expected))
assert not unexpected, unexpected
assert all((root / name).is_file() for name in expected + created)
guard = (root / created[0]).read_text(encoding='utf-8')
assert not any(token in guard for token in ['localStorage', 'sessionStorage', 'indexedDB', 'fetch('])
head = (root / '.git/HEAD').read_text().strip()
assert head == 'ref: refs/heads/feature/ui-ux-redesign', head
report = {
    'verifiedAtUTC': datetime.now(timezone.utc).isoformat(),
    'branch': 'feature/ui-ux-redesign',
    'baseline': 'phase-0/production-before.json; tracked apps/web, services, packages/deploy where present, PRODUCT.md and DESIGN.md',
    'baselineFiles': len(baseline), 'changedBaselineFiles': changed,
    'unchangedBaselineFiles': len(baseline) - len(changed), 'unexpectedChanges': unexpected,
    'backendAndContractFilesUnchanged': True,
    'productAndDesignBaselineUnchanged': all(name not in changed for name in ['PRODUCT.md', 'DESIGN.md']),
    'packageManifestsUnchanged': all(name not in changed for name in ['apps/web/package.json', 'apps/web/package-lock.json']),
    'newProductionAndTestFiles': created,
    'documentsChanged': ['REDESIGN_PLAN.md', 'artifacts/redesign/phase-0/REVIEW.md'],
    'implementationSHA256': {name: sha256((root / name).read_bytes()).hexdigest() for name in expected + created},
    'noNewDraftStorageOrNetworkInGuard': True,
    'gitCommandsExecutedByThisCheck': False,
}
(out / 'scope-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'baselineFiles': len(baseline), 'changedFrontendFiles': len(changed), 'newFrontendAndTestFiles': len(created), 'unexpectedChanges': unexpected, 'branch': report['branch']}, indent=2))
