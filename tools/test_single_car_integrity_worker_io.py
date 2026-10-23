"""Integration check: executable never opens truth/labels and output is invariant."""
import contextlib
from dataclasses import asdict
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import run_single_car_integrity_worker as worker
from test_single_car_integrity import config,stable
from test_single_car_sequential_replay import synthetic_events


class WorkerIOTests(unittest.TestCase):
    def test_truth_and_label_reads_forbidden_and_counterfactual_values_irrelevant(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            conf=root/'config.json';conf.write_text(json.dumps(config()))
            sensors=root/'sensors.jsonl'
            sensors.write_text(''.join(json.dumps(asdict(e))+'\n' for e in synthetic_events(5.)))
            actual_open=Path.open
            attempted=[]
            def guard(path,*args,**kwargs):
                if path.name in ('truth.csv','fault_labels.json'):
                    attempted.append(str(path));raise AssertionError('Estimator attempted forbidden truth/label access')
                return actual_open(path,*args,**kwargs)
            outputs=[]
            for version in range(2):
                (root/'truth.csv').write_text('counterfactual truth '+str(version*100000))
                (root/'fault_labels.json').write_text(json.dumps({'fake_fault':bool(version),'future_label':version}))
                target=root/('output_'+str(version))
                args=['worker','--config',str(conf),'--sensors',str(sensors),'--output',str(target)]
                with patch.object(Path,'open',guard),patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
                    worker.main()
                outputs.append([json.loads(line) for line in (target/'updates.jsonl').read_text().splitlines()])
            self.assertEqual(attempted,[])
            self.assertEqual(stable(outputs[0]),stable(outputs[1]))
