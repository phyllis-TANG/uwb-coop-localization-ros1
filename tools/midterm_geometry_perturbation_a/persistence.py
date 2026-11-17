"""Conservative output lease and orphan gate; no solver imports."""
from contextlib import contextmanager
from pathlib import Path
import fcntl

@contextmanager
def exclusive_output(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with (out/'.run.lock').open('a+') as fd:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('OUTPUT_DIRECTORY_ALREADY_LOCKED')
        try:
            ensure_no_orphans(out)
            yield
        finally:fcntl.flock(fd,fcntl.LOCK_UN)

def ensure_no_orphans(out):
    orphan=[str(p) for p in Path(out).rglob('*.attempt') if not Path(str(p)[:-len('.attempt')]).exists()]
    if orphan:raise RuntimeError('UNRESOLVED_ATTEMPT_NO_AUTOMATIC_RETRY: '+repr(orphan))
