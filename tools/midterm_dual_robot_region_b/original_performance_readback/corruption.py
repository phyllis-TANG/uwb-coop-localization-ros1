"""Exercise the unchanged downstream certificate rejection boundary on saved outputs."""
import copy
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'original_performance'))
from study import D, LOCK, load_a, read

_,checker=load_a(LOCK)
for arm in ('original','candidate'):
    unit='domain_closed_contact_'+arm
    directory=D/'pilot'/unit
    original=read(directory/(unit+'.certificate.json.gz'))
    x=read(directory/'job.json')['case']['a_input']
    assert checker.check(x,original)['certificate_valid']
    for field in ('projections','bias_recovery','queue'):
        invalid=copy.deepcopy(original)
        if field=='projections':
            invalid[field]['p']['rectangles'].pop()
        elif field=='bias_recovery':
            invalid[field][0]['result']['status']='invalid'
        else:
            invalid[field].append('invalid')
        try:
            checker.check(x,invalid)
        except checker.Invalid:
            continue
        raise AssertionError('Accepted corruption: '+field)
print('PASS: both authentic certificates accepted and all six altered certificates rejected.')
