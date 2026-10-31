"""Every number Paper B states, from its committed result files only.

Reads experiments/results/icpc/ and recomputes nothing about circuits.
Writes:
  ../paper/numbers.tex         one \\newcommand per number, each commented with its source file
  results/icpc/numbers_b.json  the same values, raw and formatted, with the source of each
Usage (from experiments/): python icpc/make_numbers_b.py
"""

from __future__ import annotations

import csv
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tool import TOOL_NAME  # noqa: E402

RES = HERE / "results"
ICPC = RES / "icpc"
TEX = HERE.parent / "paper" / "numbers.tex"
NUMS: dict = {}


def put(name: str, value, text: str, source: str):
    assert name.isalpha() and name not in NUMS, name
    NUMS[name] = {"value": value, "tex": text, "source": source}


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}\\%"


def sci(x: float) -> str:
    m, e = f"{x:.1e}".split("e")
    return f"\\ensuremath{{{m}\\times 10^{{{int(e)}}}}}"


def cnt(n: int) -> str:
    return f"{n:,}".replace(",", "{,}")


WORDS = "zero one two three four five six seven eight nine ten".split()


def word(n: int, cap: bool = False) -> str:
    """Counts up to ten as words, for running text; larger counts as numerals."""
    w = WORDS[n] if 0 <= n <= 10 else cnt(n)
    return w.capitalize() if cap else w


def const(path: str, name: str):
    """A module-level integer constant of one of the study's scripts, read from its source."""
    m = re.search(rf"^{name}\s*=\s*(\d+)\s*$", (HERE / path).read_text(), re.M)
    assert m, (path, name)
    return int(m.group(1))


def pval(p: float) -> str:
    if p < 1e-10:
        return "p < 10^{-10}"
    if p < 0.001:
        m, e = f"{p:.1e}".split("e")
        return f"p = {m}\\times 10^{{{int(e)}}}"
    return f"p = {p:.3f}" if p < 0.1 else f"p = {p:.2f}"


def rows(path: Path):
    return list(csv.DictReader(open(path)))


def by_pair(path: Path, key="slicer"):
    out = defaultdict(dict)
    for r in rows(path):
        out[(r["path"], r["target"])][r[key]] = r
    return out


def main() -> int:
    HAS_TOOL = True
    # ---- qubit slice profiles over the corpora (Deviation I-17, tool-v5; tool/corpus/profiles.py) ----------
    PR = ICPC / "profiles"
    for f, nm in (("bugs4q", "Bugs"), ("textbook", "Text"), ("lintq500", "Lintq")):
        r = [x for x in rows(PR / f"{f}.csv") if not x["error"]]
        src = f"results/icpc/profiles/{f}.csv"
        put(f"Prof{nm}Files", len({x["file"] for x in r}), cnt(len({x["file"] for x in r})), src)
        put(f"Prof{nm}Qubits", len(r), cnt(len(r)), src)
        fn = sum(x["in_function"] == "1" for x in r) / len(r)
        put(f"Prof{nm}InFunction", fn, pct(fn, 0), src)
        fb = sum(x["fwd_lines"] != x["bwd_lines"] for x in r) / len(r)
        put(f"Prof{nm}FwdNeBwd", fb, pct(fb, 0), src)
    lq = rows(PR / "lintq500.csv")
    put("ProfLintqSample", len({x["file"] for x in lq}), cnt(len({x["file"] for x in lq})), "results/icpc/profiles/lintq500.csv")
    put("ProfLintqTimeouts", sum(x["error"] == "timeout" for x in lq), cnt(sum(x["error"] == "timeout" for x in lq)), "results/icpc/profiles/lintq500.csv")
    ac = rows(PR / "alias_check_textbook.csv")
    flagged = {x["file"] for x in rows(PR / "textbook.csv") if not x["error"] and int(x["names"]) > 1}
    assert flagged == {x["file"] for x in ac}, "alias check does not cover the flagged textbook files"
    put("ProfTextAliasFlagged", len(ac), cnt(len(ac)), "results/icpc/profiles/alias_check_textbook.csv")
    put("ProfTextAliasGenuine", sum(x["genuine"] == "1" for x in ac), cnt(sum(x["genuine"] == "1" for x in ac)),
        "results/icpc/profiles/alias_check_textbook.csv")

    # ---- classical lines from srcSlice against the interpreter's (Deviation I-20) ----
    src = "results/icpc/srcslice/qubits.csv"
    ss = [x for x in rows(ICPC / "srcslice" / "qubits.csv") if not x["error"]]
    lset = lambda t: {int(v) for v in t.split(";") if v}  # noqa: E731
    put("SsFiles", len({(x["corpus"], x["file"]) for x in ss}), cnt(len({(x["corpus"], x["file"]) for x in ss})), src)
    put("SsQubits", len(ss), cnt(len(ss)), src)
    cont = sum(lset(x["interp"]) <= lset(x["srcslice"]) for x in ss) / len(ss)
    put("SsContainPct", cont, pct(cont, 0), src)
    db = [x for x in ss if x["corpus"] in ("dev", "bugs4q")]
    dbc = sum(lset(x["interp"]) <= lset(x["srcslice"]) for x in db) / len(db)
    put("SsDevBugsContainPct", dbc, pct(dbc, 0), src)
    eq = sum(lset(x["interp"]) == lset(x["srcslice"]) for x in ss) / len(ss)
    put("SsEqualPct", eq, pct(eq, 0), src)
    hit = sum(len(lset(x["interp"]) & lset(x["srcslice"])) for x in ss)
    rec = hit / sum(len(lset(x["interp"])) for x in ss)
    prec = hit / sum(len(lset(x["srcslice"])) for x in ss)
    put("SsRecall", rec, f"{rec:.2f}", src)
    put("SsPrecision", prec, f"{prec:.2f}", src)
    ft = sorted({(x["corpus"], x["file"]): float(x["srcslice_s"]) for x in ss}.values())
    put("SsMedianMs", ft[len(ft) // 2], f"{1000 * ft[len(ft) // 2]:.0f}", src)
    # the run before the two srcSlice fixes of Deviation I-21
    src = "results/icpc/srcslice_i20/qubits.csv"
    s0 = [x for x in rows(ICPC / "srcslice_i20" / "qubits.csv") if not x["error"]]
    c0 = sum(lset(x["interp"]) <= lset(x["srcslice"]) for x in s0) / len(s0)
    put("SsBeforeContainPct", c0, pct(c0, 0), src)
    d0 = [x for x in s0 if x["corpus"] in ("dev", "bugs4q")]
    dc0 = sum(lset(x["interp"]) <= lset(x["srcslice"]) for x in d0) / len(d0)
    put("SsBeforeDevBugsContainPct", dc0, pct(dc0, 0), src)
    h0 = sum(len(lset(x["interp"]) & lset(x["srcslice"])) for x in s0) / sum(len(lset(x["interp"])) for x in s0)
    put("SsBeforeRecall", h0, f"{h0:.2f}", src)
    bq = [x for x in ss if x["corpus"] == "bugs4q"]
    put("SsBugsContain", sum(lset(x["interp"]) <= lset(x["srcslice"]) for x in bq), cnt(sum(lset(x["interp"]) <= lset(x["srcslice"]) for x in bq)), "results/icpc/srcslice/qubits.csv")
    put("SsBugsQubits", len(bq), cnt(len(bq)), "results/icpc/srcslice/qubits.csv")

    # ---- OpenQASM 2 through srcML: Behler et al.'s markup and the quantum layer over it ----
    sd = ICPC / "qasm_srcml"
    oq3 = lambda f: "/openqasm3_" in f  # OpenQASM 3 data (official examples, grammar tests, round-trip corpus)
    eq = [r for r in rows(sd / "equiv.csv") if not oq3(r["file"])]
    src = "results/icpc/qasm_srcml/equiv.csv"
    checked = [r for r in eq if r["layer_vs_qiskit"] in ("True", "False")]
    same = [r for r in checked if r["layer_vs_qiskit"] == "True"]
    rej = [r for r in rows(sd / "rejected.csv") if not oq3(r["file"])]
    assert len(rej) == len(checked) - len(same), "every file not equal to Qiskit's circuit is rejected"
    assert all(r["qiskit"].startswith("rejects") for r in rej), "Qiskit rejects every file the front end rejects"
    assert all(r["layer_vs_reader"] == "True" for r in same)
    import hashlib  # the corpora hold some files twice (qasmbench/ and QASMBench-master/): count distinct contents
    uniq = lambda rs: len({hashlib.sha256(open(r["file"], "rb").read()).hexdigest() for r in rs})
    put("SmlChecked", uniq(checked), cnt(uniq(checked)), src)
    put("SmlSame", uniq(same), cnt(uniq(same)), src)
    put("SmlRejected", uniq(rej), cnt(uniq(rej)), "results/icpc/qasm_srcml/rejected.csv")
    lg = [r for r in eq if r["note"].startswith("large")]
    put("SmlLarge", uniq(lg), cnt(uniq(lg)), src)
    ll = [r for r in rows(sd / "lossless.csv") if not oq3(r["file"]) and r["version"] != "" and not r["version"].startswith("3")]
    src = "results/icpc/qasm_srcml/lossless.csv"
    marked = [r for r in ll if not r["error"].startswith("larger than")]
    assert all(r["ok"] == "True" for r in marked), "every OpenQASM 2 file up to 20 MB is marked up losslessly"
    put("SmlLossless", uniq(marked), cnt(uniq(marked)), src)
    # ---- OpenQASM 3 through srcML, the subset (results/icpc/qasm3_srcml, experiments/icpc/qasm3_check.py) ----
    q3 = json.load(open(ICPC / "qasm3_srcml" / "summary.json"))
    src = "results/icpc/qasm3_srcml/summary.json"
    assert q3["grammar"]["invalid_accepted"] == 0 and q3["examples"]["crash"] == q3["veriqbench"]["crash"] == 0
    assert q3["roundtrip_ours"]["equal"] == q3["roundtrip_ours"]["files"]
    assert q3["roundtrip_corpus"]["equal"] == q3["roundtrip_corpus"]["files"]
    put("QthreeRefCases", q3["grammar"]["reference_cases"], cnt(q3["grammar"]["reference_cases"]), src)
    put("QthreeRefMatch", q3["grammar"]["reference_match"], cnt(q3["grammar"]["reference_match"]), src)
    put("QthreeInvalidRejected", q3["grammar"]["invalid_rejected"], cnt(q3["grammar"]["invalid_rejected"]), src)
    put("QthreeOurs", q3["roundtrip_ours"]["files"], cnt(q3["roundtrip_ours"]["files"]), src)
    rtc = [r for r in rows(ICPC / "qasm3_srcml" / "roundtrip_corpus.csv") if r["equal"] == "True"]
    import hashlib as _h
    nd = len({_h.sha256((HERE.parent / "data" / "openqasm3_roundtrip" / "corpus" / r["file"]).read_bytes()).hexdigest()
              for r in rtc})
    put("QthreeCorpus", nd, cnt(nd), "results/icpc/qasm3_srcml/roundtrip_corpus.csv")
    put("QthreeExamples", q3["examples"]["files"], cnt(q3["examples"]["files"]), src)
    put("QthreeExamplesTraced", q3["examples"]["trace"], cnt(q3["examples"]["trace"]), src)
    put("QthreeExamplesReported", q3["examples"]["reported"], cnt(q3["examples"]["reported"]), src)
    put("QthreeExamplesOutside", q3["examples"]["trace_with_outside_constructs"], cnt(q3["examples"]["trace_with_outside_constructs"]), src)
    put("QthreeVeriqFiles", q3["veriqbench"]["files"], cnt(q3["veriqbench"]["files"]), src)
    put("QthreeVeriqRejected", q3["veriqbench"]["rejected"], cnt(q3["veriqbench"]["rejected"]), src)

    from tool.tests import test_qasm_srcml as T  # the grammar, invalid-program and specification test cases
    put("SmlGrammarCases", len(T.VALID), cnt(len(T.VALID)), "tool/tests/test_qasm_srcml.py")
    put("SmlInvalidCases", len(T.INVALID), cnt(len(T.INVALID)), "tool/tests/test_qasm_srcml.py")
    put("SmlSpecPrograms", len(T.SPEC), cnt(len(T.SPEC)), "tool/tests/qasm2/spec_*.qasm")
    src = "results/icpc/lintq_compare/c1.csv"
    c1 = rows(ICPC / "lintq_compare" / "c1.csv")
    qrules = {"ql-operation-after-measurement", "ql-double-measurement", "ql-oversized-circuit",
              "ql-conditional-without-measurement", "ql-unmeasurable-qubits"}
    qr = [x for x in c1 if x["rule_id"] in qrules]
    put("LqTp", len(c1), cnt(len(c1)), src)
    put("LqQubitTp", len(qr), cnt(len(qr)), src)
    put("LqQubitTraced", sum(x["traced"] == "1" for x in qr), cnt(sum(x["traced"] == "1" for x in qr)), src)
    put("LqQubitExposed", sum(x["exposed"] == "1" for x in qr), cnt(sum(x["exposed"] == "1" for x in qr)), src)
    rd = sorted(int(x["slice_lines"]) for x in qr if x["slice_lines"])
    cd = sorted(int(x["code_lines"]) for x in qr if x["slice_lines"])
    put("LqReadMedian", rd[len(rd) // 2], cnt(rd[len(rd) // 2]), src)
    put("LqCodeMedian", cd[len(cd) // 2], cnt(cd[len(cd) // 2]), src)
    put("LqReadN", len(rd), cnt(len(rd)), src)
    for nm, f in (("Fp", "c1_fp.csv"), ("Sarif", "c1_sarif.csv")):
        x = rows(ICPC / "lintq_compare" / f)
        t = [r for r in x if r["traced"] == "1"]
        put(f"Lq{nm}Warnings", len(x), cnt(len(x)), "results/icpc/lintq_compare/" + f)
        put(f"Lq{nm}Traced", len(t), cnt(len(t)), "results/icpc/lintq_compare/" + f)
        put(f"Lq{nm}Fires", sum(r["exposed"] == "1" for r in t), cnt(sum(r["exposed"] == "1" for r in t)), "results/icpc/lintq_compare/" + f)

    # ---- scalability (Deviation I-22) ----
    sc = ICPC / "scale"
    tf = lambda r, ks: sum(float(r[k]) for k in ks if r.get(k))  # noqa: E731
    src = "results/icpc/scale/s1_lintq.csv"
    s1 = rows(sc / "s1_lintq.csv")
    ok1 = [r for r in s1 if not r["error"]]
    put("ScaleSOneFiles", len(s1), cnt(len(s1)), src)
    put("ScaleSOneSliced", len(ok1), cnt(len(ok1)), src)
    put("ScaleSOneTimeouts", sum(r["error"] == "timeout" for r in s1), cnt(sum(r["error"] == "timeout" for r in s1)), src)
    tot = sorted(tf(r, ["t_srcml", "t_interp", "t_slice", "t_srcslice", "t_profile"]) for r in ok1)
    put("ScaleSOneMedianMs", st.median(tot), f"{1000 * st.median(tot):.0f}", src)
    put("ScaleSOneNinetyNine", tot[int(0.99 * len(tot))], f"{tot[int(0.99 * len(tot))]:.0f}", src)
    for k, nm in (("t_srcml", "Srcml"), ("t_interp", "Interp"), ("t_slice", "Slice"), ("t_srcslice", "Srcslice"), ("t_profile", "Profile")):
        v = st.median(float(r[k]) for r in ok1)
        put(f"ScaleSOne{nm}Ms", v, f"{1000 * v:.1f}" if v < 0.01 else f"{1000 * v:.0f}", src)
    big = max(ok1, key=lambda r: int(r["ops"]))
    put("ScaleSOneMaxOps", int(big["ops"]), cnt(int(big["ops"])), src)
    put("ScaleSOneMaxOpsS", tf(big, ["t_srcml", "t_interp", "t_slice", "t_srcslice", "t_profile"]),
        f"{tf(big, ['t_srcml', 't_interp', 't_slice', 't_srcslice', 't_profile']):.0f}", src)
    b10 = [r for r in ok1 if int(r["ops_beyond_10th_iteration"]) > 0]
    put("LqBeyondTenFiles", len(b10), cnt(len(b10)), src)
    v = sum(int(r["ops_beyond_10th_iteration"]) for r in b10) / sum(int(r["ops"]) for r in b10)
    put("LqBeyondTenOpsPct", v, pct(v, 0), src)
    share = [int(x) / int(r["code_lines"]) for r in ok1 if int(r["code_lines"]) for x in r["slice_lines"].split(";") if x]
    put("ScaleReadMedianPct", st.median(share), pct(st.median(share), 0), src)
    put("ScaleReadQubits", len(share), cnt(len(share)), src)
    # S2 through srcML (rerun 2026-10-31, RERUNS.md): our rows timed again, the baselines' rows copied unchanged
    src = "results/icpc/scale__rerun-20261031/s2_qasmbench.csv"
    s2 = rows(ICPC / "scale__rerun-20261031" / "s2_qasmbench.csv")
    sq = {r["path"]: r for r in s2 if r["tool"] == TOOL_NAME and not r["error"]}
    sbad = [r for r in s2 if r["tool"] == TOOL_NAME and r["error"] == "QasmSemanticError"]
    put("ScaleQbRejected", len(sbad), cnt(len(sbad)), src)
    put("ScaleQbFiles", len({r["path"] for r in s2}), cnt(len({r["path"] for r in s2})), src)
    put("ScaleQbRead", len(sq), cnt(len(sq)), src)
    put("ScaleQbMillion", sum(int(r["ops"]) >= 1_000_000 for r in sq.values()), cnt(sum(int(r["ops"]) >= 1_000_000 for r in sq.values())), src)
    put("ScaleQbMaxQubits", max(int(r["qubits"]) for r in sq.values()), cnt(max(int(r["qubits"]) for r in sq.values())), src)
    bp = max(sq, key=lambda p: int(sq[p]["ops"]))
    b = sq[bp]
    put("ScaleQbMaxOps", int(b["ops"]), f"{int(b['ops']) / 1e6:.1f}~million", src)
    put("ScaleQbMaxOpsQubits", int(b["qubits"]), cnt(int(b["qubits"])), src)
    put("ScaleQbReadS", float(b["t_read"]), f"{float(b['t_read']):.0f}", src)
    put("ScaleQbMarkupS", float(b["t_markup"]), f"{float(b['t_markup']):.0f}", src)
    put("ScaleQbLayerS", float(b["t_layer"]), f"{float(b['t_layer']):.0f}", src)
    put("ScaleQbReadMin", float(b["t_read"]) / 60, f"{float(b['t_read']) / 60:.0f}", src)
    big = [r for r in sq.values() if int(r["ops"]) >= 100_000]
    rate = sum(int(r["ops"]) for r in big) / sum(float(r["t_read"]) for r in big)
    put("ScaleQbOpsPerS", rate, cnt(int(round(rate, -2))), src)
    put("ScaleQbAllS", tf(b, ["t_terminal", "t_all"]), f"{tf(b, ['t_terminal', 't_all']):.0f}", src)
    put("ScaleQbOneS", tf(b, ["t_terminal", "t_one"]), f"{tf(b, ['t_terminal', 't_one']):.0f}", src)
    dag = {r["path"]: r for r in s2 if r["tool"] == "qiskit-dag" and not r["error"]}
    d = dag[bp]
    put("ScaleQbDagLoadS", float(d["t_load"]), f"{float(d['t_load']):.0f}", src)
    put("ScaleQbDagOneS", tf(d, ["t_build", "t_one"]), f"{tf(d, ['t_build', 't_one']):.0f}", src)
    put("ScaleQbDagAllMin", int(b["qubits"]) * tf(d, ["t_build", "t_one"]) / 60, f"{int(b['qubits']) * tf(d, ['t_build', 't_one']) / 60:.0f}", src)
    qp = {r["path"]: r for r in s2 if r["tool"] == "qpdg"}
    okq = [(int(sq[p]["ops"]), p) for p in qp if p in sq and not qp[p]["error"]]
    mo, mp = max(okq)
    put("ScaleQpdgMaxOps", mo, cnt(mo), src)
    put("ScaleQpdgMaxS", tf(qp[mp], ["t_build", "t_one"]), f"{tf(qp[mp], ['t_build', 't_one']):.0f}", src)
    put("ScaleQpdgSqS", tf(sq[mp], ["t_read", "t_terminal", "t_all"]), f"{tf(sq[mp], ['t_read', 't_terminal', 't_all']):.2f}", src)
    put("ScaleQpdgOver", sum(qp[p]["error"] != "" and p in sq for p in qp), cnt(sum(qp[p]["error"] != "" and p in sq for p in qp)), src)
    lc = {r["path"]: r for r in s2 if r["tool"] == "qiskit-lightcone"}
    lok = [p for p in lc if p in sq and not lc[p]["error"]]
    put("ScaleLcOk", len(lok), cnt(len(lok)), src)
    if lok:
        lm = max(lok, key=lambda p: int(sq[p]["ops"]))
        put("ScaleLcMaxOps", int(sq[lm]["ops"]), cnt(int(sq[lm]["ops"])), src)
        put("ScaleLcMaxS", tf(lc[lm], ["t_build", "t_one"]), f"{tf(lc[lm], ['t_build', 't_one']):.0f}", src)
        put("ScaleLcSqS", tf(sq[lm], ["t_terminal", "t_all"]), f"{tf(sq[lm], ['t_terminal', 't_all']):.1f}", src)
        put("ScaleLcQubits", int(sq[lm]["qubits"]), cnt(int(sq[lm]["qubits"])), src)
    put("ScaleLcOver", sum(lc[p]["error"] in ("timeout",) or lc[p]["error"].startswith("skipped") for p in lc if p in sq),
        cnt(sum(lc[p]["error"] in ("timeout",) or lc[p]["error"].startswith("skipped") for p in lc if p in sq)), src)
    src = "results/icpc/scale/s3_parametric.csv"
    s3 = rows(sc / "s3_parametric.csv")
    q600 = next(r for r in s3 if r["program"] == "qft" and r["size"] == "600" and r["tool"] == TOOL_NAME)
    put("ScaleQftOps", int(q600["ops"]), cnt(int(q600["ops"])), src)
    put("ScaleQftS", tf(q600, ["t_srcml", "t_interp", "t_all", "t_srcslice"]), f"{tf(q600, ['t_srcml', 't_interp', 't_all', 't_srcslice']):.0f}", src)
    r600 = next(r for r in s3 if r["program"] == "qft" and r["size"] == "600" and r["tool"] == "qiskit-run-dag")
    put("ScaleQftRunS", tf(r600, ["t_load", "t_build", "t_one"]), f"{tf(r600, ['t_load', 't_build', 't_one']):.1f}", src)
    put("ScaleQftLines", int(q600["code_lines"]), cnt(int(q600["code_lines"])), src)

    # ---- Deviation I-23: held-out srcSlice, coverage reasons, like-for-like timing ----
    src = "results/icpc/srcslice_heldout/qubits.csv"
    hz = [x for x in rows(ICPC / "srcslice_heldout" / "qubits.csv") if not x["error"]]
    put("SsHeldFiles", len({x["file"] for x in hz}), cnt(len({x["file"] for x in hz})), src)
    put("SsHeldQubits", len(hz), cnt(len(hz)), src)
    hc = sum(lset(x["interp"]) <= lset(x["srcslice"]) for x in hz) / len(hz)
    put("SsHeldContainPct", hc, pct(hc, 0), src)
    lq = [x for x in ss if x["corpus"] == "lintq"]
    lc_ = sum(lset(x["interp"]) <= lset(x["srcslice"]) for x in lq) / len(lq)
    put("SsLintqContainPct", lc_, pct(lc_, 0), "results/icpc/srcslice/qubits.csv")
    src = "results/icpc/scale/coverage_reasons.json"
    cr = json.load(open(ICPC / "scale" / "coverage_reasons.json"))
    for k, nm in (("no_circuit_files", "NoCircuit"), ("no-construction", "NoConstruction"), ("from-file-or-lib", "FromFile"), ("other", "Other")):
        put(f"Cov{nm}", cr[k], cnt(cr[k]), src)
    src = "results/icpc/scale__rerun-20261031/s2_qasmbench.csv"
    s2r = rows(ICPC / "scale__rerun-20261031" / "s2_qasmbench.csv")
    sqr = {r["path"]: r for r in s2r if r["tool"] == TOOL_NAME and not r["error"]}
    dgr = {r["path"]: r for r in s2r if r["tool"] == "qiskit-dag" and not r["error"]}
    one = lambda r, ks: sum(float(r[k]) for k in ks)  # noqa: E731
    rat = [one(sqr[p], ["t_terminal", "t_one"]) / one(dgr[p], ["t_build", "t_one"]) for p in sqr if p in dgr and one(dgr[p], ["t_build", "t_one"]) > 0]
    put("ScaleOneRatio", st.median(rat), f"{st.median(rat):.1f}", src)
    rb = [one(sqr[p], ["t_terminal", "t_one"]) / one(dgr[p], ["t_build", "t_one"]) for p in sqr if p in dgr and int(sqr[p]["ops"]) >= 100000]
    put("ScaleOneRatioBig", st.median(rb), f"{st.median(rb):.1f}", src)

    # ---- the static program slicer (Deviation I-15, I-18; tool-v7, the final version; earlier versions' results kept) --
    sys.path.insert(0, str(HERE.parent))
    from tool.gates import GATES  # noqa: PLC0415
    put("ToolGateTable", len(GATES), cnt(len(GATES)), "tool/gates.py")
    import qiskit  # noqa: PLC0415
    from tool.gates import _from_qiskit, _legacy, _special  # noqa: PLC0415
    gq, gs = _from_qiskit(), _special()
    gl = set(_legacy()) - set(gq) - set(gs)
    put("ToolGateQiskit", len(gq), cnt(len(gq)), "tool/gates.py (_from_qiskit)")
    put("ToolGateLegacy", len(gl), cnt(len(gl)), "tool/gates.py (_legacy)")
    put("ToolGateSpecial", len(gs), word(len(gs)), "tool/gates.py (_special)")
    put("ToolGateControlled", sum(any(n.startswith("control") for n, _ in s.args) for s in gq.values()),
        cnt(sum(any(n.startswith("control") for n, _ in s.args) for s in gq.values())), "tool/gates.py")
    put("QiskitVersion", qiskit.__version__, qiskit.__version__.rsplit(".", 1)[0], "qiskit.__version__")
    from tool.interp import MAX_UNKNOWN_COPIES  # noqa: PLC0415
    put("ToolMaxCopies", MAX_UNKNOWN_COPIES, cnt(MAX_UNKNOWN_COPIES), "tool/interp.py")
    TA = ICPC / "tool_acceptance"
    dev = json.load(open(TA / "dev_checks.json"))
    src = "results/icpc/tool_acceptance/dev_checks.json"
    put("ToolDevPrograms", len(dev), cnt(len(dev)), src)
    put("ToolDevTraceEqual", sum(r["trace_equal"] for r in dev), cnt(sum(r["trace_equal"] for r in dev)), src)
    put("ToolDevSliceEqual", sum(r["slices_equal"] for r in dev), cnt(sum(r["slices_equal"] for r in dev)), src)
    put("ToolDevMaxOps", max(r["ops"] for r in dev), cnt(max(r["ops"] for r in dev)), src)
    assert all(r["nested_conditions"] for r in dev if not r["slices_equal"]), "a slice difference outside nested conditions"
    ts = json.load(open(TA / "tool-v7" / "summary.json"))
    src = "results/icpc/tool_acceptance/tool-v7/summary.json"
    for k, nm in (("t1_bugs", "ToolTOneBugs"), ("t1_exact", "ToolTOneExact"), ("t1_ops_prepared", "ToolTOneOps"),
                  ("t1_ops_matched", "ToolTOneOpsMatched"), ("t2_units_mapped", "ToolTTwoUnits"), ("t2_equal_mapped", "ToolTTwoEqual")):
        put(nm, ts[k], cnt(ts[k]), src)
    nc = json.load(open(TA / "nested_check.json"))
    put("ToolNestedDraws", nc["draws"], cnt(nc["draws"]), "results/icpc/tool_acceptance/nested_check.json")
    put("ToolNestedStudyWrong", nc["study_wrong_max"], cnt(nc["study_wrong_max"]), "results/icpc/tool_acceptance/nested_check.json")
    put("ToolNestedToolWrong", nc["tool_wrong_total"], cnt(nc["tool_wrong_total"]), "results/icpc/tool_acceptance/nested_check.json")
    for path, nm, src in ((TA / "tool-v7" / "t3_bugs4q.csv", "Bugs", "results/icpc/tool_acceptance/tool-v7/t3_bugs4q.csv"),
                          (ICPC / "tool_coverage" / "textbook_v7.csv", "Textbook", "results/icpc/tool_coverage/textbook_v7.csv"),
                          (ICPC / "tool_coverage" / "lintq_v7.csv", "Lintq", "results/icpc/tool_coverage/lintq_v7.csv")):
        cov = rows(path)
        q = [r for r in cov if r["uses_qiskit"] == "1"]
        put(f"Tool{nm}Files", len(cov), cnt(len(cov)), src)
        put(f"Tool{nm}Qiskit", len(q), cnt(len(q)), src)
        put(f"Tool{nm}Parsed", sum(r["parsed"] == "1" for r in q), cnt(sum(r["parsed"] == "1" for r in q)), src)
        put(f"Tool{nm}Circuit", sum(int(r["ops"]) > 0 for r in q), cnt(sum(int(r["ops"]) > 0 for r in q)), src)
        put(f"Tool{nm}Resolved", sum(int(r["ops"]) > 0 and r["may_ops"] == "0" for r in q),
            cnt(sum(int(r["ops"]) > 0 and r["may_ops"] == "0" for r in q)), src)
        crashes = sum(bool(r["crash"]) and r["crash"] != "timeout" for r in q)  # a 60 s timeout is not a crash
        put(f"Tool{nm}Crashes", crashes, cnt(crashes), src)
        tos = sum(r["crash"] == "timeout" for r in q)
        put(f"Tool{nm}Timeouts", tos, ["zero", "one", "two", "three"][tos] if tos < 4 else cnt(tos), src)
        sec = sorted(float(r["seconds"]) for r in q)
        put(f"Tool{nm}MedianMs", st.median(sec) * 1000, f"{st.median(sec) * 1000:.0f}", src)

    if HAS_TOOL:
        tlim = int(re.search(r'add_argument\("--timeout", type=int, default=(\d+)\)', (HERE.parent / "tool" / "corpus" / "coverage.py").read_text()).group(1))
        put("ToolFileLimit", tlim, str(tlim), "tool/corpus/coverage.py (--timeout default)")
    # ---- Deviation I-25: Qiskit HumanEval, current Qiskit (exploratory) ---------------------------------------
    if (ICPC / "qhe" / "summary.json").exists():
        qh = json.load(open(ICPC / "qhe" / "summary.json"))
        src = "results/icpc/qhe/summary.json"
        s, h = qh["standard"], qh["hard"]
        assert (s["tasks"], s["circuit"]) == (h["tasks"], h["circuit"]), "the two sets share their programs"
        builds = s["tasks"] - s["no_circuit_reasons"].get("no-construction", 0)
        put("QheTasks", s["tasks"], cnt(s["tasks"]), src)
        put("QheTraced", s["circuit"], cnt(s["circuit"]), src)
        put("QheNoConstruction", s["tasks"] - builds, cnt(s["tasks"] - builds), src)
        put("QheBuilds", builds, cnt(builds), src)
        put("QheTracedOfBuildsPct", s["circuit"] / builds, pct(s["circuit"] / builds, 0), src)
        put("QheMedianMs", s["median_ms"], f"{s['median_ms']:.0f}", src)
        put("QheMayFiles", s["may_files"], cnt(s["may_files"]), src)
        # slice share on the hard-set files, which hold the program without the prompt's docstring
        put("QheSliceSharePct", h["median_slice_share"], pct(h["median_slice_share"], 0), src)

    # ---- Deviation I-26: in-circuit control flow (exploratory) --------------------------------------------------
    if (ICPC / "controlflow" / "summary.json").exists():
        cf = json.load(open(ICPC / "controlflow" / "summary.json"))
        ng = json.load(open(ICPC / "controlflow" / "negative.json"))
        src = "results/icpc/controlflow/summary.json"
        assert not cf["unsound"], "a control-flow slice is unsound"
        put("CfPrograms", cf["programs"], cnt(cf["programs"]), src)
        put("CfQubits", cf["qubits"], cnt(cf["qubits"]), src)
        put("CfInputs", cf["inputs_per_qubit"], word(cf["inputs_per_qubit"]), src)
        put("CfSound", cf["sound"], cnt(cf["sound"]), src)
        src = "results/icpc/controlflow/negative.json"
        put("CfKickbackDropFidelity", ng["kickback_cnot_removed_min_fidelity"], f"{ng['kickback_cnot_removed_min_fidelity']:.2f}", src)
        put("CfOldWrong", ng["archived_programs_wrong"], word(ng["archived_programs_wrong"]), src)
        rr = list(csv.DictReader(open(ICPC / "controlflow" / "real.csv")))
        # main_59bca5.py mentions switch only in comments and loads its circuits from files
        uses = [r for r in rr if r["file"] != "main_59bca5.py"]
        put("CfRealFiles", len(uses), word(len(uses)), "results/icpc/controlflow/real.csv")
        put("CfRealTraced", sum(not r["error"] for r in uses), word(sum(not r["error"] for r in uses)), "results/icpc/controlflow/real.csv")

    # ---- the same statistics for every subject (corpus_sizes.py; code lines are non-blank, non-comment lines) --
    if (ICPC / "corpus_sizes.json").exists():
        cz = json.load(open(ICPC / "corpus_sizes.json"))
        src = "results/icpc/corpus_sizes.json"
        names = {"corpus_a": "A", "generated": "Gen", "sweeps": "Sweep", "corpus_l": "L", "qasmbench": "Qb", "bugs4q": "Bugs",
                 "textbook": "Text", "lintq": "Lintq", "qhe": "Qhe", "parametric": "Param", "controlflow": "Cf"}
        for k, nm in names.items():
            s = cz[k]
            for f, fn in (("count", "Count"), ("traced", "Traced"), ("min_qubits", "MinQubits"), ("max_qubits", "MaxQubits"),
                          ("median_ops", "MedianOps"), ("max_ops", "MaxOps"), ("median_lines", "MedianLines")):
                if f in s:
                    v = s[f]
                    tex = (f"{v / 1e6:.1f}~million" if v >= 1e6 else cnt(round(v)))
                    put(f"Subj{nm}{fn}", v, tex, src)
        # names used by the related-work table
        put("SizeAMinQubits", cz["corpus_a"]["min_qubits"], cnt(cz["corpus_a"]["min_qubits"]), src)
        put("SizeAMaxQubits", cz["corpus_a"]["max_qubits"], cnt(cz["corpus_a"]["max_qubits"]), src)
        put("SizeAMaxOps", cz["corpus_a"]["max_ops"], cnt(cz["corpus_a"]["max_ops"]), src)
        for k, nm in (("bugs4q", "Bugs"), ("textbook", "Text"), ("lintq", "Lintq"), ("qhe", "Qhe")):
            put(f"Size{nm}Files", cz[k]["count"], cnt(cz[k]["count"]), src)
        if HAS_TOOL:
            from tool.interp import MAX_OPS  # noqa: PLC0415
            put("ToolMaxOps", MAX_OPS, cnt(MAX_OPS), "tool/interp.py (MAX_OPS)")
        # Paper A, Table I: every circuit with a ground truth (corpus A, generated, width sweeps, corpus L)
        n = sum(cz[k]["count"] for k in ("corpus_a", "generated", "sweeps", "corpus_l"))
        put("StudyCircuits", n, cnt(n), src)
        if "RqThreeUnits" in NUMS and "LinesUnits" in NUMS:
            n = NUMS["RqThreeUnits"]["value"] + NUMS["BugsFourQUnits"]["value"]
            put("StudyFaultUnits", n, cnt(n), "results/icpc/rq3/records.csv + results/icpc/source_map/units.csv")

    # ---- Deviation I-27: the role table and the calls outside it, on LintQ's corpus (descriptive) -------------
    if (ICPC / "unmodelled" / "calls_per_kind.json").exists():
        ck = json.load(open(ICPC / "unmodelled" / "calls_per_kind.json"))
        src = "results/icpc/unmodelled/calls_per_kind.json"
        for k, nm in (("single", "Single"), ("two", "Two"), ("multi", "Multi"), ("legacy", "Legacy"), ("special", "Special"),
                      ("composition", "Compose"), ("control_flow", "Flow"), ("transform", "Transform"), ("to_dag", "Dag")):
            put(f"Calls{nm}", ck["per_kind"][k], cnt(ck["per_kind"][k]), src)
            put(f"Kind{nm}N", len(ck["methods"][k]), cnt(len(ck["methods"][k])), src)
        um = json.load(open(ICPC / "unmodelled" / "summary.json"))["lintq"]
        src = "results/icpc/unmodelled/summary.json"
        put("UnmodMethodProgs", um["method_not_modelled"]["programs"], cnt(um["method_not_modelled"]["programs"]), src)
        put("UnmodUnknownProgs", um["result_unknown"]["programs"], cnt(um["result_unknown"]["programs"]), src)
        put("UnmodDagProgs", um["to_dag"]["programs"], cnt(um["to_dag"]["programs"]), src)
        put("UnmodUnseenProgs", um["circuit_to_unseen_code"], cnt(um["circuit_to_unseen_code"]), src)
        top = dict(um["method_not_modelled"]["top"])
        for m, nm in (("reverse_bits", "ReverseBits"), ("save_unitary", "SaveUnitary"), ("from_qasm_str", "FromQasm"),
                      ("run", "Run"), ("diagonal", "Diagonal"), ("iso", "Iso")):
            put(f"Unmod{nm}", top.get(m, 0), cnt(top.get(m, 0)), src)
        qh = json.load(open(ICPC / "unmodelled" / "summary.json"))["qhe"]["method_not_modelled"]
        put("UnmodQhePrepare", dict(qh["top"]).get("prepare_state", 0), word(dict(qh["top"]).get("prepare_state", 0)), src)

    # ---- Paper B's motivating example: tool/tests/big/teleport_chain.py, slice of q[4] (tool.cli --json) ------------
    if HAS_TOOL and (ICPC / "b_example" / "teleport_chain_q4.json").exists():
        ex4 = json.load(open(ICPC / "b_example" / "teleport_chain_q4.json"))
        put("ExSliceOps", ex4["slices"][0]["operations"], cnt(ex4["slices"][0]["operations"]), "results/icpc/b_example/teleport_chain_q4.json")
        put("ExAllOps", ex4["operations"], cnt(ex4["operations"]), "results/icpc/b_example/teleport_chain_q4.json")

    # ---- Bugs4Q: the light cone's lines keep a faulty line (icpc/b_bugs4q.py) ---------------------------------
    fl = [r for r in rows(ICPC / "tool_acceptance" / "tool-v7" / "fault_lines.csv") if r["fault_lines"] != "0"]
    src = "results/icpc/tool_acceptance/tool-v7/fault_lines.csv"
    put("LinesLcContained", sum(r["contained"] == "1" for r in fl), cnt(sum(r["contained"] == "1" for r in fl)), src)
    put("LinesUnits", len(fl), cnt(len(fl)), src)

    # ---- write ----------------------------------------------------------------------------------------------
    TEX.parent.mkdir(parents=True, exist_ok=True)
    out = ["% Generated by experiments/icpc/make_numbers_b.py from committed results. Do not edit by hand.", ""]
    for k, v in NUMS.items():
        v["tex"] = v["tex"].replace("-", "\\ensuremath{-}") if v["tex"][:1] in "-[" else v["tex"]
        out.append(f"\\newcommand{{\\num{k}}}{{\\ensuremath{{{v['tex']}}}}}  % {v['source']}" if v["tex"].startswith("p ")
                   else f"\\newcommand{{\\num{k}}}{{{v['tex']}}}  % {v['source']}")
    TEX.write_text("\n".join(out) + "\n")
    (ICPC / "numbers_b.json").write_text(json.dumps(NUMS, indent=1))
    print(f"{len(NUMS)} numbers; wrote {TEX} and {ICPC / 'numbers_b.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
