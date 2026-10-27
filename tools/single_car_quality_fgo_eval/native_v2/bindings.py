"""Link graph/publication/CSV and original scalar/message SHA sidecars."""
import argparse
import csv
import gzip
import json
from pathlib import Path
from .common import begin,finish,lines,require,sha,write,write_lines


def publication_binding(graphs,pubs,csvrows):
    by={r['record_id']:r for r in graphs};require(len(pubs)==len(csvrows),'CSV/publication count differs');require(len({r['publication_id'] for r in csvrows})==len(csvrows),'duplicate CSV publication')
    for pub,c in zip(pubs,csvrows):
        require(pub['graph_record_id'] in by,'publication references absent graph');g=by[pub['graph_record_id']];require(g['role']=='main' and g['state_epoch_ns']==pub['state_epoch_ns'] and g['row']==pub['row'],'published state differs from solved main graph')
        require(c['publication_id']==pub['publication_id'] and c['state_epoch_ns']==str(pub['state_epoch_ns']) and c['availability_cutoff_epoch_ns']==str(pub['availability_cutoff_epoch_ns']),'CSV publication/state binding')
        r=pub['row'];values=dict(base_x_m=r['pose'][0],base_y_m=r['pose'][1],yaw_rad=r['pose'][2],antenna_x_m=r['antenna_xy_m'][0],antenna_y_m=r['antenna_xy_m'][1],bias_rad_s=r['bias_rad_s'])
        for k,x in values.items():require(c[k]=='' if x is None else abs(float(c[k])-x)<1e-14,'CSV numerical value differs '+k)
        require(c['status']==r['status'] and c['estimate_valid']==str(r['estimate_valid']),'CSV status/validity differs')
    return len(pubs)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--performance',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_publication_CSV_and_original_scalar_message_binding')
    try:
        receipts=[];resolved=[]
        for case in ('004023','005135'):
            ready=a.prepared/'stage1/ready_for_A_001'/case;catalog=json.loads(gzip.open(ready/'scalar_catalog.json.gz','rt').read());lookup={}
            for scalar_id,row in catalog.items():
                if row['kind']=='uwb_component' and not row['ambiguous_link_in_frame']:lookup[row['source_file_sha256'],row['record_index'],row['topic'],row['link_id']]=(scalar_id,row)
            for group in ('Q0','Q1','Q2','Q3'):
                d=a.performance/(case+'_'+group);pubs=lines(d/'publications.jsonl.gz');graphs=lines(d/'graphs.jsonl.gz');count=publication_binding(graphs,pubs,list(csv.DictReader((d/'published.csv').open())));factor_count=0
                for factor in lines(d/'quality_ledger.jsonl.gz'):
                    scalars=[]
                    for dep in factor['target_dependencies']:
                        ident=dep['identity'];scalar_id,row=lookup[ident['source_file_sha256'],ident['record_index'],ident['topic'],factor['target']];require(row['component_value']==dep['raw_range_m'] and row['header_epoch_ns']==ident['header_epoch_ns'] and row['receive_epoch_ns']==ident['receive_epoch_ns'],'scalar sidecar original binding mismatch');scalars.append(dict(catalog_id=scalar_id,original_message_sha256=row['raw_message_sha256']))
                    resolved.append(dict(case_id=case,group=group,factor_id=factor['factor_id'],target=factor['target'],state_epoch_ns=factor['state_epoch_ns'],catalog_sha256=sha(ready/'scalar_catalog.json.gz'),support=scalars));factor_count+=1
                receipts.append(dict(case_id=case,group=group,published_graph_CSV_bound=count,quality_factors_with_original_scalar_mapping=factor_count))
        write_lines(a.output/'resolved_constraints.jsonl.gz',resolved);write(a.output/'verification.json',dict(status='PASS',checks=receipts,resolved_constraints=len(resolved),original_scalar_support_references=sum(len(r['support']) for r in resolved),native_A_metadata_not_fabricated=True,new_estimator_runs=0));finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
