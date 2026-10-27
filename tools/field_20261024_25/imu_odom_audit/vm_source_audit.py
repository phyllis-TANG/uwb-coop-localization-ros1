"""Read-only comparison of uploaded VM reference sources and archived Car2.

Vendor C++ is treated only as text, never compiled, imported or executed.
Function comparison ignores comments/whitespace; it is not a C++ semantic proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


NAMES = ('wheeltec_robot.cpp', 'wheeltec_robot.h',
         'Quaternion_Solution.cpp', 'Quaternion_Solution.h')
FUNCTIONS = ('IMU_Trans', 'Odom_Trans', 'Publish_ImuSensor', 'Publish_Odom',
             'Get_Sensor_Data_New', 'Control')
LEX = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def no_comments(text):
    return LEX.sub(lambda m: '' if m[0].startswith(('//', '/*')) else m[0], text)


def function(text, name):
    text = no_comments(text)
    match = re.search(r'\bturn_on_robot::' + re.escape(name)
                      + r'\s*\([^)]*\)\s*\{', text)
    if match is None:
        raise ValueError('function missing: ' + name)
    start = match.end() - 1
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == '{':
            depth += 1
        elif text[pos] == '}':
            depth -= 1
            if depth == 0:
                return re.sub(r'\s+', '', text[start:pos + 1])
    raise ValueError('unbalanced function: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uploaded-dir', type=Path, required=True)
    parser.add_argument('--car2-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = dict(scope='static reference-source comparison only',
                  auditor_sha256=sha(Path(__file__).read_bytes()),
                  vendor_code_executed=False, estimator_modified=False,
                  car1_deployed_source_identified=False,
                  historical_firmware_identified=False,
                  upstream_gyro_independence_proven=False,
                  raw_vendor_sources_republished=False, files={}, functions={})
    files = {}
    for name in NAMES:
        candidates = list(args.car2_dir.rglob(name))
        if len(candidates) != 1:
            raise ValueError('need exactly one Car2 source: ' + name)
        vm = (args.uploaded_dir / name).read_bytes()
        car2 = candidates[0].read_bytes()
        files[name] = (vm.decode('utf-8'), car2.decode('utf-8'))
        result['files'][name] = dict(uploaded_sha256=sha(vm),
                                    archived_car2_sha256=sha(car2),
                                    uploaded_bytes=len(vm), archived_car2_bytes=len(car2),
                                    byte_identical=vm == car2)
    vm, car2 = files['wheeltec_robot.cpp']
    for name in FUNCTIONS:
        a, b = function(vm, name), function(car2, name)
        result['functions'][name] = dict(comments_and_whitespace_ignored=True,
                                        uploaded_normalized_sha256=sha(a.encode()),
                                        car2_normalized_sha256=sha(b.encode()),
                                        equal=a == b)
    needles = {
        'separate_odom_rate_field': 'Robot_Vel.Z = Odom_Trans(Receive_Data.rx[6],Receive_Data.rx[7])',
        'separate_gyro_z_field': 'Mpu6050_Data.gyros_z_data = IMU_Trans(Receive_Data.rx[18],Receive_Data.rx[19])',
        'odom_heading_integration': 'Robot_Pos.Z+=Robot_Vel.Z * Sampling_Time',
        'IMU_orientation_calculated_separately': 'Quaternion_Solution(Mpu6050.angular_velocity.x',
        'fixed_20Hz_attitude_step': '#define SAMPLING_FREQ 20.0f',
        'proportional_gain_1': 'twoKp = 1.0f',
        'integral_gain_0': 'twoKi = 0.0f',
    }
    joined = '\n'.join(a for a, b in files.values())
    result['reviewed_pattern_matches'] = {key: needle in joined for key, needle in needles.items()}
    if not all(result['reviewed_pattern_matches'].values()):
        raise ValueError('reviewed source pattern changed: manual review required')
    guard = 'if(_Last_Time.toSec()==0) _Last_Time=_Now'
    result['first_sample_time_guard'] = dict(uploaded_present=guard in no_comments(vm),
                                           archived_car2_present=guard in no_comments(car2),
                                           field_failure_diagnosed=False)
    result['interpretation'] = dict(
        covariance_switch='Publish_Odom changes declared covariance; no IMU state fusion in that branch',
        attitude_feedback='gyro plus gravity-direction feedback; gain is not an encoder/IMU percentage',
        Ki_zero='this host attitude routine has integral feedback disabled; MCU bias compensation unknown',
        provenance='user supplied VM ZIP members; ZIP filename/dates are not deployed firmware identity')
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps(dict(status='STATIC_COMPARISON_COMPLETE', files=4,
                          identical_files=sum(r['byte_identical'] for r in result['files'].values()),
                          equal_function_bodies=sum(r['equal'] for r in result['functions'].values()),
                          vendor_code_executed=False)))


if __name__ == '__main__':
    main()
