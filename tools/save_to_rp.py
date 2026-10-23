"""Save the ICPC 2027 paper (projects/_workspaces/qslice-icpc) into its own Research Pilot project.

The project is created on the first run, owned by the same user as the ICSE project #31399, and its id
is kept in tools/rp_project_id.txt so later runs update it instead of creating another. Project #31399
stays the ICSE record and is never written. Uses only the app's own functions (crud, write_phase_output,
compile_latex); no Research Pilot code is changed.
Run from the Research Pilot repository root:
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 projects/_workspaces/qslice-icpc/tools/save_to_rp.py
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
REPO = WS.parents[2]
os.chdir(REPO)
sys.path.insert(0, str(REPO))
from db.database import SessionLocal  # noqa: E402
from db import crud  # noqa: E402
from phases.contracts import write_phase_output  # noqa: E402
from utils.latex_compile import compile_latex  # noqa: E402
from agents.writer import _pdf_page_count  # noqa: E402

ICSE_PID = uuid.UUID("3139969e-1591-4679-a249-02462fa9ab85")
ID_FILE = WS / "tools" / "rp_project_id.txt"
PAPER = WS / "paper"


def inline_inputs(tex: str) -> str:
    """The app stores one main.tex, so every \\input{...} under paper/ is inlined."""
    import re  # noqa: PLC0415
    while (m := re.search(r"\\input\{([^}]+)\}", tex)):
        tex = tex[:m.start()] + (PAPER / f"{m.group(1)}.tex").read_text() + tex[m.end():]
    return tex


def main() -> None:
    db = SessionLocal()
    from db.models import Project  # noqa: PLC0415
    icse = db.get(Project, ICSE_PID)
    title = (PAPER / "title.txt").read_text().strip()
    if ID_FILE.exists():
        pid = uuid.UUID(ID_FILE.read_text().strip())
        project = db.get(Project, pid)
        assert project is not None, f"recorded project {pid} not found"
        created = False
    else:
        project = crud.create_project(db, icse.user_id, title)
        pid = project.id
        ID_FILE.write_text(str(pid) + "\n")
        created = True
    assert pid != ICSE_PID
    now = datetime.now(timezone.utc).isoformat()
    crud.upsert_project_data(db, pid, "pipeline_intent", {"intent": "maturation"})
    crud.upsert_project_data(db, pid, "publication_target", {"target": "icse"})
    crud.upsert_project_data(db, pid, "governance_mode", {"mode": "collaborative"})
    short = str(ICSE_PID).replace("-", "")[:5].upper()
    decisions = [
        ("D1", "predecessor", "setup", f"ICPC 2027 resubmission of the ICSE 2027 paper in project #{short}; that project stays the ICSE record",
         "Integrity rule: keep the reviewed submission unchanged."),
        ("D2", "scope", "architect", "Split: research paper on validated quantum dependences and slicing criteria; srcML/srcSlice for Qiskit and OpenQASM as the ICPC Tool Demonstration paper",
         "Author decision, 2026-10-23 (PAPER_OUTLINE.md)."),
        ("D3", "title", "writer", title, "Author decision, 2026-10-23."),
        ("D4", "rp_project", "setup", "A new Research Pilot project for the ICPC paper", "Author decision, 2026-10-23."),
    ]
    old = (crud.get_project_data(db, pid, "decision_log") or {}).get("decisions") or []
    have = {d["id"] for d in old}
    crud.upsert_project_data(db, pid, "decision_log", {"decisions": old + [
        {"id": i, "type": t, "actor": "Hakam Alomari", "stage": s, "choice": c, "rationale": r, "timestamp": now, "alternatives": []}
        for i, t, s, c, r in decisions if i not in have]})

    tex = inline_inputs((PAPER / "main.tex").read_text())
    bib = (PAPER / "references.bib").read_text()
    import api.main as m  # noqa: PLC0415
    fdir = m._project_figures_dir(pid)
    fdir.mkdir(parents=True, exist_ok=True)
    for pdf in (PAPER / "figures").glob("*.pdf"):
        (fdir / pdf.name).write_bytes(pdf.read_bytes())
    ui_root = Path.home() / "Library/CloudStorage/GoogleDrive-alomarhw@miamioh.edu/.shortcut-targets-by-id/0B51rXHkfdbSkTU1Bd1U1bkhyaFU/MU-Research/research-pilot-codex"
    ui_fdir = ui_root / "projects" / "_figures" / str(pid)
    if ui_root.is_dir() and ui_fdir.resolve() != fdir.resolve():  # the UI backend serves from its own checkout
        ui_fdir.mkdir(parents=True, exist_ok=True)
        for f in fdir.glob("*.pdf"):
            (ui_fdir / f.name).write_bytes(f.read_bytes())
        for c in (ui_root / "projects" / "_pdf_cache").glob(f"{pid}_*.pdf"):
            c.unlink()
    res = compile_latex(tex, bib, figures_dir=fdir)
    pages = _pdf_page_count(res.get("pdf_path"))
    wo = {
        "title": title, "author": "Hakam Alomari", "institution": "Miami University", "anonymous": True,
        "template": "ieeetran", "mainTex": tex, "bib": bib, "compiled": bool(res.get("ok")),
        "pageCount": str(pages or ""), "wordCount": len(tex.split()), "fixAttempts": 0,
        "placeholders": tex.count("\\TODO{"), "paperMode": "draft: title and abstract; sections not yet written",
        "claimStrength": "draft", "claims": [], "unresolvedCitations": [], "citationsAdded": 0, "groundingIssues": [],
        "referencesAvailable": 0, "referencesCited": 0,
        "postEditNotes": ["Written outside the pipeline in projects/_workspaces/qslice-icpc (branch icpc); every number comes from "
                          "paper/numbers.tex, generated from committed results by experiments/icpc/make_numbers.py.",
                          f"Predecessor: ICSE 2027 project #{short} (unchanged)."],
    }
    write_phase_output(db, pid, "writer", wo)
    print(f"project {'created' if created else 'updated'}: {pid} (#{str(pid).replace('-', '')[:5].upper()}); "
          f"compiled {bool(res.get('ok'))}, pages {pages}, placeholders {wo['placeholders']}")


if __name__ == "__main__":
    main()
