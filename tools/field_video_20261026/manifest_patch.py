"""Produce a coordinator-owned manifest proposal without editing public inputs."""
import argparse
import copy
import difflib
import hashlib
import json
from pathlib import Path
import common


def propose(base,assets,qcs):
    result=copy.deepcopy(base)
    by_id={a['id']:a for a in result['assets']}
    for exp in ['T11','T12','T13','T14','T15']:
        aid=exp+'_video';intake=assets[aid];qc=qcs[aid]
        if qc['decode_status']!='passed' or intake['crc']!='passed_all_members':
            raise ValueError('Intake/decode gate not passed: '+aid)
        asset=by_id.get(aid)
        if asset is None:
            asset=dict(id=aid,name=intake['archive'],
                url='https://github.com/phyllis-TANG/uwb-coop-localization-ros1/releases/download/field-data-20261025/'+intake['archive'],
                sha256=intake['archive_sha256'],size_bytes=intake['size_bytes'],extract_subdir=aid,archive_format='zip')
            result['assets'].append(asset)
        asset.update(status='independently_hash_crc_and_full_decode_verified',
            sha256_source='independently_recomputed_original_download_bytes')
        movie=dict(experiment_id=exp,asset_id=aid,relative_path=qc['relative_path'],sha256=qc['sha256'],
            size_bytes=qc['size_bytes'],duration_s=qc['duration_s'],encoded_width=qc['encoded_width'],
            encoded_height=qc['encoded_height'],declared_frames=qc['declared_frames'],decoded_frames=qc['decoded_frames'],
            rotation_ccw_deg=qc['rotation'],full_decode_status='passed',
            experiment_mapping_source='operator_archive_label_not_independent_action_identity',
            motion_coverage_status='separate_event_audit_required',bag_time_mapping_status='not_accepted',use_frame_pts=True)
        result['motion_videos']=[v for v in result['motion_videos'] if v['asset_id']!=aid]+[movie]
    result['pending_videos']=[v for v in result.get('pending_videos',[]) if v['experiment_id'] not in ['T14','T15']]
    result['pending_qc_video_assets']=[v for v in result.get('pending_qc_video_assets',[]) if v['asset_id'] not in qcs]
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--intake',type=Path,required=True)
    p.add_argument('--media',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    raw=a.base.read_bytes();text=a.base.read_text(encoding='utf-8');base=json.loads(text)
    assets={};qcs={}
    for exp in ['T11','T12','T13','T14','T15']:
        aid=exp+'_video';assets[aid]=json.loads((a.intake/(aid+'.json')).read_text(encoding='utf-8'))
        candidates=list(a.media.glob(aid+'__*/media_qc.json'))
        if len(candidates)!=1:raise ValueError('Expected exactly one original movie for '+aid)
        qcs[aid]=json.loads(candidates[0].read_text(encoding='utf-8'))
    result=propose(base,assets,qcs)
    operations=[]
    for key in ['assets','motion_videos','pending_videos','pending_qc_video_assets']:
        operations += [dict(op='test',path='/'+key,value=base[key]),dict(op='replace',path='/'+key,value=result[key])]
    document=dict(schema_version=1,base_commit='4a379da4044a5fd6d36cb8c3e2c53f4a7d120d5b',
        base_manifest_git_blob_sha=hashlib.sha1(b'blob '+str(len(text.encode())).encode()+b'\0'+text.encode()).hexdigest(),
        base_manifest_canonical_utf8_lf_sha256=hashlib.sha256(text.encode()).hexdigest(),
        checked_out_manifest_raw_sha256=hashlib.sha256(raw).hexdigest(),
        newline_note='Git for Windows checkout uses CRLF; canonical hash is UTF-8 LF Git content',
        status='proposal_for_coordinator_only',public_geometry_modified=False,rfc6902_operations=operations)
    common.write_json(a.output/'coordinator_manifest_patch.json',document)
    proposed=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    diff=''.join(difflib.unified_diff(text.splitlines(True),proposed.splitlines(True),
        fromfile='a/docs/field_tests/20261024_25/manifest.json',tofile='b/docs/field_tests/20261024_25/manifest.json'))
    (a.output/'manifest_proposal.diff').write_text(diff,encoding='utf-8')
    common.write_json(a.output/'new_video_identities.json',qcs)
    print(json.dumps({k:dict(name=v['relative_path'],frames=v['decoded_frames'],sha256=v['sha256']) for k,v in qcs.items()}),flush=True)


if __name__=='__main__':main()
