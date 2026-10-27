"""Project verified PR59 identities into scalar catalog for quality auditors.

A UWB message contains several links: same message SHA/record_index can support
multiple distinct scalar components. No opaque full-UWB-message leaf is allowed
in a target-excluded shadow's dependency closure.
"""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
from evidence import begin,finish,require,sha,write


def project(row):
    base={k:row[k] for k in ('case_id','source_file_sha256','record_index','topic','header_epoch_ns','receive_epoch_ns','raw_message_sha256')}
    for key in ('record_index','receive_epoch_ns'):require(type(base[key]) is int,'integer input identity')
    prefix=base['source_file_sha256']+':'+str(base['record_index'])
    if row['kind']=='uwb':
        groups=Counter(x['anchor_id'] for x in row['message']['ranges']);items=[]
        for i,item in enumerate(row['message']['ranges']):
            v=dict(base,kind='uwb_component',component_key='ranges['+str(i)+'].range',link_id=item['anchor_id'],component_value=item['range'],ambiguous_link_in_frame=groups[item['anchor_id']]!=1)
            items.append((prefix+':'+v['component_key'],v))
        return items
    if row['kind'] in ('odom','imu'):return [(prefix+':'+row['kind'],dict(base,kind=row['kind'],link_id=None,component_key=row['kind'],component_value=None))]
    return []


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reused',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_quality_scalar_catalog_not_new_export')
    try:
        manifest=json.loads((a.reused/'reuse_manifest.json').read_text());require(manifest['status']=='PASS','reuse not verified');cases=[]
        for case in ('004023','005135'):
            catalog={};counts=Counter();path=a.reused/'inputs'/case/'events.jsonl.gz';rows=0
            with gzip.open(path,'rt') as f:
                for line in f:
                    row=json.loads(line);require(row['case_id']==case,'case isolation');rows+=1
                    for key,item in project(row):require(key not in catalog,'duplicate scalar identity');catalog[key]=item;counts[item['kind']]+=1
            target=a.output/(case+'_catalog.json.gz')
            with target.open('xb') as f,gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as z:z.write(json.dumps(catalog,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
            cases.append(dict(case_id=case,original_records=rows,projected_kinds=dict(counts),catalog_sha256=sha(target),catalog_file=target.name,source_rich_packet_sha256=sha(path)))
        write(a.output/'index.json',dict(status='DONE',cases=cases,all_original_fields_remain_in_reused_packet=True,original_normalization_not_redeveloped=True,manual_endpoint_or_window_in_catalog=False,
          projection='message identity plus scalar field path. A full UWB frame cannot be treated as a link-free source just because its shared message contains other anchors. Unused Odom/IMU values remain in rich packet, not invented here.'))
        v['inputs']=[dict(path=str(a.reused/'reuse_manifest.json'),sha256=sha(a.reused/'reuse_manifest.json'))];finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
