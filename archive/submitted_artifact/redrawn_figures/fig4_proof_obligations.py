"""Redraw Fig. 4 (Isabelle proof obligations) from the submitted theory.

The original drawing script was not saved. This script reads the seven theorems from the unchanged
reported_results/rq6_isabelle/SemanticPreservation_v2.thy, runs `isabelle build` on a scratch copy
(if isabelle is on the PATH) to decide whether they are machine-checked, and records which of the
four axioms each proof cites by name (a textual scan of the proof). Unlike the submitted figure,
it shows those axiom dependencies, because the obligations hold only relative to them, and two are
unsound as stated (PROVENANCE.md, D3).

Usage: python fig4_proof_obligations.py [out_dir]     (default: ./out)
"""

from __future__ import annotations

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
ISA = HERE.parent / "reported_results" / "rq6_isabelle"
LABELS = {  # theorem name -> label used in the submitted figure
    "semantic_preservation_skip": "Skip preservation",
    "semantic_preservation_assign": "Off-criterion unitary (assign)",
    "semantic_preservation_seq": "Sequential composition",
    "semantic_preservation_if": "Conditional (if)",
    "ed_edge_soundness": "Entanglement-edge soundness",
    "semantic_preservation_while": "While loop (fuel induction)",
    "main_semantic_preservation": "Aggregate (main theorem)",
}
UNSOUND = {"unitary_off_V_preserves_rdm", "rdm_locality"}


def isabelle_build() -> bool | None:
    if not shutil.which("isabelle"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        for f in ISA.iterdir():
            if f.suffix == ".thy" or f.name == "ROOT":
                shutil.copy(f, tmp)
        return subprocess.run(["isabelle", "build", "-d", ".", "QSlicePreserv"], cwd=tmp,
                              capture_output=True).returncode == 0


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out"
    out.mkdir(parents=True, exist_ok=True)
    text = (ISA / "SemanticPreservation_v2.thy").read_text()
    body = text.split("axiomatization where", 1)[1]
    axioms = re.findall(r"^\s+(\w+):", body.split("(* ====", 1)[0], flags=re.M)
    blocks = re.split(r"^theorem\s+", text, flags=re.M)[1:]
    theorems = []
    for b in blocks:
        name = b.split(":", 1)[0].strip()
        proof = b.split("\ntheorem", 1)[0]
        theorems.append((name, [a for a in axioms if re.search(rf"\b{a}\b", proof)], "sorry" in proof))
    built = isabelle_build()
    status = {True: "machine-checked", False: "build failed", None: "not built (no isabelle)"}[built]
    print(f"theorems: {len(theorems)}; axioms: {axioms}; isabelle build: {status}")

    fig, ax = plt.subplots(figsize=(14, 5.8))
    for i, (name, deps, has_sorry) in enumerate(theorems):
        y = len(theorems) - 1 - i
        ok = built is True and not has_sorry
        ax.barh(y, 0.8, left=0, align="center", color="#2E8B57" if ok else "#9CA3AF", height=0.62)
        ax.text(0.03, y, "machine-checked" if ok else status, va="center", color="white",
                fontweight="bold", fontsize=11)
        ax.text(0.86, y, LABELS.get(name, name), va="center", fontsize=12)
        dep = ", ".join(("⚠ " if a in UNSOUND else "") + a for a in deps) or "no axiom cited"
        ax.text(2.05, y, dep, va="center", fontsize=9.5,
                color="#B91C1C" if set(deps) & UNSOUND else "#374151")
    ax.text(2.05, len(theorems) - 0.35, "axioms cited in the proof", fontsize=10, fontweight="bold")
    ax.set_xlim(0, 3.7)
    ax.set_ylim(-1.6, len(theorems))
    ax.axis("off")
    ax.text(0, -1.1, f"isabelle build: {status}. All obligations hold only relative to the 4 axioms\n"
            f"({', '.join(axioms)}); ⚠ = unsound as stated (see PROVENANCE.md, D3).",
            fontsize=9.5, color="#374151")
    fig.tight_layout()
    fig.savefig(out / "fig4_proof_obligations_redrawn.png", dpi=220)
    print(f"wrote {out / 'fig4_proof_obligations_redrawn.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
