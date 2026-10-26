"""Serial verified intake using the existing safe extractor; never edits common manifest."""
import argparse
import datetime as dt
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import urllib.request
import zipfile
import download_ranges

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'field_20261024_25'))
import prepare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release-snapshot', required=True, type=Path)
    p.add_argument('--manifest', type=Path, default=prepare.DEFAULT_MANIFEST)
    p.add_argument('--data-root', required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--proxy')
    p.add_argument('--assets', nargs='+', required=True)
    args = p.parse_args()
    if args.proxy:
        urllib.request.install_opener(urllib.request.build_opener(
            urllib.request.ProxyHandler({'http': args.proxy, 'https': args.proxy})))
    root = prepare.validate_data_root(args.data_root)
    args.output.mkdir(parents=True, exist_ok=False)
    snapshot = json.loads(args.release_snapshot.read_text(encoding='utf-8'))
    manifest = prepare.load_manifest(args.manifest)
    assets = {a['id']: dict(a) for a in manifest['assets']}
    release = {a['name']: a for a in snapshot['assets']}
    for exp in ('T14', 'T15'):
        r = release[exp + '.zip']
        assets[exp + '_video'] = dict(id=exp+'_video', name=r['name'],
            url=r['url'], sha256=r['sha256'], size_bytes=r['size_bytes'],
            extract_subdir=exp+'_video', archive_format='zip',
            status='release_metadata_only_until_local_verification')
    manifest['assets'] = list(assets.values())
    overlay = args.output / 'manifest_overlay.json'
    overlay.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    # All data-root mutations happen in this single process under one lock.
    root.mkdir(parents=True, exist_ok=True)
    lock = root / '.prepare.lock'
    lock.mkdir()
    results = []
    try:
        for asset_id in args.assets:
            a = assets[asset_id]
            r = release[a['name']]
            if (r['sha256'], r['size_bytes']) != (a['sha256'], a['size_bytes']):
                raise ValueError('Release and base manifest differ for '+asset_id)
            print('START '+asset_id, flush=True)
            downloads = root/'downloads'
            downloads.mkdir(parents=True, exist_ok=True)
            archive = downloads/a['name']
            if archive.exists():
                prepare.verify_download(archive, a)
                download = 'verified_cache'
            else:
                archive = download_ranges.download(a,downloads,args.proxy)
                download = 'bounded_ranges_downloaded_verified'
            crc = None
            if a.get('archive_format') == 'zip':
                with zipfile.ZipFile(archive) as z:
                    bad = z.testzip()
                    if bad is not None:
                        raise ValueError('CRC failure: '+bad)
                    crc = 'passed_all_members'
            extraction = prepare.extract_asset(archive, root/'extracted'/a['extract_subdir'], a)
            receipt = prepare.verify_extraction(root/'extracted'/a['extract_subdir'], a)
            row = dict(asset_id=asset_id, archive=a['name'], archive_sha256=a['sha256'],
                size_bytes=a['size_bytes'], download=download, crc=crc,
                extraction=extraction, receipt=receipt,
                checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
            target = args.output/(asset_id+'.json')
            target.write_text(json.dumps(row, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
            results.append(row)
            print('PASS '+asset_id+' '+a['sha256'], flush=True)
    finally:
        lock.rmdir()
        (args.output/'intake_results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
