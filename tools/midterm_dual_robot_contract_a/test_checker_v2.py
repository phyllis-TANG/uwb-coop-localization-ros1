"""53 unchanged historical tests rebound to v2, plus one cache isolation regression."""
import copy
import unittest
import core
import checker_v2
from generate import make

class CacheIsolation(unittest.TestCase):
    def test_cache_isolation_vehicle_and_observation_input(self):
        x=make('isolation')[0]
        # Same exact geometric box in both vehicles, but deliberately different data/variance.
        x['observation_intervals'][4]=['100','100'];x['noise_model']['variance'][4]='1/100'
        core.seal(x)
        box=[['0','1'],['1','2']]*2
        ctx=checker_v2.PreparedInput(x);z=ctx.box(box)
        p=ctx.anchors_for(0,z[:2]);s=ctx.anchors_for(1,z[:2])
        self.assertEqual(p[0],s[0]) # same distances
        self.assertNotEqual(p[1:],s[1:]) # different observations cannot share residual bounds
        for mode in ('4d','5d','no_peer'):
            b=box+[x['domains'][4]] if mode=='5d' else box
            self.assertEqual(ctx.bounds(b,mode),core.bounds(x,b,mode))
            self.assertEqual(ctx.bounds(b,mode),core.bounds(x,b,mode)) # cache-hit path
        self.assertGreater(ctx.anchor_hits,0); self.assertEqual(ctx.anchor_misses,2)
        old=ctx.bounds(box,'no_peer')
        y=copy.deepcopy(x);y['observation_intervals'][0]=['200','200'];core.seal(y)
        ctx2=checker_v2.PreparedInput(y)
        self.assertEqual(ctx2.anchor_hits,0);self.assertEqual(len(ctx2._anchor_cache),0)
        self.assertNotEqual(ctx2.bounds(box,'no_peer'),old)
        self.assertEqual(ctx2.bounds(box,'no_peer'),core.bounds(y,box,'no_peer'))
        self.assertEqual(ctx.bounds(box,'no_peer'),old)
        # Exact numeric key equivalence, without decimal rounding or tolerance.
        same=[['0/2','2/2'],['2/2','4/2']]*2
        misses=ctx.anchor_misses;self.assertEqual(ctx.bounds(same,'no_peer'),old);self.assertEqual(ctx.anchor_misses,misses)
        # Caller mutation cannot poison a prepared snapshot; a fresh check reparses new input.
        x['observation_intervals'][0]=['300','300'];core.seal(x)
        self.assertEqual(ctx.bounds(box,'no_peer'),old)
        self.assertEqual(checker_v2.PreparedInput(x).bounds(box,'no_peer'),core.bounds(x,box,'no_peer'))
        # A path-loaded entry must ignore an unrelated B module also named core.
        import importlib.util, sys, types
        from pathlib import Path
        saved=sys.modules['core'];sys.modules['core']=types.ModuleType('unrelated_B_core')
        try:
            spec=importlib.util.spec_from_file_location('entry_collision_test',Path(checker_v2.__file__))
            entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
            self.assertEqual(entry.PreparedInput(y).bounds(box,'no_peer'),core.bounds(y,box,'no_peer'))
        finally:sys.modules['core']=saved

if __name__=='__main__':
    import test_contract
    import check as archive_module
    # Test-only rebinding. Production v2 never mutates core or archive globals.
    test_contract.check=checker_v2.check
    archive_module.check=checker_v2.check
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(test_contract.ContractTests),
                            unittest.defaultTestLoader.loadTestsFromTestCase(CacheIsolation)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
