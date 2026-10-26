import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import random
import tempfile
import time
import unittest

import numpy as np

import model
import replay
import synthetic_validation as synthetic
from test_model import config, odom, range_event, ORIGIN


def collect(events, cfg=None, duration=300_000_000):
    result=list(replay.replay_events(events,cfg or config(),"synthetic",ORIGIN,ORIGIN+duration))
    return [r for rows,d,e in result for r in rows],result


class ReplayTests(unittest.TestCase):
    def test_future_append_does_not_change_any_earlier_publication(self):
        events=[odom(index=0),odom("car2",index=1),range_event(value=2.8)]
        base,result=collect(events)
        future=odom(offset=1_000_000_000,pose=(999.,999.,2.),index=999)
        extended,later=collect(events+[future])
        self.assertEqual(base,extended)
        self.assertEqual(result,later)

    def test_each_measurement_admitted_only_after_its_arrival(self):
        events=[odom(index=0),odom("car2",index=1),range_event(offset=10_000_000,receive_offset=250_000_000)]
        rows,result=collect(events)
        for _,tick,decisions in result:
            for d in decisions:
                self.assertLessEqual(d["receive_epoch_ns"],tick["publish_receive_epoch_ns"])
                if d["status"] in ("wall_updated","peer_updated"):
                    self.assertLessEqual(d["measurement_epoch_ns"],d["receive_epoch_ns"])

    def test_unsorted_inputs_have_same_result_as_arrival_order(self):
        events=[odom(index=0),odom("car2",index=1),range_event(value=2.8),odom(offset=100_000_000,pose=(.1,0.,.1),index=4)]
        a,_=collect(events)
        random.Random(19).shuffle(events)
        b,_=collect(events)
        self.assertEqual(a,b)

    def test_duplicate_rows_do_not_change_estimates(self):
        events=[odom(index=0),odom("car2",index=1),range_event(value=2.8)]
        a,_=collect(events)
        b,_=collect(events+[copy.deepcopy(events[2])])
        self.assertEqual(a,b)

    def test_publication_holds_anchor_and_does_not_interpolate_future_odometry(self):
        c=config();c["publish_period_ns"]=50_000_000
        events=[odom(index=0),odom("car2",index=1),odom(offset=100_000_000,pose=(10.,0.,0.),index=5)]
        rows,_=collect(events,c)
        r=next(r for r in rows if r["method_id"]=="odom_only" and r["vehicle_id"]=="car1" and r["publish_receive_epoch_ns"]==ORIGIN+50_000_000)
        self.assertEqual(r["state_epoch_ns"],ORIGIN)
        self.assertAlmostEqual(r["x_m"],c["vehicles"]["car1"]["initial_room_pose"]["value"][0])

    def test_missing_vehicle_is_null_and_does_not_block_independent_car1(self):
        c=config();c["vehicles"]["car2"]["initial_room_pose"]["value"]=None
        rows,_=collect([odom(index=0),odom("car2",index=1),range_event()],c)
        a=next(r for r in rows if r["method_id"]=="independent" and r["vehicle_id"]=="car1" and r["canonical_time_s"]==.1)
        b=next(r for r in rows if r["method_id"]=="independent" and r["vehicle_id"]=="car2" and r["canonical_time_s"]==.1)
        self.assertTrue(a["valid"])
        self.assertFalse(b["valid"])
        self.assertIsNone(b["x_m"])
        self.assertEqual(b["fallback_status"],"BLOCKED")

    def test_deadline_is_bounded(self):
        with self.assertRaisesRegex(TimeoutError,"budget"):
            list(replay.replay_events([],config(),"synthetic",ORIGIN,ORIGIN+100_000_000,deadline=time.monotonic()-1))

    def test_holdout_cli_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            output=Path(tmp)/"out"
            with self.assertRaises(SystemExit) as e:
                replay.main(["--normalized",tmp,"--config","missing","--experiment","T09","--output",str(output)])
            self.assertEqual(e.exception.code,2)
            self.assertFalse(output.exists())

    def test_existing_output_and_lock_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"out";p.mkdir();(p/"old.lock").write_text("keep")
            with self.assertRaises(FileExistsError):replay.create_run(p,Path("missing"),[])
            self.assertEqual((p/"old.lock").read_text(),"keep")

    def test_field_csv_reader_skips_holdout_and_preserves_exact_epoch(self):
        field=json.loads(Path(__file__).with_name("field_config.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            a=odom()["row"];a["experiment_id"]="T08"
            b=dict(a,experiment_id="T09",position_x="bad holdout",receive_epoch_ns="bad holdout")
            with (root/"odom.csv").open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(a));w.writeheader();w.writerows([a,b])
            events,counts,meta=replay.read_events(root,"T08",field,{"formal_bags":[{"id":"T08","sha256":"f"*64}]})
        self.assertEqual(counts,{"odom":1})
        self.assertEqual(events[0]["row"]["receive_epoch_ns"],ORIGIN+5_000_000)
        self.assertFalse(meta["range_tables_ingested"])

    def test_mismatched_input_identity_is_rejected(self):
        field=json.loads(Path(__file__).with_name("field_config.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=odom()["row"];a["experiment_id"]="T08"
            with (root/"odom.csv").open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(a));w.writeheader();w.writerow(a)
            with self.assertRaisesRegex(ValueError,"bag identity"):
                replay.read_events(root,"T08",field,{"formal_bags":[{"id":"T08","sha256":"0"*64}]})

    def test_blocked_methods_write_null_rows_and_per_tick_reasons(self):
        field=json.loads(Path(__file__).with_name("field_config.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp);run={"publications_completed":0}
            s=replay.write_replay(output,[odom(index=0),odom("car2",index=1)],field,"T08",ORIGIN,ORIGIN+100_000_000,run,time.monotonic()+10)
            with (output/"estimate.csv").open() as f:rows=list(csv.DictReader(f))
            tick=json.loads((output/"tick_diagnostics.jsonl").read_text().splitlines()[-1])
        self.assertEqual(s["methods"]["odom_only"]["status"],"DONE")
        self.assertEqual(s["methods"]["joint"]["status"],"BLOCKED")
        self.assertTrue(tick["methods"]["joint"]["vehicles"]["car1"]["blocked_reasons"])
        joint=[r for r in rows if r["method_id"]=="joint"]
        self.assertTrue(all(r["x_m"]=="" and r["valid"]=="0" for r in joint))
        local=[r for r in rows if r["method_id"]=="odom_only" and r["valid"]=="1"]
        self.assertTrue(all(r["state_epoch_ns"]=="" and r["z_m"]=="" for r in local))


class NoisySyntheticTests(unittest.TestCase):
    def test_noisy_reproducible_and_covariance_finite(self):
        c=config();c["validation_protocol"]["duration_s"]=3
        events,truth,origin,end=synthetic.fixture(c,7,"noisy_nominal")
        a=list(replay.replay_events(events,c,"synthetic",origin,end))
        b=list(replay.replay_events(events,c,"synthetic",origin,end))
        self.assertEqual(a,b)
        rows=[r for rr,d,e in a for r in rr]
        metrics=synthetic.evaluate(rows,truth)
        for value in metrics.values():
            self.assertGreater(value["xy_rmse_m"],0.)
            self.assertLess(value["xy_max_m"],2.)
        for r in rows:
            if r["pose_covariance"] is not None:
                self.assertGreaterEqual(np.linalg.eigvalsh(r["pose_covariance"]).min(),-1e-12)

    def test_disturbance_fixture_exercises_delay_duplicate_and_disconnect(self):
        c=config()
        events,truth,origin,end=synthetic.fixture(c,19,"noisy_delay_dropout")
        result=list(replay.replay_events(events,c,"synthetic",origin,end))
        final=result[-1][1]["methods"]["joint"]["cumulative_event_status"]
        self.assertGreater(final.get("duplicate_trace",0),0)
        self.assertGreater(final.get("measurement_before_odometry_anchor:car1",0),0)
        self.assertTrue(any(rows["methods"]["joint"]["vehicles"]["car2"]["fallback_status"]=="stale_odometry_hold" for r,rows,e in result))
        metrics=synthetic.evaluate([r for rows,d,e in result for r in rows],truth)
        self.assertTrue(all(np.isfinite(v["xy_rmse_m"]) for v in metrics.values()))


if __name__=="__main__":unittest.main()
