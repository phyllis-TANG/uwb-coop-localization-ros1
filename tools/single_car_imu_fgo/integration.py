"""Bounded, receipt-visible left-hold angular integration with exact ns traces."""
import bisect
import copy
import math
import numpy as np


class AngularBuffer:
    def __init__(self,hold_ns=100_000_000,capacity=512):
        self.hold_ns,self.capacity=hold_ns,capacity
        self.rows=[]; self.last_source=None; self.counters={}; self.peak=0
    def add(self,identity,rate):
        def status(s): self.counters[s]=self.counters.get(s,0)+1; return s
        source=identity['mapped_header_epoch_ns']
        if not math.isfinite(rate): return status('nonfinite_angular_rate')
        if source>identity['receive_epoch_ns']: return status('angular_source_after_receipt')
        if self.last_source is not None and source<=self.last_source: return status('duplicate_or_out_of_order_angular_source')
        if len(self.rows)>=self.capacity: raise BufferError('angular buffer capacity exceeded')
        self.rows.append(dict(identity=copy.deepcopy(identity),rate_rad_s=float(rate))); self.last_source=source; self.peak=max(self.peak,len(self.rows))
        return status('angular_control_accepted')
    def prune(self,start):
        i=bisect.bisect_right([r['identity']['mapped_header_epoch_ns'] for r in self.rows],start)-1
        if i>0: del self.rows[:i]
    def integrate(self,start,end,cutoff):
        if not all(type(x) is int for x in (start,end,cutoff)) or end<=start: raise ValueError('integer positive integration interval required')
        eligible=[r for r in self.rows if r['identity']['receive_epoch_ns']<=cutoff]
        sources=[r['identity']['mapped_header_epoch_ns'] for r in eligible]; segments=[]; gaps=[]; total=0.; cursor=start
        while cursor<end:
            i=bisect.bisect_right(sources,cursor)-1
            next_source=sources[i+1] if i+1<len(sources) else end
            if i<0 or cursor>=sources[i]+self.hold_ns:
                stop=min(end,next_source)
                if stop<=cursor: stop=end
                gaps.append(dict(start_epoch_ns=cursor,end_epoch_ns=stop)); cursor=stop; continue
            row=eligible[i]; stop=min(end,next_source,sources[i]+self.hold_ns)
            dt=stop-cursor; angle=row['rate_rad_s']*(dt/1e9); total+=angle
            segments.append(dict(start_epoch_ns=cursor,end_epoch_ns=stop,dt_ns=dt,rate_rad_s=row['rate_rad_s'],angle_rad=angle,dependency=copy.deepcopy(row['identity'])))
            cursor=stop
        return dict(valid=not gaps,start_epoch_ns=start,end_epoch_ns=end,dt_ns=end-start,raw_angle_rad=total if not gaps else None,
                    partial_angle_rad=total,segments=segments,gaps=gaps,rule='arrived left-hold; no future endpoint; no partial angle factor on gaps')


def angular_covariance(dt,angle_density,bias_density):
    if not (dt>0 and angle_density>0 and bias_density>0): raise ValueError('positive densities and dt required')
    qg,qb=angle_density**2,bias_density**2
    return np.array([[qg*dt+qb*dt**3/3,-qb*dt**2/2],[-qb*dt**2/2,qb*dt]])
