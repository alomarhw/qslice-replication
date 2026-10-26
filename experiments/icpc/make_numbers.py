"""Every number the ICPC paper states, from committed result files only (plan Phase 4; PROTOCOL_ICPC.md §9).

Reads results/ and recomputes nothing about circuits. The only statistics computed here are the §6.4 T2
comparisons (exact McNemar on top-3 hits, paired bootstrap CI of the difference), because no committed file
holds them. The §9 confirmatory family is read from results/icpc/confirmatory/summary.json.
Writes:
  ../paper/numbers.tex       one \\newcommand per number, each commented with its source file
  results/icpc/numbers.json  the same values, raw and formatted, for PROVENANCE.md
p-values below 1e-10 are written "10^{-10}" with a "<" (plan Phase 4 rule).
Usage (from experiments/): python icpc/make_numbers.py
"""

from __future__ import annotations

import csv
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
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
    put("HFourCILow", c["H4"]["ci95_difference"][0], f"{100 * c['H4']['ci95_difference'][0]:.1f}", src)
    put("HFourCIHigh", c["H4"]["ci95_difference"][1], f"{100 * c['H4']['ci95_difference'][1]:.1f}", src)
    put("HFiveSizeDiff", c["H5"]["mean_difference"], f"{c['H5']['mean_difference']:.1f}", src)
    put("HFiveExamDiff", c["H5"]["exam_slice_alongside"]["mean_difference"], f"{c['H5']['exam_slice_alongside']['mean_difference']:.3f}", src)
    put("HFiveExamQHigher", -c["H5"]["exam_slice_alongside"]["mean_difference"], f"{-c['H5']['exam_slice_alongside']['mean_difference']:.3f}", src)  # state-based minus wire

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
    u = [r for r in rows(ICPC / "rq3" / "units.csv") if r["analysis"] == "primary"]
    put("CQFour", sum(r["cq4"] == "1" for r in u), cnt(sum(r["cq4"] == "1" for r in u)), "results/icpc/rq3/units.csv")
    put("CQFourRecovered", sum(r["cq4_remedy_contains"] == "1" for r in u), cnt(sum(r["cq4_remedy_contains"] == "1" for r in u)), "results/icpc/rq3/units.csv")

    # ---- RQ3: Bugs4Q, source map -------------------------------------------------------------------------
    b = Counter(r["outcome"] for r in rows(ICPC / "rq3_bugs4q" / "bugs.csv"))
    for o, nm in (("killed", "Killed"), ("injured", "Injured"), ("alive", "Alive"), ("excluded", "Excluded")):
        put(f"BugsFourQ{nm}", b[o], cnt(b[o]), "results/icpc/rq3_bugs4q/bugs.csv")
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
        put(f"CostDepth{nm}OverLimit", sum(r["limit"] == "wall" for r in x), cnt(sum(r["limit"] == "wall" for r in x)), src)
        put(f"CostBuildDepth{nm}", st.median(float(r["build_seconds"]) for r in x), f"{st.median(float(r['build_seconds']) for r in x):.1f}", src)
    put("CostWallLimit", 120, "120", "icpc/cost_run.py")
    w = [float(r["q_total"]) for r in co if r["kind"].startswith("width-") and r.get("q_total")]
    put("CostWidthQMax", max(w), f"{max(w):.1f}", src)
    cl = rows(ICPC / "corpus_l" / "circuits.csv")
    put("CorpusLCircuits", len(cl), cnt(len(cl)), "results/icpc/corpus_l/circuits.csv")
    put("CorpusLCompleted", sum(r["completed"] == "1" for r in cl), cnt(sum(r["completed"] == "1" for r in cl)), "results/icpc/corpus_l/circuits.csv")

    # ---- Discussion: noise and hardware ------------------------------------------------------------------
    src = "results/icpc/noise/pairs.csv"
    nz_ = rows(ICPC / "noise" / "pairs.csv")
    for s, nm in (("lc", "Lc"), ("q", "Q")):
        ex_ = [float(r["D_cross"]) for r in nz_ if r["slicer"] == s and r["shots_full"] == "1"]
        dy = [float(r["D_cross"]) for r in nz_ if r["slicer"] == s and r["shots_full"] != "1"]
        put(f"Noise{nm}CrossExactMax", max(ex_), sci(max(ex_)) if max(ex_) < 0.01 else f"{max(ex_):.2f}", src)
        put(f"Noise{nm}CrossExactNonzero", sum(x > 1e-9 for x in ex_), cnt(sum(x > 1e-9 for x in ex_)), src)
        put(f"Noise{nm}CrossExactN", len(ex_), cnt(len(ex_)), src)
        put(f"Noise{nm}CrossShotMax", max(dy), f"{max(dy):.3f}", src)
    put("NoiseShots", 1024, cnt(1024), "icpc/noise_run.py")
    hw = rows(ICPC / "hardware" / "hardware_tvd_corrected.csv")
    put("HwCircuits", len(hw), cnt(len(hw)), "results/icpc/hardware/hardware_tvd_corrected.csv")
    put("HwWithin", sum(r["within_delta"] == "True" for r in hw), cnt(sum(r["within_delta"] == "True" for r in hw)), "results/icpc/hardware/hardware_tvd_corrected.csv")
    put("HwOutside", sum(r["within_delta"] != "True" for r in hw), ["zero", "one", "two", "three"][sum(r["within_delta"] != "True" for r in hw)], "results/icpc/hardware/hardware_tvd_corrected.csv")
    put("HwNoiseFreeZero", sum(float(r["TVD_noise_free"]) == 0 for r in hw), cnt(sum(float(r["TVD_noise_free"]) == 0 for r in hw)), "results/icpc/hardware/hardware_tvd_corrected.csv")

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
    put("MutOperators", len({m["operator"] for m in mut}), cnt(len({m["operator"] for m in mut})), "results/icpc/rq3/mutants.csv")
    put("RqThreeSecondary", sum(r["analysis"] == "secondary" for r in rows(ICPC / "rq3" / "units.csv")), cnt(sum(r["analysis"] == "secondary" for r in rows(ICPC / "rq3" / "units.csv"))), "results/icpc/rq3/units.csv")
    put("OracleErr", 2.2e-16, sci(2.2e-16), "experiments/logs/icpc/test_oracle_icpc.log (joint rho_W vs Statevector/partial_trace, random unitary circuits)")
    put("InfluenceInputs", 11, "11", "icpc/influence.py (|0...0> + N_INPUTS=10)")
    put("InfluencePerturbations", 2, "2", "icpc/influence.py (N_PERTURBATIONS)")
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

    # ---- the static program slicer (Deviation I-15; tool-v4, the final version; earlier versions' results kept) --
    sys.path.insert(0, str(HERE.parents[1]))
    from tool.gates import GATES  # noqa: PLC0415
    put("ToolGateTable", len(GATES), cnt(len(GATES)), "tool/gates.py")
    TA = ICPC / "tool_acceptance"
    dev = json.load(open(TA / "dev_checks.json"))
    src = "results/icpc/tool_acceptance/dev_checks.json"
    put("ToolDevPrograms", len(dev), cnt(len(dev)), src)
    put("ToolDevTraceEqual", sum(r["trace_equal"] for r in dev), cnt(sum(r["trace_equal"] for r in dev)), src)
    put("ToolDevSliceEqual", sum(r["slices_equal"] for r in dev), cnt(sum(r["slices_equal"] for r in dev)), src)
    put("ToolDevMaxOps", max(r["ops"] for r in dev), cnt(max(r["ops"] for r in dev)), src)
    assert all(r["nested_conditions"] for r in dev if not r["slices_equal"]), "a slice difference outside nested conditions"
    ts = json.load(open(TA / "tool-v4" / "summary.json"))
    src = "results/icpc/tool_acceptance/tool-v4/summary.json"
    for k, nm in (("t1_bugs", "ToolTOneBugs"), ("t1_exact", "ToolTOneExact"), ("t1_ops_prepared", "ToolTOneOps"),
                  ("t1_ops_matched", "ToolTOneOpsMatched"), ("t2_units_mapped", "ToolTTwoUnits"), ("t2_equal_mapped", "ToolTTwoEqual")):
        put(nm, ts[k], cnt(ts[k]), src)
    nc = json.load(open(TA / "nested_check.json"))
    put("ToolNestedDraws", nc["draws"], cnt(nc["draws"]), "results/icpc/tool_acceptance/nested_check.json")
    put("ToolNestedStudyWrong", nc["study_wrong_max"], cnt(nc["study_wrong_max"]), "results/icpc/tool_acceptance/nested_check.json")
    put("ToolNestedToolWrong", nc["tool_wrong_total"], cnt(nc["tool_wrong_total"]), "results/icpc/tool_acceptance/nested_check.json")
    for path, nm, src in ((TA / "tool-v4" / "t3_bugs4q.csv", "Bugs", "results/icpc/tool_acceptance/tool-v4/t3_bugs4q.csv"),
                          (ICPC / "tool_coverage" / "textbook_v4.csv", "Textbook", "results/icpc/tool_coverage/textbook_v4.csv"),
                          (ICPC / "tool_coverage" / "lintq_v4.csv", "Lintq", "results/icpc/tool_coverage/lintq_v4.csv")):
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
    put("AnsYzExtra", len(set(B_["slices"]["yz"]) - set(B_["dep"])), "zero one two three four five six seven eight nine".split()[len(set(B_["slices"]["yz"]) - set(B_["dep"]))], "paper/figures/src/fig_programs_facts.json")
    put("ExRandomInputs", 20, "20", "paper/figures/src/make_fig_example.py (N_RANDOM)")
    put("ExQSliceWrong", ex["facts"]["2"]["q"]["unsound_random"], cnt(ex["facts"]["2"]["q"]["unsound_random"]), "paper/figures/src/fig_example_facts.json")
    put("ExDuFidelity", ex["facts"]["0"]["du"]["F0"], f"{ex['facts']['0']['du']['F0']:.2f}", "paper/figures/src/fig_example_facts.json")

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
