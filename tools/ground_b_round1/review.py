"""Read-only reconstruction of #143 decisions and vehicle-clock error episodes."""
import argparse
from bisect import bisect_right
import csv
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'docs/research/ground_continuous_b'
OUT = ROOT / 'docs/research/ground_b_round1/evaluation'
AL = .10
CUTOFF = 64.


def save(path, rows):
    with path.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0], lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def read_table(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt') as f:
        return list(csv.DictReader(f))


def select(rows):
    return [r for r in rows if r['view']=='delivery' and r['car']=='1'
            and r['method']=='B2' and float(r['AL_m'])==AL]


def reconstruct(folder):
    """Join the released estimate to current truth only on the evaluation side."""
    with gzip.open(folder/'records.json.gz','rt') as f:
        records=json.load(f)
    with gzip.open(folder/'truth.json.gz','rt') as f:
        truth=json.load(f)
    times=[]
    for r in records:
        times.append(max(r['cutoff'], times[-1] if times else 0.)+r['b2_cost'])
    rows=select(read_table(folder/'ticks.csv.gz'))
    assert len(rows)==len(truth)==1280
    for i,row in enumerate(rows):
        now=i/20
        assert float(row['time_s'])==now
        j=bisect_right(times,now)-1
        xy=None
        if j<0:
            status='STARTUP'
            assert row['state_s']==row['ready_s']==''
        else:
            r=records[j]
            assert (int(row['state_s']),float(row['ready_s']))==(r['t'],times[j])
            if times[j]>r['t']+2:
                status='LATE'
            elif now>r['t']+2:
                status='EXPIRED'
            else:
                xy=r['xy'][0]
                d=r['b2'][0]
                status='NO_DECISION'
                if r['pub_ready'] and d['computable']:
                    status='ALARM' if d['alarm'] else 'AVAILABLE'
        assert row['status']==status
        if xy is None:
            assert row['error_m']==row['x_m']==row['y_m']==''
        else:
            assert xy==[float(row['x_m']),float(row['y_m'])]
            assert math.isclose(math.dist(xy,truth[i][0]),float(row['error_m']),abs_tol=1e-12,rel_tol=0)
    return rows


def episodes(rows,cutoff):
    """One observed excursion; loss of position suspends observation until reacquisition."""
    current=None
    results=[]
    previous_status=None
    for r in rows:
        t=float(r['time_s'])
        status=r['status']
        error=float(r['error_m']) if r['error_m'] else None
        if current and error is not None and error<=AL:
            current.update(end_s=t,end_reason='OBSERVED_WITHIN_AL',recovery_status=status)
            results.append(current)
            current=None
        if current is None and error is not None and error>AL:
            current=dict(first_exceed_s=t,available_at_start=status=='AVAILABLE',status_at_start=status,
                         first_loss_of_availability_tick_s=None,first_expiry_tick_s=None,
                         first_available_again_tick_s=None,first_alarm_ready_s=None,first_alarm_tick_s=None,
                         alarm_received=False,no_position_ticks=0,exceed_available_ticks=0,
                         end_s=None,end_reason=None,recovery_status=None,record_cutoff_s=cutoff)
        if current is None:
            previous_status=status
            continue
        if status!='AVAILABLE' and current['first_loss_of_availability_tick_s'] is None and previous_status=='AVAILABLE' and t>current['first_exceed_s']:
            current['first_loss_of_availability_tick_s']=t
        if status=='EXPIRED' and current['first_expiry_tick_s'] is None:
            current['first_expiry_tick_s']=t
        if status=='AVAILABLE' and current['first_loss_of_availability_tick_s'] is not None and current['first_available_again_tick_s'] is None:
            current['first_available_again_tick_s']=t
        if status=='ALARM' and not current['alarm_received']:
            current.update(first_alarm_ready_s=float(r['ready_s']),first_alarm_tick_s=t,alarm_received=True)
        previous_status=status
        current['no_position_ticks']+=error is None
        current['exceed_available_ticks']+=status=='AVAILABLE' and error is not None and error>AL
    if current:
        current.update(end_s=cutoff,end_reason='CENSORED')
        results.append(current)
    return results


def main(out):
    out.mkdir(parents=True,exist_ok=True)
    counts=[]
    for run in ('101_nominal','2026111901_wall'):
        rows=reconstruct(OLD/'runs'/run)
        events=episodes(rows,CUTOFF)
        save(out/(run+'_ticks.csv'),rows)
        save(out/(run+'_events.csv'),events)
        counts.append(dict(run=run,ticks=len(rows),alarm_ticks=sum(r['status']=='ALARM' for r in rows),
                      no_position_ticks=sum(not r['x_m'] for r in rows),
                      exceed_available_ticks=sum(e['exceed_available_ticks'] for e in events),
                      events=len(events),without_alarm=sum(not e['alarm_received'] for e in events)))
        if run=='101_nominal':
            assert counts[-1]['alarm_ticks']==0 and min(counts[-1]['no_position_ticks'],counts[-1]['exceed_available_ticks'])>0
            continue
        by_time={float(r['time_s']):r for r in rows}
        first=next(r for r in rows if 24<=float(r['time_s'])<38 and r['error_m'] and float(r['error_m'])>AL)
        example=json.loads((OLD/'EXAMPLE.json').read_text())
        assert all(first[k]==example[k] for k in first)
        old=next(r for r in select(read_table(OLD/'runs'/run/'episodes.csv')) if r['start_s']==first['time_s'])
        assert old['end_exclusive_s']=='27.05' and old['first_alarm_s']==''
        window=next(
            r for r in read_table(OLD/'WINDOW_DELAY.csv') if (r['seed'],r['scene'],r['car'],r['method'],r['view'])==('2026111901','wall','1','B2','delivery'))
        e=next(e for e in events if e['first_exceed_s']==float(first['time_s']))
        arrival=e['first_alarm_ready_s']
        visible=e['first_alarm_tick_s']
        assert visible==float(window['alarm_at_or_after_s']) and round(visible-e['first_exceed_s'],2)==float(window['delay_s'])
        assert by_time[31]['state_s']=='29' and by_time[31]['status']=='AVAILABLE'
        save(out/'wall_event.csv',[dict(run=run,car=1,method='B2',AL_m=AL,injection_s=24.,injection_end_s=38.,
              **e,old_episode_end_s=old['end_exclusive_s'],old_episode_alarm=old['first_alarm_s'],
              displayed_at_31_state_s=by_time[31]['state_s'],error_at_31_m=by_time[31]['error_m'],
              injection_to_ready_s=arrival-24,exceed_to_ready_s=arrival-e['first_exceed_s'],
              injection_to_alarm_tick_s=round(visible-24,2),exceed_to_alarm_tick_s=round(visible-e['first_exceed_s'],2))])
    save(out/'counts.csv',counts)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=OUT)
    main(parser.parse_args().out)
