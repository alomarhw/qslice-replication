"""Run one function per corpus file, each in its own process killed at a hard wall-clock limit.
SIGALRM alone cannot stop a file whose time goes into a long C-level call, so the per-file limit the corpus runners
report is enforced here: a process that overruns the limit (plus a grace period) is killed and its file gets
on_timeout(args) as its result."""
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor

GRACE = 15  # seconds beyond the limit before the process is killed; the in-process limits normally fire first


def _child(conn, fn, args):
    try:
        conn.send(fn(*args))
    finally:
        conn.close()


def _one(fn, args, limit, on_timeout):
    ctx = mp.get_context("spawn")
    recv, send = ctx.Pipe(duplex=False)
    p = ctx.Process(target=_child, args=(send, fn, args), daemon=True)
    p.start()
    send.close()
    try:
        if recv.poll(limit + GRACE):
            return recv.recv()
        return on_timeout(*args)
    except EOFError:  # the process died without a result
        return on_timeout(*args)
    finally:
        if p.is_alive():
            p.kill()
        p.join()
        recv.close()


def run_all(fn, arglist, limit, on_timeout, workers=1):
    """fn(*args) for every args in arglist, in order, at most workers at a time."""
    with ThreadPoolExecutor(max_workers=workers) as ex:
        yield from ex.map(lambda args: _one(fn, args, limit, on_timeout), arglist)
