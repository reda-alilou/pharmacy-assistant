"""Read-only source integrity check; writes reports/manifest in Phase 0 only."""
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote
import json
import re
import subprocess

out = Path(__file__).resolve().parent
root = out.parents[2]
baseline = json.loads((out / 'production-before.json').read_text(encoding='utf-8-sig'))
changed, missing = [], []
for relative, expected in baseline.items():
    path = root / relative
    if not path.is_file():
        missing.append(relative)
    elif sha256(path.read_bytes()).hexdigest() != expected:
        changed.append(relative)
additions = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', 'apps/web', 'services', 'packages', 'deploy'], cwd=root, text=True).splitlines()
storage = {}
for path in sorted(out.glob('direction-?.html')):
    text = path.read_text(encoding='utf-8')
    storage[path.name] = re.findall(r'\b(?:localStorage|sessionStorage|indexedDB|fetch|XMLHttpRequest|WebSocket|serviceWorker)\b', text)
report = {
    'verifiedAtUTC': datetime.now(timezone.utc).isoformat(),
    'baselineFiles': len(baseline), 'changed': changed, 'missing': missing,
    'newUntrackedProductionFiles': additions,
    'scope': 'tracked production files from apps/web, services, packages, deploy; PRODUCT.md and DESIGN.md',
    'baselineContextUnchanged': all(p not in changed + missing for p in ['PRODUCT.md', 'DESIGN.md']),
    'prototypeNetworkOrStorageAPIMatches': storage,
    'result': 'pass' if not (changed or missing or additions or any(storage.values())) else 'review required',
    'preexistingWork': 'services/platform/README.md was already modified; its bytes match the Phase 0 starting snapshot',
    'outsideArtifactModification': 'REDESIGN_PLAN.md modified; .impeccable/config.json created by requested hook triage with file-scoped proposal exceptions only',
}
(out / 'production-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

# Include this generated manifest itself; no source-tree mutation.
manifest = out / 'FILES.md'
manifest.touch(exist_ok=True)
files = sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file())
lines = ['# Exact Phase 0 file manifest', '',
         'Modified outside this directory: `REDESIGN_PLAN.md`. Created outside this directory after the requested hook triage: [.impeccable/config.json](../../../.impeccable/config.json), containing only file-scoped detector exceptions for the unapproved prototypes. Existing unrelated work is untouched.', '',
         f'Created under `artifacts/redesign/phase-0/`: **{len(files)} files** (including this manifest).', '',
         'The nine direction files are the HTML prototypes and candidate MD/JSON systems; screenshots contain the rendered evidence. Seed-context files are isolated skill-helper provenance, not application configuration or an adopted system.', '',
         '| Created file |', '| --- |']
lines += [f'| [{name}](<{name}>) |' for name in files]
manifest.write_text('\n'.join(lines) + '\n', encoding='utf-8')

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        self.links += [value for key, value in attrs if key in ('href','src') and value]
broken = []
for path in out.glob('*.html'):
    parsed = Links(); parsed.feed(path.read_text(encoding='utf-8'))
    for href in parsed.links:
        url = urlparse(href)
        if not url.scheme and url.path and not (path.parent / unquote(url.path)).exists():
            broken.append({'file':path.name, 'target':href})
assert not broken, broken
assert report['result'] == 'pass', report
print(json.dumps({'baselineFiles':len(baseline), 'unchanged':True, 'newProductionFiles':additions, 'artifacts':len(files), 'brokenHTMLLinks':broken}, indent=2))
