#!/usr/bin/env python3
"""Fetch verified field assets and extract them without touching a ROS system.

Python 3.8+, standard library only. Raw data must remain outside a Git worktree.
Existing downloads or extraction trees are checked, never silently overwritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO / 'docs/field_tests/20261024_25/manifest.json'
RECEIPT = '.prepared.json'
MAX_MEMBERS = 20000
MAX_UNPACKED = 20 * 1024 ** 3
BLOCK = 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(BLOCK), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_data_root(value):
    path = Path(value).expanduser().resolve()
    # Check all ancestors, including a .git file used by Git worktrees.
    if any((parent / '.git').exists() for parent in [path] + list(path.parents)):
        raise ValueError('data root must be outside every Git worktree: ' + str(path))
    return path


def load_manifest(path):
    manifest = json.loads(Path(path).read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1:
        raise ValueError('unsupported manifest schema_version')
    assets = manifest.get('assets')
    if not isinstance(assets, list) or not assets:
        raise ValueError('manifest assets must be a nonempty list')
    seen_ids, seen_names = set(), set()
    for asset in assets:
        for key in ('id', 'name', 'url', 'sha256', 'size_bytes', 'extract_subdir'):
            if key not in asset:
                raise ValueError('asset missing ' + key)
        for key in ('id', 'name', 'extract_subdir'):
            if safe_relative(asset[key]).as_posix() != asset[key] or '/' in asset[key]:
                raise ValueError('asset ' + key + ' must be a simple filename/component')
        if asset['id'] in seen_ids or asset['name'].casefold() in seen_names:
            raise ValueError('duplicate asset id or filename')
        seen_ids.add(asset['id']); seen_names.add(asset['name'].casefold())
        if len(asset['sha256']) != 64 or any(c not in '0123456789abcdef' for c in asset['sha256']):
            raise ValueError('invalid SHA256 for ' + asset['id'])
        if not isinstance(asset['size_bytes'], int) or asset['size_bytes'] <= 0:
            raise ValueError('invalid byte size for ' + asset['id'])
        if urllib.parse.urlparse(asset['url']).scheme != 'https':
            raise ValueError('asset URL must use HTTPS')
    return manifest


def safe_relative(name):
    """Reject POSIX and Windows escapes even on a POSIX host."""
    if not isinstance(name, str) or not name or '\x00' in name or '\\' in name or ':' in name:
        raise ValueError('unsafe archive/asset name: ' + repr(name))
    path = PurePosixPath(name)
    parts = path.parts
    if path.is_absolute() or not parts or any(p in ('.', '..') for p in parts):
        raise ValueError('unsafe archive/asset path: ' + repr(name))
    for part in parts:
        if part.endswith((' ', '.')):
            raise ValueError('ambiguous Windows archive name: ' + repr(name))
        if part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL'} | {
                prefix + str(i) for prefix in ('COM', 'LPT') for i in range(1, 10)}:
            raise ValueError('reserved Windows archive name: ' + repr(name))
    if path.as_posix() != name.rstrip('/'):
        raise ValueError('noncanonical archive path: ' + repr(name))
    return path


def verify_download(path, asset):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('download must be a regular file: ' + str(path))
    if path.stat().st_size != asset['size_bytes']:
        raise ValueError('existing download size mismatch; preserved: ' + str(path))
    actual = sha256_file(path)
    if actual != asset['sha256']:
        raise ValueError('existing download SHA256 mismatch; preserved: ' + str(path))
    return actual


def obtain_asset(asset, downloads, offline=False):
    if downloads.is_symlink():
        raise ValueError('downloads directory must not be a symlink')
    downloads.mkdir(parents=True, exist_ok=True)
    destination = downloads / asset['name']
    if destination.exists() or destination.is_symlink():
        verify_download(destination, asset)
        return destination, 'verified_cache'
    if offline:
        raise ValueError('offline mode: required download missing: ' + str(destination))
    # A failed transfer is kept under a unique partial name, never mistaken for
    # the canonical download and never overwriting an earlier partial transfer.
    fd, temporary = tempfile.mkstemp(prefix=asset['name'] + '.partial-', dir=str(downloads))
    temporary = Path(temporary)
    try:
        request = urllib.request.Request(asset['url'], headers={'User-Agent': 'uwb-field-intake/1'})
        with os.fdopen(fd, 'wb') as output, urllib.request.urlopen(request, timeout=30) as response:
            if urllib.parse.urlparse(response.geturl()).scheme != 'https':
                raise ValueError('refusing HTTPS downgrade')
            count = 0
            while True:
                chunk = response.read(BLOCK)
                if not chunk:
                    break
                count += len(chunk)
                if count > asset['size_bytes']:
                    raise ValueError('download exceeds manifest byte size')
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        verify_download(temporary, asset)
        if destination.exists() or destination.is_symlink():
            raise ValueError('download destination appeared during transfer; partial preserved')
        temporary.rename(destination)
        return destination, 'downloaded_verified'
    except Exception as error:
        raise ValueError('transfer failed; partial preserved at %s: %s' % (temporary, error)) from error


def _validate_members(members):
    """members contains (name, size, is_directory); validate before any write."""
    if len(members) > MAX_MEMBERS or sum(x[1] for x in members) > MAX_UNPACKED:
        raise ValueError('archive exceeds member/unpacked-size limit')
    names, kinds, prefixes = {}, {}, {}
    for name, size, directory in members:
        rel = safe_relative(name)
        if rel.as_posix() == RECEIPT or size < 0:
            raise ValueError('reserved receipt path or negative archive size')
        folded = rel.as_posix().casefold()
        if folded in names:
            raise ValueError('duplicate or case-colliding archive path: ' + name)
        names[folded] = rel.as_posix(); kinds[folded] = directory
        for index in range(1, len(rel.parts) + 1):
            prefix = PurePosixPath(*rel.parts[:index]).as_posix()
            key = prefix.casefold()
            if key in prefixes and prefixes[key] != prefix:
                raise ValueError('case-colliding archive parent: ' + name)
            prefixes[key] = prefix
    for folded in names:
        parents = PurePosixPath(folded).parents
        if any(str(parent) in kinds and not kinds[str(parent)] for parent in parents):
            raise ValueError('archive file is also a parent directory')


def _copy_member(source, path, expected_size):
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(); count = 0
    with path.open('xb') as output:
        while True:
            chunk = source.read(BLOCK)
            if not chunk:
                break
            count += len(chunk)
            if count > expected_size:
                raise ValueError('archive member exceeds declared size')
            output.write(chunk); digest.update(chunk)
    if count != expected_size:
        raise ValueError('archive member shorter than declared size')
    return {'path': path, 'size_bytes': count, 'sha256': digest.hexdigest()}


def verify_extraction(destination, asset):
    destination = Path(destination)
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError('extraction destination is not a regular directory')
    receipt_path = destination / RECEIPT
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ValueError('existing extraction has no trusted receipt; preserved: ' + str(destination))
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt.get('archive_sha256') != asset['sha256'] or receipt.get('asset_id') != asset['id']:
        raise ValueError('existing extraction receipt does not match manifest')
    expected = set()
    for item in receipt.get('files', []):
        rel = safe_relative(item['path']); path = destination.joinpath(*rel.parts)
        if path.is_symlink() or not path.is_file() or any(p.is_symlink() for p in path.parents if p != destination.parent):
            raise ValueError('missing or symlinked extracted file: ' + str(path))
        if path.stat().st_size != item['size_bytes'] or sha256_file(path) != item['sha256']:
            raise ValueError('extracted file hash mismatch; preserved: ' + str(path))
        expected.add(rel.as_posix())
    actual = set()
    for path in destination.rglob('*'):
        if path.is_symlink():
            raise ValueError('symlink in extracted tree: ' + str(path))
        if path.is_file() and path != receipt_path:
            actual.add(path.relative_to(destination).as_posix())
    if actual != expected:
        raise ValueError('unexpected or missing files in extracted tree')
    return receipt


def extract_asset(archive, destination, asset):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        verify_extraction(destination, asset)
        return 'verified_extraction_cache'
    if destination.parent.is_symlink():
        raise ValueError('extracted directory must not be a symlink')
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.' + asset['id'] + '.extract-', dir=str(destination.parent)))
    files = []
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as container:
                entries = container.infolist()
                for entry in entries:
                    mode = (entry.external_attr >> 16) & 0o170000
                    if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                        raise ValueError('archive links/special files are forbidden: ' + entry.filename)
                _validate_members([(e.filename, e.file_size, e.is_dir()) for e in entries])
                for entry in entries:
                    path = staging.joinpath(*safe_relative(entry.filename).parts)
                    if entry.is_dir():
                        path.mkdir(parents=True, exist_ok=True)
                    else:
                        with container.open(entry) as source:
                            files.append(_copy_member(source, path, entry.file_size))
        elif tarfile.is_tarfile(archive):
            with tarfile.open(archive, 'r:*') as container:
                entries = container.getmembers()
                if any(not (e.isfile() or e.isdir()) for e in entries):
                    raise ValueError('archive links/special files are forbidden')
                _validate_members([(e.name, e.size, e.isdir()) for e in entries])
                for entry in entries:
                    path = staging.joinpath(*safe_relative(entry.name).parts)
                    if entry.isdir():
                        path.mkdir(parents=True, exist_ok=True)
                    else:
                        with container.extractfile(entry) as source:
                            files.append(_copy_member(source, path, entry.size))
        else:
            return 'not_an_archive'
        records = [dict(path=x['path'].relative_to(staging).as_posix(), size_bytes=x['size_bytes'], sha256=x['sha256']) for x in files]
        receipt = {'schema_version': 1, 'asset_id': asset['id'], 'archive_sha256': asset['sha256'], 'files': records}
        (staging / RECEIPT).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        if destination.exists() or destination.is_symlink():
            raise ValueError('extraction destination appeared; will not overwrite')
        staging.rename(destination)
        return 'extracted_verified'
    finally:
        if staging.exists():
            shutil.rmtree(staging)  # Only our newly-created staging tree.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--data-root', required=True, help='data directory outside all Git worktrees')
    parser.add_argument('--assets', nargs='+', required=True, help='manifest asset IDs, e.g. bags camera_reference T08_video')
    parser.add_argument('--extract', action='store_true', help='extract verified archives into extracted/<asset_id>')
    parser.add_argument('--offline', action='store_true', help='require cached files; never use network')
    args = parser.parse_args(argv)
    lock = None
    try:
        manifest = load_manifest(args.manifest)
        assets = {a['id']: a for a in manifest['assets']}
        unknown = set(args.assets) - set(assets)
        if unknown or len(set(args.assets)) != len(args.assets):
            raise ValueError('unknown or repeated asset IDs: ' + ', '.join(sorted(unknown)))
        data_root = validate_data_root(args.data_root)
        data_root.mkdir(parents=True, exist_ok=True)
        candidate = data_root / '.prepare.lock'
        try:
            candidate.mkdir()  # Atomic process lock; an existing lock is never removed.
        except FileExistsError as error:
            raise ValueError('preparation lock exists: %s; confirm no other prepare process is active before removing an interrupted run\'s empty lock directory' % candidate) from error
        lock = candidate
        for asset_id in args.assets:
            asset = assets[asset_id]
            archive, state = obtain_asset(asset, data_root / 'downloads', args.offline)
            result = {'asset_id': asset_id, 'download': state, 'sha256': asset['sha256']}
            if args.extract:
                result['extraction'] = extract_asset(archive, data_root / 'extracted' / asset['extract_subdir'], asset)
            print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    except Exception as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1
    finally:
        if lock is not None:
            lock.rmdir()


if __name__ == '__main__':
    sys.exit(main())
