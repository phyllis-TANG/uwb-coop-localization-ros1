import copy
import csv
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import audit
import bridge


class BridgeContractTests(unittest.TestCase):
    def test_pr52_policy_and_pr53_hypotheses_remain_frozen(self):
        protocol, original = bridge.protocol()
        self.assertEqual(len(protocol['methods']), 9)
        self.assertEqual(protocol['profiles'], original['profiles'])
        self.assertFalse(protocol['field_accuracy_evaluated'])
        self.assertEqual(protocol['reference_status'], 'not_accepted')

    def test_holdout_event_refused_before_estimator(self):
        with self.assertRaisesRegex(ValueError, 'holdout'):
            next(bridge.process([dict(kind='odom', row=dict(experiment_id='T11',source_file_sha256='wrong'))],
                json.loads((bridge.ROOT/'docs/field_tests/20261024_25/t10_exploratory_20261027/nominal_config.json').read_text()),
                bridge.protocol()[0]['policy'], 0, 1, time.monotonic()+1))

    def test_protocol_cannot_be_repurposed_for_other_bag(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'protocol.json';value=copy.deepcopy(bridge.protocol()[0])
            value['experiment_id']='T09';path.write_text(json.dumps(value))
            with patch.object(bridge,'PROTOCOL',path), self.assertRaisesRegex(ValueError,'holdout'):
                bridge.protocol()

    def test_archive_modified_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'estimate.csv';path.write_text('original')
            run=dict(status='DONE_EXPLORATORY_ONLY',outputs={'estimate.csv':bridge.sha(path)})
            audit.verify_outputs(root,run);path.write_text('edited')
            with self.assertRaisesRegex(ValueError,'modified output'):audit.verify_outputs(root,run)

    def test_archive_traversal_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'unsafe'):
            audit.verify_outputs(Path('.'),dict(status='DONE_EXPLORATORY_ONLY',outputs={'../outside':'x'}))

    def test_old_baseline_parity_detects_changed_state(self):
        row={k:'' for k in bridge.COLUMNS}
        row.update(method_id='independent',vehicle_id='car1',publish_receive_epoch_ns='100',valid='1',x_m='1',y_m='2',yaw_rad='0')
        with tempfile.TemporaryDirectory() as folder:
            paths=[Path(folder)/name for name in ('new','old')]
            for path in paths:
                path.mkdir()
                with (path/'estimate.csv').open('w') as f:
                    writer=csv.DictWriter(f,fieldnames=bridge.COLUMNS);writer.writeheader();writer.writerow(row)
            self.assertEqual(audit.baseline_parity(*paths)['rows'],1)
            row['x_m']='1.1'
            with (paths[0]/'estimate.csv').open('w') as f:
                writer=csv.DictWriter(f,fieldnames=bridge.COLUMNS);writer.writeheader();writer.writerow(row)
            with self.assertRaisesRegex(ValueError,'regression'):audit.baseline_parity(*paths)


if __name__ == '__main__':unittest.main()
