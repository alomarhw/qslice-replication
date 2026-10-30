"""Paper B: the tool on the teleportation chain of Fig. 1, srcML, the trace it yields, and the slice of q[4] by line and hop.

(1) srcML's own text for line 14, the CNOT whose qubits come from src and a, and lines 18-19, the conditioned repair,
from srcml --position, with the elements the tool reads lettered as in make_fig_tool.py: c gate names, d qubit
arguments, e bits and the condition, f the with of if_test, g the position (the source line).
(2) The tool's trace of the first hop, one row per operation, with its line and iteration.
(3) For every gate line of the loop, its operation in each hop, filled where it is in the slice of q[4].
Everything comes from srcML and the tool. Asserts that the slice has the size the paper reports
(results/icpc/b_example/teleport_chain_q4.json).
Usage (from the workspace root): python paper/figures/src/make_fig_b_tool.py -> paper/figures/src/fig_b_tool.tex
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))
import make_fig_tool as T  # noqa: E402  (shared rendering of srcML)
from tool.interp import trace_file  # noqa: E402
from tool.slicer import wire_slice  # noqa: E402

PROG = ROOT / "tool" / "tests" / "big" / "teleport_chain.py"
T.GATES = ("h", "cx", "measure", "x", "z")
T.QUBIT_INDEX_IS_D = True
CRIT = 4


def fragments():
    xml = subprocess.run(["srcml", "--position", "-l", "Python", str(PROG)], capture_output=True, text=True,
                         check=True).stdout
    cx = re.search(r'<expr_stmt pos:start="14:\d+"[^>]*>.*?</expr_stmt>', xml, re.S).group(0)
    cond = re.search(r'<with pos:start="18:\d+"[^>]*>.*?</with>', xml, re.S).group(0)
    out = []
    for frag in (cx, cond):
        head, rest = frag.split(">", 1)
        head = re.sub(r' pos:end="[^"]*"', "", head)
        out.append(head + ">" + T.POS.sub("", rest))
    return out


def main():
    circ = trace_file(PROG).main_circuit()
    ops = list(enumerate(circ.ops))
    keep = set(wire_slice(circ, [CRIT]).ops)
    ex = json.load(open(ROOT / "experiments" / "results" / "icpc" / "b_example" / "teleport_chain_q4.json"))
    assert len(ops) == ex["operations"] and len(keep) == ex["slices"][0]["operations"], (len(ops), len(keep))

    o = [T.HEAD.replace("make_fig_tool.py from programs/ansatz.py", "make_fig_b_tool.py from teleport_chain.py")]
    WL, WT, WR, GAP = 18.0, 7.6, 10.0, 0.4
    XT, XR = 0.0, 7.6 + 0.4

    def header(x, n, title, w):
        o.append(rf"\node[stnum] at ({x + 0.2},0.5) {{{n}}};")
        o.append(rf"\node[stage] at ({x + 0.45},0.5) {{{title}}};")
        o.append(rf"\draw[rule, line width=0.6pt] ({x},0.28) -- ({x + w},0.28);")

    # ---- 1 srcML
    header(0, 1, "srcML of lines 14 and 18--19", WL)
    pitch, y, state = 0.37, 0.0, {"last": None}
    for fi, s in enumerate(fragments()):
        if fi:
            y -= 0.2
            state["last"] = None
        for ind, ts, first in T.rows_of(s):
            x = 0.05 + (T.CH * ind if first else T.CH * (ind + 4))
            lead = "" if first else r"\textcolor{mute}{\rmfamily\fontsize{9}{11}\selectfont$\hookrightarrow$}\,"
            o.append(rf"\node[xml] at ({x},{y}) {{{lead}{T.render(ts, state)}}};")
            y -= pitch
    legend = (r"\hl{c}\,gate\enspace \hl{d}\,qubit argument, evaluated per iteration\enspace "
              r"\hl{e}\,classical bit, written by a measurement and read by the condition\\"
              r"\hl{f}\,\texttt{if\_test} $\to$ conditioned block\enspace \hl{g}\,position $\to$ source line")
    o.append(rf"\node[anchor=north west, align=left, font=\fontsize{{9}}{{11}}\selectfont, text=ink, inner sep=0pt] "
             rf"at (0.05,{y + 0.08}) {{{legend}}};")
    o.append(rf"\begin{{scope}}[yshift={y - 1.45:.3f}cm]")

    # ---- 2 trace of the first hop
    header(XT, 2, "Trace, line 8 and hop $h = 0$", WT)
    rows = [r"\textcolor{mute}{line}&\textcolor{mute}{hop}&\textcolor{mute}{operation}\\[0pt]"]
    for k, op in ops:
        it = dict(op.iters) if op.iters else {}
        if it and it.get(10, 0) != 0:
            continue
        if not it and op.line != 8:
            continue
        qs = r",\,".join("$q_{%d}$" % next(iter(op.qubits[j])) for j in range(len(op.qubits)))
        txt = rf"\texttt{{{op.name}}} {qs}"
        if op.clbits:
            txt += r" $\to$ $c_{%d}$" % next(iter(op.clbits[0]))
        if op.cond:
            txt += r" if $c_{%d}$" % next(iter(op.cond))
        rows.append(rf"{op.line}&{it.get(10, r'\textcolor{mute}{--}')}&{txt}\\[0pt]")
    rows.append(r"&\textcolor{mute}{1--3}&\textcolor{mute}{the same on the next qubits}\\[0pt]")
    o.append(rf"\node[anchor=north west, font=\fontsize{{9}}{{11}}\selectfont, text=ink, inner sep=0pt] at ({XT + 0.04},-0.05) "
             rf"{{\setlength{{\tabcolsep}}{{5pt}}\begin{{tabular}}{{rll}}{''.join(rows)}\end{{tabular}}}};")

    # ---- 3 slice of q[4] by line and hop
    header(XR, 3, r"Slice of \texttt{q[4]}", WR)
    lines = [12, 13, 14, 15, 16, 17, 19, 21]
    cell, x0, y0 = 0.62, XR + 1.5, -0.95
    for ci, ln in enumerate(lines):
        o.append(rf"\node[font=\fontsize{{9}}{{11}}\selectfont, text=ink, anchor=south] at ({x0 + ci * cell + cell / 2 - 0.02},{y0 + 0.05}) {{{ln}}};")
    for h in range(4):
        yy = y0 - h * cell
        o.append(rf"\node[font=\fontsize{{9}}{{11}}\selectfont, text=mute, anchor=east] at ({x0 - 0.08},{yy - cell / 2}) {{$h = {h}$}};")
        for ci, ln in enumerate(lines):
            k = next(k for k, op in ops if op.line == ln and dict(op.iters).get(10) == h)
            o.append(rf"\draw[draw=ink!45, line width=0.4pt, fill={'wire' if k in keep else 'white'}] "
                     rf"({x0 + ci * cell},{yy}) rectangle ++({cell - 0.05},{-(cell - 0.05)});")
    n_in = len(keep)
    o.append(rf"\node[font=\fontsize{{9}}{{11}}\selectfont, text=ink, anchor=north west, align=left] at ({XR + 0.05},{y0 - 4 * cell - 0.15}) "
             rf"{{line 8 \textcolor{{wire}}{{\bfseries in}}, line 23 out\enspace\textcolor{{wire}}{{\bfseries {n_in}}} of {len(ops)} operations}};")
    o.append(rf"\draw[flowarrow] ({XT + WT - 0.3},0.5) -- ({XR - 0.04},0.5);")
    o.append(r"\end{scope}")
    o.append(r"\end{tikzpicture}")
    o.append(r"\end{document}")
    (SRC / "fig_b_tool.tex").write_text("\n".join(o) + "\n")
    print("wrote fig_b_tool.tex | slice", n_in, "of", len(ops))


if __name__ == "__main__":
    main()
