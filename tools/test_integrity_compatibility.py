#!/usr/bin/env python3
"""Recovery-only regressions; fixtures never execute an estimator."""
import contextlib
import copy
import csv
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import single_car_integrity_compat as compat
import run_single_car_integrity_experiment as runner

REPOSITORY=Path(__file__).resolve().parents[1]
EXPERIMENT=REPOSITORY/'docs/field_tests/integrity_feasibility_v1_1_20261022'


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='integrity relocated ')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)/'new repository'
        self.out=self.root/'docs/field_tests/custom_v1_1'
        self.out.mkdir(parents=True)
        self.core=[compat.RUNNER,'tools/single_car_integrity.py','tools/single_car_integrity_sim.py']
        for name in self.core:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
        self.snapshot='tools/integrity_compat/v1_2_0/original_sources/runner.py'
        path=self.root/self.snapshot;path.parent.mkdir(parents=True);path.write_text('original frozen runner')
        self.bag=self.root/'datasets/original.bag';self.bag.parent.mkdir();self.bag.write_bytes(b'original bag')
        self.protocol=dict(experiment='integrity-feasibility-v1.1',historical_cases=[dict(id='case',bag='datasets/original.bag',sha256=compat.checksum(self.bag))],development_seeds=[1],scenarios=[dict(id='nominal',seeds=[2])])
        self.write(self.out/'protocol.json',self.protocol)
        self.write(self.out/'estimator_config.json',dict(model='frozen'))
        expected=self.state();expected['sources'][compat.RUNNER]=compat.checksum(self.root/self.snapshot)
        self.write(self.out/'source_lock.json',dict(locked=expected))
        self.write(self.out/'thresholds.json',dict(source_lock_sha256=compat.checksum(self.out/'source_lock.json'),values=dict(M1=1,M2=.062)))
        self.manifest=dict(compatibility_version=compat.VERSION,supported_execution_source_lock_sha256=[compat.checksum(self.out/'source_lock.json')],compatibility_sources={compat.RUNNER:compat.checksum(self.root/compat.RUNNER)},source_replacements={compat.RUNNER:dict(original_sha256=compat.checksum(self.root/self.snapshot),compatible_sha256=compat.checksum(self.root/compat.RUNNER),snapshot=self.snapshot)})
        self.write(self.root/compat.MANIFEST,self.manifest)
        self.records=[]
        for identifier,group in [('history_case','historical'),('dev_nominal_1','development'),('test_nominal_2','diagnostic')]:
            target=self.out/'runs'/identifier;target.mkdir(parents=True)
            sensor=target/'sensors.jsonl';sensor.write_text('{"sensor":"archived"}\n')
            output=target/'output.json';output.write_text('{"published":"archived"}\n')
            original=self.root.parent/'old checkout'/identifier/'input';original.parent.mkdir(parents=True);original.write_bytes(self.bag.read_bytes() if group=='historical' else sensor.read_bytes())
            record=dict(id=identifier,group=group,status='completed',input_path=str(original),input_sha256=compat.checksum(self.bag if group=='historical' else sensor),source_lock_sha256=compat.checksum(self.out/'source_lock.json'),config_sha256=compat.checksum(self.out/'estimator_config.json'),threshold_sha256=compat.checksum(self.out/'thresholds.json') if group=='diagnostic' else None,output_files={'output.json':compat.checksum(output)})
            self.write(target/'run.json',record);self.records.append(record)
        self.write(self.out/'run_inventory.json',self.records)
        (self.root/'HANDOFF.md').write_text('frozen original root handoff')

    @staticmethod
    def write(path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,sort_keys=True)+'\n')

    def state(self):
        return dict(protocol_sha256=compat.checksum(self.out/'protocol.json'),config_sha256=compat.checksum(self.out/'estimator_config.json'),sources={name:compat.checksum(self.root/name) for name in self.core})

    @contextlib.contextmanager
    def runtime(self):
        with patch.object(runner,'ROOT',self.root),patch.object(runner,'CORE',self.core),patch.object(runner,'save_generated',side_effect=AssertionError('generator forbidden')),patch.object(runner.subprocess,'run',side_effect=AssertionError('worker forbidden')),patch.object(runner,'freeze_thresholds',side_effect=AssertionError('threshold selection forbidden')):
            yield

    def test_relocated_sensors_preserve_absolute_provenance(self):
        record=self.records[1];before=copy.deepcopy(record)
        result=compat.resolve_input(self.out,self.root,record,self.protocol)
        self.assertEqual(Path(result['resolved_input_path']),self.out/'runs'/record['id']/'sensors.jsonl')
        self.assertEqual(result['recorded_input_path'],record['input_path']);self.assertEqual(record,before)

    def test_missing_local_input_never_falls_back_to_valid_old_path(self):
        record=self.records[1];(self.out/'runs'/record['id']/'sensors.jsonl').unlink()
        self.assertTrue(Path(record['input_path']).exists())
        with self.assertRaises(FileNotFoundError):compat.resolve_input(self.out,self.root,record,self.protocol)

    def test_corrupt_local_input_never_falls_back(self):
        record=self.records[1];(self.out/'runs'/record['id']/'sensors.jsonl').write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'SHA256'):compat.resolve_input(self.out,self.root,record,self.protocol)

    def test_historical_bag_uses_current_repository(self):
        record=self.records[0];Path(record['input_path']).unlink()
        result=compat.resolve_input(self.out,self.root,record,self.protocol)
        self.assertEqual(Path(result['resolved_input_path']),self.bag)
        self.assertEqual(result['resolution'],'current_repository')

    def test_historical_hash_disagreement_and_corruption_rejected(self):
        protocol=copy.deepcopy(self.protocol);protocol['historical_cases'][0]['sha256']='bad'
        with self.assertRaisesRegex(ValueError,'hashes disagree'):compat.resolve_input(self.out,self.root,self.records[0],protocol)
        self.bag.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'SHA256'):compat.resolve_input(self.out,self.root,self.records[0],self.protocol)

    def test_path_traversal_and_symlink_escape_rejected(self):
        for relative in ('../old checkout/input','/absolute/input'):
            with self.subTest(relative=relative),self.assertRaises(ValueError):compat.within(self.root,relative)
        (self.root/'escape').symlink_to(self.root.parent)
        with self.assertRaises(ValueError):compat.within(self.root,'escape/input')

    def test_unknown_input_group_rejected(self):
        record=dict(self.records[1],group='unknown')
        with self.assertRaises(ValueError):compat.resolve_input(self.out,self.root,record,self.protocol)

    def test_v1_1_handoff_uses_actual_experiment_and_quoted_paths(self):
        for out in (self.out,self.root.parent/'external experiment v1_1'):
            out.mkdir(exist_ok=True);self.write(out/'protocol.json',self.protocol)
            text=compat.handoff_text(out,self.root,'checked',self.records)
            commands=[line for line in text.splitlines() if line.startswith('OPENBLAS')]
            self.assertEqual(len(commands),2)
            for command in commands:
                arguments=shlex.split(command);value=arguments[arguments.index('--experiment')+1]
                self.assertEqual((self.root/value).resolve(),out.resolve())
            self.assertIn('--resume-only',commands[0]);self.assertIn('integrity-feasibility-v1.1',text)
            self.assertNotIn('integrity_feasibility_v1_20261022',text)
        self.assertEqual((self.root/'HANDOFF.md').read_text(),'frozen original root handoff')

    def test_resume_only_all_phases_no_generator_worker_or_threshold_selection(self):
        before={path:path.read_bytes() for path in self.out.rglob('*') if path.is_file()}
        destination=self.out/'compatibility/v1_2_0/HANDOFF.md'
        with self.runtime():result=runner.resume_existing(self.out,self.protocol,handoff_output=destination)
        self.assertEqual(result['runs_verified'],3);self.assertEqual(result['estimator_runs_started'],0)
        self.assertFalse(result['thresholds_reselected']);self.assertIn('--experiment',destination.read_text())
        for path,content in before.items():self.assertEqual(path.read_bytes(),content)
        with self.runtime(),self.assertRaises(FileExistsError):runner.resume_existing(self.out,self.protocol,handoff_output=destination)

    def test_resume_missing_or_incomplete_never_starts_worker(self):
        path=self.out/'runs'/self.records[1]['id']/'run.json'
        path.unlink()
        with self.runtime(),self.assertRaises(FileNotFoundError):runner.resume_existing(self.out,self.protocol)
        self.write(path,dict(self.records[1],status='failed'))
        with self.runtime(),self.assertRaises(ValueError):runner.resume_existing(self.out,self.protocol)

    def test_existing_run_uses_portable_hash_check(self):
        Path(self.records[1]['input_path']).unlink()
        with self.runtime(),contextlib.redirect_stdout(io.StringIO()):
            record=runner.run_one(self.out,self.protocol,self.records[1]['id'],'development')
        self.assertEqual(record,self.records[1])

    def test_output_and_threshold_corruption_rejected(self):
        record=self.records[2];target=self.out/'runs'/record['id']/'output.json'
        old=target.read_bytes();target.write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'Saved output'):compat.verify_record(self.out,self.root,record,self.protocol)
        target.write_bytes(old);(self.out/'thresholds.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'threshold'):compat.verify_record(self.out,self.root,record,self.protocol)

    def test_original_lock_preserved_exact_registered_runner_only(self):
        path=self.out/'source_lock.json';before=path.read_bytes()
        result=compat.verify_execution_state(self.out,self.root,self.state())
        self.assertEqual(result['mode'],'registered_compatibility');self.assertEqual(result['changed_execution_sources'],[compat.RUNNER])
        self.assertEqual(path.read_bytes(),before)
        for name in self.core[1:]:
            file=self.root/name;old=file.read_bytes();file.write_text('unregistered source')
            with self.subTest(name=name),self.assertRaises(ValueError):compat.verify_execution_state(self.out,self.root,self.state())
            file.write_bytes(old)

    def test_protocol_config_runner_snapshot_and_manifest_tampering_rejected(self):
        for path in (self.out/'protocol.json',self.out/'estimator_config.json',self.root/compat.RUNNER,self.root/self.snapshot):
            old=path.read_bytes();path.write_text('changed')
            with self.subTest(path=str(path)),self.assertRaises(ValueError):compat.verify_execution_state(self.out,self.root,self.state())
            path.write_bytes(old)
        manifest=copy.deepcopy(self.manifest);manifest['supported_execution_source_lock_sha256']=[]
        self.write(self.root/compat.MANIFEST,manifest)
        with self.assertRaisesRegex(ValueError,'not registered'):compat.verify_execution_state(self.out,self.root,self.state())

    def test_checkpoint_does_not_rewrite_frozen_inventory_or_root_handoff(self):
        inventory=self.out/'run_inventory.json';before=inventory.read_bytes()
        with self.runtime():runner.checkpoint(self.out,'test checkpoint')
        self.assertEqual(inventory.read_bytes(),before)
        handoff=self.out/'compatibility/v1_2_0/checkpoints/HANDOFF.md'
        self.assertIn('custom_v1_1',handoff.read_text());self.assertIn('--experiment',handoff.read_text())
        self.assertEqual((self.root/'HANDOFF.md').read_text(),'frozen original root handoff')

    def test_original_ledger_accepts_only_explicit_source_snapshot_replacements(self):
        ledger=self.root/'ledger.txt';expected=self.manifest['source_replacements'][compat.RUNNER]['original_sha256']
        ledger.write_text(expected+'  '+compat.RUNNER+'\n'+compat.checksum(self.out/'protocol.json')+'  '+str((self.out/'protocol.json').relative_to(self.root))+'\n')
        result=compat.preserve_original_artifact_hashes(self.root,ledger)
        self.assertEqual(result['original_ledger_entries_checked'],2)
        self.assertEqual(result['explicit_source_replacements'],[compat.RUNNER])
        (self.out/'protocol.json').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Original artifact changed'):compat.preserve_original_artifact_hashes(self.root,ledger)

    def test_cli_requires_explicit_experiment(self):
        with patch('sys.argv',['runner','--resume-only']),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:runner.main()
        self.assertEqual(error.exception.code,2)

    def test_archived_metrics_are_87_rows_15_development_72_diagnostic(self):
        with (EXPERIMENT/'results_reviewed/metrics.csv').open() as stream:rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),87)
        self.assertEqual(sum(row['group']=='development' for row in rows),15)
        self.assertEqual(sum(row['group']=='diagnostic' for row in rows),72)


class ArchivedRelocationTests(unittest.TestCase):
    def test_real_archive_relocated_resume_and_audit_without_estimator(self):
        with tempfile.TemporaryDirectory(prefix='integrity archive relocation ') as temporary:
            root=Path(temporary)/'new repository';root.mkdir()
            shutil.copytree(REPOSITORY/'tools',root/'tools',ignore=shutil.ignore_patterns('__pycache__'))
            out=root/EXPERIMENT.relative_to(REPOSITORY)
            shutil.copytree(EXPERIMENT,out)
            for name in runner.CORE:
                target=root/name
                if not target.exists():
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(REPOSITORY/name,target)
            protocol=json.loads((out/'protocol.json').read_text())
            for case in protocol['historical_cases']:
                target=root/case['bag'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(REPOSITORY/case['bag'],target)
            before={path:compat.checksum(path) for path in out.rglob('*') if path.is_file()}
            environment=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
            argument=str(out.relative_to(root));handoff=root/'new handoff.md'
            commands=[
                [sys.executable,'tools/run_single_car_integrity_experiment.py','--experiment',argument,'--resume-only','--handoff-output',str(handoff)],
                [sys.executable,'tools/verify_single_car_integrity_artifacts.py','--experiment',argument]]
            results=[]
            for command in commands:
                completed=subprocess.run(command,cwd=root,env=environment,text=True,capture_output=True,timeout=60)
                self.assertEqual(completed.returncode,0,completed.stderr);results.append(json.loads(completed.stdout))
            resume,audit=results
            self.assertEqual(resume['runs_verified'],31);self.assertEqual(resume['estimator_runs_started'],0)
            self.assertEqual(audit['runs_checked'],31);self.assertEqual(audit['updates_checked'],2769)
            self.assertEqual(audit['independent_hypothesis_records_checked'],11076)
            self.assertEqual(audit['synthetic_inputs_regenerated'],0)
            for resolutions in (resume['input_resolutions'],audit['input_resolution_records']):
                self.assertEqual(len(resolutions),31)
                for row in resolutions:
                    self.assertTrue(Path(row['resolved_input_path']).is_relative_to(root))
                    self.assertFalse(Path(row['recorded_input_path']).is_relative_to(root))
            self.assertIn('integrity_feasibility_v1_1_20261022',handoff.read_text())
            self.assertIn('--experiment',handoff.read_text());self.assertIn('--resume-only',handoff.read_text())
            for path,expected in before.items():self.assertEqual(compat.checksum(path),expected)


if __name__=='__main__':unittest.main()
