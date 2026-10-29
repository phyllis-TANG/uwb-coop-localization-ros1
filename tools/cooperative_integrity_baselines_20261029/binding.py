"""Read-only imports; all 19 original files must match PR68's frozen manifest."""
import os
import sys
from pathlib import Path
from common import ROOT
os.environ['PEER_GATE_FROZEN_ROOT'] = str(ROOT)
sys.path.insert(0, str(ROOT/'tools/cooperative_peer_gate_probe_20261028'))
from pinned import MANIFEST, frontend, graph, legacy, replay, simulate  # noqa: E402
from probe import decision, numeric, semantic  # noqa: E402
# Frozen imports are now resolved and SHA-checked; local adapters must retain
# precedence over the older wrapper's generic evaluate/report module names.
sys.path.insert(0, str(Path(__file__).resolve().parent))
