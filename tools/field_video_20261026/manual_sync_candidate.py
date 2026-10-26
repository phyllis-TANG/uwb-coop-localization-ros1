"""Separate timing sensitivity candidate using the explicit manual Car2 pixel track."""
import argparse
import csv
import json
from pathlib import Path
import common
import event_sync


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--primary',required=True,type=Path);p.add_argument('--manual',required=True,type=Path)
    p.add_argument('--odom-events',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--experiment',default='T12')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    primary=list(csv.DictReader(a.primary.open(encoding='utf-8')))
    manual=list(csv.DictReader(a.manual.open(encoding='utf-8')))
    odom=next(e for e in json.loads(a.odom_events.read_text(encoding='utf-8'))['experiments'] if e['experiment_id']==a.experiment)
    image_events=[];motion={};ros_events=[]
    for car in ['car1','car2']:
        rows=[r for r in (primary if car=='car1' else manual) if r['vehicle_id']==car]
        motion[car]=event_sync.image_motion(rows);image_events+=motion[car]['events']
        ros_events+=event_sync.boundaries(event_sync.merge_intervals(odom['vehicles'][car]['translational_intervals']),car)
    result=event_sync.align(image_events,ros_events)
    result.update(experiment_id=a.experiment,video_sha256=primary[0]['video_sha256'],
        source_clock='original_video_PTS',destination_clock='bag_receive_ROS_record_clock',
        destination_origin_epoch_ns=odom['receive_origin_epoch_ns'],video_motion=motion,
        source='Car1 primary observations + explicit Car2 manual-seed timing-only track',
        fusion_estimates_used=False,metric_positions_used=False,
        scope='Sensitivity alternative; no accepted mapping replaced or selected using localization errors')
    common.write_json(a.output/(a.experiment+'_manual_event_candidate.json'),result)
    print(json.dumps({k:result.get(k) for k in ['status','candidate_model']}),flush=True)


if __name__=='__main__':main()
