"""Run the dependence catalogue (PROTOCOL_ICPC.md section 2.2) and compare with its committed
expectations (tests/dependence_catalogue.py). Disagreements are reported, never edited away.

Writes results/icpc/catalogue/catalogue.json and catalogue_report.md.
Usage (from experiments/): python tests/run_catalogue.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from common.evaluate import materialise  # noqa: E402
from icpc import oracle_icpc as oi  # noqa: E402
from icpc.influence import contribution, influence, influence_sets  # noqa: E402
from slicers.registry import NotApplicable, Slicers  # noqa: E402
from tests.dependence_catalogue import CATALOGUE  # noqa: E402

SLICERS = ["du", "lc", "lcq", "lcq_z", "yz", "q", "4e_unfixed", "4e_fixed"]
OUT = HERE / "results" / "icpc" / "catalogue"


def sound(qc, positions, t) -> tuple[bool, float]:
    full = oi.reduced_states(qc, [t])[t]
    got = oi.reduced_states(materialise(qc, positions), [t])[t]
    f = oi.uhlmann_fidelity(full, got)
    return f >= 1 - oi.FIDELITY_EPS, f


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, problems = [], []
    for kid, kind, build, t, exp in CATALOGUE:
        qc = build()
        s = Slicers(qc, kid)
        inf = influence_sets(influence(qc), qc.num_qubits)[t]
        con = contribution(qc)
        contrib_any = {k for k, v in con.items() if t in v["any"]}
        row = {"id": kid, "kind": kind, "criterion": t, "n_ops": len(qc.data), "dynamic": exp["dynamic"],
               "influence": sorted(inf), "contribution_any_input": sorted(contrib_any), "slicers": {}}
        if inf != exp["influence"]:
            problems.append(f"{kid} q{t} influence: expected {sorted(exp['influence'])}, got {sorted(inf)}")
        for name in SLICERS:
            try:
                sl = s.get(name)(t)
            except NotApplicable as exc:
                row["slicers"][name] = {"not_applicable": str(exc)}
                if name in ("lcq",) and not exp["dynamic"]:
                    problems.append(f"{kid} q{t} lcq: not applicable on a unitary circuit ({exc})")
                continue
            ok, f = sound(qc, sl, t)
            row["slicers"][name] = {"slice": sorted(sl), "sound": ok, "fidelity": f,
                                    "missed_influence": sorted(inf - sl), "non_influencing_included": sorted(sl - inf)}
            if name in exp:
                if sl != exp[name]:
                    problems.append(f"{kid} q{t} {name}: expected {sorted(exp[name])}, got {sorted(sl)}")
                if ok != exp["sound"][name]:
                    problems.append(f"{kid} q{t} {name}: expected sound={exp['sound'][name]}, got {ok} (F={f:.6f})")
            elif name == "lcq":
                if not ok or not sl <= exp["lc"]:
                    problems.append(f"{kid} q{t} lcq: expected sound and subset of lc {sorted(exp['lc'])}, got {sorted(sl)} sound={ok}")
        rows.append(row)
        print(f"{kid:5s} q{t}: influence {sorted(inf)}; " + "; ".join(
            f"{k}={v.get('slice', 'n/a')}{'' if v.get('sound', True) else '(UNSOUND)'}" for k, v in row["slicers"].items()), flush=True)
    (OUT / "catalogue.json").write_text(json.dumps({"rows": rows, "disagreements": problems}, indent=2))
    lines = ["# Dependence catalogue: run vs committed expectations", "",
             f"{len(CATALOGUE)} entries; {len(problems)} disagreement(s) with the expectations committed in e1dfdc3.", ""]
    lines += [f"- {p}" for p in problems] or ["- none"]
    (OUT / "catalogue_report.md").write_text("\n".join(lines) + "\n")
    print(f"\n{len(problems)} disagreement(s):")
    for p in problems:
        print("  " + p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
