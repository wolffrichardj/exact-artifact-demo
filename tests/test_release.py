import gzip
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import release as r


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        (self.source / 'public').mkdir(parents=True)
        (self.source / r.PAYLOAD).write_text('<h1>Synthetic fixture</h1>\n')
        self.git('init', '-q'); self.git('add', '.'); self.commit()
        self.context = dict(repository='example/sample', workflow='synthetic-local', run_id='123', attempt='2')
        self.info = r.package(self.source, self.root / 'output', **self.context)
        self.records = r.read_members(Path(self.info['archive']).read_bytes())

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.source), *args], check=True, capture_output=True).stdout

    def commit(self):
        self.git('-c', 'user.name=Synthetic Test', '-c', 'user.email=synthetic@example.test', 'commit', '-qm', 'Synthetic fixture')

    def check(self, **changes):
        return r.validate(**(self.info | changes))

    def rebind(self, data, manifest=None):
        # Trusted test-builder operation, never performed by validate().
        Path(self.info['archive']).write_bytes(data)
        self.info['expected_sha'] = r.digest(data)
        if manifest is not None:
            self.info['expected_manifest'] = r.digest(manifest)
        fields = r.evidence_fields(**self.context, revision=self.info['revision'], tree=self.info['tree'],
                                  archive=Path(self.info['archive']).name, sha=self.info['expected_sha'], manifest=self.info['expected_manifest'])
        Path(self.info['evidence']).write_text(''.join(f'{k}: {v}\n' for k, v in fields.items()))

    def rewrite(self, records, regenerate=False):
        records = dict(records)
        if regenerate:
            records.pop('MANIFEST.sha256', None)
            records['MANIFEST.sha256'] = r.manifest_bytes(records)
        self.rebind(r.archive_bytes(records), records.get('MANIFEST.sha256'))

    def rejected(self, code, **changes):
        with self.assertRaisesRegex(ValueError, '^' + code + ':'):
            self.check(**changes)

    def test_exact_artifact_and_reproducibility(self):
        self.assertEqual(self.check()['status'], 'verified')
        self.assertEqual(self.check()['members'], 3)
        again = r.package(self.source, self.root / 'again', **self.context)
        for key in ('archive', 'evidence'):
            self.assertEqual(Path(again[key]).read_bytes(), Path(self.info[key]).read_bytes())

    def test_raw_archive_tamper(self):
        p = Path(self.info['archive']); p.write_bytes(p.read_bytes() + b'changed')
        self.rejected('ARCHIVE_HASH_MISMATCH')

    def test_payload_tamper_is_sensitive_to_disabling_per_file_hashing(self):
        records = self.records | {r.PAYLOAD: b'<h1>Substituted</h1>'}
        self.rewrite(records)  # Re-pin outer hash, retain original manifest bytes.
        self.assertEqual(self.info['expected_manifest'], r.digest(self.records['MANIFEST.sha256']))
        self.rejected('PAYLOAD_HASH_MISMATCH')
        def inventory_only(expected, actual):
            r.require(expected.keys() == actual.keys(), 'INVENTORY_MISMATCH: test')
        with patch.object(r, 'verify_payload', side_effect=inventory_only):
            self.assertEqual(self.check()['status'], 'verified')

    def test_replacing_all_trusted_inputs_can_forge_agreement(self):
        self.rewrite(self.records | {r.PAYLOAD: b'Replaced synthetic bytes'}, regenerate=True)
        self.assertEqual(self.check()['status'], 'verified')

    def test_wrong_expected_source_and_tree(self):
        self.rejected('IDENTITY_MISMATCH', revision='c' * 40)
        self.rejected('EVIDENCE_MISMATCH', tree='c' * 40)
        self.rejected('IDENTITY_MISMATCH', revision='short')

    def test_release_identity_types_keys_and_values(self):
        metadata = json.loads(self.records['RELEASE.json'])
        for change in ({'commit': 'c' * 40}, {'tree': 'c' * 40}, {'dirty': True}, {'dirty': 0},
                       {'format_version': True}, {'format_version': 2}, {'extra': 1}):
            with self.subTest(change=change):
                self.rewrite(self.records | {'RELEASE.json': json.dumps(metadata | change).encode()}, regenerate=True)
                self.rejected('IDENTITY_MISMATCH')

    def test_duplicate_and_malformed_metadata(self):
        for data in (b'{"commit":"x","commit":"y"}', b'[]', b'not json', b'\xff'):
            with self.subTest(data=data):
                self.rewrite(self.records | {'RELEASE.json': data}, regenerate=True)
                self.rejected('IDENTITY_MISMATCH')

    def test_missing_and_extra_members_even_with_new_hashes(self):
        for name in r.MEMBERS:
            with self.subTest(missing=name):
                records = dict(self.records); del records[name]
                self.rewrite(records)
                self.rejected('INVENTORY_MISMATCH')
        for regenerate in (False, True):
            with self.subTest(extra_in_manifest=regenerate):
                self.rewrite(self.records | {'public/unexpected.html': b'extra'}, regenerate=regenerate)
                self.rejected('INVENTORY_MISMATCH')

    def test_removing_payload_and_its_manifest_row_still_fails(self):
        records = dict(self.records); del records[r.PAYLOAD]
        self.rewrite(records, regenerate=True)
        self.rejected('INVENTORY_MISMATCH')

    def test_manifest_digest_mismatch(self):
        self.rejected('EVIDENCE_MISMATCH', expected_manifest='0' * 64)
        p = Path(self.info['evidence']); p.write_text(p.read_text().replace(self.info['expected_manifest'], '0' * 64))
        self.rejected('MANIFEST_HASH_MISMATCH', expected_manifest='0' * 64)

    def test_manifest_syntax_duplicates_inventory_and_paths(self):
        manifest = self.records['MANIFEST.sha256']
        cases = [(b'invalid\n', 'STRUCTURE_INVALID'), (manifest + manifest, 'INVENTORY_MISMATCH'),
                 (b'', 'INVENTORY_MISMATCH'), (manifest.splitlines(keepends=True)[0], 'INVENTORY_MISMATCH'),
                 (manifest + b'0' * 64 + b'  public/extra\n', 'INVENTORY_MISMATCH'),
                 (manifest.replace(b'public/index.html', b'../outside'), 'STRUCTURE_INVALID')]
        for content, code in cases:
            with self.subTest(content=content):
                self.rewrite(self.records | {'MANIFEST.sha256': content})
                self.rejected(code)

    def test_context_substitution(self):
        for change in ({'repository': 'fork/sample'}, {'workflow': 'other'}, {'run_id': '124'}, {'attempt': '1'},
                       {'run_id': '0'}, {'attempt': '-1'}, {'repository': 'invalid'}, {'workflow': 'bad\nline'}, {'workflow': 'bad\u2028line'}):
            with self.subTest(change=change): self.rejected('EVIDENCE_MISMATCH', **change)

    def test_invalid_event_ref_and_conclusion(self):
        p = Path(self.info['evidence']); original = p.read_text()
        for old, new in [('Workflow event: push', 'Workflow event: pull_request'),
                         ('Workflow event: push', 'Workflow event: workflow_dispatch'),
                         ('Workflow ref: refs/heads/main', 'Workflow ref: refs/heads/topic'),
                         ('Workflow conclusion: success', 'Workflow conclusion: failure')]:
            with self.subTest(new=new):
                p.write_text(original.replace(old, new)); self.rejected('EVIDENCE_MISMATCH')

    def test_missing_extra_duplicate_malformed_and_missing_file_evidence(self):
        p = Path(self.info['evidence']); original = p.read_text()
        for text in ('', '\n'.join(original.splitlines()[1:]) + '\n', original + 'Extra: data\n',
                     original + 'Workflow conclusion: success\n', original + '\n', original.replace('Repository: ', 'Repository:  ')):
            with self.subTest(text=text):
                p.write_text(text); self.rejected('EVIDENCE_MISMATCH')
        p.unlink(); self.rejected('STRUCTURE_INVALID')

    def special_archive(self, name=r.PAYLOAD, kind=tarfile.REGTYPE, duplicate=False):
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode='w', format=tarfile.USTAR_FORMAT) as bundle:
            for old, data in self.records.items():
                item = tarfile.TarInfo(name if old == r.PAYLOAD else old)
                item.type = kind if old == r.PAYLOAD else tarfile.REGTYPE
                item.size = len(data) if item.isfile() else 0
                item.linkname = 'outside' if item.issym() or item.islnk() else ''
                bundle.addfile(item, io.BytesIO(data) if item.isfile() else None)
                if duplicate and old == r.PAYLOAD: bundle.addfile(item, io.BytesIO(data))
        return gzip.compress(raw.getvalue(), mtime=0)

    def test_unsafe_paths_duplicate_links_specials_and_pax(self):
        variants = [self.special_archive(name=name) for name in ('../outside', '/absolute', './public/index.html',
                    'public//index.html', 'public/../outside', 'public\\index.html', 'public/new\nline')]
        variants += [self.special_archive(kind=kind) for kind in
                     (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.DIRTYPE, tarfile.XHDTYPE)]
        variants.append(self.special_archive(duplicate=True))
        for data in variants:
            with self.subTest(sha=r.digest(data)):
                self.rebind(data); self.rejected('STRUCTURE_INVALID')

    def test_truncated_gzip_tar_and_hidden_members(self):
        valid = Path(self.info['archive']).read_bytes()
        hidden = gzip.compress(gzip.decompress(valid) + gzip.decompress(valid), mtime=0)
        for data in (valid[:20], gzip.compress(b'not tar', mtime=0), hidden, gzip.compress(gzip.decompress(valid)[:512], mtime=0)):
            with self.subTest(size=len(data)):
                self.rebind(data); self.rejected('STRUCTURE_INVALID')

    def test_resource_bounds(self):
        for data in (bytes(r.LIMIT + 1), gzip.compress(bytes(r.LIMIT + 512), mtime=0)):
            with self.subTest(size=len(data)):
                self.rebind(data); self.rejected('STRUCTURE_INVALID')

    def test_archive_and_evidence_links(self):
        for key in ('archive', 'evidence'):
            with self.subTest(key=key):
                p = Path(self.info[key]); target = p.with_suffix('.target')
                p.rename(target); p.symlink_to(target)
                self.rejected('STRUCTURE_INVALID')
                p.unlink(); target.rename(p)

    def test_archive_name_and_missing_archive(self):
        p = Path(self.info['archive']); renamed = p.with_name('wrong.tar.gz'); p.rename(renamed)
        self.rejected('IDENTITY_MISMATCH', archive=renamed)
        self.rejected('STRUCTURE_INVALID')

    def test_dirty_or_untracked_source(self):
        for p in (self.source / r.PAYLOAD, self.source / 'untracked.txt'):
            with self.subTest(path=p.name):
                before = p.read_bytes() if p.exists() else None
                p.write_text('changed')
                with self.assertRaisesRegex(ValueError, '^SOURCE_INVALID: dirty'):
                    r.package(self.source, self.root / 'refused', **self.context)
                self.assertFalse((self.root / 'refused').exists())
                if before is None: p.unlink()
                else: p.write_bytes(before)

    def test_committed_unexpected_member_and_symlink(self):
        extra = self.source / 'public/extra.html'; extra.write_text('extra')
        self.git('add', '.'); self.commit()
        with self.assertRaisesRegex(ValueError, '^SOURCE_INVALID: unexpected'):
            r.package(self.source, self.root / 'refused', **self.context)
        extra.unlink(); p = self.source / r.PAYLOAD; p.unlink(); p.symlink_to('missing')
        self.git('add', '.'); self.commit()
        with self.assertRaisesRegex(ValueError, '^SOURCE_INVALID: payload'):
            r.package(self.source, self.root / 'refused', **self.context)

    def test_output_external_empty_and_not_overwritten(self):
        for output in (self.source / 'build', Path(self.info['archive']).parent):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, '^SOURCE_INVALID:'):
                r.package(self.source, output, **self.context)
        self.assertEqual(self.check()['status'], 'verified')

    def test_all_object_lookups_use_captured_revision(self):
        calls = []; original = r.git
        def observe(source, *args):
            calls.append(args); return original(source, *args)
        with patch.object(r, 'git', side_effect=observe):
            r.package(self.source, self.root / 'observed', **self.context)
        lookups = [args for args in calls if args[0] in ('show', 'ls-tree')]
        self.assertTrue(lookups)
        self.assertTrue(all(self.info['revision'] in ' '.join(args) for args in lookups))

    def test_completion_source_change_removes_owned_outputs(self):
        original = r.clean; calls = 0
        def race(source):
            nonlocal calls
            calls += 1
            if calls == 2: (source / r.PAYLOAD).write_text('concurrent change')
            original(source)
        output = self.root / 'raced'
        with patch.object(r, 'clean', side_effect=race), self.assertRaisesRegex(ValueError, '^SOURCE_INVALID: dirty'):
            r.package(self.source, output, **self.context)
        self.assertEqual(list(output.iterdir()), [])

    def test_cli_exit_status_and_no_accepted_output_on_rejection(self):
        flags = []
        for name in ('repository', 'workflow', 'revision', 'tree', 'run_id', 'attempt', 'expected_sha', 'expected_manifest'):
            flags.extend(['--' + name.replace('_', '-'), self.info[name]])
        cmd = [sys.executable, str(Path(r.__file__)), 'validate', self.info['archive'], self.info['evidence'], *flags]
        good = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)['status'], 'verified')
        p = Path(self.info['archive']); p.write_bytes(p.read_bytes() + b'changed')
        bad = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1); self.assertEqual(bad.stdout, '')
        self.assertTrue(json.loads(bad.stderr)['error'].startswith('ARCHIVE_HASH_MISMATCH:'))


if __name__ == '__main__': unittest.main()
