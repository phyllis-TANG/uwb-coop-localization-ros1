"""Stateful engineering policy, independent of the main solution and labels."""
import math


class LinkPolicy:
    def __init__(self,p):
        self.p=dict(p);self.mode='normal';self.gain=1.;self.warn=self.severe=self.clear=self.recover=0;self.last_epoch=None
    def step(self,epoch,score,unknown_reason=None):
        if type(epoch) is not int or self.last_epoch is not None and epoch<=self.last_epoch:raise ValueError('each link decision once, increasing state time')
        self.last_epoch=epoch;before=self.mode
        if unknown_reason is not None or score is None or not math.isfinite(score):
            self.warn=self.severe=self.clear=self.recover=0
            return dict(state='unknown',policy_mode_held=self.mode,reason=unknown_reason or 'NONFINITE_SCORE',information_multiplier=self.gain,score=None,monitorable=False,transition=False)
        p=self.p;self.warn=self.warn+1 if score>=p['warn_score'] else 0;self.severe=self.severe+1 if score>=p['disable_score'] else 0;self.clear=self.clear+1 if score<=p['clear_score'] else 0
        reason='CONSISTENT_FIXED_SHADOW'
        if self.mode=='normal':
            if self.severe>=p['disable_count']:self.mode='disabled';self.gain=0.;reason='PERSISTENT_SEVERE_INCONSISTENCY'
            elif self.warn>=p['warn_count']:self.mode='downweighted';self.gain=p['lowered_information'];reason='PERSISTENT_INCONSISTENCY'
            elif self.warn:reason='PENDING_CONFIRMATION_BASE_WEIGHT'
        elif self.mode in ('downweighted','disabled'):
            if self.severe>=p['disable_count']:self.mode='disabled';self.gain=0.;reason='PERSISTENT_SEVERE_INCONSISTENCY'
            elif self.clear>=p['clear_count']:self.mode='recovering';self.gain=p['recovery_information'];self.recover=0;reason='CLEAR_PERSISTENCE_START_RECOVERY'
            else:reason='HYSTERESIS_HOLD_ATTENUATION'
        else:
            if score>=p['disable_score']:self.mode='disabled';self.gain=0.;self.recover=0;reason='RECOVERY_RELAPSE_SEVERE'
            elif score>=p['warn_score']:self.mode='downweighted';self.gain=p['lowered_information'];self.recover=0;reason='RECOVERY_RELAPSE'
            elif score<=p['clear_score']:
                self.recover+=1;reason='RECOVERY_TRIAL'
                if self.recover>=p['recover_count']:self.mode='normal';self.gain=1.;reason='RECOVERED_AFTER_HYSTERESIS'
            else:self.recover=0;reason='RECOVERY_HOLD_NOT_CLEAR'
        return dict(state=self.mode,policy_mode_held=self.mode,reason=reason,information_multiplier=self.gain,score=float(score),monitorable=True,transition=self.mode!=before,
                    persistence=dict(warn=self.warn,severe=self.severe,clear=self.clear,recover=self.recover))
