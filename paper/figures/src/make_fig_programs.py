"""Generate the dependence-graph figure from two realistic Qiskit programs and the study's code.

programs/teleport.py  teleportation with if_test corrections (needs control dependence), criterion q2
programs/ansatz.py    hardware-efficient VQE ansatz built in loops (needs quantum dependence), criterion q0

Each program is executed with QuantumCircuit._append wrapped to record the creating source line of every
instruction, then prepared as the study prepares circuits (common.corpus.prepare: terminal measurements
dropped). Dependence edges are derived from the read/write rules of Section 3:
  data     an edge on a qubit that the classical PDG also has,
  control  an edge on a classical bit (measurement -> conditioned operation),
  quantum  an edge the wire rule has and the classical PDG lacks (a controlled gate writing its control).
The backward reachability of each rule's graph is asserted equal to the study's slicer (slicers/registry.py,
icpc/cpdg.py) before anything is drawn; dependences come from icpc/influence.py, fidelities from the oracle.
Writes fig_programs.tex and fig_programs_facts.json next to this file.
Usage (from experiments/): python ../paper/figures/src/make_fig_programs.py
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
PROG = SRC / "programs"
sys.path.insert(0, str(SRC.parents[2] / "experiments"))

SYM = {"ry": "R_y", "rz": "R_z", "rx": "R_x", "h": "H", "x": "X", "z": "Z", "cx": r"\oplus", "measure": "M", "if_else": r"\mathit{if}"}


def build(name):
    from qiskit import QuantumCircuit
    path = PROG / name
    log, orig = [], QuantumCircuit._append

    def wrapped(self, *a, **k):
        out = orig(self, *a, **k)
        log.append((id(self), next((f.lineno for f in inspect.stack(0)[1:] if f.filename == str(path)), None)))
        return out
    QuantumCircuit._append = wrapped
    try:
        ns: dict = {}
        exec(compile(path.read_text(), str(path), "exec"), ns)
    finally:
        QuantumCircuit._append = orig
    qc = ns["qc"]
    lines = [ln for cid, ln in log if cid == id(qc)]
    assert len(lines) == len(qc.data)
    from common.corpus import prepare
    prep = prepare(qc)
    # map prepared instructions back to built ones: prepare only drops (barriers, terminal measurements)
    j, pl = 0, []
    for inst in prep.data:
        while not (qc.data[j].operation.name == inst.operation.name and
                   [qc.find_bit(x).index for x in qc.data[j].qubits] == [prep.find_bit(x).index for x in inst.qubits]):
            j += 1
        pl.append(lines[j])
        j += 1
    return prep, pl


def rw(qc, rule):
    """(reads, writes) per instruction under 'cpdg' or 'wire' (Section 3)."""
    from icpc.cpdg import _condition_bits
    out = []
    for inst in qc.data:
        op = inst.operation
        qs = [qc.find_bit(q).index for q in inst.qubits]
        cs = {("c", qc.find_bit(c).index) for c in inst.clbits}
        cond = _condition_bits(op, qc)
        if rule == "wire":
            loc = {("q", x) for x in qs} | cs | cond
            out.append((loc, {("q", x) for x in qs} | cs))
        else:
            nc = int(getattr(op, "num_ctrl_qubits", 0) or 0)
            r = {("q", x) for x in qs}
            w = {("q", x) for x in qs[nc:]} if nc and len(qs) > nc else set(r)
            if op.name == "measure":
                w |= cs
            out.append((r | cond, w))
    return out


def edges(qc, rule):
    """Reaching-definition edges (i, j, location)."""
    R = rw(qc, rule)
    E, last = [], {}
    for j, (r, w) in enumerate(R):
        for loc in r:
            if loc in last:
                E.append((last[loc], j, loc))
        for loc in w:
            last[loc] = j
    return E


def back(n_ops, E, seeds):
    pred = {}
    for i, j, _ in E:
        pred.setdefault(j, set()).add(i)
    seen, st = set(), list(seeds)
    while st:
        x = st.pop()
        if x not in seen:
            seen.add(x)
            st.extend(pred.get(x, ()))
    return seen


def facts_for(name, t):
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.cpdg import cpdg_slice
    from icpc.influence import influence, influence_sets
    from slicers.registry import Slicers
    qc, lines = build(name)
    n = qc.num_qubits
    s = Slicers(qc, name)
    base = oi.reduced_states(qc, range(n))
    dep = sorted(influence_sets(influence(qc), n)[t])
    slices = {"du": sorted(s.du(t)), "cpdg": sorted(cpdg_slice(qc, t)), "yz": sorted(s.yz(t)), "lc": sorted(s.lc(t)), "q": sorted(s.q(t))}
    fid = {m: float(oi.uhlmann_fidelity(base[t], oi.reduced_states(materialise(qc, set(v)), range(n))[t])) for m, v in slices.items()}
    Ew, Ec = edges(qc, "wire"), edges(qc, "cpdg")
    on_t = [k for k, inst in enumerate(qc.data) if t in [qc.find_bit(x).index for x in inst.qubits]]
    seed = {max(on_t)}
    assert back(len(qc.data), Ew, seed) == set(slices["lc"]), (name, "wire graph != S-lc")
    cpdg_seed = {max(k for k, (r, w) in enumerate(rw(qc, "cpdg")) if ("q", t) in w)}
    assert back(len(qc.data), Ec, cpdg_seed) == set(slices["cpdg"]), (name, "cpdg graph != S-cpdg")
    cset = {(i, j) for i, j, _ in Ec}
    kinds = {}
    for i, j, loc in Ew:
        k = "control" if loc[0] == "c" else ("data" if (i, j) in cset else "quantum")
        kinds[(i, j)] = "quantum" if kinds.get((i, j)) == "quantum" or k == "quantum" else k if (i, j) not in kinds else kinds[(i, j)]
    ops = [{"name": inst.operation.name, "qubits": [qc.find_bit(x).index for x in inst.qubits], "line": lines[k]}
           for k, inst in enumerate(qc.data)]
    return {"program": name, "criterion": t, "ops": ops, "dep": dep, "slices": slices, "fidelity": fid,
            "edges": [[i, j, kinds[(i, j)]] for (i, j) in sorted(kinds)], "lines": lines}


def graph_tikz(F, title, ox, xs, ys, extra_spurious, tag):
    """TikZ for one program's wire-rule dependence graph."""
    ops, t = F["ops"], F["criterion"]
    sl, dep = set(F["slices"]["lc"]), set(F["dep"])
    spur = set(F["slices"]["yz"]) - dep
    nq = 1 + max(q for o in ops for q in o["qubits"])
    out = [rf"\begin{{scope}}[xshift={ox}cm]",
           rf"\node[anchor=west, font=\footnotesize\bfseries] at (-0.55,{(nq - 1) * ys + 0.62}) {{{title}}};"]
    for q in range(nq):
        y = (nq - 1 - q) * ys
        out.append(rf"\draw[black!12, line width=2.4pt] (0.1,{y}) -- ({(len(ops) + 0.2) * xs},{y}); \node[anchor=east, font=\scriptsize] at (0.1,{y}) {{$q_{q}$}};")
    pos = {}
    for k, o in enumerate(ops):
        qs = o["qubits"]
        y = (nq - 1 - (min(qs) + max(qs)) / 2) * ys
        pos[k] = ((k + 0.7) * xs, y)
        style = "sl" if k in sl else ("spur" if k in spur else "gn")
        if k in set(F["slices"]["cpdg"]):
            style += ",cp"
        lab = SYM.get(o["name"], o["name"])
        out.append(rf"\node[{style}] (n{tag}{k}) at ({pos[k][0]:.3f},{pos[k][1]:.3f}) {{${lab}$}};")
        out.append(rf"\node[lin] at ({pos[k][0]:.3f},{pos[k][1] - 0.39:.3f}) {{{o['line']}}};")
    for i, j, kind in F["edges"]:
        bend = "" if abs(pos[i][1] - pos[j][1]) < 1e-6 and j - i == 1 else ""
        out.append(rf"\draw[{kind}E] (n{tag}{i}) to{bend} (n{tag}{j});")
    for i, j in extra_spurious:
        out.append(rf"\draw[entE] (n{tag}{i}) to[bend left=18] (n{tag}{j});")
    out.append(r"\end{scope}")
    return "\n".join(out)


def main():
    A = facts_for("teleport.py", 2)
    B = facts_for("ansatz.py", 0)
    (SRC / "fig_programs_facts.json").write_text(json.dumps({"teleport": A, "ansatz": B}, indent=1))
    # entanglement-closure edges into the q0 slice from its non-dependences (a sample, labelled as such)
    spurB = sorted(set(B["slices"]["yz"]) - set(B["dep"]))
    criterion_last = max(B["slices"]["lc"])
    extra = [(k, criterion_last) for k in spurB]

    def lines_of(F, m):
        return sorted({F["lines"][k] for k in F["slices"][m]})

    def verdict(F, m, label):
        n, f = len(F["slices"][m]), F["fidelity"][m]
        return rf"{label}: {n} ops, lines {', '.join(map(str, lines_of(F, m)))}, $F={f:.2f}$"

    def code(name, first, last):
        return (r"\lstinputlisting[style=qiskit,firstline=" + str(first) + ",lastline=" + str(last) +
                ",firstnumber=" + str(first) + "]{programs/" + name + "}")

    tex = [
        "% Generated by make_fig_programs.py from programs/*.py and the study's code. Do not edit by hand.",
        r"\documentclass[border=3pt,varwidth=17.8cm]{standalone}",
        r"\usepackage{amsmath,amssymb,xcolor,listings,tikz}\usetikzlibrary{arrows.meta}",
        r"\definecolor{cblue}{HTML}{0072B2}\definecolor{cver}{HTML}{D55E00}\definecolor{cora}{HTML}{E69F00}\definecolor{cgreen}{HTML}{009E73}",
        r"\lstdefinestyle{qiskit}{language=Python,basicstyle=\ttfamily\tiny,numbers=left,numberstyle=\tiny\color{black!55},"
        r"numbersep=3pt,keywordstyle=\color{cblue}\bfseries,commentstyle=\color{black!55}\itshape,showstringspaces=false,"
        r"frame=single,rulecolor=\color{black!25},xleftmargin=9pt,framexleftmargin=9pt,columns=flexible,keepspaces=true}",
        r"\tikzset{gn/.style={circle,draw=black!70,fill=white,line width=0.4pt,minimum size=5.4mm,inner sep=0pt,font=\tiny},"
        r"sl/.style={gn,fill=cblue!28}, spur/.style={gn,fill=cora!55}, cp/.style={draw=black,line width=1.3pt}, lin/.style={font=\fontsize{4.2}{5}\selectfont\color{black!60}},"
        r"dataE/.style={-{Stealth[length=1.2mm]},draw=black!55,line width=0.45pt},"
        r"quantumE/.style={-{Stealth[length=1.3mm]},draw=cblue,line width=0.9pt},"
        r"controlE/.style={-{Stealth[length=1.3mm]},draw=cgreen,line width=0.8pt,dash pattern=on 2.2pt off 1.2pt},"
        r"entE/.style={-{Stealth[length=1.2mm]},draw=cora,line width=0.6pt,dash pattern=on 1.2pt off 1pt}}",
        r"\begin{document}\begin{varwidth}{17.8cm}",
        r"\begin{minipage}[t]{0.27\linewidth}\vspace{0pt}{\footnotesize\textbf{(a) Teleportation}}\\[2pt]" + code("teleport.py", 7, 17) + r"\end{minipage}\hfill",
        r"\begin{minipage}[t]{0.71\linewidth}\vspace{0pt}\begin{tikzpicture}",
        graph_tikz(A, r"(b) Wire-rule dependence graph, criterion $q_2$", 0.0, 0.92, 0.82, [], "a"),
        r"\end{tikzpicture}\\[1pt]\scriptsize "
        + verdict(A, "du", "def-use") + r"\quad " + verdict(A, "cpdg", "classical PDG = wire"),
        r"\end{minipage}\\[8pt]",
        r"\begin{minipage}[t]{0.27\linewidth}\vspace{0pt}{\footnotesize\textbf{(c) VQE ansatz}}\\[2pt]" + code("ansatz.py", 5, 17) + r"\end{minipage}\hfill",
        r"\begin{minipage}[t]{0.71\linewidth}\vspace{0pt}\begin{tikzpicture}",
        graph_tikz(B, r"(d) Wire-rule dependence graph, criterion $q_0$", 0.0, 0.70, 0.82, extra, "b"),
        r"\end{tikzpicture}\\[1pt]\scriptsize "
        + verdict(B, "cpdg", "classical PDG") + r"\quad " + rf"QPDG: +{len(spurB)} non-dependences" + r"\quad "
        + rf"wire: {len(B['slices']['lc'])} ops $=$ dependences, $F={B['fidelity']['lc']:.2f}$",
        r"\end{minipage}\\[6pt]",
        r"\centering\scriptsize"
        r"\tikz\draw[dataE](0,0)--(0.5,0); data\quad \tikz\draw[controlE](0,0)--(0.5,0); control\quad"
        r"\tikz\draw[quantumE](0,0)--(0.5,0); quantum, missing from the classical PDG\quad"
        r"\tikz\draw[entE](0,0)--(0.5,0); entanglement closure (QPDG)\\"
        r"\tikz\node[sl,minimum size=3mm]{}; wire slice\quad \tikz\node[gn,cp,minimum size=3mm]{}; classical PDG slice\quad"
        r"\tikz\node[spur,minimum size=3mm]{}; added by QPDG, not a dependence\quad small numbers: source line",
        r"\end{varwidth}\end{document}",
    ]
    (SRC / "fig_programs.tex").write_text("\n".join(tex) + "\n")
    print(json.dumps({"teleport": {m: (v, round(A["fidelity"][m], 3)) for m, v in A["slices"].items()},
                      "ansatz": {m: (v, round(B["fidelity"][m], 3)) for m, v in B["slices"].items()},
                      "kinds_teleport": sorted({k for *_, k in A["edges"]}), "kinds_ansatz": sorted({k for *_, k in B["edges"]})}))


if __name__ == "__main__":
    main()
