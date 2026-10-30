"""Run the original adapter suite natively and with scoped diagnostic math.

Native failures are retained; passing in diagnostic mode does not claim native
portability or original event-archive identity. No estimator is executed.
"""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from audit_identity import decimal_math

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New directory')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(args.repo/'tools/integrity_validation_20261030'))
    path=args.repo/'tools/integrity_validation_20261030/test_adapter.py'
    spec=importlib.util.spec_from_file_location('original_adapter_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    import experiment
    original_math=experiment.simulate.math
    results=[]
    for mode in ('native','decimal120'):
        stream=io.StringIO()
        suite=unittest.defaultTestLoader.loadTestsFromModule(module)
        runner=unittest.TextTestRunner(stream=stream,verbosity=2)
        if mode=='native': result=runner.run(suite)
        else:
            with decimal_math(experiment.simulate,120): result=runner.run(suite)
        assert experiment.simulate.math is original_math
        (args.output/(mode+'.log')).write_text(stream.getvalue(),encoding='utf-8')
        results.append(dict(mode=mode,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                            success=result.wasSuccessful(),math_namespace_restored=True))
    (args.output/'ADAPTER_CHECKS.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results))
    if not results[-1]['success']:raise SystemExit(1)

if __name__=='__main__':main()
