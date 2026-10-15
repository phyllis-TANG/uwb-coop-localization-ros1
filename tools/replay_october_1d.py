#!/usr/bin/env python3
"""Modern-Python offline adapter for unchanged historical Python 2 scripts.

Only ROS bag access and Python-2 binary CSV streams are adapted. Parameters,
timestamp choices and algorithms remain in the hash-preserved original files.
"""
import argparse
import builtins
import contextlib
import importlib.util
import io
import json
import sys
import types
from pathlib import Path

from rosbags.highlevel import AnyReader


class ReadOnlyBag:
    def __init__(self, path, mode='r'):
        if mode != 'r':
            raise ValueError('Read-only adapter')
        self.reader = AnyReader([Path(path)])

    def __enter__(self):
        self.reader.open()
        return self

    def __exit__(self, *args):
        self.reader.close()

    def get_start_time(self):
        return self.reader.start_time/1e9

    def get_end_time(self):
        return (self.reader.end_time-1)/1e9

    def read_messages(self, topics=None):
        selected = [c for c in self.reader.connections if topics is None or c.topic in topics]
        for conn, timestamp, raw in self.reader.messages(connections=selected):
            stamp = types.SimpleNamespace(to_sec=lambda timestamp=timestamp: timestamp/1e9)
            yield conn.topic, self.reader.deserialize(raw, conn.msgtype), stamp


def csv_open(path, mode='r'):
    if mode == 'wb':
        return builtins.open(path, 'w', newline='')
    return builtins.open(path, mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    data = Path(args.data_root)/'20261011'
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent/'field_session_20261010_11'
    # The shim exists only inside this dedicated offline process.
    sys.modules['rosbag'] = types.SimpleNamespace(Bag=ReadOnlyBag)
    records = []
    for method, directory, filename, entry in [
        ('filter_1d', 'fusion_1d_pilot', 'uwb_odom_1d_pilot.py', 'main'),
        ('graph_1d', 'factor_graph_1d_pilot', 'uwb_odom_1d_factor.py', 'run_bag')]:
        spec = importlib.util.spec_from_file_location(method, source/filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.open = csv_open
        for label, name, reference in [
            ('forward1', 'CAR2_WALL_UWB_ODOM_IMU_key_forward_20261011_045550.bag', 1.020),
            ('forward2', 'CAR2_WALL_UWB_ODOM_IMU_key_forward_repeat_20261011_051810.bag', 1.010),
            ('return', 'CAR2_WALL_UWB_ODOM_IMU_key_return_20261011_052421.bag', .950)]:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                getattr(module, entry)(str(data/name), reference,
                                       str(output/(method+'_'+label+'.csv')))
            result = stdout.getvalue()
            (output/(method+'_'+label+'_summary.txt')).write_text(result)
            expected = (data/directory/(label+'_summary.txt')).read_text()
            got = [line for line in result.splitlines() if 'signed=' in line]
            reported = [line for line in expected.splitlines() if 'signed=' in line]
            if len(got) != 3 or got != reported:
                raise ValueError('Historical summary mismatch: '+method+' '+label)
            records.append({'method': method, 'run': label, 'reference_m': reference,
                            'field_summary_reproduced_3dp': True})
            print(method, label, 'PASS')
    (output/'reproduction.json').write_text(json.dumps(records, indent=2)+'\n')
    print('PASS: all six historical summaries reproduced to reported precision.')


if __name__ == '__main__':
    main()
