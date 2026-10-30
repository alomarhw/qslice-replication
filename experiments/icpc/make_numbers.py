"""Every number the ICPC paper states, from committed result files only (PROTOCOL_ICPC.md §9).

Reads results/ and recomputes nothing about circuits. The only statistics computed here are the §6.4 T2
comparisons (exact McNemar on top-3 hits, paired bootstrap CI of the difference), because no committed file
holds them. The §9 confirmatory family is read from results/icpc/confirmatory/summary.json.
Writes:
  ../paper/numbers.tex       one \\newcommand per number, each commented with its source file
  results/icpc/numbers.json  the same values, raw and formatted, with the source of each
p-values below 1e-10 are written "10^{-10}" with a "<".
Usage (from experiments/): python icpc/make_numbers.py
"""

from __future__ import annotations

import csv
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tool import TOOL_NAME  # noqa: E402
from common.evaluate import BOOT_RESAMPLES, SEED, mcnemar_exact  # noqa: E402

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
    # ---- RQ1: dependence definitions on corpus A (784 pairs at |0...0>) -------------------------------
    src = "results/icpc/rq1/records.csv"
    rq1 = by_pair(ICPC / "rq1" / "records.csv")
    put("NPairs", len(rq1), cnt(len(rq1)), src)
    put("NCircuits", len({p for p, _ in rq1}), cnt(len({p for p, _ in rq1})), src)
    names = {"du": "Du", "lc": "Lc", "yz": "Yz", "q": "Q", "4e_unfixed": "FourEdgeUnfixed", "4e_fixed": "FourEdgeFixed"}
    for s, nm in names.items():
        rs = [v[s] for v in rq1.values() if s in v and v[s]["applicable"] == "1"]
        bad = sum(r["sound"] != "1" for r in rs)
        put(f"RqOne{nm}Unsound", bad, cnt(bad), src)
        put(f"RqOne{nm}UnsoundPct", bad / len(rs), pct(bad / len(rs)), src)
        put(f"RqOne{nm}Recall", st.mean(float(r["dep_recall"]) for r in rs), f"{st.mean(float(r['dep_recall']) for r in rs):.3f}", src)
        put(f"RqOne{nm}Precision", st.mean(float(r["dep_precision"]) for r in rs), f"{st.mean(float(r['dep_precision']) for r in rs):.3f}", src)
        put(f"RqOne{nm}Size", st.mean(float(r["size_fraction"]) for r in rs), pct(st.mean(float(r["size_fraction"]) for r in rs)), src)
    miss = Counter((m["slicer"], m["category"]) for m in rows(ICPC / "rq1" / "misses.csv"))
    for cat, nm in (("kickback", "Kickback"), ("same-wire", "SameWire"), ("written-operand", "WrittenOperand"), ("feedback", "Feedback")):
        put(f"RqOneDuMiss{nm}", miss[("du", cat)], cnt(miss[("du", cat)]), "results/icpc/rq1/misses.csv")
    pairs = rows(ICPC / "rq1" / "pairs.csv")
    for col, nm in (("q_removed", "Removed"), ("removed_non_influencing", "RemovedNonInfluencing"),
                    ("removed_influencing_contributing_some_input", "RemovedContributing")):
        v = sum(int(p[col]) for p in pairs)
        put(f"RqOneQ{nm}", v, cnt(v), "results/icpc/rq1/pairs.csv")
    v = sum(p["q_pruned"] == "1" for p in pairs)
    put("RqOneQPrunedPairs", v, cnt(v), "results/icpc/rq1/pairs.csv")

    # Qiskit LightCone, order-aligned mapping (Deviation I-9)
    src = "results/icpc/rq1_lcq_remap/records.csv"
    lq = {(r["path"], r["target"]): r for r in rows(ICPC / "rq1_lcq_remap" / "records.csv") if r["slicer"] == "lcq"}
    ap = [k for k, r in lq.items() if r["applicable"] == "1"]
    put("LcqApplicable", len(ap), cnt(len(ap)), src)
    put("LcqNotApplicable", len(lq) - len(ap), cnt(len(lq) - len(ap)), src)
    meas = sum("contains measurements" in r["note"] for r in lq.values())
    put("LcqNaMeasurements", meas, cnt(meas), src)
    put("LcqNaReorder", len(lq) - len(ap) - meas, cnt(len(lq) - len(ap) - meas), src)
    assert all("in-order subsequence" in r["note"] for r in lq.values() if r["applicable"] != "1" and "contains measurements" not in r["note"])
    put("LcqUnsound", sum(lq[k]["sound"] != "1" for k in ap), cnt(sum(lq[k]["sound"] != "1" for k in ap)), src)
    sz = lambda k, s: int(lq[k]["size"]) if s == "lcq" else int(rq1[k][s]["size"])  # noqa: E731
    smaller = sum(sz(k, "lcq") < sz(k, "lc") for k in ap)
    put("LcqSmallerThanLc", smaller, cnt(smaller), src)
    put("LcqRecall", st.mean(float(lq[k]["dep_recall"]) for k in ap), f"{st.mean(float(lq[k]['dep_recall']) for k in ap):.3f}", src)
    dyn_ap = [k for k in ap if lq[k]["dynamic"] == "1"]
    put("LcqDynamicN", len(dyn_ap), cnt(len(dyn_ap)), src)
    put("LcqDynamicUnsound", sum(lq[k]["sound"] != "1" for k in dyn_ap), cnt(sum(lq[k]["sound"] != "1" for k in dyn_ap)), src)
    nz = [k for k in ap if sz(k, "lcq") > 0]
    red = st.mean(1 - sz(k, "q") / sz(k, "lcq") for k in nz)
    put("QVsLcqReduction", red, pct(red), src)
    pooled = 1 - sum(sz(k, "q") for k in ap) / sum(sz(k, "lcq") for k in ap)
    put("QVsLcqReductionPooled", pooled, pct(pooled), src)
    put("QLargerThanLcq", sum(sz(k, "q") > sz(k, "lcq") for k in ap), cnt(sum(sz(k, "q") > sz(k, "lcq") for k in ap)), src)

    # ---- Confirmatory family H1-H5 (§9) ----------------------------------------------------------------
    src = "results/icpc/confirmatory/summary.json"
    c = json.load(open(ICPC / "confirmatory" / "summary.json"))
    put("HOnePHolm", c["holm"]["H1"]["p_holm"], pval(c["holm"]["H1"]["p_holm"]), src)
    put("HTwoDiff", c["H2"]["mean_difference"], f"{100 * c['H2']['mean_difference']:.1f}", src)
    put("HTwoCILow", c["H2"]["ci95_mean_difference"][0], f"{100 * c['H2']['ci95_mean_difference'][0]:.1f}", src)
    put("HTwoCIHigh", c["H2"]["ci95_mean_difference"][1], f"{100 * c['H2']['ci95_mean_difference'][1]:.1f}", src)
    put("HTwoRelative", c["H2"]["relative_reduction"], pct(c["H2"]["relative_reduction"]), src)
    put("HTwoSmaller", c["H2"]["q_strictly_smaller"], cnt(c["H2"]["q_strictly_smaller"]), src)
    put("HTwoPHolm", c["holm"]["H2"]["p_holm"], pval(c["holm"]["H2"]["p_holm"]), src)
    put("HTwoR", c["H2"]["rank_biserial"], f"{c['H2']['rank_biserial']:.2f}", src)
    put("HThreeRate", c["H3"]["rate"], pct(c["H3"]["rate"]), src)
    put("HThreeCILow", c["H3"]["wilson95"][0], pct(c["H3"]["wilson95"][0]), src)
    put("HThreeCIHigh", c["H3"]["wilson95"][1], pct(c["H3"]["wilson95"][1]), src)
    put("HThreePrunedRate", c["H3"]["pruned_pairs"]["rate"], pct(c["H3"]["pruned_pairs"]["rate"]), src)
    put("HThreePrunedRobust", c["H3"]["pruned_pairs"]["robust"], cnt(c["H3"]["pruned_pairs"]["robust"]), src)
    put("HThreePrunedN", c["H3"]["pruned_pairs"]["n"], cnt(c["H3"]["pruned_pairs"]["n"]), src)
    put("HFourContainQ", c["H4"]["containment_q"], pct(c["H4"]["containment_q"]), src)
    put("HFourContainLc", c["H4"]["containment_lc"], pct(c["H4"]["containment_lc"]), src)
    put("HFourDiff", c["H4"]["difference"], f"{100 * c['H4']['difference']:.1f}", src)
    assert c["H4"]["difference"] < 0, "H4 text says pruning lowers containment"
    put("HFourDiffAbs", -c["H4"]["difference"], f"{-100 * c['H4']['difference']:.1f}", src)
    put("HFourCILow", c["H4"]["ci95_difference"][0], f"{100 * c['H4']['ci95_difference'][0]:.1f}", src)
    put("HFourCIHigh", c["H4"]["ci95_difference"][1], f"{100 * c['H4']['ci95_difference'][1]:.1f}", src)
    put("HFiveSizeDiff", c["H5"]["mean_difference"], f"{c['H5']['mean_difference']:.1f}", src)
    put("HFiveExamDiff", c["H5"]["exam_slice_alongside"]["mean_difference"], f"{c['H5']['exam_slice_alongside']['mean_difference']:.3f}", src)
    put("HFiveExamQHigher", -c["H5"]["exam_slice_alongside"]["mean_difference"], f"{-c['H5']['exam_slice_alongside']['mean_difference']:.3f}", src)  # state-based minus wire
    # tests and Holm-corrected p of H3-H5, and the EXAM test reported alongside H5 (Paper A, review 2026-10-29)
    for h, nm in (("H3", "HThree"), ("H4", "HFour"), ("H5", "HFive")):
        put(f"{nm}PHolm", c["holm"][h]["p_holm"], pval(c["holm"][h]["p_holm"]), src)
    put("HFourOnlyLc", c["H4"]["b_only"], cnt(c["H4"]["b_only"]), src)
    put("HFourOnlyQ", c["H4"]["a_only"], cnt(c["H4"]["a_only"]), src)
    put("HFiveExamP", c["H5"]["exam_slice_alongside"]["p_value"], pval(c["H5"]["exam_slice_alongside"]["p_value"]), src)
    put("HFiveN", c["H5"]["n"], cnt(c["H5"]["n"]), src)

    # ---- RQ2: robustness under three input regimes -------------------------------------------------------
    src = "results/icpc/rq2_robustness/pairs.csv"
    rob = rows(ICPC / "rq2_robustness" / "pairs.csv")
    for reg, nm in (("R-basis", "Basis"), ("R-haar", "Haar"), ("R-param", "Param")):
        qp = [r for r in rob if r["slicer"] == "q" and r["regime"] == reg and r["pruned"] == "1"]
        put(f"RobQPruned{nm}", sum(r["robust"] == "1" for r in qp) / len(qp), pct(sum(r["robust"] == "1" for r in qp) / len(qp)), src)
        lc = [r for r in rob if r["slicer"] == "lc" and r["regime"] == reg]
        put(f"RobLc{nm}", sum(r["robust"] == "1" for r in lc) / len(lc), pct(sum(r["robust"] == "1" for r in lc) / len(lc)), src)
    src = "results/icpc/rq2_robustness_lcq/pairs.csv"
    rl = [r for r in rows(ICPC / "rq2_robustness_lcq" / "pairs.csv") if r["slicer"] == "lcq" and r["applicable"] == "1"]
    for reg, nm in (("R-basis", "Basis"), ("R-haar", "Haar"), ("R-param", "Param")):
        x = [r for r in rl if r["regime"] == reg]
        put(f"RobLcq{nm}Robust", sum(r["robust"] == "1" for r in x), cnt(sum(r["robust"] == "1" for r in x)), src)
        put(f"RobLcq{nm}N", len(x), cnt(len(x)), src)

    # ---- Four-edge ablation before / after the seeding fix -----------------------------------------------
    for tag, path in (("Unfixed", RES / "rq4_ablation" / "TAB_ablation_rerun.csv"), ("Fixed", ICPC / "ablation_fixed" / "TAB_ablation_rerun.csv")):
        t = {r["variant"]: r for r in rows(path) if r["scope"] == "A+B" and r["unit"] == "pair"}
        for v, nm in (("QSlice-full", "Full"), ("QDG-no-ED", "NoED"), ("QDG-no-MD", "NoMD"), ("QDG-no-UED", "NoUED"), ("QDG-no-CD", "NoCD")):
            put(f"Abl{tag}{nm}", float(t[v]["svr"]), pct(float(t[v]["svr"])), str(path.relative_to(HERE)))
    put("AblPairs", int(t["QSlice-full"]["n"]), cnt(int(t["QSlice-full"]["n"])), "results/icpc/ablation_fixed/TAB_ablation_rerun.csv")

    # ---- Structure families, catalogue -------------------------------------------------------------------
    src = "results/icpc/families/rows.csv"
    fam = [r for r in rows(ICPC / "families" / "rows.csv") if r["applicable"] == "1"]
    put("FamCircuits", len({(r["family"], r["circuit"]) for r in fam}), cnt(len({(r["family"], r["circuit"]) for r in fam})), src)
    for s, nm in (("lc", "Lc"), ("yz", "Yz"), ("q", "Q"), ("du", "Du")):
        x = [r for r in fam if r["slicer"] == s]
        put(f"Fam{nm}Unsound", sum(r["sound"] != "1" for r in x), cnt(sum(r["sound"] != "1" for r in x)), src)
    xq = [r for r in fam if r["slicer"] == "q"]
    put("FamQSoundNotMinimal", sum(r["sound_not_minimal"] == "1" for r in xq), cnt(sum(r["sound_not_minimal"] == "1" for r in xq)), src)
    put("FamQRows", len(xq), cnt(len(xq)), src)
    cat = json.load(open(ICPC / "catalogue" / "catalogue.json"))
    put("CatEntries", len(cat["rows"]), cnt(len(cat["rows"])), "results/icpc/catalogue/catalogue.json")

    # ---- RQ3: seeded faults ------------------------------------------------------------------------------
    src = "results/icpc/rq3/records.csv"
    rec = [r for r in rows(ICPC / "rq3" / "records.csv") if r["analysis"] == "primary"]
    units = {(r["path"], r["mutant"], r["target"]) for r in rec}
    put("RqThreeUnits", len(units), cnt(len(units)), src)
    for s, nm in (("du", "Du"), ("lc", "Lc"), ("yz", "Yz"), ("q", "Q"), ("random", "Random")):
        x = [float(r["contained"]) for r in rec if r["slicer"] == s]
        put(f"RqThreeContain{nm}", sum(x) / len(x), pct(sum(x) / len(x)), src)
    byu = {}
    for r in rec:
        byu.setdefault((r["mutant"], r["target"]), {})[r["slicer"]] = r["contained"]
    lmiss = [u for u, v in byu.items() if v["lc"] != "1"]
    put("LcMissYzContained", sum(byu[u]["yz"] == "1" for u in lmiss), cnt(sum(byu[u]["yz"] == "1" for u in lmiss)), src)
    u = [r for r in rows(ICPC / "rq3" / "units.csv") if r["analysis"] == "primary"]
    put("CQFour", sum(r["cq4"] == "1" for r in u), cnt(sum(r["cq4"] == "1" for r in u)), "results/icpc/rq3/units.csv")
    put("CQFourRecovered", sum(r["cq4_remedy_contains"] == "1" for r in u), cnt(sum(r["cq4_remedy_contains"] == "1" for r in u)), "results/icpc/rq3/units.csv")

    # ---- RQ3: Bugs4Q, source map -------------------------------------------------------------------------
    b = Counter(r["outcome"] for r in rows(ICPC / "rq3_bugs4q" / "bugs.csv"))
    for o, nm in (("killed", "Killed"), ("injured", "Injured"), ("alive", "Alive"), ("excluded", "Excluded")):
        put(f"BugsFourQ{nm}", b[o], word(b[o]), "results/icpc/rq3_bugs4q/bugs.csv")
    tri = rows(HERE / "bugs4q" / "triage.csv")
    put("BugsFourQTriaged", len(tri), cnt(len(tri)), "bugs4q/triage.csv")
    put("BugsFourQIncluded", sum(r["included"] == "1" for r in tri), cnt(sum(r["included"] == "1" for r in tri)), "bugs4q/triage.csv")
    src = "results/icpc/source_map/"
    bm = rows(ICPC / "source_map" / "bugs.csv")
    ni, nu = sum(int(r["n_instructions"]) for r in bm), sum(int(r["n_unmapped"]) for r in bm)
    put("MapInstructions", ni, cnt(ni), src + "bugs.csv")
    put("MapMapped", ni - nu, cnt(ni - nu), src + "bugs.csv")
    xc = [r for r in rows(ICPC / "source_map" / "crosscheck.csv") if r.get("compared") not in (None, "", "0")]
    put("MapCrossCompared", sum(int(r["compared"]) for r in xc), cnt(sum(int(r["compared"]) for r in xc)), src + "crosscheck.csv")
    put("MapCrossAgree", sum(int(r["agree"]) for r in xc), cnt(sum(int(r["agree"]) for r in xc)), src + "crosscheck.csv")
    put("MapCrossPrograms", len(xc), cnt(len(xc)), src + "crosscheck.csv")
    um = [r for r in rows(ICPC / "source_map" / "units.csv") if r["analysis"] == "primary" and r["n_fault_lines"] != "0"]
    for s, nm in (("full", "Full"), ("lc", "Lc"), ("q", "Q"), ("du", "Du")):
        x = [r for r in um if r["slicer"] == s]
        put(f"Lines{nm}Contained", sum(r["contained_lines"] == "1" for r in x), cnt(sum(r["contained_lines"] == "1" for r in x)), src + "units.csv")
        put(f"Lines{nm}Mean", st.mean(int(r["slice_lines"]) for r in x), f"{st.mean(int(r['slice_lines']) for r in x):.1f}", src + "units.csv")
    put("LinesUnits", len([r for r in um if r["slicer"] == "full"]), cnt(len([r for r in um if r["slicer"] == "full"])), src + "units.csv")
    ua = [r for r in rows(ICPC / "source_map" / "units.csv") if r["analysis"] == "primary" and r["slicer"] == "full"]
    put("BugsFourQUnits", len(ua), cnt(len(ua)), src + "units.csv")  # all primary units; LinesUnits keeps those whose faulty lines map
    put("LinesDuMissed", NUMS["LinesUnits"]["value"] - NUMS["LinesDuContained"]["value"],
        ["no", "one", "two", "three"][NUMS["LinesUnits"]["value"] - NUMS["LinesDuContained"]["value"]], src + "units.csv")

    # ---- RQ3: MBFL ---------------------------------------------------------------------------------------
    src = "results/icpc/mbfl/units.csv"
    mb = [r for r in rows(ICPC / "mbfl" / "units.csv") if not r.get("excluded")]
    put("MbflUnits", len(mb), cnt(len(mb)), src)
    put("MbflNLc", sum(bool(r["exam_lc_avg"]) for r in mb), cnt(sum(bool(r["exam_lc_avg"]) for r in mb)), src)
    put("MbflNQ", sum(bool(r["exam_q_avg"]) for r in mb), cnt(sum(bool(r["exam_q_avg"]) for r in mb)), src)
    for s, nm in (("all", "All"), ("q", "Q"), ("lc", "Lc")):
        x = [float(r[f"exam_{s}_avg"]) for r in mb if r.get(f"exam_{s}_avg")]
        put(f"MbflExam{nm}", st.mean(x), f"{st.mean(x):.3f}", src)
    pb = [r for r in mb if r["fault_in_lc"] == "1" and r["fault_in_q"] == "1"]
    put("MbflPairedN", len(pb), cnt(len(pb)), src)
    for s, nm in (("all", "All"), ("q", "Q"), ("lc", "Lc")):
        x = st.mean(float(r[f"exam_{s}_avg"]) for r in pb)
        put(f"MbflPaired{nm}", x, f"{x:.3f}", src)

    # ---- RQ3: LLM fault localization (T2, §6.4): context prompt, temperature 0, run 0 --------------------
    src = "results/llm/t2_scores.csv"
    t2 = [r for r in rows(RES / "llm" / "t2_scores.csv") if r["split"] == "score" and r["context"] == "context" and r["run"] == "0"]
    hit = defaultdict(dict)
    for r in t2:
        hit[(r["arm"], r["input"])][r["item"]] = int(r["top3"])
    arms = {"claude-sonnet-5-5": "Sonnet", "claude-haiku-5-5": "Haiku", "O-mid": "QwenMid", "O-small": "QwenSmall"}
    rng = np.random.default_rng(SEED)
    for arm, nm in arms.items():
        for inp, inm in (("full", "Full"), ("lc", "Lc"), ("q", "Q"), ("du", "Du")):
            h = hit[(arm, inp)]
            put(f"TTwo{nm}{inm}", sum(h.values()) / len(h), pct(sum(h.values()) / len(h)), src)
        for ref, rnm in (("full", "Full"), ("lc", "Lc")):
            items = sorted(set(hit[(arm, "q")]) & set(hit[(arm, ref)]))
            a = np.array([hit[(arm, "q")][i] for i in items])
            b_ = np.array([hit[(arm, ref)][i] for i in items])
            mc = mcnemar_exact(list(a == 1), list(b_ == 1))
            d = a - b_
            boots = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(BOOT_RESAMPLES)])
            put(f"TTwo{nm}QVs{rnm}Diff", float(d.mean()), f"{100 * d.mean():.1f}", src)
            put(f"TTwo{nm}QVs{rnm}CI", [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
                f"[{100 * np.percentile(boots, 2.5):.1f}, {100 * np.percentile(boots, 97.5):.1f}]", src)
            put(f"TTwo{nm}QVs{rnm}P", mc["p_value"], pval(mc["p_value"]), src)
    put("TTwoItems", len(hit[("claude-sonnet-5-5", "full")]), cnt(len(hit[("claude-sonnet-5-5", "full")])), src)
    drops = [-NUMS[f"TTwo{nm}QVsFullDiff"]["value"] for nm in ("Sonnet", "Haiku", "QwenMid")]
    put("TTwoMaxDrop", max(drops), f"{100 * max(drops):.1f}", src)

    # ---- RQ3: LLM T1 (§6.3): which operations affect a qubit, temperature 0, run 0 ------------------------
    src = "results/llm/t1_scores.csv"
    t1 = [r for r in rows(RES / "llm" / "t1_scores.csv") if r["split"] == "score" and r["run"] == "0" and r["consistency"] == "0"]
    for arm, nm in arms.items():
        x = [r for r in t1 if r["arm"] == arm]
        for k, knm in (("recall", "Recall"), ("precision", "Prec"), ("recall_kickback", "Kick")):
            v = [float(r[k]) for r in x if r[k] != ""]
            put(f"TOne{nm}{knm}", st.mean(v), f"{st.mean(v):.2f}", src)
    put("TOneItems", len([r for r in t1 if r["arm"] == "claude-sonnet-5-5"]), cnt(len([r for r in t1 if r["arm"] == "claude-sonnet-5-5"])), src)

    # ---- RQ4: cost ---------------------------------------------------------------------------------------
    src = "results/icpc/cost/circuits.csv"
    co = rows(ICPC / "cost" / "circuits.csv")
    dep = [r for r in co if r["kind"] == "F-depth"]
    put("CostLcMaxMs", max(float(r["lc_total"]) for r in co if r.get("lc_total")), f"{1000 * max(float(r['lc_total']) for r in co if r.get('lc_total')):.0f}", src)
    for d, nm in (("d10", "Ten"), ("d20", "Twenty"), ("d40", "Forty")):
        x = [float(r["q_total"]) for r in dep if r["name"].startswith(d + "_") and r.get("q_total")]
        put(f"CostQDepth{nm}", st.median(x), f"{st.median(x):.1f}", src)
        y = [float(r["build_seconds"]) for r in dep if r["name"].startswith(d + "_")]
        put(f"CostBuildDepth{nm}", st.median(y), f"{st.median(y):.2f}", src)
    for d, nm in (("d80", "Eighty"), ("d160", "OneSixty")):
        x = [r for r in dep if r["name"].startswith(d + "_")]
        put(f"CostDepth{nm}OverLimit", sum(r["limit"] == "wall" for r in x), word(sum(r["limit"] == "wall" for r in x)), src)
        put(f"CostBuildDepth{nm}", st.median(float(r["build_seconds"]) for r in x), f"{st.median(float(r['build_seconds']) for r in x):.1f}", src)
    for d, nm in (("d40", "Forty"), ("d160", "OneSixty")):
        md = st.median(int(r["depth"]) for r in dep if r["name"].startswith(d + "_"))
        put(f"CostMeasuredDepth{nm}", md, f"{md:.0f}", src)
    put("CostWallLimit", 120, "120", "icpc/cost_run.py")
    seeds = {r["name"].split("_s")[1] for r in dep}
    assert all(len([r for r in dep if r["name"].startswith(d + "_")]) == len(seeds) for d in {r["name"].split("_")[0] for r in dep})
    put("CostDepthCircuits", len(seeds), word(len(seeds)), src)
    put("CostDepthWidth", int(dep[0]["n_qubits"]), dep[0]["n_qubits"], src)
    assert {r["n_qubits"] for r in dep} == {dep[0]["n_qubits"]}
    wid = [r for r in co if r["kind"].startswith("width-") and r.get("q_total")]
    w = [float(r["q_total"]) for r in wid]
    put("CostWidthQMax", max(w), f"{max(w):.1f}", src)
    wmax = max(int(r["n_qubits"]) for r in wid)
    assert int(max(wid, key=lambda r: float(r["q_total"]))["n_qubits"]) == wmax, "the slowest width run is not the widest"
    put("CostWidthMaxQubits", wmax, str(wmax), src)
    cl = rows(ICPC / "corpus_l" / "circuits.csv")
    put("CorpusLCircuits", len(cl), cnt(len(cl)), "results/icpc/corpus_l/circuits.csv")
    put("CorpusLMinQubits", min(int(r["n_qubits"]) for r in cl), str(min(int(r["n_qubits"]) for r in cl)), "results/icpc/corpus_l/circuits.csv")
    put("CorpusLMaxQubits", max(int(r["n_qubits"]) for r in cl), str(max(int(r["n_qubits"]) for r in cl)), "results/icpc/corpus_l/circuits.csv")
    put("CorpusLCompleted", sum(r["completed"] == "1" for r in cl), cnt(sum(r["completed"] == "1" for r in cl)), "results/icpc/corpus_l/circuits.csv")

    # ---- RQ2: noise --------------------------------------------------------------------------------------
    src = "results/icpc/noise/pairs.csv"
    nz_ = rows(ICPC / "noise" / "pairs.csv")
    put("NoiseMaxQubits", max(int(r["n_qubits"]) for r in nz_), word(max(int(r["n_qubits"]) for r in nz_)), src)
    for s, nm in (("lc", "Lc"), ("q", "Q")):
        ex_ = [float(r["D_cross"]) for r in nz_ if r["slicer"] == s and r["shots_full"] == "1"]
        dy = [float(r["D_cross"]) for r in nz_ if r["slicer"] == s and r["shots_full"] != "1"]
        put(f"Noise{nm}CrossExactMax", max(ex_), sci(max(ex_)) if max(ex_) < 0.01 else f"{max(ex_):.2f}", src)
        put(f"Noise{nm}CrossExactNonzero", sum(x > 1e-9 for x in ex_), cnt(sum(x > 1e-9 for x in ex_)), src)
        put(f"Noise{nm}CrossExactN", len(ex_), cnt(len(ex_)), src)
        put(f"Noise{nm}CrossShotMax", max(dy), f"{max(dy):.3f}", src)
    put("NoiseShots", 1024, cnt(1024), "icpc/noise_run.py")

    # ---- classical PDG baseline (Deviation I-12) -------------------------------------------------------------
    src = "results/icpc/cpdg/rq1_records.csv"
    cp = rows(ICPC / "cpdg" / "rq1_records.csv")
    bad = sum(r["sound"] != "1" for r in cp)
    put("CpdgUnsound", bad, cnt(bad), src)
    put("CpdgUnsoundPct", bad / len(cp), pct(bad / len(cp)), src)
    put("CpdgRecall", st.mean(float(r["dep_recall"]) for r in cp), f"{st.mean(float(r['dep_recall']) for r in cp):.3f}", src)
    put("CpdgSize", st.mean(float(r["size_fraction"]) for r in cp), pct(st.mean(float(r["size_fraction"]) for r in cp)), src)
    dyn = [r for r in cp if r["dynamic"] == "1"]
    put("CpdgDynamicUnsound", sum(r["sound"] != "1" for r in dyn), cnt(sum(r["sound"] != "1" for r in dyn)), src)
    put("NDynamicPairs", len(dyn), cnt(len(dyn)), src)
    put("CpdgUnitaryUnsound", bad - sum(r["sound"] != "1" for r in dyn), cnt(bad - sum(r["sound"] != "1" for r in dyn)), src)
    ddyn = [v["du"] for v in rq1.values() if v["du"]["dynamic"] == "1"]
    put("DuDynamicUnsound", sum(r["sound"] != "1" for r in ddyn), cnt(sum(r["sound"] != "1" for r in ddyn)), "results/icpc/rq1/records.csv")
    cm = Counter(m["category"] for m in rows(ICPC / "cpdg" / "rq1_misses.csv"))
    put("CpdgMissKickback", cm["kickback"], cnt(cm["kickback"]), "results/icpc/cpdg/rq1_misses.csv")
    put("CpdgMissFeedback", cm["feedback"], cnt(cm["feedback"]), "results/icpc/cpdg/rq1_misses.csv")
    put("CpdgMissSameWire", cm["same-wire"], cnt(cm["same-wire"]), "results/icpc/cpdg/rq1_misses.csv")
    put("CpdgMissWritten", cm["written-operand"], cnt(cm["written-operand"]), "results/icpc/cpdg/rq1_misses.csv")
    put("CpdgMissTotal", sum(cm.values()), cnt(sum(cm.values())), "results/icpc/cpdg/rq1_misses.csv")
    c3 = [r for r in rows(ICPC / "cpdg" / "rq3_records.csv") if r["analysis"] == "primary"]
    put("RqThreeContainCpdg", sum(int(r["contained"]) for r in c3) / len(c3), pct(sum(int(r["contained"]) for r in c3) / len(c3)), "results/icpc/cpdg/rq3_records.csv")
    fc = rows(ICPC / "cpdg" / "families_rows.csv")
    put("FamCpdgUnsound", sum(r["sound"] != "1" for r in fc), cnt(sum(r["sound"] != "1" for r in fc)), "results/icpc/cpdg/families_rows.csv")

    # ---- study design counts ----------------------------------------------------------------------------------
    lcr = [v["lc"] for v in rq1.values()]
    for corp, nm in (("MQT Bench", "Mqt"), ("QASMBench", "Qasm"), ("VeriQBench", "Veriq")):
        put(f"Pairs{nm}", sum(r["corpus"] == corp for r in lcr), cnt(sum(r["corpus"] == corp for r in lcr)), "results/icpc/rq1/records.csv")
        put(f"Circuits{nm}", len({r["path"] for r in lcr if r["corpus"] == corp}), cnt(len({r["path"] for r in lcr if r["corpus"] == corp})), "results/icpc/rq1/records.csv")
    put("MaxQubits", max(int(r["n_qubits"]) for r in lcr), cnt(max(int(r["n_qubits"]) for r in lcr)), "results/icpc/rq1/records.csv")
    mut = rows(ICPC / "rq3" / "mutants.csv")
    put("Mutants", len(mut), cnt(len(mut)), "results/icpc/rq3/mutants.csv")
    for o, nm in (("killed", "Killed"), ("injured", "Injured"), ("alive", "Alive"), ("equivalent", "Equivalent")):
        put(f"Mutants{nm}", sum(m["outcome"] == o for m in mut), cnt(sum(m["outcome"] == o for m in mut)), "results/icpc/rq3/mutants.csv")
    put("MutantsExcluded", sum(m["outcome"] == "excluded" for m in mut), cnt(sum(m["outcome"] == "excluded" for m in mut)), "results/icpc/rq3/mutants.csv")
    ops_ = {m["operator"] for m in mut}
    put("MutOperators", len(ops_), word(len(ops_)), "results/icpc/rq3/mutants.csv")
    assert "M-par" in ops_  # the angle perturbation is the study's own operator; the others are published
    put("MutPublished", len(ops_ - {"M-par"}), word(len(ops_ - {"M-par"})), "results/icpc/rq3/mutants.csv")
    put("RqThreeSecondary", sum(r["analysis"] == "secondary" for r in rows(ICPC / "rq3" / "units.csv")), cnt(sum(r["analysis"] == "secondary" for r in rows(ICPC / "rq3" / "units.csv"))), "results/icpc/rq3/units.csv")
    put("OracleErr", 2.2e-16, sci(2.2e-16), "experiments/logs/icpc/test_oracle_icpc.log (joint rho_W vs Statevector/partial_trace, random unitary circuits)")
    put("InfluenceInputs", 11, "11", "icpc/influence.py (|0...0> + N_INPUTS=10)")
    put("InfluencePerturbations", 2, "two", "icpc/influence.py (N_PERTURBATIONS)")
    put("RobDraws", 100, "100", "icpc/rq2_robustness.py (N_DRAWS)")
    put("CostMemLimit", 4, "4", "icpc/cost_run.py (RSS_GIB)")
    put("LcqPrecision", st.mean(float(lq[k]["dep_precision"]) for k in ap), f"{st.mean(float(lq[k]['dep_precision']) for k in ap):.3f}", "results/icpc/rq1_lcq_remap/records.csv")
    put("LcqSize", st.mean(float(lq[k]["size_fraction"]) for k in ap), pct(st.mean(float(lq[k]["size_fraction"]) for k in ap)), "results/icpc/rq1_lcq_remap/records.csv")
    put("CpdgPrecision", st.mean(float(r["dep_precision"]) for r in cp), f"{st.mean(float(r['dep_precision']) for r in cp):.3f}", "results/icpc/cpdg/rq1_records.csv")
    for s_, nm in (("lc", "Lc"), ("yz", "Yz"), ("q", "Q"), ("du", "Du")):
        x = [float(r["size_fraction"]) for r in rec if r["slicer"] == s_]
        put(f"RqThreeSize{nm}", st.mean(x), pct(st.mean(x)), "results/icpc/rq3/records.csv")
    put("RqThreeSizeCpdg", st.mean(float(r["size_fraction"]) for r in c3), pct(st.mean(float(r["size_fraction"]) for r in c3)), "results/icpc/cpdg/rq3_records.csv")

    # wire-rule misses by mutation operator (omission faults)
    uu = {(r["path"], r["mutant"], r["target"]): r["operator"] for r in rows(ICPC / "rq3" / "units.csv") if r["analysis"] == "primary"}
    lm = Counter(uu[(r["path"], r["mutant"], r["target"])] for r in rec if r["slicer"] == "lc" and r["contained"] == "0")
    put("LcMissTotal", sum(lm.values()), cnt(sum(lm.values())), "results/icpc/rq3/records.csv + units.csv")
    for op, nm in (("M-crm", "Crm"), ("M-qsw", "Qsw"), ("M-ent", "Ent"), ("M-del", "Del")):
        put(f"LcMiss{nm}", lm[op], cnt(lm[op]), "results/icpc/rq3/records.csv + units.csv")
    put("LcMissOtherOps", sum(v for k, v in lm.items() if k not in ("M-crm", "M-qsw", "M-ent", "M-del")), "0" if not sum(v for k, v in lm.items() if k not in ("M-crm", "M-qsw", "M-ent", "M-del")) else "NONZERO", "results/icpc/rq3/records.csv + units.csv")

    # magnitudes for prose ("loses 13.5 points"), and table cells that must not be typed by hand
    put("HFourLoss", -c["H4"]["difference"], f"{-100 * c['H4']['difference']:.1f}", "results/icpc/confirmatory/summary.json")
    put("TTwoSonnetQVsLcLoss", -NUMS["TTwoSonnetQVsLcDiff"]["value"], f"{-100 * NUMS['TTwoSonnetQVsLcDiff']['value']:.1f}", "results/llm/t2_scores.csv")
    put("RobLcqParamFail", NUMS["RobLcqParamN"]["value"] - NUMS["RobLcqParamRobust"]["value"],
        cnt(NUMS["RobLcqParamN"]["value"] - NUMS["RobLcqParamRobust"]["value"]), "results/icpc/rq2_robustness_lcq/pairs.csv")
    for s_, nm in (("yz", "Yz"), ("lc", "Lc"), ("q", "Q")):
        x = [v[s_] for v in rq1.values() if v[s_]["dynamic"] == "1"]
        put(f"{nm}DynamicUnsound", sum(r["sound"] != "1" for r in x), cnt(sum(r["sound"] != "1" for r in x)), "results/icpc/rq1/records.csv")

    # ---- slice size against the dependence floor (Deviation I-13, descriptive, after the results) ----------
    src = "results/icpc/rq1/records.csv"
    lcr = {k: v["lc"] for k, v in rq1.items()}
    dep = {k: int(r["n_influencing"]) / int(r["n_ops"]) for k, r in lcr.items()}
    put("DepFloor", st.mean(dep.values()), pct(st.mean(dep.values())), src)
    put("DepFloorMedian", st.median(dep.values()), pct(st.median(dep.values())), src)
    exc = {k: (int(r["size"]) - int(r["n_influencing"])) / int(r["n_ops"]) for k, r in lcr.items()}
    assert min(exc.values()) >= 0, "wire slice smaller than the dependence set: contradicts Proposition 1"
    put("LcExcess", st.mean(exc.values()), f"{round(100 * NUMS['RqOneLcSize']['value'], 1) - round(100 * st.mean(dep.values()), 1):.1f}", src)
    exact = sum(e == 0 for e in exc.values())
    put("LcExact", exact, cnt(exact), src)
    put("LcExcessPairs", len(exc) - exact, cnt(len(exc) - exact), src)
    assert exact + (len(exc) - exact) == NUMS["NPairs"]["value"]
    yex = st.mean((int(v["yz"]["size"]) - int(v["yz"]["n_influencing"])) / int(v["yz"]["n_ops"]) for v in rq1.values())
    put("YzExcess", yex, f"{round(100 * NUMS['RqOneYzSize']['value'], 1) - round(100 * st.mean(dep.values()), 1):.1f}", src)
    alld = sum(int(r["n_influencing"]) == int(r["n_ops"]) for r in lcr.values())
    put("PairsAllDep", alld, cnt(alld), src)
    assert NUMS["DepFloor"]["value"] <= NUMS["RqOneLcSize"]["value"]
    for lo, hi, nm in ((2, 3, "WTwo"), (4, 6, "WFour"), (7, 10, "WSeven"), (11, 14, "WEleven")):
        put(f"{nm}Lo", lo, str(lo), src)
        put(f"{nm}Hi", hi, str(hi), src)
        ks = [k for k, r in lcr.items() if lo <= int(r["n_qubits"]) <= hi]
        put(f"{nm}Pairs", len(ks), cnt(len(ks)), src)
        put(f"{nm}Floor", st.mean(dep[k] for k in ks), pct(st.mean(dep[k] for k in ks)), src)
        for s_, sn in (("lc", "Lc"), ("yz", "Yz")):
            x = st.mean(float(rq1[k][s_]["size_fraction"]) for k in ks)
            put(f"{nm}{sn}", x, pct(x), src)
        kq = [k for k in ks if k in lq and lq[k]["applicable"] == "1"]
        x = st.mean(float(lq[k]["size_fraction"]) for k in kq)
        put(f"{nm}Lcq", x, pct(x), "results/icpc/rq1_lcq_remap/records.csv")
    src = "results/icpc/corpus_l/slices.csv"
    nops = {r["path"]: int(r["n_ops"]) for r in rows(ICPC / "corpus_l" / "circuits.csv")}
    empty = {p for p, n in nops.items() if n == 0}  # loaded with no operations: no size to report
    put("CorpusLEmpty", len(empty), cnt(len(empty)), "results/icpc/corpus_l/circuits.csv")
    cls = [r for r in rows(ICPC / "corpus_l" / "slices.csv") if r["path"] not in empty]
    for s_, sn in (("lc", "Lc"), ("lcq", "Lcq"), ("yz", "Yz"), ("q", "Q")):
        x = [int(r["size"]) / nops[r["path"]] for r in cls if r["slicer"] == s_ and r["applicable"] == "1"]
        put(f"CorpusLSize{sn}", st.mean(x), pct(st.mean(x)), src)
        put(f"CorpusLSize{sn}N", len(x), cnt(len(x)), src)

    stg = [json.loads(l) for l in open(ICPC / "cost" / "stages.jsonl")]
    lcs = [r["lc_seconds"] for r in stg if r.get("kind") == "F-depth" and str(r.get("stage", "")).startswith("q:")]
    put("CostLcMaxCritMs", max(lcs) * 1000, f"{max(lcs) * 1000:.0f}", "results/icpc/cost/stages.jsonl")
    # symbolic-angle commutation (Deviation I-14, B1; exploratory)
    src = "results/icpc/rq1_lcq_symbolic/records.csv"
    ls_ = [r for r in rows(ICPC / "rq1_lcq_symbolic" / "records.csv") if r["slicer"] == "lcqs" and r["applicable"] == "1"]
    put("LcqsSize", st.mean(float(r["size_fraction"]) for r in ls_), pct(st.mean(float(r["size_fraction"]) for r in ls_)), src)
    put("LcqsUnsound", sum(r["sound"] != "1" for r in ls_), cnt(sum(r["sound"] != "1" for r in ls_)), src)
    put("LcqsN", len(ls_), cnt(len(ls_)), src)
    put("LcqsDynamicUnsound", sum(r["sound"] != "1" for r in ls_ if r["dynamic"] == "1"),
        cnt(sum(r["sound"] != "1" for r in ls_ if r["dynamic"] == "1")), src)
    put("LcqsRecall", st.mean(float(r["dep_recall"]) for r in ls_), f"{st.mean(float(r['dep_recall']) for r in ls_):.3f}", src)
    put("LcqsPrecision", st.mean(float(r["dep_precision"]) for r in ls_), f"{st.mean(float(r['dep_precision']) for r in ls_):.3f}", src)
    for reg, nm in (("R-param", "Param"), ("R-basis", "Basis"), ("R-haar", "Haar")):
        rb = [r for r in rows(ICPC / "rq1_lcq_symbolic" / "robustness.csv") if r["slicer"] == "lcqs" and r["regime"] == reg]
        put(f"Lcqs{nm}Robust", sum(r["robust"] == "1" for r in rb), cnt(sum(r["robust"] == "1" for r in rb)), "results/icpc/rq1_lcq_symbolic/robustness.csv")
        put(f"Lcqs{nm}N", len(rb), cnt(len(rb)), "results/icpc/rq1_lcq_symbolic/robustness.csv")
    # flow-sensitive QPDG reading (Deviation I-16; exploratory)
    src = "results/icpc/yz_flow/records.csv"
    yf = rows(ICPC / "yz_flow" / "records.csv")
    rq1_yz = {(r["path"], r["target"]): r["size"] for r in rows(ICPC / "rq1" / "records.csv") if r["slicer"] == "yz"}
    assert all(rq1_yz[(r["path"], r["target"])] == r["size"] for r in yf if r["slicer"] == "yz"), "S-yz rerun differs from RQ1"
    yzf = [r for r in yf if r["slicer"] == "yzf"]
    assert all(r["contains_lc"] == "1" and r["within_yz"] == "1" for r in yzf)
    put("YzfN", len(yzf), cnt(len(yzf)), src)
    put("YzfSize", st.mean(float(r["size_fraction"]) for r in yzf), pct(st.mean(float(r["size_fraction"]) for r in yzf)), src)
    put("YzfUnsound", sum(r["sound"] != "1" for r in yzf), cnt(sum(r["sound"] != "1" for r in yzf)), src)
    put("YzfDynamicUnsound", sum(r["sound"] != "1" for r in yzf if r["dynamic"] == "1"),
        cnt(sum(r["sound"] != "1" for r in yzf if r["dynamic"] == "1")), src)
    put("YzfRecall", st.mean(float(r["dep_recall"]) for r in yzf), f"{st.mean(float(r['dep_recall']) for r in yzf):.3f}", src)
    put("YzfPrecision", st.mean(float(r["dep_precision"]) for r in yzf), f"{st.mean(float(r['dep_precision']) for r in yzf):.3f}", src)
    yfx = round(100 * NUMS['YzfSize']['value'], 1) - round(100 * NUMS['DepFloor']['value'], 1)
    put("YzfExcess", yfx, f"{yfx:.1f}", src)
    fam = [r for r in rows(ICPC / "yz_flow" / "families.csv") if r["slicer"] == "yzf"]
    put("YzfFamUnsound", sum(r["sound"] != "1" for r in fam), cnt(sum(r["sound"] != "1" for r in fam)), "results/icpc/yz_flow/families.csv")

    # ---- foundations measures (Deviation I-17, exploratory): four-edge graph, undirected slices, forward slices --
    fd = json.load(open(ICPC / "foundations" / "summary.json"))
    src = "results/icpc/foundations/summary.json"
    idle = sum(r["slicer"] == "lc" and r["size"] == "0" for r in rows(ICPC / "rq1" / "records.csv"))
    assert fd["lc"]["n"] + idle == NUMS["NPairs"]["value"] and fd["excluded"] == 0, "foundations pairs differ from RQ1"
    put("FdPairs", fd["lc"]["n"], cnt(fd["lc"]["n"]), src)
    put("FdIdleQubits", idle, cnt(idle), "results/icpc/rq1/records.csv")
    assert fd["lc"]["equal_to_lc"] == fd["lc"]["n"] and fd["lc_all"]["equal_to_lc"] == fd["lc"]["n"]
    assert fd["cpdg"]["unsound"] == NUMS["CpdgUnsound"]["value"], "classical PDG reading differs from RQ1"
    put("FdFourEdgeNoClosureEqual", fd["4e_nocl"]["equal_to_lc"], cnt(fd["4e_nocl"]["equal_to_lc"]), src)
    put("FdFourEdgeSize", fd["4e"]["size"], pct(fd["4e"]["size"]), src)
    put("FdFourEdgeEqual", fd["4e"]["equal_to_lc"], cnt(fd["4e"]["equal_to_lc"]), src)
    put("FdFourEdgePrecision", fd["4e"]["precision"], f"{fd['4e']['precision']:.3f}", src)
    assert fd["und_qdg"] == fd["und_4e"]
    put("FdUndSize", fd["und_qdg"]["size"], pct(fd["und_qdg"]["size"]), src)
    put("FdUndPrecision", fd["und_qdg"]["precision"], f"{fd['und_qdg']['precision']:.3f}", src)
    put("FdUndEqual", fd["und_qdg"]["equal_to_lc"], cnt(fd["und_qdg"]["equal_to_lc"]), src)
    put("FdLcPrecision", fd["lc"]["precision"], f"{fd['lc']['precision']:.3f}", src)
    for k, nm in (("cpdg", "Cpdg"), ("du", "Du")):
        put(f"Fd{nm}Unsound", fd[k]["unsound"], cnt(fd[k]["unsound"]), src)
        put(f"Fd{nm}ZMatch", fd[k]["unsound_but_z_matches"], cnt(fd[k]["unsound_but_z_matches"]), src)
        put(f"Fd{nm}ZMatchPct", fd[k]["unsound_but_z_matches"] / fd[k]["unsound"],
            pct(fd[k]["unsound_but_z_matches"] / fd[k]["unsound"], 0), src)
    fw = fd["forward"]
    assert fw["complete"] == fw["ops"] and fw["dual_ok"] == fw["ops"]
    put("FdFwdOps", fw["ops"], cnt(fw["ops"]), src)
    put("FdFwdPrecision", fw["precision"], f"{fw['precision']:.3f}", src)
    ob = fd["cpdg"]["unsound"] - fd["cpdg"]["unsound_but_z_matches"]
    put("FdCpdgObservable", ob, cnt(ob), src)
    put("FdCpdgObservablePct", ob / NUMS["NPairs"]["value"], pct(ob / NUMS["NPairs"]["value"]), src)
    cl = rows(ICPC / "corpus_l" / "slices.csv")
    src = "results/icpc/corpus_l/slices.csv"
    chk = [r for r in cl if r["slicer"] == "lc" and r["sound"] != ""]
    put("CorpusLSoundCircuits", len({r["path"] for r in chk}), cnt(len({r["path"] for r in chk})), src)
    put("CorpusLSoundPairs", len(chk), cnt(len(chk)), src)
    for s, nm in (("lc", "Lc"), ("yz", "Yz"), ("du", "Du")):
        bad = sum(r["sound"] == "0" for r in cl if r["slicer"] == s)
        put(f"CorpusLWrong{nm}", bad, cnt(bad), src)

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

    # ---- OpenQASM front end, LintQ comparison (Deviation I-22) ----
    src = "results/icpc/qasm_frontend/check.json"
    qc = json.load(open(ICPC / "qasm_frontend" / "check.json"))["summary"]
    assert qc["trace_equal"] == qc["slice_equal"] == qc["onepass_equal"] == qc["corpus_a_circuits"]
    assert qc["qasmbench_onepass_equal"] == qc["qasmbench_checked"]
    put("QasmCircuitsChecked", qc["corpus_a_circuits"], cnt(qc["corpus_a_circuits"]), src)
    put("QasmOnepassChecked", qc["qasmbench_checked"], cnt(qc["qasmbench_checked"]), src)
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
    src = "results/icpc/scale/s2_qasmbench.csv"
    s2 = rows(sc / "s2_qasmbench.csv")
    sq = {r["path"]: r for r in s2 if r["tool"] == TOOL_NAME and not r["error"]}
    put("ScaleQbFiles", len({r["path"] for r in s2}), cnt(len({r["path"] for r in s2})), src)
    put("ScaleQbRead", len(sq), cnt(len(sq)), src)
    put("ScaleQbMillion", sum(int(r["ops"]) >= 1_000_000 for r in sq.values()), cnt(sum(int(r["ops"]) >= 1_000_000 for r in sq.values())), src)
    put("ScaleQbMaxQubits", max(int(r["qubits"]) for r in sq.values()), cnt(max(int(r["qubits"]) for r in sq.values())), src)
    bp = max(sq, key=lambda p: int(sq[p]["ops"]))
    b = sq[bp]
    put("ScaleQbMaxOps", int(b["ops"]), f"{int(b['ops']) / 1e6:.1f}~million", src)
    put("ScaleQbMaxOpsQubits", int(b["qubits"]), cnt(int(b["qubits"])), src)
    put("ScaleQbReadS", float(b["t_read"]), f"{float(b['t_read']):.0f}", src)
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
    src = "results/icpc/scale/s2_qasmbench.csv"
    s2r = rows(ICPC / "scale" / "s2_qasmbench.csv")
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

    # ---- figure facts (generated by paper/figures/src/make_fig_*.py from the study's code) -----------------
    figs = HERE.parent / "paper" / "figures" / "src"
    mot = json.load(open(figs / "fig_motivating_facts.json"))
    put("MotFidelity", mot["F_q0_buggy_vs_fixed"], f"{mot['F_q0_buggy_vs_fixed']:.2f}", "paper/figures/src/fig_motivating_facts.json")
    put("MotPOne", mot["P1_buggy"][0], f"{mot['P1_buggy'][0]:.1f}", "paper/figures/src/fig_motivating_facts.json")
    put("MotDuFidelity", mot["F_du_q0_at_00"], f"{mot['F_du_q0_at_00']:.2f}", "paper/figures/src/fig_motivating_facts.json")
    bv = json.load(open(figs / "fig_bv_facts.json"))
    src = "paper/figures/src/fig_bv_facts.json"
    assert set(bv["dep"]) == set(bv["op_slices"]["lc"]), "BV: the QDG slice should be exactly the dependences"
    assert bv["min_purity_q0"] > 1 - 1e-9, "BV: q0 should never be entangled"
    words = lambda xs: ", ".join(str(x) for x in xs[:-1]) + (" and " if len(xs) > 1 else "") + str(xs[-1])  # noqa: E731
    put("BvCpdgLines", bv["tool_lines"]["cpdg"]["quantum"], words(bv["tool_lines"]["cpdg"]["quantum"]), src)
    put("BvQdgLines", bv["tool_lines"]["lc"]["quantum"], words(bv["tool_lines"]["lc"]["quantum"]), src)
    put("BvMissedLines", bv["cpdg_missed_lines"], words(bv["cpdg_missed_lines"]), src)
    put("BvCpdgClassical", bv["tool_lines"]["cpdg"]["classical"], words(bv["tool_lines"]["cpdg"]["classical"]), src)
    put("BvQdgClassical", bv["tool_lines"]["lc"]["classical"], words(bv["tool_lines"]["lc"]["classical"]), src)
    put("BvCpdgFidelity", bv["fidelity_slice_vs_program"]["cpdg"], f"{bv['fidelity_slice_vs_program']['cpdg']:.2f}", src)
    put("BvFixFidelity", bv["F_q0_buggy_vs_fixed"], f"{bv['F_q0_buggy_vs_fixed']:.2f}", src)
    put("BvOps", len(bv["ops"]), cnt(len(bv["ops"])), src)
    put("BvQdgOps", len(bv["op_slices"]["lc"]), cnt(len(bv["op_slices"]["lc"])), src)
    put("BvCpdgOps", len(bv["op_slices"]["cpdg"]), cnt(len(bv["op_slices"]["cpdg"])), src)
    (ob, pb), = bv["P_buggy"].items()
    (of, pf), = bv["P_fixed"].items()
    assert pb > 1 - 1e-9 and pf > 1 - 1e-9
    pf0 = bv["profile_q0"]
    assert pf0["backward_lines"] == bv["tool_lines"]["lc"]["quantum"] and not pf0["functions"] and not pf0["conditioned_lines"]
    assert sorted(pf0["names"]) == ["i", "q"]
    put("BvProfDefs", pf0["defs_uses"], words(pf0["defs_uses"]), src)
    put("BvProfNameI", pf0["names"]["i"], words(pf0["names"]["i"]), src)
    put("BvProfNameQ", pf0["names"]["q"], words(pf0["names"]["q"]), src)
    put("BvProfDependents", pf0["dependents"], words([f"$q_{d}$" for d in pf0["dependents"]]), src)
    put("BvProfBits", pf0["bits"], words([f"$c_{d}$" for d in pf0["bits"]]), src)
    put("BvProfForward", pf0["forward_lines"], words(pf0["forward_lines"]), src)
    sets = lambda xs: "\\{" + ", ".join(str(x) for x in xs) + "\\}"  # noqa: E731  (used in math mode)
    put("BvProfDefsSet", pf0["defs_uses"], sets(pf0["defs_uses"]), src)
    put("BvProfNameISet", pf0["names"]["i"], sets(pf0["names"]["i"]), src)
    put("BvProfNameQSet", pf0["names"]["q"], sets(pf0["names"]["q"]), src)
    put("BvProfDependentsSet", pf0["dependents"], sets(f"q_{d}" for d in pf0["dependents"]), src)
    put("BvProfBitsSet", pf0["bits"], sets(f"c_{d}" for d in pf0["bits"]), src)
    put("BvProfBackwardSet", pf0["backward_lines"], sets(pf0["backward_lines"]), src)
    put("BvProfForwardSet", pf0["forward_lines"], sets(pf0["forward_lines"]), src)
    put("BvBuggyOut", ob, ob, src)
    put("BvFixedOut", of, of, src)
    ex = json.load(open(figs / "fig_example_facts.json"))
    pr = json.load(open(figs / "fig_programs_facts.json"))
    A_, B_ = pr["teleport"], pr["ansatz"]
    put("TelDuOps", len(A_["slices"]["du"]), cnt(len(A_["slices"]["du"])), "paper/figures/src/fig_programs_facts.json")
    put("TelDuFidelity", A_["fidelity"]["du"], f"{A_['fidelity']['du']:.2f}", "paper/figures/src/fig_programs_facts.json")
    put("TelOps", len(A_["ops"]), cnt(len(A_["ops"])), "paper/figures/src/fig_programs_facts.json")
    put("AnsOps", len(B_["ops"]), cnt(len(B_["ops"])), "paper/figures/src/fig_programs_facts.json")
    put("AnsCpdgOps", len(B_["slices"]["cpdg"]), cnt(len(B_["slices"]["cpdg"])), "paper/figures/src/fig_programs_facts.json")
    put("AnsCpdgFidelity", B_["fidelity"]["cpdg"], f"{B_['fidelity']['cpdg']:.2f}", "paper/figures/src/fig_programs_facts.json")
    put("AnsWireOps", len(B_["slices"]["lc"]), cnt(len(B_["slices"]["lc"])), "paper/figures/src/fig_programs_facts.json")
    src = "paper/figures/src/fig_programs_facts.json"
    put("AnsDuOps", len(B_["slices"]["du"]), cnt(len(B_["slices"]["du"])), src)
    put("AnsDuFidelity", B_["fidelity"]["du"], f"{B_['fidelity']['du']:.2f}", src)
    put("AnsCpdgMissed", len(set(B_["dep"]) - set(B_["slices"]["cpdg"])), cnt(len(set(B_["dep"]) - set(B_["slices"]["cpdg"]))), src)
    put("AnsQdgFidelity", B_["fidelity"]["lc"], f"{B_['fidelity']['lc']:.2f}", src)
    put("AnsYzOps", len(B_["slices"]["yz"]), cnt(len(B_["slices"]["yz"])), src)
    put("AnsYzFidelity", B_["fidelity"]["yz"], f"{B_['fidelity']['yz']:.2f}", src)
    put("AnsYzroOps", len(B_["slices"]["yzro"]), cnt(len(B_["slices"]["yzro"])), src)
    put("AnsYzroFidelity", B_["fidelity"]["yzro"], f"{B_['fidelity']['yzro']:.2f}", src)
    assert set(B_["slices"]["du"]) < set(B_["slices"]["cpdg"]) < set(B_["dep"]) == set(B_["slices"]["lc"]), "ansatz: du < cpdg < QDG = dependences"
    put("AnsYzExtra", len(set(B_["slices"]["yz"]) - set(B_["dep"])), "zero one two three four five six seven eight nine".split()[len(set(B_["slices"]["yz"]) - set(B_["dep"]))], "paper/figures/src/fig_programs_facts.json")
    put("ExRandomInputs", 20, "20", "paper/figures/src/make_fig_example.py (N_RANDOM)")
    put("ExQSliceWrong", ex["facts"]["2"]["q"]["unsound_random"], cnt(ex["facts"]["2"]["q"]["unsound_random"]), "paper/figures/src/fig_example_facts.json")
    put("ExDuFidelity", ex["facts"]["0"]["du"]["F0"], f"{ex['facts']['0']['du']['F0']:.2f}", "paper/figures/src/fig_example_facts.json")

    # ---- review analyses (Deviation I-19; exploratory) ---------------------------------------------------------
    src = "results/icpc/gt_convergence/pairs.csv"
    gc = rows(ICPC / "gt_convergence" / "pairs.csv")
    new = rows(ICPC / "gt_convergence" / "new_deps.csv")
    glc = [r for r in gc if r["slicer"] == "lc"]
    assert len(glc) == 784 and all(x["in_qdg"] == "1" for x in new), "convergence: a new dependence outside the QDG"
    d0, d3 = sum(int(r["n_dep0"]) for r in glc), sum(int(r["n_dep3"]) for r in glc)
    put("GcDepsBefore", d0, cnt(d0), src)
    put("GcDepsNew", d3 - d0, cnt(d3 - d0), src)
    put("GcDepsNewPct", (d3 - d0) / d0, pct((d3 - d0) / d0, 2), src)
    put("GcDepsNewEntangled", sum(x["stage"] == "3" for x in new), cnt(sum(x["stage"] == "3" for x in new)),
        "results/icpc/gt_convergence/new_deps.csv")
    put("GcInputs", 51, "51", "icpc/gt_convergence.py (11 + 30 product + 10 entangled)")
    ne = int(re.search(r"EXTRA_PERT, EXTRA_PRODUCT, N_ENTANGLED = \d+, \d+, (\d+)", (HERE / "icpc" / "gt_convergence.py").read_text()).group(1))
    put("GcEntangledInputs", ne, word(ne), "icpc/gt_convergence.py (N_ENTANGLED)")
    put("GcPerturbations", 8, "eight", "icpc/gt_convergence.py (2 + 6)")
    for sl, nm in (("lc", "Lc"), ("yz", "Yz"), ("cpdg", "Cpdg"), ("q", "Q")):
        x = [r for r in gc if r["slicer"] == sl]
        put(f"GcPrecision{nm}", st.mean(float(r["precision3"]) for r in x), f"{st.mean(float(r['precision3']) for r in x):.3f}", src)
        dm = abs(st.mean(float(r["recall3"]) for r in x) - st.mean(float(r["recall0"]) for r in x))
        put(f"GcRecallShift{nm}", dm, f"{dm:.3f}", src)

    src = "results/icpc/qpdg_ro/rq1_records.csv"
    ro = rows(ICPC / "qpdg_ro" / "rq1_records.csv")
    for sl, nm in (("yzro", "Ro"), ("yzrof", "Rof")):
        x = [r for r in ro if r["slicer"] == sl]
        assert len(x) == 784
        bad = sum(r["sound"] != "1" for r in x)
        put(f"Yz{nm}Unsound", bad, cnt(bad), src)
        put(f"Yz{nm}UnsoundCircuits", len({r["path"] for r in x if r["sound"] != "1"}),
            cnt(len({r["path"] for r in x if r["sound"] != "1"})), src)
        put(f"Yz{nm}Size", st.mean(float(r["size_fraction"]) for r in x), pct(st.mean(float(r["size_fraction"]) for r in x)), src)
        put(f"Yz{nm}Recall", st.mean(float(r["dep_recall"]) for r in x), f"{st.mean(float(r['dep_recall']) for r in x):.3f}", src)
        miss = [m for m in rows(ICPC / "qpdg_ro" / "rq1_misses.csv") if m["slicer"] == sl]
        put(f"Yz{nm}Missed", len(miss), cnt(len(miss)), "results/icpc/qpdg_ro/rq1_misses.csv")
        put(f"Yz{nm}MissedKick", sum(m["category"] == "kickback" for m in miss), cnt(sum(m["category"] == "kickback" for m in miss)),
            "results/icpc/qpdg_ro/rq1_misses.csv")
    r3 = [r for r in rows(ICPC / "qpdg_ro" / "rq3_records.csv") if r["analysis"] == "primary" and r["slicer"] == "yzro"]
    put("YzRoContain", st.mean(int(r["contained"]) for r in r3), pct(st.mean(int(r["contained"]) for r in r3)),
        "results/icpc/qpdg_ro/rq3_records.csv")

    cc = json.load(open(ICPC / "cluster_ci" / "summary.json"))
    src = "results/icpc/cluster_ci/summary.json"
    ci = lambda k, f: f"{f(cc[k]['ci_families'][0])} to {f(cc[k]['ci_families'][1])}"  # noqa: E731
    p1 = lambda x: f"{100 * x:.0f}\\%"  # noqa: E731
    put("CcFamilies", cc["rq1_unsound_cpdg"]["n_families"], cnt(cc["rq1_unsound_cpdg"]["n_families"]), src)
    put("CcCpdgUnsound", cc["rq1_unsound_cpdg"]["ci_families"], ci("rq1_unsound_cpdg", p1), src)
    put("CcLcSize", cc["rq1_size_lc"]["ci_families"], ci("rq1_size_lc", p1), src)
    put("CcHThree", cc["h3_robust_q"]["ci_families"], ci("h3_robust_q", p1), src)
    put("CcHFour", cc["h4_contained_q_minus_lc"]["ci_families"],
        ci("h4_contained_q_minus_lc", lambda x: f"{100 * x:.1f}"), src)
    assert cc["h3_robust_q"]["ci_families"][1] < 0.95 and cc["h4_contained_q_minus_lc"]["ci_families"][1] < -0.05, \
        "a cluster interval changes the H3 or H4 decision"

    sc = json.load(open(ICPC / "rq3_size_control" / "summary.json"))
    src = "results/icpc/rq3_size_control/summary.json"
    for sl, nm in (("cpdg", "Cpdg"), ("lc", "Lc"), ("yz", "Yz"), ("q", "Q"), ("du", "Du")):
        d = sc[sl]["difference"]
        put(f"SizeCtl{nm}Random", sc[sl]["random_same_size"]["point"], pct(sc[sl]["random_same_size"]["point"]), src)
        put(f"SizeCtl{nm}Gain", d["point"], f"{100 * d['point']:.1f}", src)
        put(f"SizeCtl{nm}GainCi", d["ci_families"], f"{100 * d['ci_families'][0]:.1f} to {100 * d['ci_families'][1]:.1f}", src)
        assert d["ci_families"][0] > 0, f"size control: {sl} not above chance"

    src = "results/icpc/mbfl/units_all_rules.csv"
    ma = [r for r in rows(ICPC / "mbfl" / "units_all_rules.csv") if not r.get("excluded")]
    rules = ("du", "cpdg", "lc", "yz", "q")
    pa = [r for r in ma if all(r[f"fault_in_{s}"] == "1" for s in rules) and r["exam_all_avg"]]
    put("MbflAllN", len(pa), cnt(len(pa)), src)
    for s, nm in (("all", "All"), ("du", "Du"), ("cpdg", "Cpdg"), ("lc", "Lc"), ("yz", "Yz"), ("q", "Q")):
        put(f"MbflAllExam{nm}", st.mean(float(r[f"exam_{s}_avg"]) for r in pa), f"{st.mean(float(r[f'exam_{s}_avg']) for r in pa):.3f}", src)
        put(f"MbflAllExamined{nm}", st.mean(int(r[f"examined_{s}"]) for r in pa), f"{st.mean(int(r[f'examined_{s}']) for r in pa):.1f}", src)
    ex = [st.mean(int(r[f"examined_{s}"]) for r in pa) for s in ("all",) + rules]
    put("MbflAllExaminedMin", min(ex), f"{min(ex):.1f}", src)
    put("MbflAllExaminedMax", max(ex), f"{max(ex):.1f}", src)
    put("MbflQRecomputedDiffers", sum(r["q_recomputed_differs"] == "1" for r in ma), cnt(sum(r["q_recomputed_differs"] == "1" for r in ma)), src)

    qr = rows(ICPC / "q_repeat" / "pairs.csv")
    assert all(r["all_equal_stored"] == "1" and r["all_sound"] == "1" for r in qr), "S-q not repeatable on corpus A"
    put("QRepeatPairs", len(qr), cnt(len(qr)), "results/icpc/q_repeat/pairs.csv")
    tlim = int(re.search(r'add_argument\("--timeout", type=int, default=(\d+)\)', (HERE.parent / "tool" / "corpus" / "coverage.py").read_text()).group(1))
    put("ToolFileLimit", tlim, str(tlim), "tool/corpus/coverage.py (--timeout default)")
    put("QRepeatRuns", const("icpc/q_repeat.py", "REPEATS"), word(const("icpc/q_repeat.py", "REPEATS")), "icpc/q_repeat.py (REPEATS)")

    yf = json.load(open(ICPC / "yz_listings" / "fig1.json"))
    src = "results/icpc/yz_listings/fig1.json"
    assert yf["missing"] == ["x(1)", "cx(0,1)"] and yf["p_q1_one"]["program"] == 1.0, "Yu-Zhao Fig. 1 facts changed"
    fr = Fraction(yf["p_q1_one"]["slice"]).limit_denominator(16)
    put("YzFigSliceProb", yf["p_q1_one"]["slice"], f"{fr.numerator}/{fr.denominator}", src)
    yl = json.load(open(ICPC / "yz_listings" / "listings.json"))
    assert all(v[q]["yz"]["slice"] == v[q]["lc"]["slice"] for v in yl.values() for q in v if q.startswith("q"))

    # ---- Deviation I-24: the write set, the nesting, the dependence set as a slice (exploratory) --------------
    ctl = NUMS["CpdgMissTotal"]["value"] - NUMS["CpdgMissFeedback"]["value"]
    put("CpdgMissControlPct", ctl / NUMS["CpdgMissTotal"]["value"], pct(ctl / NUMS["CpdgMissTotal"]["value"]),
        "results/icpc/cpdg/rq1_misses.csv")
    put("YzLcExcessRatio", NUMS["YzExcess"]["value"] / NUMS["LcExcess"]["value"],
        f"{float(NUMS['YzExcess']['tex']) / float(NUMS['LcExcess']['tex']):.1f}", "results/icpc/rq1/records.csv")
    gs = json.load(open(ICPC / "gate_signal" / "summary.json"))
    src = "results/icpc/gate_signal/summary.json"
    put("GateSignalN", gs["n_gates"], cnt(gs["n_gates"]), src)
    put("GateSignalBoth", gs["n_both"], cnt(gs["n_both"]), src)
    if (ICPC / "nesting" / "summary.json").exists():
        ns = json.load(open(ICPC / "nesting" / "summary.json"))
        src = "results/icpc/nesting/summary.json"
        assert ns["pairs"] == NUMS["NPairs"]["value"], "nesting pairs differ from RQ1"
        for k, nm in (("pairs", "Pairs"), ("d_in_qdg", "DInQdg"), ("qdg_in_qpdg", "QdgInQpdg"), ("qpdg_pairs", "QpdgPairs"),
                      ("d_eq_qdg", "DEqQdg"), ("qdg_eq_qpdg", "QdgEqQpdg"), ("d_sound", "DSound")):
            put(f"Nest{nm}", ns[k], cnt(ns[k]), src)
        put("NestDUnsound", ns["pairs"] - ns["d_sound"], cnt(ns["pairs"] - ns["d_sound"]), src)
        put("NestViolations", len(ns["violations"]), cnt(len(ns["violations"])), src)
        npairs = rows(ICPC / "nesting" / "pairs.csv")  # D lies within the QPDG slice, so equal sizes mean equal sets
        deq = sum(r["qpdg"] != "" and int(r["d"]) == int(r["qpdg"]) for r in npairs)
        put("NestDEqQpdg", deq, cnt(deq), "results/icpc/nesting/pairs.csv")
        put("NestQpdgLarger", len(npairs) - ns["qdg_eq_qpdg"], cnt(len(npairs) - ns["qdg_eq_qpdg"]), src)

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

    # ---- write ----------------------------------------------------------------------------------------------
    TEX.parent.mkdir(parents=True, exist_ok=True)
    out = ["% Generated by experiments/icpc/make_numbers.py from committed results. Do not edit by hand.", ""]
    for k, v in NUMS.items():
        v["tex"] = v["tex"].replace("-", "\\ensuremath{-}") if v["tex"][:1] in "-[" else v["tex"]
        out.append(f"\\newcommand{{\\num{k}}}{{\\ensuremath{{{v['tex']}}}}}  % {v['source']}" if v["tex"].startswith("p ")
                   else f"\\newcommand{{\\num{k}}}{{{v['tex']}}}  % {v['source']}")
    TEX.write_text("\n".join(out) + "\n")
    (ICPC / "numbers.json").write_text(json.dumps(NUMS, indent=1))
    print(f"{len(NUMS)} numbers; wrote {TEX} and {ICPC / 'numbers.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
