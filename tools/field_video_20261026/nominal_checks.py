"""Independent-of-fit nominal Q checks, explicitly NOT surveyed position truth."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import common
import observations


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--media',type=Path,required=True);p.add_argument('--transforms',type=Path,required=True)
    p.add_argument('--calibration',type=Path,required=True);p.add_argument('--geometry',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mount-confirmation',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);cv2.setNumThreads(2)
    transforms=json.loads(a.transforms.read_text(encoding='utf-8'))
    cameras={r['video_sha256']:r for r in transforms['records']}
    models=json.loads(a.calibration.read_text(encoding='utf-8'))['models']
    geometry=json.loads(a.geometry.read_text(encoding='utf-8'))
    confirmation=json.loads(a.mount_confirmation.read_text(encoding='utf-8')) if a.mount_confirmation else None
    config=json.loads(Path(observations.__file__).with_name('observation_config.json').read_text(encoding='utf-8'))
    ds=observations.detectors(config)
    mapping={'IMG_7365':('car2','Q1'),'IMG_7366':('car2','Q2'),'IMG_7367':('car2','Q3'),
        'IMG_7369':('car1','Q1'),'IMG_7370':('car1','Q2'),'IMG_7371':('car1','Q3'),'IMG_7373':('car1','Q3_extra')}
    checks=[]
    for qc in sorted(a.media.glob('camera_reference__*/media_qc.json')):
        info=json.loads(qc.read_text(encoding='utf-8'));stem=Path(info['relative_path']).stem
        if stem not in mapping:continue
        vehicle,point=mapping[stem];marker=0 if vehicle=='car1' else 1
        target=geometry['independent_check_points'][point.replace('_extra','')+'_xy_m']
        camera=cameras[info['sha256']];samples=[]
        for frame in info['diagnostic_frames']:
            image=cv2.imread(str(qc.parent/frame['path']));found,_=observations.decode(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),ds)
            row=dict(frame_index=frame['frame_index'],video_time_s=frame['video_time_s'],
                decoded=marker in found,actual_independent_position_error_m=None,model_candidates={})
            if marker in found:
                corners,method=found[marker];row['method']=method;row['corners_encoded_px']=corners.tolist()
                match=min(camera['clips'],key=lambda r:abs(r['video_time_s']-frame['video_time_s']))
                for name,pose in match.get('room_pose_candidates',{}).items():
                    if 'T_room_camera' not in pose:continue
                    K,D=models[name]['K'],models[name]['D'];T=pose['T_room_camera']
                    mount=geometry['mounts'][vehicle];height=mount['black_border_center_height_m']
                    H=cv2.getPerspectiveTransform(common.marker_object_points(.144)[:,:2].astype(np.float32),corners.astype(np.float32))
                    center=common.transform_pixels([[0,0]],H)[0]
                    xyz=common.intersect_room_plane(center,K,D,T,height)
                    edge_xyz=np.array([common.intersect_room_plane(q,K,D,T,height) for q in corners])
                    forward=(edge_xyz[0]+edge_xyz[1]-edge_xyz[2]-edge_xyz[3])[:2]
                    heading=float(np.arctan2(forward[1],forward[0]))
                    hypotheses={}
                    for label,offset in [('body_front_marker_plus_Y',0.),('body_front_marker_minus_Y',np.pi)]:
                        body_heading=heading+offset
                        antenna=common.antenna_from_body_offset(xyz,body_heading,mount['marker_center_to_antenna_body_aligned_xyz_m'])
                        hypotheses[label]=dict(assumed_body_heading_rad=body_heading,antenna_room_m=antenna.tolist(),
                            nominal_only_discrepancy_m=float(np.linalg.norm(antenna[:2]-target)),
                            rotation_status='hypothesis_not_measurement_not_selected_using_Q')
                    wrong=common.intersect_room_plane(center,K,D,T,0)
                    row['model_candidates'][name]=dict(marker_center_room_m=xyz.tolist(),antenna_room_m=None,
                        body_heading_hypotheses=hypotheses,
                        reconstructed_edge_lengths_m=np.linalg.norm(np.roll(edge_xyz,-1,axis=0)-edge_xyz,axis=1).tolist(),
                        actual_marker_side_m=.144,ground_plane_without_height_error_xy_m=float(np.linalg.norm(wrong[:2]-xyz[:2])),
                        assumptions=['Nominal P room coordinates','Clip intrinsics equal chosen calibration candidate',
                            'Horizontal board at reported center height','Marker/body rotation is unknown; both opposite directions retained'],
                        actual_independent_position_error_m=None)
            else:row['reason']='Expected vehicle marker not automatically decoded; manual tracking excluded from metric checks'
            samples.append(row)
        checks.append(dict(video=info['relative_path'],video_sha256=info['sha256'],vehicle_id=vehicle,
            checkpoint_id=point,nominal_antenna_xy_m=target,point_video_mapping_status='provisional_by_recording_sequence',
            physical_coordinates_status='instructed_not_independently_surveyed',used_for_spatial_fit=False,
            independent_actual_error_m=None,samples=samples))
    report=dict(schema_version=1,approved_scope='not_accepted',status='BLOCKED',
        actual_independently_measured_checkpoint_errors=None,nominal_feasibility_checks=checks,
        primary_candidate_fixed_before_Q='IMG_7337_all',other_models='sensitivity_only_no_selection_using_Q',
        body_heading_policy='Both directions retained; Car1 nominal minus-Y, if stated, comes from separate operator front-side evidence, never Q error minimization',
        operator_mount_confirmation=confirmation,
        acceptance_tolerance_m=None,uncertainty_model=None,
        allowed_uses=['Original media QC','Pixel observations with explicit methods and failures',
            'Provisional motion event timing','Nominal-geometry feasibility and sensitivity'],
        not_allowed=['Continuous antenna truth','Checkpoint position accuracy claims','Localization RMSE or calibration tuned on Q'],
        blockers=['Actual P/Q coordinates, placement and measurement uncertainty not supplied',
            'Reference-video Q correspondence/headings provisional',
            'Camera intrinsics/processing equivalence and stability unapproved',
            'Marker/body rotation and lever-arm uncertainty unverified',
            'Car2 curved/tilted board and view-dependent extraction unvalidated',
            'No independently bounded video/measurement-clock mapping'],
        why_no_checkpoints_csv='No independent surveyed-point validation passed; nominal checks cannot be promoted to checkpoints',
        no_Q_fit=True,no_fusion_trajectory_used=True)
    common.write_json(a.output/'reference_validation.json',report)
    print(json.dumps([{ 'video':r['video'],'detected_samples':sum(s['decoded'] for s in r['samples'])} for r in checks]),flush=True)


if __name__=='__main__':main()
