"""Generate the running-example figure (quantikz) from example_circuit.py and the study's own code.

The Qiskit program in example_circuit.py is executed, and every slice drawn is computed by the study's
slicers (experiments/slicers/registry.py), the dependences by the semantic ground truth
(experiments/icpc/influence.py), and every verdict by the independent oracle (experiments/icpc/oracle_icpc.py).
Nothing in the figure is typed by hand. Writes fig_example.tex and fig_example_facts.json next to this file.
Usage (from experiments/): python ../paper/figures/src/make_fig_example.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parent
EXP = SRC.parents[2] / "experiments"
sys.path.insert(0, str(EXP))

N_RANDOM, SEED = 20, 20261023


def build():
    ns: dict = {}
    code = (SRC / "example_circuit.py").read_text()
    exec(compile(code, str(SRC / "example_circuit.py"), "exec"), ns)
    qc = ns["qc"]
    lines = [i + 1 for i, ln in enumerate(code.splitlines()) if "# o" in ln]
    assert len(lines) == len(qc.data), "every operation must carry its '# o<k>' line"
    return qc, lines


def facts(qc):
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.influence import influence, influence_sets
    from icpc.cpdg import cpdg_slice
    from slicers.registry import Slicers
    n = qc.num_qubits
    base = oi.reduced_states(qc, range(n))
    dep = influence_sets(influence(qc), n)
    s = Slicers(qc, "example")
    rng = np.random.default_rng(SEED)
    preps = [oi.haar_product_input(n, rng) for _ in range(N_RANDOM)]
    out = {}
    for t in range(n):
        out[t] = {"dep": sorted(dep[t])}
        for m in ("du", "cpdg", "yz", "lc", "q"):
            sl = set(cpdg_slice(qc, t)) if m == "cpdg" else set(s.get(m)(t))
            f0 = oi.uhlmann_fidelity(base[t], oi.reduced_states(materialise(qc, sl), range(n))[t])
            bad = 0
            for p in preps:
                a = oi.reduced_states(oi.with_input(qc, p), [t])[t]
                b = oi.reduced_states(oi.with_input(materialise(qc, sl), p), [t])[t]
                bad += oi.uhlmann_fidelity(a, b) < 1 - oi.FIDELITY_EPS
            out[t][m] = {"slice": sorted(sl), "F0": round(float(f0), 6), "unsound_random": bad}
    return out


GATE = {"h": "H", "x": "X", "z": "Z", "y": "Y", "s": "S", "t": "T"}
STY = {
    "dep": "fill=black!14,draw=none,rounded corners=2pt,inner sep=0.4pt",
    "in": "fill=cblue!28,draw=none,rounded corners=2pt,inner sep=0.4pt",
    "spur": "fill=cora!55,draw=none,rounded corners=2pt,inner sep=0.4pt",
    "miss": "draw=cver,line width=0.8pt,dash pattern=on 2pt off 1.2pt,fill=none,rounded corners=2pt,inner sep=0.4pt",
}


def circuit(qc, marks: dict, criterion: int, labels: bool = False) -> str:
    """quantikz code; marks = {op index: style key}; labels adds o_k above each column."""
    n = qc.num_qubits
    rows = [[f"\\lstick{{$q_{q}$}}"] for q in range(n)]
    for k, inst in enumerate(qc.data):
        qs = [qc.find_bit(x).index for x in inst.qubits]
        name = inst.operation.name
        cells = ["" for _ in range(n)]
        if name == "cx":
            c, t = qs
            cells[c] = f"\\ctrl{{{t - c}}}"
            cells[t] = "\\targ{}"
        elif name in ("ry", "rz", "rx"):
            cells[qs[0]] = f"\\gate{{R_{name[1]}}}"
        else:
            cells[qs[0]] = f"\\gate{{{GATE[name]}}}"
        if k in marks:
            top = min(qs)
            cells[top] += f"\\gategroup[wires={max(qs) - top + 1},steps=1,style={{{STY[marks[k]]}}},background]{{}}"
        for q in range(n):
            rows[q].append(cells[q])
    for q in range(n):
        rows[q].append("\\rstick{\\scriptsize criterion}" if q == criterion else "")
    if labels:
        rows.insert(0, [""] + [f"\\push{{\\scriptstyle o_{{{k}}}}}" for k in range(len(qc.data))] + [""])
    body = " \\\\\n".join(" & ".join(r) for r in rows)
    wt = ("n," if labels else "") + ",".join("q" for _ in range(n))
    return "\\begin{quantikz}[row sep={0.62cm,between origins}, column sep=0.2cm, wire types={" + wt + "}]\n" + body + "\n\\end{quantikz}"


def panel(title: str, qc, marks, criterion, verdict: str, labels: bool = False) -> str:
    return ("\\begin{minipage}[t]{0.49\\linewidth}\\centering\n"
            f"{{\\footnotesize\\textbf{{{title}}}}}\\\\[1pt]\n"
            + circuit(qc, marks, criterion, labels) +
            f"\\\\[-1pt]{{\\scriptsize {verdict}}}\n\\end{{minipage}}")


def main():
    qc, lines = build()
    F = facts(qc)
    (SRC / "fig_example_facts.json").write_text(json.dumps({"lines": lines, "facts": F}, indent=1))
    d0, d2 = F[0], F[2]

    def marks(rule, t):
        dep, sl = set(F[t]["dep"]), set(F[t][rule]["slice"])
        m = {k: "in" for k in sl & dep}
        m.update({k: "spur" for k in sl - dep})
        m.update({k: "miss" for k in dep - sl})
        return m

    def srclines(rule, t):
        ls = [lines[k] for k in F[t][rule]["slice"]]
        return "source lines " + ", ".join(map(str, ls))

    def verdict(rule, t):
        x = F[t][rule]
        ok0 = x["F0"] >= 1 - 1e-6
        rand = "correct at all" if x["unsound_random"] == 0 else f"wrong at {x['unsound_random']} of"
        return (f"keeps {srclines(rule, t)}\\\\ fidelity {x['F0']:.2f} at $\\ket{{000}}$; {rand} {N_RANDOM} random inputs")

    code = ("\\begin{minipage}[t]{0.49\\linewidth}\\centering\n"
            "{\\footnotesize\\textbf{(a) Qiskit program}}\\\\[3pt]\n"
            "\\begin{minipage}{0.92\\linewidth}\\lstinputlisting[style=qiskit]{example_circuit.py}\\end{minipage}\n"
            "\\end{minipage}")
    dep_marks = {k: "dep" for k in d0["dep"]}
    tex = [
        "% Generated by make_fig_example.py from example_circuit.py and the study's code. Do not edit by hand.",
        "\\documentclass[border=3pt,varwidth=17.6cm]{standalone}",
        "\\usepackage{amsmath,amssymb,xcolor,listings}",
        "\\usepackage{tikz}\\usetikzlibrary{quantikz2}",
        "\\providecommand{\\ket}[1]{\\lvert #1\\rangle}",
        "\\definecolor{cblue}{HTML}{0072B2}\\definecolor{cver}{HTML}{D55E00}\\definecolor{cora}{HTML}{E69F00}",
        "\\lstdefinestyle{qiskit}{language=Python,basicstyle=\\ttfamily\\scriptsize,numbers=left,numberstyle=\\tiny\\color{black!55},"
        "numbersep=4pt,keywordstyle=\\color{cblue}\\bfseries,commentstyle=\\color{black!55}\\itshape,stringstyle=\\color{cver},"
        "showstringspaces=false,frame=single,rulecolor=\\color{black!25},xleftmargin=10pt,framexleftmargin=10pt,columns=flexible,keepspaces=true}",
        "\\begin{document}\\begin{varwidth}{17.6cm}",
        code + "\\hfill",
        panel("(b) Dependences of $q_0$ (ground truth)", qc, dep_marks, 0,
              "source lines " + ", ".join(str(lines[k]) for k in d0["dep"]) + "\\\\ operations where a change can alter $q_0$'s state", labels=True) + "\\\\[6pt]",
        panel("(c) Classical PDG slice of $q_0$ (data + control)", qc, marks("cpdg", 0), 0, verdict("cpdg", 0)) + "\\hfill",
        panel("(d) Entanglement-closure (QPDG) slice of $q_0$", qc, marks("yz", 0), 0, verdict("yz", 0)) + "\\\\[6pt]",
        panel("(e) Wire-rule slice of $q_0$", qc, marks("lc", 0), 0, verdict("lc", 0)) + "\\hfill",
        panel("(f) State-based (QSlice) slice of $q_2$ at $\\ket{000}$", qc, marks("q", 2), 2, verdict("q", 2)) + "\\\\[6pt]",
        "\\centering\\scriptsize"
        "\\tikz\\fill[black!14,rounded corners=1pt] (0,0) rectangle (0.32,0.22); dependence\\quad"
        "\\tikz\\fill[cblue!28,rounded corners=1pt] (0,0) rectangle (0.32,0.22); in slice and a dependence\\quad"
        "\\tikz\\fill[cora!55,rounded corners=1pt] (0,0) rectangle (0.32,0.22); in slice, not a dependence\\quad"
        "\\tikz\\draw[cver,line width=0.8pt,dash pattern=on 2pt off 1.2pt,rounded corners=1pt] (0,0) rectangle (0.32,0.22); missed dependence",
        "\\end{varwidth}\\end{document}",
    ]
    (SRC / "fig_example.tex").write_text("\n".join(tex) + "\n")
    print(json.dumps({t: {k: (v if k == "dep" else v["slice"]) for k, v in F[t].items()} for t in F}))


if __name__ == "__main__":
    main()
