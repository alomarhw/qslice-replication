"""S-lcw: the wire rule with SWAP as a move (Deviation I-14, B2).

The wire rule (Section 3): every instruction reads and writes all its qubits and classical bits, and an
if_else also reads the bits its condition tests; the backward pass uses reaching definitions for classical
bits. S-lcw changes one thing. A top-level, unconditioned swap(a, b) exchanges the two wires' states
exactly, so it joins the slice when a or b is needed, and the needed set is permuted (a <-> b) instead of
widened to both qubits. With move=False the pass is the wire rule; the run checks it against S-lc
(slicers/registry.py) on every pair before scoring S-lcw.

Scoring as icpc/lcq_symbolic.py: soundness at |0...0>, dependence recall and precision against
icpc/influence.py, robustness in R-basis, R-haar and R-param with the draws of icpc/rq2_robustness.py,
and soundness on the structure families and the dependence catalogue.
Output: results/icpc/rq1_wire_swap/ (records.csv, robustness.csv, families.csv, catalogue.csv, excluded.json).
Usage (from experiments/): python icpc/wire_swap.py --part corpus-a --data-root ../data --eval-code ../selection [--workers 6]
                           python icpc/wire_swap.py --part families | catalogue
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Set

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from icpc.cpdg import _condition_bits  # noqa: E402
from icpc.rq2_robustness import N_DRAWS, REGIMES, _rng, n_rebindable, rebind  # noqa: E402

OUT = HERE / "results" / "icpc" / "rq1_wire_swap"


def wire_slice(qc, t: int, move: bool = True) -> Set[int]:
    needed, include = {("q", t)}, set()
    for k in range(len(qc.data) - 1, -1, -1):
        inst = qc.data[k]
        op = inst.operation
        qs = [qc.find_bit(q).index for q in inst.qubits]
        if move and op.name == "swap" and len(qs) == 2 and not getattr(op, "condition", None):
            a, b = ("q", qs[0]), ("q", qs[1])
            if needed & {a, b}:
                include.add(k)
                needed = {b if x == a else a if x == b else x for x in needed}
            continue
        cs = {("c", qc.find_bit(c).index) for c in inst.clbits}
        cw = cs if op.name == "measure" else set()  # only a measurement writes a bit; other bits are read
        w = {("q", x) for x in qs} | cw
        if w & needed:
            include.add(k)
            needed = (needed - cw) | {("q", x) for x in qs} | (cs - cw) | _condition_bits(op, qc)
    return include


def _write(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.influence import influence, influence_sets
    from slicers.registry import Slicers

    t0 = time.time()
    qc = load(Path(data_root) / rel)
    n, nops = qc.num_qubits, len(qc.data)
    s = Slicers(qc, name)
    sl = {}
    for t in range(n):
        lc = frozenset(s.lc(t))
        assert frozenset(wire_slice(qc, t, move=False)) == lc, (rel, t, "wire pass != S-lc")
        sl[(t, "lc")], sl[(t, "lcw")] = lc, frozenset(wire_slice(qc, t))
    try:
        base = oi.reduced_states(qc, range(n))
        dep = influence_sets(influence(qc), n)
    except oi.OracleError as exc:
        return {"excluded": f"oracle: {exc}", "corpus": corpus, "circuit": name, "path": rel}
    common = {"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops,
              "has_swap": int(any(i.operation.name == "swap" for i in qc.data))}
    recs, cache = [], {}
    for t in range(n):
        x = sl[(t, "lcw")]
        if x not in cache:
            cache[x] = oi.reduced_states(materialise(qc, x), range(n))
        f = oi.uhlmann_fidelity(base[t], cache[x][t])
        hit = len(x & dep[t])
        recs.append(common | {"target": t, "slicer": "lcw", "size": len(x), "size_fraction": len(x) / max(nops, 1),
                              "lc_size": len(sl[(t, "lc")]), "fidelity": f, "sound": int(f >= 1 - oi.FIDELITY_EPS),
                              "n_influencing": len(dep[t]), "dep_recall": hit / len(dep[t]) if dep[t] else 1.0,
                              "dep_precision": hit / len(x) if x else 1.0, "slice": ";".join(map(str, sorted(x)))})
    rob = []
    distinct = sorted(set(sl.values()), key=sorted)
    for regime in REGIMES:
        if regime == "R-param" and n_rebindable(qc) == 0:
            continue
        rng = _rng(regime, rel)
        sound = {k: 0 for k in sl}
        try:
            for _ in range(N_DRAWS):
                if regime == "R-param":
                    full_c, _ = rebind(qc, rng)
                    prep = None
                else:
                    full_c = qc
                    prep = oi.basis_input(n, rng) if regime == "R-basis" else oi.haar_product_input(n, rng)
                b = oi.reduced_states(oi.with_input(full_c, prep), range(n))
                st_ = {y: oi.reduced_states(oi.with_input(materialise(full_c, y), prep), range(n)) for y in distinct}
                for k, y in sl.items():
                    if oi.uhlmann_fidelity(b[k[0]], st_[y][k[0]]) >= 1 - oi.FIDELITY_EPS:
                        sound[k] += 1
        except oi.OracleError as exc:
            return {"excluded": f"oracle ({regime}): {exc}", "corpus": corpus, "circuit": name, "path": rel}
        for (t, m), c in sound.items():
            rob.append(common | {"regime": regime, "target": t, "slicer": m, "sound_draws": c, "robust": int(c == N_DRAWS)})
    return {"recs": recs, "rob": rob, "seconds": time.time() - t0}


def corpus_a(a) -> int:
    from common.corpus import corpus_a as load_a
    root = Path(a.data_root).resolve()
    A = load_a(root, Path(a.eval_code))
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"} for e in A if e.qc is None]
    sizes = {e.path: len(e.qc.data) * e.qc.num_qubits for e in A if e.qc is not None}
    jobs = sorted([(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None], key=lambda j: -sizes[j[2]])
    recs, rob, t0 = [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_worker, j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            res = f.result()
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                recs += res["recs"]
                rob += res["rob"]
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    key = lambda r: (r["path"], r["target"], r["slicer"], r.get("regime", ""))  # noqa: E731
    _write(OUT / "records.csv", sorted(recs, key=key))
    _write(OUT / "robustness.csv", sorted(rob, key=key))
    (OUT / "excluded.json").write_text(json.dumps(excluded, indent=2))
    print(f"lcw pairs {len(recs)}; unsound {sum(not r['sound'] for r in recs)}; wrote {OUT}")
    return 0


def small(part: str) -> int:
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from slicers.registry import Slicers
    if part == "families":
        from families.generate import families
        items = [(f"{f}:{n}", c, None) for f, n, c in families()]
    else:
        from tests.dependence_catalogue import CATALOGUE
        items = [(kid, build(), t) for kid, kind, build, t, exp in CATALOGUE]
    rows = []
    for name, qc, only in items:
        s = Slicers(qc, name)
        base = oi.reduced_states(qc, range(qc.num_qubits))
        for t in ([only] if only is not None else range(qc.num_qubits)):
            assert wire_slice(qc, t, move=False) == s.lc(t), (name, t, "wire pass != S-lc")
            x = wire_slice(qc, t)
            f = oi.uhlmann_fidelity(base[t], oi.reduced_states(materialise(qc, x), [t])[t])
            rows.append({"circuit": name, "target": t, "size": len(x), "lc_size": len(s.lc(t)), "n_ops": len(qc.data),
                         "fidelity": f, "sound": int(f >= 1 - oi.FIDELITY_EPS)})
    _write(OUT / f"{part}.csv", rows)
    print(f"{part}: {len(rows)} pairs, unsound {sum(not r['sound'] for r in rows)}, "
          f"smaller than S-lc {sum(r['size'] < r['lc_size'] for r in rows)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["corpus-a", "families", "catalogue"], required=True)
    ap.add_argument("--data-root")
    ap.add_argument("--eval-code", default="../selection")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    return corpus_a(a) if a.part == "corpus-a" else small(a.part)


if __name__ == "__main__":
    sys.exit(main())
