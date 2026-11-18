"""Verified state-time records, queued readiness and retrospective error."""
import csv
from monitor import *

def save_csv(name,rows):
    with (D/name).open('w') as f:
        w=csv.DictWriter(f,rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)

def assess():
    E,A,I=modules()
    events=read(D/'events.json');truth=read(D/'evaluation_xyz.json')
    services={(s['case'],s['method']):s for s in read(D/'services.json')}
    clocks={};rows=[];repro=[];requests=[]
    for e in events:
        key=e['case'];state=F(str(e['state_s']));pub=state+F(str(e['fix_latency_s']))
        for method in ['P4','N4']:
            queue=(e['route'],e['condition'],method)
            service=services[key,method]; start=max(pub,clocks.get(queue,pub))
            ready=start+F(str(service['region_wall_s']));clocks[queue]=ready
            payload=read(D/'certificates'/(key+'_'+method+'.json.gz'))
            x,c=payload['original'],payload['certificate']
            pos=truth[key];points=[F(v) for p in pos for v in p[:2]]
            keep=[n for n in c['nodes'] if n['kind'] in ('INSIDE','PENDING','UNDECIDED')]
            joint=any(all(F(a)<=v<=F(b) for v,(a,b) in zip(points,n['box'])) for n in keep)
            hits=[]
            for k,car in enumerate('ps'):
                xy=e['published_xy'][k];source=F(x['source_times'][car]);offset=source-state
                err2=sum((F(v)-p)**2 for v,p in zip(xy,points[2*k:2*k+2]))
                radius=F(service['PL'][k])
                carhit=any(all(F(a)<=v<=F(b) for v,(a,b) in zip(points[2*k:2*k+2],r['box'])) for r in c['projections'][car]['rectangles'])
                hits.append(carhit)
                assert not carhit or err2<=radius**2
                for al in AL:
                    public=dict(case=key,seed=2026111801,car=car,state_time=str(source),estimate_xy=xy,
                                decision_ready_time=str(ready+offset),AL=al,as_of=str(ready+offset),
                                deadline=str(source+2),valid_until=str(source+2),published_at=str(pub+offset),
                                input_hash=x['input_hash'],frame=x['frame'],mode=c['mode'])
                    dec=I.decide(public,x,c)
                    requests.append(dict(publication=public,decision=dec,
                                         evidence='certificates/'+key+'_'+method+'.json.gz'))
                    if dec['PL'] is not None:assert F(dec['PL'])==radius
                    rows.append(dict(**dec,route=e['route'],condition=e['condition'],index=e['i'],method=method,
                         scene_state_s=float(state),source_p_s=e['source_p_s'],source_s_s=e['source_s_s'],observation_available_s=float(state),scene_published_s=float(pub),
                         scene_ready_s=float(ready),declared_available_s=float(ready) if dec['available'] else None,service_s=service['region_wall_s'],
                         queue_wait_s=float(start-pub),latency_s=float(ready-state),late=ready>state+2,miss_next_tick=ready>state+F(str(e['dt'])),
                         retrospective_PL_m=float(radius),error_m=math.sqrt(float(err2)),covered=err2<=radius**2,car_hit=carhit,joint_hit=joint,resolution=service['resolution']))
            if e['old']:
                base=read(CACHE/OLD/SLANT/'results'/(key+'_'+method)/'receipt.json')['row']
                assert [joint,*hits,service['resolution']]==[base[f] for f in ('joint_hit','p_hit','s_hit','resolution_met')]
                repro.append(dict(case=key,method=method,tree_queue_projections_equal=True,joint_hit=joint,p_hit=hits[0],s_hit=hits[1],resolution=service['resolution']))
    dump(D/'publication_decisions.json.gz',requests)
    save_csv('availability.csv',rows);save_csv('replication.csv',repro)
    # Latest arrived, unexpired certificate at each actual publication tick.
    delivery=[]
    groups={}
    for r in rows:groups.setdefault((r['route'],r['condition'],r['method'],r['car'],r['AL']),[]).append(r)
    for group,records in groups.items():
        for tick in records:
            now=tick['scene_state_s']
            arrived=[r for r in records if r['scene_ready_s']<=now<=r['scene_state_s']+2]
            latest=max(arrived,key=lambda r:r['index']) if arrived else None
            delivery.append(dict(zip(('route','condition','method','car','AL'),group),scene_query_s=now,
                        available=bool(latest and latest['available']),matched_index=latest['index'] if latest else None,
                        reason=latest['reason'] if latest else 'NO_ARRIVED_UNEXPIRED_DECISION'))
    save_csv('delivery_ticks.csv',delivery)

if __name__=='__main__':assess()
