import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import numpy as np
import engine
from engine import Candidate,METHODS,NONFEEDBACK,Gate
import model
from io_utils import DEFAULT_PROTOCOL,provenance,sha,verify_unit,dump
from simulate import generate,plan
import run
import verify_outputs as verifier
from test_model import odom,range_event,initialized,config,ORIGIN


def protocol():return json.loads(DEFAULT_PROTOCOL.read_text())


def small():
    p=protocol();p.update(duration_s=2,fault_start_s=.5,fault_end_s=1.5)
    return p


def initialized_candidate(method,policy=None):
    p=protocol();candidate=Candidate(method,p["baseline_config"],policy or p["policy"])
    candidate.process(odom(index=0));candidate.process(odom("car2",index=1));return candidate


class OriginalPathTests(unittest.TestCase):
    def test_default_none_reproduces_original_all_three_methods_bitwise(self):
        original=subprocess.run(["git","show",protocol()["base_commit"]+":tools/field_20261024_25/causal_baselines/model.py"],check=True,capture_output=True,text=True).stdout
        legacy=types.ModuleType("frozen_original_model");exec(compile(original,"frozen_original_model.py","exec"),legacy.__dict__)
        p=small();events,_,_,origin,end,_=generate(p,"normal","car1",17)
        for method in model.METHODS:
            before=legacy.Baseline(method,p["baseline_config"]);after=model.Baseline(method,p["baseline_config"])
            for event in events:self.assertEqual(before.process(event),after.process(event))
            self.assertEqual(before.snapshot(end),after.snapshot(end))
            np.testing.assert_array_equal(before.x,after.x);np.testing.assert_array_equal(before.P,after.P)

    def test_all_peer_candidates_match_independent_when_no_peer(self):
        p=small();events,_,_,origin,end,_=generate(p,"normal","car1",19)
        events=[e for e in events if e["kind"]=="odom" or e["row"]["target_id"] in model.WALLS]
        independent=model.Baseline("independent",p["baseline_config"])
        candidates={m:Candidate(m,p["baseline_config"],p["policy"]) for m in METHODS if m!="odom_only"}
        for event in events:
            independent.process(event)
            for candidate in candidates.values():candidate.process(event)
        for candidate in candidates.values():
            self.assertEqual(independent.snapshot(end),candidate.snapshot(end))
            np.testing.assert_array_equal(independent.P,candidate.engine.P)

    def test_shadow_matches_independent_after_every_event_without_shared_memory(self):
        p=small();events,*_=generate(p,"peer_bias","car1",23)
        independent=model.Baseline("independent",p["baseline_config"])
        candidates={m:Candidate(m,p["baseline_config"],p["policy"]) for m in METHODS}
        for event in events:
            independent.process(event)
            for method,candidate in candidates.items():
                candidate.process(event)
                np.testing.assert_array_equal(independent.x,candidate.shadow.x)
                np.testing.assert_array_equal(independent.P,candidate.shadow.P)
                self.assertFalse(np.shares_memory(candidate.engine.P,candidate.shadow.P))
                if method in NONFEEDBACK:
                    np.testing.assert_array_equal(independent.x,candidate.engine.x);np.testing.assert_array_equal(independent.P,candidate.engine.P)

    def test_instances_do_not_retain_gate_or_shadow_across_runs(self):
        first=initialized_candidate("gate_cap_shadow");fresh=initialized_candidate("gate_cap_shadow")
        first.process(range_event(target="node_0",value=50.,index=100))
        self.assertNotEqual(first.policy.gate.state,fresh.policy.gate.state)
        again=initialized_candidate("gate_cap_shadow")
        np.testing.assert_array_equal(fresh.engine.x,again.engine.x);self.assertEqual(fresh.policy.gate.state,again.policy.gate.state)


class PolicySemanticsTests(unittest.TestCase):
    def test_gate_quarantine_three_bad_reopens_four_good_per_direction(self):
        gate=Gate(protocol()["policy"])
        for _ in range(3):self.assertFalse(gate.admit("car1",4))
        self.assertTrue(gate.state["car1"]["closed"])
        for _ in range(3):self.assertFalse(gate.admit("car1",0))
        self.assertTrue(gate.admit("car1",0));self.assertFalse(gate.state["car1"]["closed"])
        self.assertEqual(gate.state["car2"],dict(bad=0,good=0,closed=False))

    def test_cap_scales_actual_gain_and_yaw_uses_scaled_gain_joseph(self):
        p=protocol()["policy"];p.update(weak_shift_cap_m=.001,healthy_shift_cap_m=.001)
        candidate=initialized_candidate("cap_only",p)
        decision=candidate.process(range_event(target="node_0",value=50.))
        d=decision["reliability"];self.assertTrue(any(d["clipped"]))
        for i,scale in enumerate(d["cap_scales"]):
            self.assertLessEqual(d["actual_shift_xy_m"][i],.001+1e-12)
            np.testing.assert_allclose(np.array(d["actual_gain"])[3*i:3*i+3],np.array(d["raw_gain"])[3*i:3*i+3]*scale)
        P=np.array(d["pre_feedback_covariance"]);H=np.array(d["H"]);K=np.array(d["actual_gain"])
        np.testing.assert_allclose(candidate.engine.P,engine.joseph(P,H,K,d["effective_variance_m2"]))
        self.assertGreater(np.linalg.eigvalsh(candidate.engine.P).min(),-1e-12)
        self.assertIn("not_calibrated",d["covariance_semantics"])

    def test_huber_on_same_six_state_filter_increases_only_peer_effective_R(self):
        candidate=initialized_candidate("huber");d=candidate.process(range_event(target="node_0",value=20.))["reliability"]
        self.assertEqual(len(candidate.engine.x),6);self.assertLess(d["huber_weight"],1.)
        self.assertGreater(d["effective_variance_m2"],d["base_variance_m2"])
        np.testing.assert_array_equal(candidate.engine.x,d["proposal"])

    def test_gate_rejection_consumes_shared_rate_slot_not_extra_good_samples(self):
        candidate=initialized_candidate("gate_only")
        decision=candidate.process(range_event(target="node_0",value=50.))
        self.assertEqual(decision["status"],"peer_gate_rejected")
        self.assertEqual(len(decision["reliability"]["raw_proposal"]),6)
        self.assertEqual(np.asarray(decision["reliability"]["raw_proposal_covariance"]).shape,(6,6))
        candidate.process(odom(offset=100_000_000,index=10))
        candidate.process(odom("car2",offset=100_000_000,index=11))
        self.assertEqual(candidate.process(range_event(target="node_0",value=3.,offset=110_000_000,index=101))["status"],"excluded_fixed_rate_thinning")
        self.assertEqual(candidate.policy.gate.state["car1"]["good"],0)

    def test_nonfeedback_output_is_null_covariance_and_expires_without_state_reset(self):
        candidate=initialized_candidate("shadow_only")
        event=range_event(target="node_0",value=5.)
        before=candidate.engine.x.copy();cov=candidate.engine.P.copy()
        decision=candidate.process(event)
        self.assertEqual(decision["status"],"peer_output_only")
        np.testing.assert_array_equal(before,candidate.engine.x);np.testing.assert_array_equal(cov,candidate.engine.P)
        now=event["row"]["receive_epoch_ns"]
        state=candidate.snapshot(now)
        self.assertIsNone(state["car1"]["covariance"]);self.assertIn("no_calibrated",state["car1"]["output_covariance_reason"])
        old=candidate.policy.output_receive_ns
        candidate.process(range_event("car2","node_1",value=999.,offset=30_000_000,index=101))
        self.assertEqual(candidate.policy.output_receive_ns,old)
        expired=candidate.snapshot(now+candidate.policy.config["output_hold_ns"]+1)
        np.testing.assert_array_equal(expired["car1"]["pose"],before[:3])
        np.testing.assert_array_equal(expired["car1"]["covariance"],cov[:3,:3])

    def test_shadow_control_shares_nonfeedback_hold_policy(self):
        p=protocol()["policy"];p.update(gate_z=1e6,weak_shift_cap_m=1e6,healthy_shift_cap_m=1e6)
        a=initialized_candidate("shadow_only",p);b=initialized_candidate("gate_cap_shadow",p)
        event=range_event(target="node_0",value=5.)
        a.process(event);b.process(event)
        self.assertEqual(a.snapshot(event["row"]["receive_epoch_ns"]),b.snapshot(event["row"]["receive_epoch_ns"]))

    def test_reverse_direction_fault_is_unconsumed_negative_control(self):
        p=small();events,_,_,origin,end,_=generate(p,"normal","car1",31)
        changed=copy.deepcopy(events)
        for event in changed:
            if event["kind"]=="range" and event["row"]["vehicle_id"]=="car2" and event["row"]["target_id"]=="node_1":event["row"]["range_m"]+=100
        a=[state for state,_,_ in run.process(events,p["baseline_config"],p["policy"],origin,end)]
        b=[state for state,_,_ in run.process(changed,p["baseline_config"],p["policy"],origin,end)]
        self.assertEqual(a,b)

    def test_wall_rank_is_geometry_only_and_can_be_weak(self):
        candidate=initialized_candidate("cap_only");health=candidate.policy.health(ORIGIN+10_000_000)
        self.assertTrue(all(not item["healthy"] and item["cap_m"]==.35 for item in health))


class CausalityAndFaultTests(unittest.TestCase):
    def test_future_append_and_mutation_do_not_change_past_outputs(self):
        p=small();events,_,_,origin,end,_=generate(p,"normal","car1",37)
        cutoff=origin+1_000_000_000
        prefix=[e for e in events if e["row"]["receive_epoch_ns"]<=cutoff]
        changed=copy.deepcopy(events)
        for event in changed:
            if event["row"]["receive_epoch_ns"]>cutoff and event["kind"]=="range":event["row"]["range_m"]+=99
        results=[]
        for selected in (prefix,events,changed):results.append([(s,e) for s,e,c in run.process(selected,p["baseline_config"],p["policy"],origin,cutoff)])
        self.assertEqual(results[0],results[1]);self.assertEqual(results[0],results[2])

    def test_raw_bridge_duplicate_stale_async_rejections_precede_policy(self):
        candidate=initialized_candidate("gate_cap")
        event=range_event(target="node_0",value=2.8)
        candidate.process(event);gate=copy.deepcopy(candidate.policy.gate.state);P=candidate.engine.P.copy()
        self.assertEqual(candidate.process(event)["status"],"duplicate_trace")
        bridge=copy.deepcopy(event);bridge["row"].update(record_index=999,source="bridge",primary_observation=0)
        self.assertEqual(candidate.process(bridge)["status"],"excluded_bridge_duplicate")
        self.assertEqual(candidate.process(range_event(target="node_0",offset=90_000_000,index=1000))["status"],"stale_odometry_support:car1")
        self.assertEqual(candidate.process(range_event(target="node_0",offset=50_000_000,receive_offset=500_000_000,index=1001))["status"],"stale_measurement_on_arrival")
        self.assertEqual(gate,candidate.policy.gate.state);np.testing.assert_array_equal(P,candidate.engine.P)

    def test_all_states_finite_symmetric_psd_with_turn_wrap_levers_and_noise(self):
        p=small();events,_,_,origin,end,_=generate(p,"normal","car1",43)
        for state,_,_ in run.process(events,p["baseline_config"],p["policy"],origin,end):
            for item in state["methods"].values():
                self.assertTrue(np.isfinite(item["feedback_state"]).all())
                P=np.array(item["feedback_covariance"]);np.testing.assert_allclose(P,P.T,atol=1e-12)
                self.assertGreaterEqual(np.linalg.eigvalsh(P).min(),-1e-10)

    def test_fault_timing_sign_and_seed_identical_pairing(self):
        p=small();normal,*_=generate(p,"normal","car1",47);fault,*_=generate(p,"peer_bias","car1",47)
        self.assertEqual(len(normal),len(fault))
        for a,b in zip(normal,fault):
            ra,rb=a["row"],b["row"]
            self.assertEqual(ra["receive_epoch_ns"],rb["receive_epoch_ns"])
            if a["kind"]=="range":
                active=p["fault_start_s"]<=(ra["header_epoch_ns"]-ORIGIN)/1e9<p["fault_end_s"]
                expected=.8 if active and ra["vehicle_id"]=="car1" and ra["target_id"]=="node_0" else 0.
                self.assertAlmostEqual(rb["range_m"]-ra["range_m"],expected)
            else:self.assertEqual(a,b)

    def test_80_planned_rows_60_unique_and_duplicate_inputs_really_identical(self):
        p=protocol();rows=plan(p)
        self.assertEqual(len(rows),80);self.assertEqual(sum(row["duplicate_of"] is None for row in rows),60)
        p=small()
        for scenario in p["role_invariant_scenarios"]:
            self.assertEqual(generate(p,scenario,"car1",53)[-1],generate(p,scenario,"car2",53)[-1])
        self.assertNotEqual(generate(p,"weak_wall_peer_bias","car1",53)[-1],generate(p,"weak_wall_peer_bias","car2",53)[-1])

    def test_estimator_has_no_truth_labels_or_simulator_import(self):
        source=Path(engine.__file__).read_text()
        for forbidden in ("from simulate", "import simulate", "import evaluate", "import reliability_stress", "truth.json", "labels.json"):
            self.assertNotIn(forbidden,source)
        self.assertEqual(set(engine.online_config(protocol()["policy"])),set(protocol()["policy"]))

    def test_holdout_library_gate_rejects_before_any_processing(self):
        cfg=config();cfg["scope"]="field"
        event=odom();event["row"]["experiment_id"]="T09"
        with self.assertRaisesRegex(ValueError,"holdout"):list(run.process([event],cfg,protocol()["policy"],ORIGIN,ORIGIN+100_000_000))


class EvidenceTests(unittest.TestCase):
    def test_independent_reader_checks_real_rows_and_detects_hash_tampering(self):
        p=small();p["duration_s"]=1;p["fault_end_s"]=.8
        condition=dict(id="test",scenario="peer_bias",role="car1",seed=59,canonical_id="test",duplicate_of=None)
        lock=provenance(DEFAULT_PROTOCOL)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"trial";unit=run.run_unit(path,condition,p,lock,time.monotonic()+30)
            result=verifier.audit_unit(path,p,lock["fingerprint_sha256"])
            self.assertEqual(result["status"],"DONE");self.assertGreater(result["events_read"],0)
            verify_unit(path,lock["fingerprint_sha256"],unit["input_sha256"])
            (path/"metrics.json").write_text("[]")
            with self.assertRaisesRegex(ValueError,"hash"):verifier.audit_unit(path,p,lock["fingerprint_sha256"])
            with self.assertRaisesRegex(ValueError,"changed"):verify_unit(path,lock["fingerprint_sha256"],unit["input_sha256"])

    def test_fingerprint_changes_for_source_or_protocol_changes_and_output_stays_external(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"protocol.json";path.write_text(DEFAULT_PROTOCOL.read_text())
            before=provenance(path);path.write_text(path.read_text()+" ")
            self.assertNotEqual(before["fingerprint_sha256"],provenance(path)["fingerprint_sha256"])
        with self.assertRaisesRegex(ValueError,"outside Git"):run.ensure_external(Path(engine.__file__).parent/"results")

    def test_resume_checks_root_and_unit_provenance_before_writing(self):
        from io_utils import verify_saved_root
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);unit=root/"runs"/"one";unit.mkdir(parents=True)
            (unit/"run.json").write_text('{"status":"DONE"}')
            dump(root/"inventory.json",[dict(id="one",status="DONE",run_json_sha256=sha(unit/"run.json"))])
            dump(root/"run.json",dict(status="DONE",outputs=[dict(relative_path="inventory.json",sha256=sha(root/"inventory.json"))]))
            self.assertEqual(verify_saved_root(root)["status"],"DONE")
            (unit/"run.json").write_text('{"status":"FAILED"}')
            with self.assertRaisesRegex(ValueError,"provenance changed"):verify_saved_root(root)
            (root/"inventory.json").write_text('[]')
            with self.assertRaisesRegex(ValueError,"root output hash"):verify_saved_root(root)

    def test_reader_detects_semantic_cap_tamper_even_with_updated_file_hash(self):
        import gzip
        from io_utils import gzread
        p=small();p["duration_s"]=1
        condition=dict(id="test_cap",scenario="peer_bias",role="car1",seed=61,canonical_id="test_cap",duplicate_of=None)
        lock=provenance(DEFAULT_PROTOCOL)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"trial";run.run_unit(path,condition,p,lock,time.monotonic()+30)
            records=list(gzread(path/"events.jsonl.gz"));changed=False
            for event in records:
                d=event["methods"]["cap_only"]["decision"].get("reliability")
                if d and d["accepted"]:d["cap_scales"][0]=.123;changed=True;break
            self.assertTrue(changed)
            with gzip.open(path/"events.jsonl.gz","wt") as stream:
                for record in records:stream.write(json.dumps(record,sort_keys=True,allow_nan=False)+"\n")
            unit=json.loads((path/"run.json").read_text())
            for item in unit["outputs"]:
                if item["relative_path"]=="events.jsonl.gz":item["sha256"]=sha(path/"events.jsonl.gz")
            dump(path/"run.json",unit)
            with self.assertRaisesRegex(ValueError,"cap scale mismatch"):verifier.audit_unit(path,p,lock["fingerprint_sha256"])

    def test_T10_preflight_preserves_pending_and_never_opens_bag(self):
        import contextlib,io
        import preflight_t10
        template=preflight_t10.DEFAULT_TEMPLATE;before=sha(template)
        with tempfile.TemporaryDirectory() as temp,contextlib.redirect_stdout(io.StringIO()):
            path=Path(temp)/"new_preflight"
            code=preflight_t10.main(["--output",str(path)])
            decision=json.loads((path/"decision.json").read_text())
            self.assertEqual(code,2);self.assertEqual(decision["status"],"BLOCKED")
            self.assertFalse(decision["bag_read"]);self.assertIsNone(decision["actual_field_ATE_RMSE"])
            self.assertTrue(any(row["field"]=="vehicles.car1.antenna_body_xy_m" for row in decision["blocked_fields"]))
            self.assertEqual(sha(template),before)

    def test_verifier_does_not_import_generator_engine_or_evaluator(self):
        source=Path(verifier.__file__).read_text()
        for forbidden in ("import model", "from model", "import engine", "from engine", "import simulate", "from simulate", "import evaluate", "from evaluate"):
            self.assertNotIn(forbidden,source)


if __name__=="__main__":unittest.main()
