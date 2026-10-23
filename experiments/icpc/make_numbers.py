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
    put("LcqRecall", st.mean(float(lq[k]["dep_recall"]) for k in ap), f"{st.mean(float(lq[k]['dep_recall']) for k in ap):.2f}", src)
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

    # ---- RQ3: MBFL ---------------------------------------------------------------------------------------
    src = "results/icpc/mbfl/units.csv"
    mb = [r for r in rows(ICPC / "mbfl" / "units.csv") if not r.get("excluded")]
    put("MbflUnits", len(mb), cnt(len(mb)), src)
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
        put(f"Noise{nm}CrossExactMax", max(ex_), sci(max(ex_)), src)
        put(f"Noise{nm}CrossExactNonzero", sum(x > 1e-9 for x in ex_), cnt(sum(x > 1e-9 for x in ex_)), src)
        put(f"Noise{nm}CrossExactN", len(ex_), cnt(len(ex_)), src)
        put(f"Noise{nm}CrossShotMax", max(dy), f"{max(dy):.3f}", src)
    put("NoiseShots", 1024, cnt(1024), "icpc/noise_run.py")
    hw = rows(ICPC / "hardware" / "hardware_tvd_corrected.csv")
    put("HwCircuits", len(hw), cnt(len(hw)), "results/icpc/hardware/hardware_tvd_corrected.csv")
    put("HwWithin", sum(r["within_delta"] == "True" for r in hw), cnt(sum(r["within_delta"] == "True" for r in hw)), "results/icpc/hardware/hardware_tvd_corrected.csv")
    put("HwNoiseFreeZero", sum(float(r["TVD_noise_free"]) == 0 for r in hw), cnt(sum(float(r["TVD_noise_free"]) == 0 for r in hw)), "results/icpc/hardware/hardware_tvd_corrected.csv")

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
