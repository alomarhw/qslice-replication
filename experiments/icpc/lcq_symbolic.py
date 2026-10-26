"""Commutation for all angles, and the wire rule's excess over the dependences (Deviation I-14, exploratory).

S-lcqs: Qiskit's LightCone, as in S-lcq (icpc/lcq_remap.py), on a copy of the circuit in which every angle
of every top-level standard rotation gate (icpc/rq2_robustness.py ANGLE_GATES, the gates R-param rebinds) is
a fresh Parameter. LightCone keeps a gate whose commutation with the observable depends on an unbound
angle, so a gate is dropped only if it commutes for every angle. Positions are those of the bound circuit:
the symbolic copy has the same instructions in the same order.

Per corpus-A circuit, one worker computes the influence ground truth once and writes:
  records.csv     RQ1 scoring of S-lcqs (and S-lcq again, as a reproduction check against
                  results/icpc/rq1_lcq_remap): soundness at |0...0>, dependence recall and precision.
  robustness.csv  R-basis, R-haar, R-param soundness of S-lcqs, S-lcq and S-lc with the draws of
                  icpc/rq2_robustness.py (S-lc and S-lcq counts must equal the committed RQ2 runs).
  excess.csv      one row per operation in the wire slice that is not a dependence of the criterion,
                  with the I-14 tags: removal_changes_any (deleting it alone changes the criterion at
                  some tested input), removed_by_lcqs, criterion_constant (the criterion's state is the
                  same at all 11 inputs), cut_by_reset_or_measure (a reset or measurement acts on one of
                  its qubits later), and category, the first tag that applies, else "other".
--part families / catalogue: soundness of S-lcqs at |0...0> (families.csv, catalogue.csv).
Output: results/icpc/rq1_lcq_symbolic/.
Usage (from experiments/): python icpc/lcq_symbolic.py --part corpus-a --data-root ../data --eval-code ../selection [--workers 6]
                           python icpc/lcq_symbolic.py --part families | catalogue
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from icpc.rq2_robustness import ANGLE_GATES, N_DRAWS, REGIMES, _rng, n_rebindable, rebind  # noqa: E402

OUT = HERE / "results" / "icpc" / "rq1_lcq_symbolic"
XYZ = ("X", "Y", "Z")


def symbolize(qc):
    """Copy of qc with every angle of every top-level ANGLE_GATES gate replaced by a fresh Parameter."""
    from qiskit.circuit import Parameter
    out = qc.copy_empty_like()
    for k, inst in enumerate(qc.data):
        op = inst.operation
        if op.name in ANGLE_GATES and op.params and all(isinstance(p, (int, float)) for p in op.params):
            op = op.to_mutable()
            op.params = [Parameter(f"a{k}_{i}") for i in range(len(op.params))]
        out.append(op, inst.qubits, inst.clbits)
    return out


def lcqs_positions(qc, t: int) -> set:
    from icpc.lcq_remap import lightcone_positions
    return lightcone_positions(symbolize(qc), t, XYZ)


def _slices(qc, name):
    from icpc.lcq_remap import NotApplicable, lightcone_positions
    from slicers.registry import Slicers
    s = Slicers(qc, name)
    sl, na = {}, {}
    for t in range(qc.num_qubits):
        sl[(t, "lc")] = frozenset(s.lc(t))
        for m, fn in (("lcq", lambda t: lightcone_positions(qc, t, XYZ)), ("lcqs", lambda t: lcqs_positions(qc, t))):
            try:
                sl[(t, m)] = frozenset(fn(t))
            except NotApplicable as exc:
                na[(t, m)] = str(exc)[:200]
    return sl, na


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.influence import _inputs, influence, influence_sets

    t0 = time.time()
    qc = load(Path(data_root) / rel)
    n, nops = qc.num_qubits, len(qc.data)
    dyn = int(any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data))
    try:
        base = oi.reduced_states(qc, range(n))
        dep = influence_sets(influence(qc), n)
    except oi.OracleError as exc:
        return {"excluded": f"oracle: {exc}", "corpus": corpus, "circuit": name, "path": rel}
    sl, na = _slices(qc, name)
    common = {"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops, "dynamic": dyn}

    # RQ1 scoring
    recs, cache = [], {}
    for t in range(n):
        for m in ("lcq", "lcqs"):
            row = common | {"target": t, "slicer": m}
            if (t, m) in na:
                recs.append(row | {"applicable": 0, "note": na[(t, m)]})
                continue
            x = sl[(t, m)]
            if x not in cache:
                cache[x] = oi.reduced_states(materialise(qc, x), range(n))
            f = oi.uhlmann_fidelity(base[t], cache[x][t])
            hit = len(x & dep[t])
            recs.append(row | {"applicable": 1, "note": "", "size": len(x), "size_fraction": len(x) / max(nops, 1),
                               "fidelity": f, "sound": int(f >= 1 - oi.FIDELITY_EPS), "n_influencing": len(dep[t]),
                               "dep_recall": hit / len(dep[t]) if dep[t] else 1.0,
                               "dep_precision": hit / len(x) if x else 1.0,
                               "lcqs_vs_lc": len(x) - len(sl[(t, "lc")]), "slice": ";".join(map(str, sorted(x)))})

    # robustness, draws as in icpc/rq2_robustness.py
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
                st_ = {x: oi.reduced_states(oi.with_input(materialise(full_c, x), prep), range(n)) for x in distinct}
                for k, x in sl.items():
                    if oi.uhlmann_fidelity(b[k[0]], st_[x][k[0]]) >= 1 - oi.FIDELITY_EPS:
                        sound[k] += 1
        except oi.OracleError as exc:
            return {"excluded": f"oracle ({regime}): {exc}", "corpus": corpus, "circuit": name, "path": rel}
        for (t, m), c in sound.items():
            rob.append(common | {"regime": regime, "target": t, "slicer": m, "sound_draws": c, "robust": int(c == N_DRAWS),
                                 "size": len(sl[(t, m)])})

    # the wire slice's excess over the dependences
    exc_rows = []
    inputs = _inputs(n)
    bases = [oi.reduced_states(oi.with_input(qc, p), range(n)) for p in inputs]
    for t in range(n):
        extra = sorted(sl[(t, "lc")] - dep[t])
        if not extra:
            continue
        const = all(oi.uhlmann_fidelity(bases[0][t], b[t]) >= 1 - oi.FIDELITY_EPS for b in bases[1:])
        for k in extra:
            qs = {qc.find_bit(q).index for q in qc.data[k].qubits}
            later = any(i.operation.name in ("reset", "measure") and {qc.find_bit(q).index for q in i.qubits} & qs
                        for i in qc.data[k + 1:])
            changes = False
            for p, b in zip(inputs, bases):
                got = oi.reduced_states(oi.with_input(oi.delete_instruction(qc, k), p), [t])[t]
                if oi.uhlmann_fidelity(b[t], got) < 1 - oi.FIDELITY_EPS:
                    changes = True
                    break
            by_lcqs = (t, "lcqs") in sl and k not in sl[(t, "lcqs")]
            tags = {"removal_changes_any": changes, "removed_by_lcqs": by_lcqs, "criterion_constant": const,
                    "cut_by_reset_or_measure": later}
            cat = next((c for c, v in tags.items() if v), "other")
            exc_rows.append(common | {"target": t, "position": k, "gate": qc.data[k].operation.name,
                                      "n_gate_qubits": len(qs), "touches_criterion": int(t in qs)}
                            | {c: int(v) for c, v in tags.items()} | {"category": cat})
    return {"recs": recs, "rob": rob, "excess": exc_rows, "seconds": time.time() - t0}


def _write(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)


def corpus_a(a) -> int:
    from common.corpus import corpus_a as load_a
    root = Path(a.data_root).resolve()
    A = load_a(root, Path(a.eval_code))
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"} for e in A if e.qc is None]
    sizes = {e.path: len(e.qc.data) * e.qc.num_qubits for e in A if e.qc is not None}
    jobs = sorted([(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None], key=lambda j: -sizes[j[2]])
    recs, rob, exc, t0 = [], [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_worker, j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            res = f.result()
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                recs += res["recs"]
                rob += res["rob"]
                exc += res["excess"]
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    key = lambda r: (r["path"], r["target"], r["slicer"], r.get("regime", ""))  # noqa: E731
    _write(OUT / "records.csv", sorted(recs, key=key))
    _write(OUT / "robustness.csv", sorted(rob, key=key))
    _write(OUT / "excess.csv", sorted(exc, key=lambda r: (r["path"], r["target"], r["position"])))
    (OUT / "excluded.json").write_text(json.dumps(excluded, indent=2))
    s = [r for r in recs if r["slicer"] == "lcqs"]
    print(f"lcqs applicable {sum(r['applicable'] for r in s)}/{len(s)}; unsound "
          f"{sum(r['applicable'] and not r['sound'] for r in s)}; excess ops {len(exc)}; wrote {OUT}")
    return 0


def small(part: str) -> int:
    """Soundness of S-lcqs at |0...0> on the structure families or the dependence catalogue."""
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.lcq_remap import NotApplicable
    if part == "families":
        from families.generate import families
        items = [(f"{f}:{n}", c, None) for f, n, c in families()]
    else:
        from tests.dependence_catalogue import CATALOGUE
        items = [(kid, build(), t) for kid, kind, build, t, exp in CATALOGUE]
    rows = []
    for name, qc, only in items:
        base = oi.reduced_states(qc, range(qc.num_qubits))
        for t in ([only] if only is not None else range(qc.num_qubits)):
            try:
                x = lcqs_positions(qc, t)
            except NotApplicable as exc:
                rows.append({"circuit": name, "target": t, "applicable": 0, "note": str(exc)[:200]})
                continue
            f = oi.uhlmann_fidelity(base[t], oi.reduced_states(materialise(qc, x), [t])[t])
            rows.append({"circuit": name, "target": t, "applicable": 1, "size": len(x), "n_ops": len(qc.data),
                         "fidelity": f, "sound": int(f >= 1 - oi.FIDELITY_EPS)})
    _write(OUT / f"{part}.csv", rows)
    ap_ = [r for r in rows if r["applicable"]]
    print(f"{part}: {len(ap_)}/{len(rows)} applicable, unsound {sum(not r['sound'] for r in ap_)}")
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
