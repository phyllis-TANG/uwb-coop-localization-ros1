"""Causal fixed-window solution separation for two UWB-equipped vehicles.

Coordinates and ranges are in metres. The numerical bound is conditional on
the local linearisation and the declared input models, not a certified PL.
"""
from collections import deque
from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import least_squares
from scipy.special import ndtr, ndtri

MODES = {f'R{r + 1}-A{a + 1}': (4*r+a,) for r in range(2) for a in range(4)}
MODES.update({'peer': (8,), 'R1-anchors': (0, 1, 2, 3), 'R2-anchors': (4, 5, 6, 7)})
NAMES = tuple(MODES)


@dataclass(frozen=True)
class Config:
    range_sigma: float = .04
    odom_sigma: float = .03              # m / sqrt(s)
    initial_sigma: float = .20           # independent surveyed position coordinate
    bias_walk_sigma: float = .01         # m / sqrt(s)
    initial_bias_sigma: float = .30      # prior at first augmented epoch
    residual_bound: float = .02          # engineering assumption, per range row
    fault_prior: float = .001            # sensitivity prior per mutually exclusive fault mode
    phmi: float = .01                    # per robot per epoch
    pfa: float = .01                     # joint test budget per epoch, conditional fixed stage
    max_augmented: int = 2
    window: int = 6
    lookback: int = 2                    # fit onset at detection and up to two previous epochs
    information_floor: float = 1.0       # minimum marginal position precision, m^{-2}
    max_condition: float = 1e5
    blind: bool = False
    gn_steps: int = 32
    gn_tol: float = 1e-6


class Window:
    """One common set of row identifiers for all independently refitted subsets."""
    def __init__(self, frames, anchors, cfg, active):
        self.frames, self.anchors, self.cfg = frames, anchors, cfg
        self.n = n = len(frames)
        self.p = p = 4*n
        self.ranges = np.asarray([f['ranges'] for f in frames])
        self.heights = np.asarray([f['heights'] for f in frames])
        self.x0 = np.concatenate([f['dr'] for f in frames])
        self.a = np.zeros((p, p))
        self.a[:4,:4] = np.eye(4)
        self.target = np.zeros(p)
        self.target[:4] = frames[0]['dr']
        prev_sigma = math.sqrt(cfg.initial_sigma**2 + cfg.odom_sigma**2*frames[0]['elapsed'])
        self.scale = np.full(p, prev_sigma)
        for i in range(1, n):
            sl = slice(4*i,4*i+4)
            self.a[sl,sl] = np.eye(4)
            self.a[sl,4*i-4:4*i] = -np.eye(4)
            self.target[sl] = frames[i]['odom']
            self.scale[sl] = cfg.odom_sigma*math.sqrt(frames[i]['t']-frames[i-1]['t'])
        self.rscale = np.broadcast_to(np.asarray(cfg.range_sigma), (9,))
        self.model = {}
        for name, onset in active.items():
            indices = [i for i,f in enumerate(frames) if f['t'] >= onset]
            if indices:
                self.model[name] = indices
        nb = sum(map(len,self.model.values()))
        self.linear = np.zeros((p+nb,p+nb))
        self.linear[:p,:p] = self.a/self.scale[:,None]
        self.y = np.r_[self.target/self.scale,np.zeros(nb)]
        self.bias_jac = np.zeros((9*n,nb))
        self.data_rows = np.ones(p+nb,dtype=bool)
        self.data_rows[:4] = False
        j = 0
        for name, ii in self.model.items():
            for h, i in enumerate(ii):
                links = np.array(MODES[name])
                self.bias_jac[9*i+links,j] = 1
                # Start of this window may be after estimated onset. Give the
                # retained bias its prior random-walk marginal at window entry.
                if h == 0:
                    self.data_rows[p+j] = False
                    sd = math.sqrt(cfg.initial_bias_sigma**2 + cfg.bias_walk_sigma**2*
                                   max(0.,frames[i]['t']-active[name]))
                else:
                    sd = cfg.bias_walk_sigma*math.sqrt(frames[i]['t']-frames[ii[h-1]]['t'])
                    self.linear[p+j,p+j-1] = -1/sd
                self.linear[p+j,p+j] = 1/sd
                j += 1
        self.size = p+nb
        self.init = np.r_[self.x0,np.zeros(nb)]
        self.ir = np.arange(n)[:,None,None]*9 + np.arange(8).reshape(1,2,4)
        self.ic = np.arange(n)[:,None,None]*4 + np.array([0,2])[None,:,None]
        self.e = np.zeros((4,self.size))
        self.e[:,p-4:p] = np.eye(4)

    def ranges_and_jac(self, state):
        n,p = self.n,self.p
        xy = state[:p].reshape(n,2,2)
        dr = xy[:,:,None,:] - self.anchors[None,None,:,:2]
        dz = self.heights[:,:,None] - self.anchors[None,None,:,2]
        lens = np.sqrt((dr**2).sum(axis=3)+dz**2)
        pair = xy[:,0,:]-xy[:,1,:]
        peer = np.sqrt((pair**2).sum(axis=1) + (self.heights[:,0]-self.heights[:,1])**2)
        predicted = np.column_stack((lens.reshape(n,8),peer)).ravel()
        j = np.zeros((9*n,self.size))
        for a in range(2):
            j[self.ir,self.ic+a] = dr[:,:,:,a]/np.maximum(lens,1e-10)
            grad = pair[:,a]/np.maximum(peer,1e-10)
            i = np.arange(n)
            j[9*i+8,4*i+a] = grad
            j[9*i+8,4*i+a+2] = -grad
        if self.size>p:
            predicted += self.bias_jac @ state[p:]
            j[:,p:] = self.bias_jac
        return predicted,j

    def fit(self, excluded):
        n,p = self.n,self.p
        # All fits start at the same *exogenous* dead-reckoning path. The
        # deleted observations never enter a sub-solution's past updates.
        state = self.init.copy()
        used = np.isfinite(self.ranges)
        if excluded:
            used[:,list(excluded)] = False
        used = used.ravel()
        scale = np.tile(self.rscale,n)[used]
        observed = self.ranges.ravel()[used]
        def linearization(point):
            pred, raw = self.ranges_and_jac(point)
            weighted = raw[used]/scale[:,None]
            return (np.r_[self.y-self.linear@point,(observed-pred[used])/scale],
                    np.vstack((self.linear,weighted)))

        for _ in range(self.cfg.gn_steps):
            residual, jac = linearization(state)
            cf = cho_factor(jac.T@jac,check_finite=False)
            delta = cho_solve(cf,jac.T@residual,check_finite=False)
            if np.max(np.abs(delta)) <= self.cfg.gn_tol:
                break
            state += delta
        else:
            # This fallback solves exactly the same least-squares objective.
            # Analytic, range-only test cases can cause undamped GN to cycle
            # when one robot's anchor group is withheld. Start again from the
            # external trajectory and verify the same final stationarity test.
            recovered = least_squares(lambda x: -linearization(x)[0], self.init,
                                      jac=lambda x: linearization(x)[1],
                                      method='trf',ftol=None,xtol=1e-13,gtol=1e-9,max_nfev=180)
            state = recovered.x
            residual, jac = linearization(state)
            cf = cho_factor(jac.T@jac,check_finite=False)
            delta = cho_solve(cf,jac.T@residual,check_finite=False)
            if not np.isfinite(delta).all() or np.max(np.abs(delta))>self.cfg.gn_tol:
                raise ArithmeticError("nonconvergence")
        j = jac[self.size:]
        # Each fit's whitened influence is embedded into the same global row
        # basis. Covariance of a difference is ||S_full-S_sub||^2 row-wise.
        left = cho_solve(cf,self.e.T,check_finite=False).T
        gain = np.zeros((4,self.size+9*n))
        gain[:,:self.size] = left @ self.linear.T
        gain[:,self.size+np.flatnonzero(used)] = left @ j.T
        cov = gain @ gain.T
        raw_gain = gain[:,self.size:]/np.tile(self.rscale,n)
        measured_info = None
        if not excluded:
            # Profile prior-free range/motion information over all nuisance
            # coordinates. Exclude initial position and initial bias priors;
            # RW increments within the retained window remain part of the
            # assumed temporal model. This catches a geometry supported only
            # by the survey (e.g. all links absent except the peer range).
            jr = np.vstack((self.linear[self.data_rows],j))
            target = np.arange(p-4,p)
            nuisance = np.delete(jr,target,axis=1)
            projected = jr[:,target]
            if nuisance.shape[1]:
                projected = projected - nuisance@np.linalg.lstsq(nuisance,projected,rcond=1e-10)[0]
            measured_info = np.linalg.eigvalsh(projected.T@projected)
        return dict(xy=state[p-4:p].copy(),gain=gain,raw_gain=raw_gain,
                    sigma=np.sqrt(np.diag(cov)),cov=cov,measured_info=measured_info,
                    bound=self.cfg.residual_bound*np.abs(raw_gain).sum(axis=1))


def _risk_envelope(primary, subs, thresholds, cfg):
    """Invert a two-sided upper bound separately for all four coordinates."""
    sig = np.stack([s['sigma'] for s in subs])
    offset = np.stack([s['bound'] for s in subs]) + thresholds
    target = cfg.phmi/2
    def risk(level):
        nominal = np.minimum(1,2*ndtr((primary['bound']-level)/primary['sigma']))
        tails = np.minimum(1,2*ndtr((offset-level)/sig))
        return nominal + cfg.fault_prior*tails.sum(axis=0)
    low = np.zeros(4)
    hi = np.maximum(primary['bound']+12*primary['sigma'],(offset+12*sig).max(axis=0))
    for _ in range(44):
        mid = (low+hi)/2
        too_small = risk(mid)>target
        low = np.where(too_small,mid,low)
        hi = np.where(too_small,hi,mid)
    return hi


def _shadow_guard(public_xy, shadows, cfg):
    # Predetermined tail probabilities. At any data-selected output position,
    # the triangle inequality holds against every fixed clean shadow (including
    # the nominal one). No conditioning on the selected world's correctness.
    axis_risk = cfg.phmi/2
    nominal_alpha = axis_risk/2
    fault_alpha = min(.999,axis_risk/(2*len(NAMES)*cfg.fault_prior))
    factors = [-ndtri(nominal_alpha/2)] + [-ndtri(fault_alpha/2)]*len(NAMES)
    return np.max([np.abs(public_xy-s['xy'])+s['bound']+k*s['sigma']
                   for k,s in zip(factors,shadows)],axis=0)


class Monitor:
    def __init__(self,anchors,heights,initial_xy,config=None):
        self.cfg = config or Config()
        self.anchors = np.asarray(anchors,dtype=float).reshape(4,3).copy()
        self.heights = np.asarray(heights,dtype=float).reshape(2).copy()
        self.dr = np.asarray(initial_xy,dtype=float).reshape(4).copy()
        self.frames = deque(maxlen=self.cfg.window)
        self.first_t = self.last_t = None
        self.active = {}
        if self.cfg.blind and self.cfg.max_augmented != 2:
            raise ValueError('blind mode uses a fixed nine-link state')
        scales = [self.cfg.initial_sigma,self.cfg.odom_sigma,self.cfg.bias_walk_sigma,
                  self.cfg.initial_bias_sigma,*np.broadcast_to(self.cfg.range_sigma,(9,))]
        if not all(np.isfinite(scales)) or min(scales)<=0 or self.cfg.window<1:
            raise ValueError('invalid measurement scales or window length')
        if not (0 < self.cfg.phmi < 1 and 0 < self.cfg.pfa < 1 and
                0 < self.cfg.fault_prior*len(NAMES) < 1):
            raise ValueError('invalid scenario risk parameters')

    def step(self,t,ranges,odom,heights=None):
        t = float(t)
        odom = np.asarray(odom,dtype=float).reshape(4)
        r = np.asarray(ranges,dtype=float).reshape(9)
        h = self.heights if heights is None else np.asarray(heights,dtype=float).reshape(2)
        if not np.isfinite(t) or not np.isfinite(odom).all() or not np.isfinite(h).all():
            raise ValueError('invalid timestamp, odometry or height')
        if self.last_t is not None and t<=self.last_t:
            raise ValueError('epochs must be strictly increasing')
        if self.first_t is None:
            self.first_t = t
            if self.cfg.blind:
                self.active = {name:t for name in NAMES[:9]}
        self.last_t = t
        self.dr += odom
        self.frames.append(dict(t=t,ranges=r.copy(),heights=h.copy(),odom=odom.copy(),
                                dr=self.dr.copy(),elapsed=t-self.first_t))
        out = dict(t=t,xy=self.dr.reshape(2,2).tolist(),hpl=[None,None],
                   status='no_current_ranges',fd_pass=False,augmented=list(self.active),
                   selected=[],test_ratio=None,condition=None,min_information=None,
                   limiting_mode=None,hpl_mixture=None,hpl_guard=None)
        if not np.isfinite(r).any():
            return out
        frames = list(self.frames)
        c = self.cfg
        # A local change is committed only after an accepted rerun; the identity
        # of the synthetic fault and the hidden trajectory are never inputs.
        active = dict(self.active)
        shadow_bank = None
        try:
            while True:
                window = Window(frames,self.anchors,c,active)
                primary = window.fit(())
                out['xy'] = primary['xy'].reshape(2,2).tolist()
                # The blind comparator reproduces a fixed nine-bias architecture
                # with its specified priors. Log its prior-free diagnostic too.
                eig = (1/np.linalg.eigvalsh(primary['cov'])[::-1]
                       if c.blind else primary['measured_info'])
                out['condition'] = float(eig[-1]/max(1.e-15,eig[0]))
                out['min_information'] = float(eig[0])
                out['prior_free_information'] = float(primary['measured_info'][0])
                if out['condition']>c.max_condition or out['min_information']<c.information_floor:
                    out['status']='weak_geometry'
                    return out
                # Accepted augmented groups have a bias model; overlapping but
                # distinct faults continue to have a leave-mode-out test.
                rem = list(NAMES) if c.blind else [k for k in NAMES if k not in active]
                subs = [window.fit(MODES[k]) for k in rem]
                if not active:
                    shadow_bank = [primary,*subs]
                # Divide joint nominal stage PFA across all vehicle axes and
                # modes. Adaptively revisiting this test is not a global PFA proof.
                scale = -ndtri(c.pfa/(2*4*len(rem)))
                thresholds = np.array([scale*np.linalg.norm(primary['gain']-s['gain'],axis=1)
                    + c.residual_bound*np.abs(primary['raw_gain']-s['raw_gain']).sum(axis=1)
                    for s in subs])
                separation = np.stack([np.abs(primary['xy']-s['xy']) for s in subs])
                ratio = separation/np.maximum(thresholds,1e-12)
                k = int(np.unravel_index(np.argmax(ratio),ratio.shape)[0])
                peak = float(ratio.max())
                out.update(test_ratio=peak,limiting_mode=rem[k])
                if peak<=1.:
                    if shadow_bank is None:
                        w0 = Window(frames,self.anchors,c,{})
                        shadow_bank=[w0.fit(())]+[w0.fit(MODES[key]) for key in NAMES]
                    level = _risk_envelope(primary,subs,thresholds,c)
                    guard = _shadow_guard(primary['xy'],shadow_bank,c)
                    out.update(hpl=np.linalg.norm(np.maximum(level,guard).reshape(2,2),axis=1).tolist(),
                               hpl_mixture=np.linalg.norm(level.reshape(2,2),axis=1).tolist(),
                               hpl_guard=np.linalg.norm(guard.reshape(2,2),axis=1).tolist(),
                               status='accepted',fd_pass=True,augmented=list(active))
                    self.active = active
                    return out
                if c.blind or len(active)>=c.max_augmented:
                    out['status']='ss_alert'
                    return out
                key=rem[k]
                onset = frames[max(0,len(frames)-1-c.lookback)]['t']
                active[key] = onset
                out['selected'].append(key)
        except (ArithmeticError,np.linalg.LinAlgError):
            out['status']='numerical_alert'
            return out
