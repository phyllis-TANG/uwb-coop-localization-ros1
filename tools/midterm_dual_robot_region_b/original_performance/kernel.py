"""B-side exact peer residual memoization, local to one P4 certificate."""
from functools import lru_cache
from fractions import Fraction
from common import load_module, TOOL
from certificate import RationalEvaluator, distance_to_interval, minus, square, plus, root


class PeerMemo(RationalEvaluator):
    def __init__(self, model, method):
        super().__init__(model, method)
        assert method == 'P4'
        lower = self.obs[8][0] - Fraction(model['bias_domain'][1])
        upper = self.obs[8][1] - Fraction(model['bias_domain'][0])

        @lru_cache(maxsize=8192)
        def peer(dx, dy):
            interval = root(plus(square(dx), square(dy)))
            low, high = distance_to_interval(interval, lower, upper)
            return low/self.v[8], high/self.v[8]
        self.peer = peer

    def __call__(self, box):
        anchors = plus(self.anchor_sum(box[:2], 0), self.anchor_sum(box[2:4], 4))
        return plus(anchors, self.peer(minus(box[0], box[2]), minus(box[1], box[3])))


def checker():
    module = load_module('p4_peer_memo_only', TOOL/'checker_v2/b_fast.py')
    module.RationalEvaluator = PeerMemo
    return module
