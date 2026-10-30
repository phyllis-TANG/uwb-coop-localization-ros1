"""Monitoring wrapper: the full G1 numerical path is never changed."""
import copy
import time
import numpy as np
from binding import frontend, graph, legacy, decision as q_decision
from common import SPEC, digest
from decisions import declarations
from influence import Influence, Primitives
from monitors import antenna, four_anchor, separation

GROUPS = ('car1_absolute','car2_absolute','peer')


def filtered(observations, peer, excluded):
    obs = copy.deepcopy(observations)
    if excluded == 'car1_absolute': obs['car1'] = {}
    elif excluded == 'car2_absolute': obs['car2'] = {}
    elif excluded not in (None, 'peer'): raise ValueError('Unknown excluded source')
    return obs, None if excluded == 'peer' else peer


class TrackedGraph(graph.WindowGraph):
    def __init__(self, config, primitives, excluded=None, covariance=True):
        super().__init__(config, excluded != 'peer')
        self.excluded = excluded
        self.noise = Influence(primitives) if covariance else None
        self.latest = None
        self.cost_wall_s = 0.; self.numeric_wall_s = 0.

    def update(self, stamp, local, observations, peer):
        start = time.perf_counter()
        obs, value = filtered(observations, peer, self.excluded)
        # No full graph state/guess/prior ever enters this update.
        before = time.perf_counter()
        result = super().update(stamp, local, obs, value)
        self.numeric_wall_s = time.perf_counter()-before
        if self.noise is not None and not getattr(self.noise,'failure_reason',None):
            try:
                self.noise.update(self, result)
            except (KeyError,np.linalg.LinAlgError) as error:
                # Current primitive model is frozen to adjacent 1s Odom edges.
                # A gap is unsupported covariance, never a successful zero score.
                self.noise.failure_reason=type(error).__name__+': '+str(error)
                self.noise.last_k=None; self.noise.last_rank=None
        self.cost_wall_s = time.perf_counter()-start
        self.latest = result
        return result

    def history(self):
        snapshot = copy.deepcopy(self.snapshot())
        if not self.peer_enabled: snapshot['peers_m'] = [None]*len(snapshot['times_s'])
        return dict(snapshot=snapshot, prediction=self.latest['prediction_pose'] if self.latest else None,
                    noise=None if self.noise is None else self.noise.record())


class MonitoredGraph(TrackedGraph):
    def __init__(self, config, covariance=True):
        self.primitives = Primitives()
        super().__init__(config, self.primitives, covariance=covariance)
        self.subsets = {group:TrackedGraph(config, self.primitives, group, covariance) for group in GROUPS}
        self.current = None

    def update(self, stamp, local, observations, peer):
        for subset in self.subsets.values(): subset.update(stamp, local, observations, peer)
        result = super().update(stamp, local, observations, peer)
        ss = {}
        for group, subset in self.subsets.items():
            values = []
            for ci, car in enumerate(legacy.CARS):
                kf = None if self.noise is None else self.noise.antenna_k(self, ci)
                ks = None if subset.noise is None else subset.noise.antenna_k(subset, ci)
                if not (result['accepted_graph'] and subset.latest['accepted_graph']) or kf is None or ks is None:
                    values.append(dict(computable=False, statistic=None, reason='GRAPH_FAILED_STARTUP_OR_RANK',
                                       delta_xy_m=None, separation_m=None, rank=None))
                else:
                    values.append(separation(antenna(result['pose'][3*ci:3*ci+3], self.config['models'][car])[:2],
                        antenna(subset.latest['pose'][3*ci:3*ci+3], self.config['models'][car])[:2], kf, ks))
            ss[group] = values
        aux = self.subsets['peer'].latest
        self.current = dict(state_time_s=stamp, ss=ss, b0=q_decision(peer, aux, self.config),
            subset_history_hashes={group:digest(g.history()) for group,g in self.subsets.items()},
            main_history_hash=digest(self.history()),
            subset_prior_hashes={group:digest(g.prior.record()) for group,g in self.subsets.items()},
            covariance_wall_s=sum(g.cost_wall_s-g.numeric_wall_s for g in [self,*self.subsets.values()]),
            graph_wall_s=sum(g.numeric_wall_s for g in [self,*self.subsets.values()]),
            subset_results={group:dict(pose=g.latest['pose'], accepted=g.latest['accepted_graph'],
                status=g.latest['status'], marginalizations=g.marginalizations,
                eliminated_constant=g.eliminated_constant,
                influence=None if g.noise is None else g.noise.record()) for group,g in self.subsets.items()})
        return result


class IntegrityReplay(frontend.JointReplay):
    def __init__(self, config, sink, origin_ns, covariance=True):
        super().__init__(config, 'D1', self.publish, origin_ns)
        self.graph = MonitoredGraph(config, covariance); self.sink = sink; self.monitor_finish = 0.

    def publish(self, row):
        start = time.perf_counter()
        if self.graph.current is None or self.graph.current['state_time_s'] != row['state_time_s']:
            unknown = dict(computable=False, statistic=None, reason='NO_CURRENT_ODOM')
            monitor = dict(ss={g:[unknown.copy(),unknown.copy()] for g in GROUPS},
                b0=dict(state='unknown', reason='NO_CURRENT_ODOM', engineering_q=None),
                covariance_wall_s=0., graph_wall_s=0., subset_history_hashes={}, subset_results={})
        else:
            monitor = copy.deepcopy(self.graph.current)
        monitor['b1'] = {noise:{car:four_anchor(row['bins'][car]['observations'],self.config['models'][car],
                            row['bins'][car]['sample_counts'],noise) for car in legacy.CARS}
                         for noise in SPEC['b1_noise_sensitivity']}
        monitor['four_anchor_wall_s'] = time.perf_counter()-start
        monitor['declarations'] = declarations(monitor,row['accepted_graph'])
        monitor['four_anchor_and_declaration_wall_s'] = time.perf_counter()-start
        cost = row['update_wall_s']+monitor['four_anchor_and_declaration_wall_s']
        self.monitor_finish = max(row['availability_cutoff_s'],self.monitor_finish)+cost
        row['monitor_available_time_virtual_s'] = self.monitor_finish
        row['total_monitored_emit_wall_s'] = cost
        row['monitor'] = monitor
        current=self.graph.current is not None and self.graph.current['state_time_s']==row['state_time_s']
        row['marginal_evidence'] = {'main':row['marginalization_details'],
            **{name:g.latest['marginalization_details'] if current else [] for name,g in self.graph.subsets.items()}}
        if current and all(g.noise is not None and g.noise.last_k is not None for g in [self.graph,*self.graph.subsets.values()]) and row['state_time_s'] in (3.,23.,24.,37.,38.,48.,59.,63.):
            row['linear_evidence'] = {name:dict(snapshot=copy.deepcopy(g.snapshot()),
                prior_b=g.noise.prior_b.tolist(), k=g.noise.last_k.tolist() if g.noise.last_k is not None else None)
                for name,g in [('main',self.graph),*self.graph.subsets.items()]}
        self.sink(row)


def run(events, config, sink, covariance=True):
    replay = IntegrityReplay(config, sink, events[0]['receive_epoch_ns'], covariance)
    for event in events: replay.ingest(event)
    replay.finish()
    return replay
