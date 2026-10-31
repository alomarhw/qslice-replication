"""Build Paper B's anonymous replication package from the committed workspace (HEAD), into build/package-b/.

Only what the paper uses is copied: the tool (as the installable package srcslice_q), the srcSlice patch, the
evaluation's scripts and results, the data that ships, and the paper. Names are scrubbed, local paths are written as
<repo> and <data-root>, and the build fails if anything that identifies the authors or another submission remains.
Then the package checks itself: its numbers equal the workspace's, the paper builds, and the front-end tests pass.
Usage (workspace root): python tools/b_package/build.py
"""
import csv, hashlib, io, os, re, shutil, subprocess, sys, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tools" / "b_package"
OUT = ROOT / "build" / "package-b"
PY = str(ROOT / ".venv" / "bin" / "python")

SCRIPTS = ["__init__", "b_reference", "b_bugs4q", "make_numbers_b", "make_fig_scale", "scale_run", "srcslice_classical",
           "lintq_compare", "unmodelled_calls", "calls_per_kind", "qhe_run", "corpus_sizes", "coverage_reasons",
           "rerun_controlflow_files", "rerun_gate_table", "qasm_srcml_lossless", "qasm_srcml_equiv", "qasm_srcml_rejected",
           "qasm3_check", "oq3_export_corpus", "quantum_markup_check", "encoding_check", "rerun_encoding_files"]
RESULTS = ["b_example", "controlflow", "lintq_compare", "profiles", "qasm3_srcml", "qasm_srcml", "qhe", "qhe__rerun-20261028",
           "scale", "scale__rerun-20261028", "scale__rerun-20261029", "scale__rerun-20261031", "scale__rerun-20261031b",
           "srcslice", "srcslice_heldout", "srcslice_i20", "tool_acceptance", "tool_coverage", "unmodelled", "quantum_markup",
           "encoding", "scale__rerun-20261101", "qhe__rerun-20261101", "unmodelled__rerun-20261101", "lintq_compare__rerun-20261101",
           "profiles__rerun-20261101", "srcslice_heldout__rerun-20261101"]
DATA = ["mqtbench", "veriqbench", "openqasm3_examples", "openqasm3_grammar", "openqasm3_roundtrip/index.csv",
        "openqasm3_roundtrip/ours", "bugs4q_ported", "lintq_artifact", "LICENSES"]
FIG_SRC = ["make_fig_b_example.py", "make_fig_b_architecture.py", "make_fig_b_tool.py", "make_fig_b_results.py",
           "srcml_marks.py", "fig_b_example.tex", "fig_b_architecture.tex", "fig_b_tool.tex", "fig_b_coverage.tex",
           "fig_b_share.tex", "fig_scale.tex", "programs/ansatz.py", "programs/teleport.py", "programs/lintq_fig1.py",
           "programs/lintq_fig5.py", "programs/lintq_fig6.py", "programs/lintq_fig11a.py", "programs/lintq_fig11b.py",
           "programs/qchecker_fig5.py"]
FIGS = ["fig_b_example.pdf", "fig_b_architecture.pdf", "fig_b_tool.pdf", "fig_b_coverage.pdf", "fig_b_share.pdf", "fig_scale.pdf"]
TEXT = (".py", ".md", ".tex", ".csv", ".json", ".jsonl", ".sh", ".txt", ".tsv", ".toml", ".diff", ".inc", ".bib", ".yaml", ".g4", "")
MODULES = "|".join(["cli", "interp", "slicer", "srcml", "srcslice", "gates", "profile", "qasm", "qasm_srcml", "qasm_layer",
                    "qasm3_srcml", "qasm3_layer", "quantum_markup", "tests", "corpus", "data"])
# identifying or linking strings: none may survive (case-insensitive)
FORBIDDEN = [r"alomarhw", r"hakam", r"miamioh", r"miami university", r"/users/", r"claude", r"anthropic", r"research pilot",
             r"qline", r"qslice", r"quslice", r"qtmslice", r"\bpaper [ab]\b", r"\b15d0f\b", r"\bea0c9\b", r"\b4e5e1\b",
             r"icpc-original", r"save_to_rp"]


def sh(*a, **k):
    return subprocess.run(a, check=True, text=True, capture_output=True, **k)


def archive():
    """The committed tree (HEAD), so the package is exactly a commit."""
    tar = subprocess.run(["git", "archive", "HEAD"], cwd=ROOT, check=True, capture_output=True).stdout
    tmp = ROOT / "build" / "_head"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(tmp, filter="data")
    return tmp


def cp(src: Path, dst: Path):
    if not src.exists():
        raise SystemExit(f"missing in HEAD: {src}")
    if src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"), dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def assemble(h: Path):
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    cp(h / "tool", OUT / "srcslice_q")
    (OUT / "srcslice_q" / "tests" / "check_qasm.py").unlink()        # the study's circuit corpus, not this paper's
    cp(h / "tools" / "srcslice", OUT / "srcslice")
    for s in SCRIPTS:
        cp(h / "experiments" / "icpc" / f"{s}.py", OUT / "experiments" / "icpc" / f"{s}.py")
    cp(h / "experiments" / "requirements.lock", OUT / "experiments" / "requirements.lock")
    for r in RESULTS:
        cp(h / "experiments" / "results" / "icpc" / r, OUT / "experiments" / "results" / "icpc" / r)
    for d in DATA:
        cp(h / "data" / d, OUT / "data" / d)
    for f in ("README.md", "reproduce.sh", "pyproject.toml", "Dockerfile", "fetch_data.py", "DATA_SOURCES.md"):
        cp(PKG / f, OUT / f)
    cp(PKG / "PROTOCOL.md", OUT / "experiments" / "PROTOCOL.md")
    cp(PKG / "RERUNS.md", OUT / "experiments" / "RERUNS.md")
    cp(PKG / "qasmbench_files.sha256.tsv", OUT / "data" / "qasmbench_files.sha256.tsv")
    cp(h / "experiments" / "OQ3_FRONTEND_PLAN.md", OUT / "experiments" / "OQ3_FRONTEND_PLAN.md")
    # corpus statistics without the circuit-level study's subjects
    import json
    cz = json.load(open(h / "experiments" / "results" / "icpc" / "corpus_sizes.json"))
    for k in ("corpus_a", "generated", "sweeps", "corpus_l"):
        cz.pop(k, None)
    (OUT / "experiments" / "results" / "icpc" / "corpus_sizes.json").write_text(json.dumps(cz, indent=1) + "\n")
    # the paper
    P = OUT / "paper"
    cp(h / "paper" / "b" / "sections", P / "sections")
    main = (h / "paper" / "b" / "main.tex").read_text()
    main = main.replace(r"\input{../numbers}", r"\input{numbers}").replace(r"\bibliography{../references}", r"\bibliography{references}")
    main = "\n".join(l for l in main.split("\n") if not re.match(r"\s*%.*(Paper [AB]|MOVED_FROM_A|inbox/|split from)", l))
    (P / "main.tex").write_text(main)
    for f in ("IEEEtran.cls", "IEEEtran.bst"):
        if (h / "paper" / "b" / f).exists():
            cp(h / "paper" / "b" / f, P / f)
    for f in FIGS:
        cp(h / "paper" / "figures" / f, P / "figures" / f)
    for f in FIG_SRC:
        cp(h / "paper" / "figures" / "src" / f, P / "figures" / "src" / f)
    cp(h / "paper" / "references.bib", P / "references.bib")
    shutil.rmtree(h)


def scrub():
    for p in OUT.rglob("*"):
        if not p.is_file() or p.suffix not in TEXT or p.name in ("MANIFEST.sha256.tsv",) or "openqasm3_grammar" in p.parts:
            continue
        s = p.read_text(errors="surrogateescape")
        t = s
        # the tool is the package srcslice_q
        t = re.sub(r"\bfrom tool\b", "from srcslice_q", t)
        t = re.sub(r"\bimport tool\b", "import srcslice_q", t)
        t = re.sub(rf"\btool\.({MODULES})\b", r"srcslice_q.\1", t)
        t = re.sub(r"(?<![\w./-])tool/", "srcslice_q/", t)
        t = re.sub(r'"tool"', '"srcslice_q"', t)
        t = t.replace("tools/srcslice/", "srcslice/").replace("tools/srcslice", "srcslice")
        # paths and names
        t = re.sub(r"/Users/[A-Za-z0-9_]+/[^\s\"',)]*?/qslice-icpc-data", "<data-root>", t)
        t = t.replace("../qslice-icpc-data", "<data-root>").replace('"../qslice-icpc/data", ', "")
        t = re.sub(r"/Users/[A-Za-z0-9_]+/[^\s\"',)]*?/qslice-icpc-v2", "<repo>", t)
        t = re.sub(r"Paper B's\b", "the paper's", t)
        t = re.sub(r"\(Paper B\)", "", t)
        t = re.sub(r"Paper B\b", "the paper", t)
        t = re.sub(r"\bQSlice\b", "srcSlice-Q", t)
        t = t.replace("experiments/icpc/make_numbers.py", "experiments/icpc/make_numbers_b.py")
        if t != s:
            p.write_text(t, errors="surrogateescape")
    # comment lines that mention the other study's package
    for p in OUT.rglob("*.py"):
        s = p.read_text()
        t = "\n".join(l for l in s.split("\n") if not re.search(r"Paper A|paper A", l))
        if t != s:
            p.write_text(t)


def bib():
    """Keep only the entries the paper cites (from a LaTeX run's .aux)."""
    P = OUT / "paper"
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "main"], cwd=P, capture_output=True)
    keys = set()
    for m in re.finditer(r"\\citation\{([^}]*)\}", (P / "main.aux").read_text()):
        keys |= {k.strip() for k in m.group(1).split(",")}
    entries = re.split(r"\n(?=@)", (P / "references.bib").read_text())
    kept = [e.strip() for e in entries if (m := re.match(r"@\w+\{([^,]+),", e.strip())) and m.group(1).strip() in keys]
    (P / "references.bib").write_text("\n\n".join(kept) + "\n")
    print(f"bibliography: {len(kept)} cited entries of {len(keys)} keys")


def numbers():
    """The package's own numbers.tex, from its own results; every macro the paper uses must equal the workspace's."""
    sh(PY, "icpc/make_numbers_b.py", cwd=OUT / "experiments")
    sh(PY, "icpc/make_fig_scale.py", cwd=OUT / "experiments")
    r = subprocess.run([PY, str(ROOT / "tools" / "b_package" / "check_numbers.py"), str(OUT / "paper" / "numbers.tex")],
                       cwd=ROOT, text=True, capture_output=True)
    print(r.stdout.strip())
    if r.returncode:
        raise SystemExit("numbers differ")


def paper():
    P = OUT / "paper"
    for c in (["pdflatex", "-interaction=nonstopmode", "main"], ["bibtex", "main"],
              ["pdflatex", "-interaction=nonstopmode", "main"], ["pdflatex", "-interaction=nonstopmode", "main"]):
        subprocess.run(c, cwd=P, capture_output=True)
    log = (P / "main.log").read_text(errors="replace")
    errs = log.count("\n!")
    undef = len(re.findall(r"undefined", log))
    pages = re.search(r"Pages:\s+(\d+)", sh("pdfinfo", "main.pdf", cwd=P).stdout).group(1)
    print(f"paper: {pages} pages, {errs} errors, {undef} undefined")
    for f in P.glob("main.*"):
        if f.suffix not in (".tex", ".pdf"):
            f.unlink()
    if errs or undef:
        raise SystemExit("paper does not build cleanly")


def tests():
    for m in ("srcslice_q.tests.test_qasm_srcml", "srcslice_q.tests.test_qasm3_grammar"):
        r = subprocess.run([PY, "-m", m], cwd=OUT, text=True, capture_output=True)
        print(m, "->", (r.stdout.strip().splitlines() or ["(no output)"])[-1])
        if r.returncode:
            raise SystemExit(f"{m} failed: {r.stderr[-400:]}")
    r = subprocess.run([PY, "-m", "srcslice_q.cli", "srcslice_q/tests/big/teleport_chain.py", "--qubits", "q[4]"],
                       cwd=OUT, text=True, capture_output=True)
    print("srcslice-q teleport_chain q[4] ->", r.stdout.strip().splitlines()[0] if r.stdout else r.stderr[-300:])
    if r.returncode:
        raise SystemExit("cli failed")


def anonymity():
    bad = []
    for p in OUT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(OUT)
        low = str(rel).lower()
        hits = [w for w in FORBIDDEN if re.search(w, low)]
        if p.suffix in TEXT and "openqasm3_grammar" not in rel.parts:
            s = p.read_text(errors="replace").lower()
            if rel.name == "references.bib":    # cited authors are not identifying; the bib is checked for the rest
                s = re.sub(r"author\s*=\s*\{[^}]*\}", "", s)
            hits += [w for w in FORBIDDEN if re.search(w, s)]
        if p.suffix == ".pdf":
            txt = subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True).stdout.lower()
            meta = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True).stdout.lower()
            hits += [w for w in FORBIDDEN if re.search(w, meta) or re.search(w, txt)]
        if hits:
            bad.append((str(rel), sorted(set(hits))))
    for b in bad:
        print("IDENTIFYING", b)
    if bad:
        raise SystemExit(f"{len(bad)} files with identifying strings")
    print("anonymity: no identifying string in", sum(1 for _ in OUT.rglob("*") if _.is_file()), "files")


def manifest():
    rows = []
    for p in sorted((OUT / "data").rglob("*")):
        if p.is_file() and "QASMBench-master" not in p.parts and p.name != "qasmbench_files.sha256.tsv":
            rows.append((str(p.relative_to(OUT)), hashlib.sha256(p.read_bytes()).hexdigest()))
    with open(OUT / "MANIFEST.sha256.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["path", "sha256"])
        w.writerows(rows)
    print(f"manifest: {len(rows)} data files")


def main():
    assemble(archive())
    scrub()
    numbers()
    bib()
    paper()
    tests()
    manifest()
    anonymity()
    shutil.make_archive(str(OUT), "zip", OUT)
    print("built", OUT, "and", str(OUT) + ".zip")


if __name__ == "__main__":
    main()
