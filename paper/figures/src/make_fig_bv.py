"""Generate the debugging-scenario figure (Section II) from the Qiskit textbook's Bernstein-Vazirani program.

programs/bv.py is the textbook's listing (ch-algorithms/bernstein-vazirani, lines 16-51, read and never run
here) with one seeded fault: line 25 applies x(n) where the textbook applies z(n), so the auxiliary qubit is
left in |+> instead of |->, no phase is kicked back, and the program returns 000 instead of s = 011.
Line-level slices of q0 come from the static tool (tool/, no program executed); operation-level slices from
the study's slicers on the circuit our own copy builds, and both are asserted to agree. Dependences come from
icpc/influence.py, fidelities and purities from icpc/oracle_icpc.py, outcomes from an exact statevector.
Writes fig_bv.tex and fig_bv_facts.json next to this file.
Usage (from experiments/): python ../paper/figures/src/make_fig_bv.py TEXTBOOK_ROOT
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))
import make_fig_programs as M  # noqa: E402

PROG = SRC / "programs" / "bv.py"
FAULT = (25, "bv_circuit.x(n)", "bv_circuit.z(n)")   # line, seeded text, textbook text
T = 0                                                # criterion: q0, the first wrong output bit


def check_against_textbook(root: Path) -> list:
    tb = (root / "ch-algorithms" / "bernstein-vazirani.py").read_text().splitlines()
    ours = PROG.read_text().splitlines()
    for ln in range(16, 52):
        want = FAULT[1] if ln == FAULT[0] else tb[ln - 1]
        assert ours[ln - 1] == want, (ln, ours[ln - 1], tb[ln - 1])
    assert tb[FAULT[0] - 1].strip() == FAULT[2]
    return ours


def runnable(fixed: bool) -> str:
    """Our copy, with the textbook line restored when fixed, plus a final line naming the circuit for build()."""
    disp = SRC / "programs" / "_display"
    disp.mkdir(exist_ok=True)
    text = PROG.read_text()
    if fixed:
        text = text.replace(FAULT[1], FAULT[2])
    lines = text.split("\n")
    assert lines[11] == ""
    lines[11] = "QuantumCircuit.i = QuantumCircuit.id  # the textbook's Qiskit had i(); a blank line, so numbers stay"
    text = "\n".join(lines)
    name = "bv_fixed_run.py" if fixed else "bv_run.py"
    (disp / name).write_text(text + "qc = bv_circuit\n")
    return "_display/" + name


def facts() -> dict:
    from qiskit.quantum_info import Statevector
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.cpdg import cpdg_slice
    from icpc.influence import influence, influence_sets
    from slicers.registry import Slicers
    from tool.interp import trace_file
    from tool.slicer import wire_slice
    B, lines = M.build(runnable(False))
    Fx, _ = M.build(runnable(True))
    n = B.num_qubits
    s = Slicers(B, "bv")
    dep = sorted(influence_sets(influence(B), n)[T])
    op = {"cpdg": sorted(cpdg_slice(B, T)), "du": sorted(s.du(T)), "lc": sorted(s.lc(T)), "yz": sorted(s.yz(T))}
    c = trace_file(PROG).main_circuit()
    tool = {}
    for rule, key in (("cpdg", "cpdg"), ("wire", "lc")):
        sl = wire_slice(c, [T], rule=rule)
        tool[key] = {"quantum": sorted(sl.quantum_lines), "classical": sorted(sl.classical_lines)}
        assert set(tool[key]["quantum"]) == {lines[k] for k in op[key]}, (rule, "tool and study slicers disagree")
    base = oi.reduced_states(B, range(n))
    fid = {m: float(oi.uhlmann_fidelity(base[T], oi.reduced_states(materialise(B, set(v)), [T])[T])) for m, v in op.items()}
    rf = oi.reduced_states(Fx, [T])
    probs = lambda qc: {k: v for k, v in Statevector(qc).probabilities_dict(qargs=range(n - 1)).items() if v > 1e-9}  # noqa: E731
    # purity of q0 after every prefix, in both versions: q0 is never entangled (Proposition 3(i))
    pur = []
    for qc in (B, Fx):
        for k in range(1, len(qc.data) + 1):
            r = oi.reduced_states(materialise(qc, set(range(k))), [T])[T]
            pur.append(float((r @ r).trace().real))
    from tool.profile import qubit_arg_texts, slice_profile
    pr = slice_profile(c, T, qubit_arg_texts(PROG))
    by_name = {}
    for k, o in enumerate(c.ops):
        if T in o.touched:
            for texts in qubit_arg_texts(PROG).get(o.line, []):
                for t in texts:
                    if t in pr.names:
                        by_name.setdefault(t, set()).add(o.line)
    profile = {"defs_uses": sorted(pr.defs_uses), "names": {k: sorted(v) for k, v in sorted(by_name.items())},
               "functions": sorted(pr.functions), "dependents": sorted(pr.dependents), "bits": sorted(pr.bits),
               "conditioned_lines": sorted(pr.conditioned_lines), "backward_lines": sorted(pr.backward_lines),
               "forward_lines": sorted(pr.forward_lines)}
    return {"profile_q0": profile, "ops": [{"name": i.operation.name, "qubits": [B.find_bit(x).index for x in i.qubits], "line": lines[k]}
                    for k, i in enumerate(B.data)],
            "dep": dep, "op_slices": op, "tool_lines": tool, "fidelity_slice_vs_program": fid,
            "F_q0_buggy_vs_fixed": float(oi.uhlmann_fidelity(base[T], rf[T])),
            "P_buggy": probs(B), "P_fixed": probs(Fx), "min_purity_q0": min(pur),
            "dep_lines": sorted({lines[k] for k in dep}), "cpdg_missed_lines": sorted({lines[k] for k in set(dep) - set(op["cpdg"])})}


def tex(ours: list, F: dict) -> str:
    esc = lambda t: t.replace("\\", "\\textbackslash{}").replace("_", "\\_").replace("{", "\\{").replace("}", "\\}").replace("#", "\\#").replace("'", "\\textquotesingle{}").replace("|", "\\textbar{}").replace(">", "\\textgreater{}")  # noqa: E731
    sl = {k: set(v["quantum"]) | set(v["classical"]) for k, v in F["tool_lines"].items()}
    miss = set(F["cpdg_missed_lines"])
    mark = lambda on: r"\tikz\fill[cblue!70](0,0)rectangle(5pt,5pt);" if on else r"\tikz\draw[black!25](0,0)rectangle(5pt,5pt);"  # noqa: E731
    rows = []
    for ln in range(16, 52):
        code = re.sub(r"\s+#.*$", "", ours[ln - 1]).rstrip()
        if not code.strip() or code.strip().startswith("#"):
            continue
        indent = len(code) - len(code.lstrip())
        body = r"\hspace*{%.1fem}" % (0.5 * indent) + esc(code.strip())
        if ln == FAULT[0]:
            body = r"\fcolorbox{cver}{cver!10}{" + body + r"}\ \textcolor{cver}{\scriptsize$\leftarrow$ fault, textbook: \texttt{" + esc(FAULT[2].split(".")[1]) + "}}"
        elif ln in miss:
            body = r"\textcolor{cver}{" + body + "}"
        rows.append(rf"{{\tiny\color{{black!50}}{ln}}} & {mark(ln in sl['cpdg'])} & {mark(ln in sl['lc'])} & {{\ttfamily\scriptsize {body}}} \\")
    pb = ", ".join(f"{k} ({v:.2f})" for k, v in sorted(F["P_buggy"].items()))
    pf = ", ".join(f"{k} ({v:.2f})" for k, v in sorted(F["P_fixed"].items()))
    head = [
        "% Generated by make_fig_bv.py from programs/bv.py and the study's code. Do not edit by hand.",
        r"\documentclass[border=3pt,varwidth=8.7cm]{standalone}",
        r"\usepackage[T1]{fontenc}\usepackage{newtxtext,newtxmath}\usepackage[varqu,scaled=0.95]{zi4}",
        r"\usepackage{amsmath,xcolor,tikz}",
        r"\definecolor{cblue}{HTML}{0072B2}\definecolor{cver}{HTML}{D55E00}",
        r"\setlength{\fboxsep}{1pt}",
        r"\begin{document}\begin{varwidth}{8.7cm}",
        r"\renewcommand{\arraystretch}{0.74}",
        r"\begin{tabular}{@{}r@{\hspace{4pt}}c@{\hspace{3pt}}c@{\hspace{6pt}}l@{}}",
        r"& {\tiny CPDG} & {\tiny QDG} & {\footnotesize\textbf{Bernstein--Vazirani} (Qiskit textbook), slices of $q_0$} \\[1pt]",
        *rows,
        r"\end{tabular}\\[4pt]",
        rf"{{\scriptsize outcomes $q_2q_1q_0$: buggy {pb}; intended {pf}}}",
        r"\end{varwidth}\end{document}",
    ]
    return "\n".join(head) + "\n"


def main():
    ours = check_against_textbook(Path(sys.argv[1]))
    F = facts()
    (SRC / "fig_bv_facts.json").write_text(json.dumps(F, indent=1))
    (SRC / "fig_bv.tex").write_text(tex(ours, F))
    print(json.dumps({k: F[k] for k in ("dep_lines", "cpdg_missed_lines", "tool_lines", "fidelity_slice_vs_program",
                                        "F_q0_buggy_vs_fixed", "P_buggy", "P_fixed", "min_purity_q0")}))


if __name__ == "__main__":
    main()
