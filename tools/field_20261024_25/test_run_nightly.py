"""Behavior tests of bounded jobs, provenance resume and isolated output."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import run_nightly as runner


def proof(fingerprint="frozen", bag_errors=None):
    return {"fingerprint": fingerprint, "identity": {}, "git": {},
            "bag_preconditions": [] if bag_errors is None else bag_errors}


def quick_job(name="quick", code="print('ok')", **extra):
    job = {"id": name, "command": [sys.executable, "-c", code],
           "timeout_s": 10, "depends_on": []}
    job.update(extra)
    return job


class NightlyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.data = self.base / "data"
        self.data.mkdir()
        self.output = self.base / "results"

    def run_plan(self, jobs, resume=False, fingerprint="frozen", bag_errors=None, **extra):
        with patch.object(runner, "provenance", return_value=proof(fingerprint, bag_errors)):
            return runner.run_jobs(self.data, self.output, .1, resume=resume, jobs=jobs, **extra)

    def test_resume_skips_only_matching_passed_artifacts(self):
        jobs = [quick_job()]
        first = self.run_plan(jobs)
        self.assertEqual(first["status"], "COMPLETE")
        state = self.run_plan(jobs, resume=True)
        self.assertEqual(len(state["tasks"]["quick"]["attempts"]), 1)
        self.assertIn("resume_verified_skip", (self.output / "tasks.jsonl").read_text())
        (self.output / "jobs/quick/attempt_0001/stdout.log").write_text("tampered")
        state = self.run_plan(jobs, resume=True)
        self.assertEqual(len(state["tasks"]["quick"]["attempts"]), 2)
        self.assertEqual(state["status"], "COMPLETE")

    def test_changed_fingerprint_refuses_resume_and_preserves_state(self):
        self.run_plan([quick_job()])
        before = (self.output / "run.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "fingerprint changed"):
            self.run_plan([quick_job()], resume=True, fingerprint="source-changed")
        self.assertEqual(before, (self.output / "run.json").read_bytes())

    def test_failure_does_not_prevent_independent_job_and_attempt_cap(self):
        jobs = [quick_job("bad", "raise SystemExit(7)"), quick_job("independent")]
        first = self.run_plan(jobs)
        self.assertEqual(first["tasks"]["bad"]["status"], "FAILED")
        self.assertEqual(first["tasks"]["independent"]["status"], "PASSED")
        self.assertEqual(first["tasks"]["bad"]["attempts"][0]["returncode"], 7)
        self.run_plan(jobs, resume=True)
        final = self.run_plan(jobs, resume=True)
        self.assertEqual(len(final["tasks"]["bad"]["attempts"]), 2)

    def test_missing_bags_block_only_bag_task(self):
        jobs = [quick_job(), quick_job("bag_qc", requires_bags=True)]
        state = self.run_plan(jobs, bag_errors=["T08: input missing"])
        self.assertEqual(state["status"], "BLOCKED")
        self.assertEqual(state["tasks"]["quick"]["status"], "PASSED")
        self.assertEqual(state["tasks"]["bag_qc"]["attempts"], [])
        self.assertFalse((self.output / "jobs/bag_qc").exists())

    def test_required_artifact_missing_is_not_success(self):
        state = self.run_plan([quick_job(artifacts=["bag_qc.json"])])
        result = state["tasks"]["quick"]["attempts"][0]
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("artifact missing", result["error"])

    def test_deadline_prevents_work_without_sleep(self):
        calls = iter([100., 500.])
        state = self.run_plan([quick_job()], now=lambda: next(calls))
        self.assertEqual(state["status"], "BUDGET_EXHAUSTED")
        self.assertFalse((self.output / "jobs").exists())

    def test_hard_killed_attempt_directory_is_preserved_on_resume(self):
        self.run_plan([quick_job()])
        state_path = self.output / "run.json"
        state = json.loads(state_path.read_text())
        state["tasks"]["quick"] = {"status": "RUNNING", "attempts": []}
        state_path.write_text(json.dumps(state))
        state = self.run_plan([quick_job()], resume=True)
        self.assertEqual(state["tasks"]["quick"]["attempts"][0]["status"], "ABANDONED")
        self.assertTrue((self.output / "jobs/quick/attempt_0001/stdout.log").is_file())
        self.assertEqual(state["tasks"]["quick"]["attempts"][1]["status"], "PASSED")

    def test_output_lock_rejects_second_writer(self):
        with runner.output_lock(self.output):
            with self.assertRaisesRegex(ValueError, "another nightly process"):
                self.run_plan([quick_job()])

    def test_reject_git_or_overlapping_raw_output_directories(self):
        with self.assertRaisesRegex(ValueError, "outside the Git"):
            runner.run_jobs(self.data, runner.ROOT / "test-nightly-output", .1, jobs=[])
        with self.assertRaisesRegex(ValueError, "must be separate"):
            runner.run_jobs(self.data, self.data / "results", .1, jobs=[])

    def test_real_subprocess_timeout_is_bounded(self):
        job = quick_job(code="import time; time.sleep(30)")
        started = time.monotonic()
        result = runner.execute_job(job, self.data, self.output, 1, .05)
        self.assertEqual(result["status"], "TIMED_OUT")
        self.assertLess(time.monotonic() - started, 2.)

    def test_plan_only_has_no_download_or_estimator_replay_commands(self):
        plan = runner.build_jobs()
        self.assertLessEqual(len(plan), 64)
        self.assertTrue(all(j["timeout_s"] > 0 for j in plan))
        self.assertEqual(sum(j.get("requires_bags", False) for j in plan), 1)
        commands = " ".join(" ".join(j["command"]) for j in plan)
        self.assertNotIn("prepare.py", commands)
        self.assertNotIn("roslaunch", commands)
        self.assertNotIn("run_two_car_independent_integrity.py", commands)


if __name__ == "__main__":
    unittest.main()
