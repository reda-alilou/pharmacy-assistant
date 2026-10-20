import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pharmacy_infrastructure.evidence import resolve_input, verify_archive


class EvidenceTests(unittest.TestCase):
    def fixture(self, root):
        target=root/'archive/historical/reports/result.json'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'{"historical":true}\n')
        manifest=dict(version=1,entries=[dict(original_path='reports/result.json',
            archived_path=target.relative_to(root).as_posix(),sha256=hashlib.sha256(target.read_bytes()).hexdigest())])
        path=root/'archive/manifest.json'
        path.write_text(json.dumps(manifest),encoding='utf-8')
        return target,manifest,path

    def test_old_and_direct_archive_inputs_resolve_with_verified_unchanged_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            target,_,_=self.fixture(root)
            self.assertEqual(resolve_input('reports/result.json',root=root),target)
            self.assertEqual(resolve_input(root/'reports/result.json',root=root),target)
            self.assertEqual(resolve_input(target,root=root),target)
            self.assertTrue(verify_archive(root)['passed'])
            self.assertFalse((root/'reports/result.json').exists())

    def test_changed_or_missing_archive_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            target,_,_=self.fixture(root)
            target.write_bytes(b'changed')
            for path in ('reports/result.json',target):
                with self.assertRaisesRegex(ValueError,'hash check'):
                    resolve_input(path,root=root)
            with self.assertRaises(ValueError):
                verify_archive(root)
            target.unlink()
            with self.assertRaises(ValueError):
                resolve_input('reports/result.json',root=root)

    def test_manifest_traversal_duplicates_and_unlisted_historical_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            target,manifest,path=self.fixture(root)
            other=target.parent/'unlisted.json'
            other.write_text('{}')
            with self.assertRaisesRegex(ValueError,'not listed'):
                resolve_input(other,root=root)
            manifest['entries'].append(manifest['entries'][0].copy())
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                verify_archive(root)
            manifest['entries']=manifest['entries'][:1]
            for name in ('../outside','/outside','C:/outside','archive/../outside'):
                manifest['entries'][0]['archived_path']=name
                path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    verify_archive(root)

    def test_active_relocations_and_explicit_external_inputs_are_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            target,manifest,path=self.fixture(root)
            manifest['active_relocations']=[dict(original_path='data/processed/current.jsonl',
                current_path='data/imports/current.jsonl',sha256=hashlib.sha256(b'{}').hexdigest())]
            current=root/'data/imports/current.jsonl'
            current.parent.mkdir(parents=True)
            current.write_bytes(b'{}')
            path.write_text(json.dumps(manifest))
            self.assertEqual(resolve_input('data/processed/current.jsonl',root=root),current)
            self.assertEqual(resolve_input(r'data\processed\current.jsonl',root=root),current)
            with tempfile.TemporaryDirectory() as other:
                external=Path(other)/'explicit.json'
                external.write_text('{}')
                self.assertEqual(resolve_input(external,root=root),external.resolve())
            manifest['active_relocations'][0]['current_path']='.runtime/private.env'
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'data/imports'):
                verify_archive(root)
