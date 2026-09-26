"""Fig. 4: what the Isabelle theory proves (../isabelle/QSliceSoundness.thy).

Reads every lemma, theorem and interpretation from the theory, runs `isabelle build` on a scratch copy
(if isabelle is on the PATH), and marks a result machine-checked only if the build succeeds and the
theory contains no `sorry`, `oops` or `axiomatization`. The footer states the scope: soundness of the
causal-cone slice, relative to the two locale assumptions.

Usage: python fig4_isabelle.py [out_png]
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ISA = HERE.parent / "isabelle"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "fig4_isabelle.png"
DESC = {
    "cone_sound": "Main theorem: the causal-cone slice preserves the criterion's reduced state",
    "cone_sound_gen": "Generalised form (states agreeing on the needed qubits)",
    "cone_subseq": "The slice is a subsequence of the circuit",
    "criterion_needed": "The criterion qubits are always needed",
    "classical": "Assumptions are satisfiable (interpretation in a classical model)",
    "classical_example": "Worked example in the model",
}


def build_ok() -> bool | None:
    if not shutil.which("isabelle"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        for f in ("QSliceSoundness.thy", "ROOT"):
            shutil.copy(ISA / f, tmp)
        return subprocess.run(["isabelle", "build", "-d", ".", "QSliceSoundness"], cwd=tmp,
                              capture_output=True).returncode == 0


text = (ISA / "QSliceSoundness.thy").read_text()
code = re.sub(r"\(\*.*?\*\)", "", text, flags=re.S)
clean = not re.search(r"\b(sorry|oops|axiomatization)\b", code)
items = re.findall(r"^(lemma|theorem|interpretation)\s+(\w+)", code, flags=re.M)
built = build_ok()
ok = built is True and clean
status = ("machine-checked" if ok else "build failed" if built is False else
          "not built (no isabelle)" if built is None else "contains sorry/axioms")
print(f"isabelle build: {built}; free of sorry/oops/axiomatization: {clean}; results: {[n for _, n in items]}")

fig, ax = plt.subplots(figsize=(12, 0.55 * len(items) + 1.9))
for i, (kind, name) in enumerate(items):
    y = len(items) - 1 - i
    ax.barh(y, 1.45, left=0, align="center", color="#2E8B57" if ok else "#9CA3AF", height=0.62)
    ax.text(0.06, y, status, va="center", color="white", fontweight="bold", fontsize=9.5)
    ax.text(1.6, y, f"{kind} {name}", va="center", fontsize=10, family="monospace")
    ax.text(4.35, y, DESC.get(name, ""), va="center", fontsize=10)
ax.set_xlim(0, 10.2)
ax.set_ylim(-2.2, len(items))
ax.axis("off")
ax.text(0, -1.75, "Scope: soundness of the causal-cone slice, relative to two locale assumptions that hold for "
        "CPTP maps under partial trace\n(locality / no-signalling, and dependence on the reduced state of "
        "W together with the operation's support; the quantum instance is not mechanized).\nPruning beyond the "
        "cone is justified by the exact runtime check, not by this proof.", fontsize=8.5, color="#374151")
fig.tight_layout()
fig.savefig(OUT, dpi=220)
print(f"wrote {OUT}")
