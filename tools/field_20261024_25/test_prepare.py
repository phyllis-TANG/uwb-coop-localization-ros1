"""Security and cache correctness tests for the offline asset preparation tool."""
import io
import json
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def asset(self, archive, asset_id='sample'):
        return dict(id=asset_id, name=archive.name,
                    sha256=prepare.sha256_file(archive), size_bytes=archive.stat().st_size,
                    url='https://example.invalid/' + archive.name, extract_subdir=asset_id)

    def make_zip(self, members):
        path = self.root / 'input.zip'
        with zipfile.ZipFile(path, 'w') as container:
            for name, content in members:
                container.writestr(name, content)
        return path

    def test_valid_zip_reuse_and_mutation_detection(self):
        archive = self.make_zip([('session/a.txt', b'original')])
        asset = self.asset(archive); target = self.root / 'extracted' / 'sample'
        self.assertEqual(prepare.extract_asset(archive, target, asset), 'extracted_verified')
        self.assertEqual(prepare.extract_asset(archive, target, asset), 'verified_extraction_cache')
        (target / 'session/a.txt').write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            prepare.extract_asset(archive, target, asset)
        self.assertEqual((target / 'session/a.txt').read_bytes(), b'modified')

    def test_tar_regular_files_and_directories(self):
        archive = self.root / 'input.tar.gz'
        with tarfile.open(archive, 'w:gz') as container:
            directory = tarfile.TarInfo('folder'); directory.type = tarfile.DIRTYPE
            container.addfile(directory)
            entry = tarfile.TarInfo('folder/data'); entry.size = 3
            container.addfile(entry, io.BytesIO(b'123'))
        target = self.root / 'target'
        prepare.extract_asset(archive, target, self.asset(archive))
        self.assertEqual((target / 'folder/data').read_bytes(), b'123')

    def test_path_traversal_and_windows_escapes_rejected_before_write(self):
        for name in ('../escape', '/absolute', 'C:/escape', r'folder\escape', 'a/../../escape',
                     'a/./b', 'a//b', 'CON.txt', 'name. ', '.prepared.json'):
            with self.subTest(name=name):
                archive = self.make_zip([(name, b'not allowed')])
                target = self.root / 'target'
                with self.assertRaises(ValueError):
                    prepare.extract_asset(archive, target, self.asset(archive))
                self.assertFalse(target.exists())
                self.assertFalse((self.root.parent / 'escape').exists())

    def test_zip_symlink_rejected(self):
        archive = self.root / 'links.zip'
        with zipfile.ZipFile(archive, 'w') as container:
            entry = zipfile.ZipInfo('link'); entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            container.writestr(entry, '../outside')
        with self.assertRaisesRegex(ValueError, 'links/special'):
            prepare.extract_asset(archive, self.root / 'out', self.asset(archive))

    def test_tar_hardlink_rejected(self):
        archive = self.root / 'links.tar'
        with tarfile.open(archive, 'w') as container:
            entry = tarfile.TarInfo('link'); entry.type = tarfile.LNKTYPE; entry.linkname = '../outside'
            container.addfile(entry)
        with self.assertRaisesRegex(ValueError, 'links/special'):
            prepare.extract_asset(archive, self.root / 'out', self.asset(archive))

    def test_case_collision_and_file_parent_collision_rejected(self):
        for members in ([('A.txt', b'a'), ('a.txt', b'b')], [('folder', b'a'), ('folder/a', b'b')],
                        [('A/file', b'a'), ('a/other', b'b')]):
            archive = self.make_zip(members)
            with self.assertRaises(ValueError):
                prepare.extract_asset(archive, self.root / 'out', self.asset(archive))

    def test_quota_checked_before_extracting(self):
        archive = self.make_zip([('a', b'12345')])
        with mock.patch.object(prepare, 'MAX_UNPACKED', 4):
            with self.assertRaisesRegex(ValueError, 'limit'):
                prepare.extract_asset(archive, self.root / 'out', self.asset(archive))
        self.assertFalse((self.root / 'out').exists())

    def test_unexpected_file_and_unprepared_directory_rejected(self):
        archive = self.make_zip([('a', b'123')]); asset = self.asset(archive)
        target = self.root / 'out'; target.mkdir(); (target / 'owned').write_text('retain')
        with self.assertRaisesRegex(ValueError, 'receipt'):
            prepare.extract_asset(archive, target, asset)
        self.assertEqual((target / 'owned').read_text(), 'retain')
        target2 = self.root / 'other'; prepare.extract_asset(archive, target2, asset)
        (target2 / 'unexpected').write_text('retain')
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            prepare.verify_extraction(target2, asset)

    def test_cached_download_wrong_hash_preserved_and_offline_never_networks(self):
        downloads = self.root / 'downloads'; downloads.mkdir()
        archive = downloads / 'sample.zip'; archive.write_bytes(b'good')
        asset = self.asset(archive)
        archive.write_bytes(b'evil')
        with mock.patch.object(prepare.urllib.request, 'urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                prepare.obtain_asset(asset, downloads, offline=False)
            network.assert_not_called()
        self.assertEqual(archive.read_bytes(), b'evil')
        archive.unlink()
        with mock.patch.object(prepare.urllib.request, 'urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'offline mode'):
                prepare.obtain_asset(asset, downloads, offline=True)
            network.assert_not_called()

    def test_download_oversize_never_promoted(self):
        source = self.root / 'tiny'; source.write_bytes(b'a'); asset = self.asset(source)
        response = io.BytesIO(b'too large'); response.geturl = lambda: asset['url']
        downloads = self.root / 'downloads'
        with mock.patch.object(prepare.urllib.request, 'urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'exceeds manifest'):
                prepare.obtain_asset(asset, downloads)
        self.assertFalse((downloads / asset['name']).exists())
        self.assertEqual(len(list(downloads.glob('*.partial-*'))), 1)

    def test_git_tree_data_root_rejected(self):
        git = self.root / 'checkout'; git.mkdir(); (git / '.git').mkdir()
        with self.assertRaisesRegex(ValueError, 'outside every Git'):
            prepare.validate_data_root(git / 'raw')
        self.assertEqual(prepare.validate_data_root(self.root / 'data'), self.root / 'data')

    @unittest.skipIf(sys.platform == 'win32', 'creating symlinks may require Windows developer mode')
    def test_controlled_directories_must_not_be_symlinks(self):
        archive = self.make_zip([('a', b'123')]); asset = self.asset(archive)
        outside = self.root / 'outside'; outside.mkdir()
        downloads = self.root / 'downloads'; downloads.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            prepare.obtain_asset(asset, downloads, offline=True)
        extracted = self.root / 'extracted'; extracted.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            prepare.extract_asset(archive, extracted / 'sample', asset)
        self.assertEqual(list(outside.iterdir()), [])

    def test_manifest_duplicate_and_bad_hash_rejected(self):
        archive = self.make_zip([('a', b'1')]); asset = self.asset(archive)
        path = self.root / 'manifest.json'
        for assets in ([asset, asset], [dict(asset, sha256='bad')]):
            path.write_text(json.dumps({'schema_version': 1, 'assets': assets}))
            with self.assertRaises(ValueError):
                prepare.load_manifest(path)


if __name__ == '__main__':
    unittest.main()
