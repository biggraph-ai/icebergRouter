import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import fetch_references as f


class SelectionTests(unittest.TestCase):
    def test_manifest_entries_are_valid(self):
        obj = json.loads((f.BASE / 'repo_manifest.json').read_text())
        for entry in obj['repositories']:
            f.validate_entry(entry)
        self.assertEqual(6, sum('core' in x['groups'] for x in obj['repositories']))

    def test_only_reviewable_source_selected(self):
        rows = [
            '100644 blob abc\tREADME.md',
            '100644 blob abc\tLICENSE',
            '100644 blob abc\tsrc/router.py',
            '100644 blob abc\tsrc/config.json',
            '100644 blob abc\tsrc/AGENTS.md',
            '100644 blob abc\tsrc/checkpoints/weights.json',
            '100644 blob abc\tsrc/weights.bin',
            '100644 blob abc\tdata/requests.json',
            '120000 blob abc\tsrc/link.py',
            '160000 commit abc\tsrc/submodule',
        ]
        self.assertEqual(['LICENSE', 'README.md', 'src/config.json', 'src/router.py'],
                         f.select_paths('\n'.join(rows), ['src', 'data']))

    def test_unsafe_manifest_rejected(self):
        for entry in [
            {'id': '../evil', 'url': 'https://github.com/a/b.git'},
            {'id': 'good', 'url': 'https://evil.example/repo.git'},
            {'id': 'good', 'url': 'https://github.com/a/b.git', 'study_roots': ['../x']},
            {'id': 'good', 'url': 'https://github.com/a/b.git', 'commit': 'main; echo nope'},
        ]:
            with self.assertRaises(ValueError):
                f.validate_entry(entry)

    def test_pattern_escaping(self):
        self.assertEqual('/src/\\[x\\]/f.py', f.sparse_pattern('src/[x]/f.py'))

    def test_atomic_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'lock.json'
            f.atomic_json(p, {'a': 1})
            f.atomic_json(p, {'a': 2})
            self.assertEqual({'a': 2}, json.loads(p.read_text()))

    def test_default_command_is_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'never-created'
            proc = subprocess.run([sys.executable, str(f.BASE / 'fetch_references.py'),
                                   '--groups', 'core', '--root', str(root)],
                                  text=True, capture_output=True, check=False)
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertIn('DRY RUN: 6 repositories', proc.stdout)
            self.assertFalse(root.exists())


class LocalGitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.upstream = self.base / 'upstream'
        self.upstream.mkdir()
        f.git(['init', '--quiet'], cwd=self.upstream)
        (self.upstream / 'src').mkdir()
        (self.upstream / 'data').mkdir()
        (self.upstream / 'README.md').write_text('Synthetic local Git fixture.\n')
        (self.upstream / 'LICENSE').write_text('Synthetic notice, not a real license.\n')
        (self.upstream / 'src/router.py').write_text('VALUE = 1\n')
        (self.upstream / 'data/private.json').write_text('{"not_for_checkout":true}\n')
        f.git(['add', '.'], cwd=self.upstream)
        f.git(['-c', 'user.name=Local Test', '-c', 'user.email=test@example.invalid',
               'commit', '-qm', 'synthetic fixture'], cwd=self.upstream)
        self.entry = {'id': 'fixture', 'url': self.upstream.as_uri(), 'study_roots': ['src']}
        self.root = self.base / 'refs'
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_pins_and_verifies_without_updating(self):
        rec = f.prepare(self.entry, self.root, None, allow_local_for_tests=True)
        target = self.root / 'fixture'
        self.assertEqual(40, len(rec['commit']))
        self.assertEqual(3, rec['source_path_count'])
        self.assertTrue((target / 'src/router.py').exists())
        self.assertFalse((target / 'data/private.json').exists())
        (self.upstream / 'src/router.py').write_text('VALUE = 2\n')
        f.git(['add', '.'], cwd=self.upstream)
        f.git(['-c', 'user.name=Local Test', '-c', 'user.email=test@example.invalid',
               'commit', '-qm', 'new upstream commit'], cwd=self.upstream)
        again = f.prepare(self.entry, self.root, rec, allow_local_for_tests=True)
        self.assertEqual(rec['commit'], again['commit'])
        self.assertIn('VALUE = 1', (target / 'src/router.py').read_text())

    def test_changed_reference_is_not_overwritten(self):
        rec = f.prepare(self.entry, self.root, None, allow_local_for_tests=True)
        target = self.root / 'fixture' / 'src/router.py'
        target.write_text('LOCAL EDIT\n')
        with self.assertRaisesRegex(RuntimeError, 'local changes'):
            f.prepare(self.entry, self.root, rec, allow_local_for_tests=True)
        self.assertEqual('LOCAL EDIT\n', target.read_text())

    def test_locked_commit_can_be_fetched_into_new_destination(self):
        rec = f.prepare(self.entry, self.root, None, allow_local_for_tests=True)
        other = self.base / 'other'
        other.mkdir()
        second = f.prepare(self.entry, other, rec, allow_local_for_tests=True)
        self.assertEqual(rec['commit'], second['commit'])

    def test_unmanaged_destination_refused(self):
        target = self.root / 'fixture'
        target.mkdir()
        (target / 'keep.txt').write_text('do not delete\n')
        with self.assertRaisesRegex(RuntimeError, 'unmanaged'):
            f.prepare(self.entry, self.root, None, allow_local_for_tests=True)
        self.assertTrue((target / 'keep.txt').exists())


if __name__ == '__main__':
    unittest.main()
