"""Repeatability of state-based pruning (Deviation I-19, exploratory).

S-q's pruning decisions compare a mutual information and a trace distance against 1e-9, and numerical noise near
those thresholds can flip a decision between runs (found on Bugs4Q StackExchange #4). Per corpus-A pair this
recomputes S-q REPEATS times, each from a fresh graph, and records whether every repeat has the size RQ1 stored and
whether each distinct slice is sound at |0...0> under the oracle (RQ1's judgement).
Output: results/icpc/q_repeat/pairs.csv.
Usage (from experiments/): python icpc/q_repeat.py --data-root ../data --eval-code ../selection [--workers 12]
"""

from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
OUT = HERE / "results" / "icpc" / "q_repeat"
REPEATS = 3


def _job(job):
    corpus, name, rel, data_root, stored = job
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from slicers.registry import Slicers
    qc = load(Path(data_root) / rel)
    n = qc.num_qubits
    try:
        base = oi.reduced_states(qc, range(n))
    except oi.OracleError:
        return []
    rows = []
    for t in range(n):
        if str(t) not in stored:
            continue
        slices = [frozenset(Slicers(qc, name).q(t)) for _ in range(REPEATS)]
        sound = {s: oi.uhlmann_fidelity(base[t], oi.reduced_states(materialise(qc, set(s)), [t])[t]) >= 1 - oi.FIDELITY_EPS
                 for s in set(slices)}
        rows.append({"corpus": corpus, "circuit": name, "path": rel, "target": t, "stored_size": stored[str(t)],
                     "distinct": len(set(slices)), "sizes": ";".join(str(len(s)) for s in slices),
                     "all_equal_stored": int(all(len(s) == stored[str(t)] for s in slices)),
                     "all_sound": int(all(sound.values()))})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", default="../selection")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    root = str(Path(a.data_root).resolve())
    OUT.mkdir(parents=True, exist_ok=True)
    stored = {}
    for r in csv.DictReader(open(HERE / "results" / "icpc" / "rq1" / "records.csv")):
        if r["slicer"] == "q" and r["applicable"] == "1":
            stored.setdefault(r["path"], {})[r["target"]] = int(r["size"])
    from common.corpus import corpus_a
    A = [e for e in corpus_a(Path(root), Path(a.eval_code)) if e.qc is not None and e.path in stored]
    rows = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(_job, (e.corpus, e.name, e.path, root, stored[e.path])) for e in A]):
            rows += f.result()
    rows.sort(key=lambda r: (r["path"], r["target"]))
    with open(OUT / "pairs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"pairs {len(rows)}; repeats differ {sum(r['distinct'] > 1 for r in rows)}; "
          f"differ from stored {sum(not r['all_equal_stored'] for r in rows)}; any unsound {sum(not r['all_sound'] for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
