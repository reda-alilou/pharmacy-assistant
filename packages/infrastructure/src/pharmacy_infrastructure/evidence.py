"""Resolve immutable historical inputs through the reviewed archive manifest."""
import hashlib
import json
from pathlib import Path, PurePosixPath

from pharmacy_infrastructure.paths import ROOT


def _inside(root: Path, name: str) -> Path:
    relative=PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
        raise ValueError('Archive manifest paths must be workspace-relative')
    path=(root/name).resolve()
    if path==root or not path.is_relative_to(root):
        raise ValueError('Archive manifest path leaves the workspace')
    return path


def archive_entries(root: Path = ROOT):
    root=Path(root).resolve()
    manifest=json.loads((root/'archive/manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version')!=1:
        raise ValueError('Unsupported archive manifest version')
    entries={}
    for row in [*manifest['entries'],*manifest.get('active_relocations',[])]:
        original=_inside(root,row['original_path'])
        destination=_inside(root,row.get('archived_path',row.get('current_path')))
        name=original.relative_to(root).as_posix()
        if name in entries or not isinstance(row.get('sha256'),str) or len(row['sha256'])!=64:
            raise ValueError('Duplicate or invalid archive manifest entry')
        if 'archived_path' in row and not destination.is_relative_to(root/'archive/historical'):
            raise ValueError('Archived inputs must remain under archive/historical')
        if 'current_path' in row and not destination.is_relative_to(root/'data/imports'):
            raise ValueError('Active input relocations must remain under data/imports')
        entries[name]=(destination,row['sha256'])
    return entries


def resolve_input(path: Path | str, *, root: Path = ROOT) -> Path:
    """Read existing explicit inputs; resolve missing old paths with verified bytes.

    This does not rewrite evidence or make historical freezes valid for new runs.
    Outputs must never use this resolver.
    """
    root=Path(root).resolve()
    # Historical Windows reports also contain relative backslash paths.
    candidate=Path(str(path).replace('\\','/'))
    candidate=(root/candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if candidate.is_file():
        # Direct archive paths also need manifest/hash validation.
        if not candidate.is_relative_to(root/'archive/historical'):
            return candidate
        mapping=archive_entries(root)
        digest=next((digest for target,digest in mapping.values() if target==candidate),None)
        if digest is None:
            raise ValueError('Historical input is not listed in the archive manifest')
        target=candidate
    else:
        if not candidate.is_relative_to(root) or not (root/'archive/manifest.json').is_file():
            raise FileNotFoundError(candidate)
        match=archive_entries(root).get(candidate.relative_to(root).as_posix())
        if match is None:
            raise FileNotFoundError(candidate)
        target,digest=match
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
        raise ValueError('Archived or relocated input failed its preservation hash check')
    return target


def verify_archive(root: Path = ROOT) -> dict:
    mapping=archive_entries(root)
    total=0
    for target,digest in mapping.values():
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise ValueError('Archived or relocated input failed its preservation hash check')
        total+=target.stat().st_size
    return dict(passed=True,verified_files=len(mapping),verified_bytes=total)
