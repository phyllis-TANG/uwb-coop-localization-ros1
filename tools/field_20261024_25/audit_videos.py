#!/usr/bin/env python3
"""Audit verified extracted video files; does not create calibrated reference truth."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys

import prepare


def check_video(path, full_decode=False):
    path = Path(path)
    result = {'filename': path.name, 'sha256': prepare.sha256_file(path), 'size_bytes': path.stat().st_size}
    probe = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=codec_name,width,height,r_frame_rate,avg_frame_rate,time_base,nb_frames,duration:stream_side_data=rotation:format=duration,size',
        '-of', 'json', str(path)], capture_output=True, text=True)
    result['probe_returncode'] = probe.returncode
    if probe.returncode:
        result.update(status='failed', error=probe.stderr.strip())
        return result
    try:
        metadata = json.loads(probe.stdout)
        if not metadata.get('streams'):
            raise ValueError('no video stream')
        result['metadata'] = metadata
    except (ValueError, TypeError) as error:
        result.update(status='failed', error='invalid ffprobe video metadata: ' + str(error))
        return result
    result['decode_status'] = 'pending'
    result['status'] = 'metadata_passed_decode_pending'
    if full_decode:
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '2', '-i', str(path),
                                  '-map', '0:v:0', '-an', '-f', 'null', '-'], capture_output=True, text=True)
        result.update(decode_returncode=decoded.returncode, decode_stderr=decoded.stderr)
        passed = decoded.returncode == 0 and not decoded.stderr.strip()
        result['decode_status'] = 'passed' if passed else 'failed'
        result['status'] = 'file_health_passed' if passed else 'failed'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=prepare.DEFAULT_MANIFEST)
    parser.add_argument('--data-root', required=True)
    parser.add_argument('--assets', nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True, help='fresh result directory; writes video_qc.json')
    parser.add_argument('--full-decode', action='store_true', help='decode every video frame using ffmpeg -xerror')
    args = parser.parse_args(argv)
    try:
        manifest = prepare.load_manifest(args.manifest)
        assets = {a['id']: a for a in manifest['assets']}
        if not set(args.assets).issubset(assets) or len(set(args.assets)) != len(args.assets):
            raise ValueError('unknown or repeated asset IDs')
        root = prepare.validate_data_root(args.data_root)
        output = args.output.expanduser().resolve()
        target = output / 'video_qc.json'
        if target.exists() or target.is_symlink():
            raise ValueError('video_qc.json already exists; choose a fresh --output')
        if shutil.which('ffprobe') is None or (args.full_decode and shutil.which('ffmpeg') is None):
            raise ValueError('ffprobe is required; --full-decode also requires ffmpeg on PATH')
        # Validate every selected input before creating outputs or running media tools.
        sources = []
        for asset_id in args.assets:
            asset = assets[asset_id]
            prepare.verify_download(root / 'downloads' / asset['name'], asset)
            directory = root / 'extracted' / asset['extract_subdir']
            receipt = prepare.verify_extraction(directory, asset)
            videos = [directory / item['path'] for item in receipt['files']
                      if Path(item['path']).suffix.lower() in ('.mov', '.mp4', '.m4v')
                      and '__MACOSX' not in Path(item['path']).parts]
            if not videos:
                raise ValueError('no video file in selected asset: ' + asset_id)
            sources.append((asset_id, asset, videos))
        rows = []
        for asset_id, asset, videos in sources:
            for path in videos:
                try:
                    result = check_video(path, args.full_decode)
                except (OSError, ValueError) as error:
                    result = {'filename': path.name, 'status': 'failed', 'error': str(error)}
                result.update(asset_id=asset_id, archive_sha256=asset['sha256'])
                rows.append(result)
                print(asset_id + '/' + path.name + ': ' + result['status'], flush=True)
        report = {
            'schema_version': 1,
            'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'manifest_sha256': prepare.sha256_file(args.manifest),
            'full_decode_requested': args.full_decode,
            'videos': rows,
            'reference_grade': 'not_evaluated',
            'limitations': ['File integrity/decoding is not spatial or temporal accuracy acceptance.',
                            'Nominal frame rate is not a substitute for actual per-frame PTS.',
                            'Marker detection, lens calibration, per-clip room pose and synchronization remain separate tasks.']}
        output.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
        return 1 if any(r['status'] == 'failed' for r in rows) else 0
    except Exception as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
