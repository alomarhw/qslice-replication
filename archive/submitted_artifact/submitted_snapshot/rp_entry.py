"""the toolkit run wrapper.

Runs an experiment script as ``__main__`` and then HARD-exits. Experiment code routinely imports
datasets/pandas/torch, which pull in PyArrow + OpenMP; their global thread pools can deadlock in C++
static destructors at interpreter shutdown on macOS — hanging the process AFTER the experiment has
finished and written its results. os._exit skips those finalizers. The real exit code is preserved
(so the runner's repair loop still detects failures), and tracebacks are printed for the repair loop.

Usage: ``python3 rp_entry.py <script.py> [args...]``
"""

from __future__ import annotations

import os
import runpy
import sys
import traceback


def _main() -> int:
    if len(sys.argv) < 2:
        print("rp_entry.py: missing target script", file=sys.stderr)
        return 2
    target = sys.argv[1]
    sys.argv = [target] + sys.argv[2:]   # present argv as if the target ran directly
    try:
        runpy.run_path(target, run_name="__main__")
        return 0
    except SystemExit as exc:
        code = exc.code
        return 0 if code is None else (code if isinstance(code, int) else 1)
    except BaseException:  # noqa: BLE001 — surface the traceback for the repair loop, then exit non-zero
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    rc = _main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc)
