"""Read-only imports for input generation and online execution only."""
from local_support import load
old_support=load('_gc_pr91_support','tools/two_car_mechanism_20261101/support.py')
old_bindings=load('_gc_pr91_bindings','tools/two_car_mechanism_20261101/bindings.py',{'support':old_support})
generator=old_bindings.generator
adapter=old_bindings.adapter
