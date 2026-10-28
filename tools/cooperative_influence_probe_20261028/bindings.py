"""Only import hash-locked F0 and existing frontend; no shared file changes."""
import importlib,os,sys
from common import ROOT,sources
sources();os.environ['PEER_GATE_FROZEN_ROOT']=str(ROOT)
sys.path.insert(0,str(ROOT/'tools/cooperative_peer_gate_probe_20261028'))
pinned=importlib.import_module('pinned');probe=importlib.import_module('probe');records=importlib.import_module('records')
base=pinned.graph;frontend=pinned.frontend;legacy=pinned.legacy;replay=pinned.replay
