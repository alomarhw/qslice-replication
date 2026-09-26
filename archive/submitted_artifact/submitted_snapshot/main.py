"""Main entry point for the controlled QPDG slicing experiments.

Requirements targeted:
- numpy==1.26.4
- pandas==3.0.3
- matplotlib==3.10.9
- qiskit==2.4.2
- qiskit-aer==0.17.2

Default execution is paper-grade/full mode for strict real-data the toolkit runs. Use --smoke for
a small local validation subset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qasm_loader import CORPUS_DIRS, SimpleCircuit, load_corpora, load_qasm_corpus

# Display label -> data subdirectory (inverse of CORPUS_DIRS), for provenance paths.
CORPUS_SUBDIR = {label: sub for sub, label in CORPUS_DIRS.items()}
from qdg import evaluate_backward, forward_coverage
from rp_data_runtime import load_manifest, resolve_data_path

RANDOM_SEED = int(os.environ.get("RP_RANDOM_SEED", 42))
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

METHOD_LABELS = {
    "qpdg": "QPDG",
    "naive": "Naive classical PDG (def-use port)",
    "causal": "Causal classical PDG (data+control light cone)",
}
METRICS = [
    "invalid_slice_rate",
    "target_state_fidelity",
    "slice_size_fraction_of_ops",
    "forward_influence_completeness",
]
QUESTIONS = {
    "RQ1": "Does a faithful classical (def-use) PDG slicer produce semantically invalid backward slices on real quantum circuits, and does QPDG (entanglement-aware) eliminate them?",
    "RQ2": "Does QPDG produce smaller SOUND backward slices than the sound causal classical PDG (precision at equal soundness)?",
    "RQ3": "Does the naive classical FORWARD slice miss entanglement-influenced operations, and does QPDG cover them?",
}


def finite_float(x: Any, name: str) -> float:
    val = float(x)
    if not math.isfinite(val):
        raise RuntimeError(f"Non-finite value for {name}: {x}")
    return val


def sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, tuple):
        return [sanitize(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return finite_float(obj, "numpy_float")
    if isinstance(obj, float):
        return finite_float(obj, "float")
    return obj


def sha256_paths(paths: list[Path], limit: int = 128) -> str:
    h = hashlib.sha256()
    for p in sorted(paths)[:limit]:
        try:
            h.update(str(p).encode("utf-8"))
            h.update(p.read_bytes()[:1024 * 1024])
        except Exception:
            continue
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(sanitize(obj), f, indent=2, allow_nan=False)


def write_provenance(data_root: Path, circuits: list[SimpleCircuit] | None, used_synthetic_rq3: bool = False) -> None:
    qasm_files = sorted(data_root.rglob("*.qasm")) if data_root.exists() else []
    manifest = load_manifest(str(data_root))
    manifest_ok = manifest.get("ok", [])
    m0 = manifest_ok[0] if manifest_ok else {}
    data_prov_path = data_root / "data_provenance.json"
    preserve_mined = False
    if data_prov_path.exists():
        try:
            preserve_mined = bool(json.loads(data_prov_path.read_text(encoding="utf-8")).get("usedMinedData", False))
        except Exception:
            preserve_mined = False
    rows = len(circuits or [])
    schema = ["OpenQASM .qasm corpus", "qreg declarations", "unitary gate operations"]
    # One dataset entry per source corpus actually loaded (real benchmarks: QASMBench / MQT / VeriQ).
    citations = {
        "QASMBench": "QASMBench OpenQASM benchmark corpus",
        "MQT Bench": "MQT Bench (Munich Quantum Toolkit) benchmark corpus",
        "VeriQBench": "VeriQBench quantum circuit benchmark corpus",
    }
    by_corpus: dict[str, int] = {}
    for c in circuits or []:
        by_corpus[c.source or "QASMBench"] = by_corpus.get(c.source or "QASMBench", 0) + 1
    if not by_corpus:
        by_corpus = {"QASMBench": 0}
    datasets: list[dict[str, Any]] = [
        {
            "name": label,
            "source": "real",
            "path": str(data_root / CORPUS_SUBDIR.get(label, "")),
            "rows": count,
            "version": m0.get("version", ""),
            "license": m0.get("license", ""),
            "citation": citations.get(label, label),
            "checksum": "",
            "recordCount": count,
            "schema": schema,
        }
        for label, count in sorted(by_corpus.items())
    ]
    if used_synthetic_rq3:
        datasets.append(
            {
                "name": "RQ3 perturbation oracle",
                "source": "synthetic",
                "path": "",
                "rows": rows,
                "version": "deterministic",
                "license": "",
                "citation": "",
                "checksum": "",
                "recordCount": rows,
                "schema": ["source_qubit", "perturbed_reduced_density_changes"],
            }
        )
    prov: dict[str, Any] = {"usedSynthetic": bool(used_synthetic_rq3), "datasets": datasets}
    if preserve_mined:
        prov["usedMinedData"] = True
    write_json(Path("results/data_provenance.json"), prov)


def mcnemar_exact(a_invalid: list[int], b_invalid: list[int], label: str = "exact McNemar test on paired invalid-slice indicators") -> dict[str, Any]:
    b01 = sum(1 for a, b in zip(a_invalid, b_invalid) if a == 0 and b == 1)
    b10 = sum(1 for a, b in zip(a_invalid, b_invalid) if a == 1 and b == 0)
    n = b01 + b10
    if n == 0:
        p = 1.0
    else:
        k = min(b01, b10)
        p = min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2**n))
    effect = (b01 - b10) / max(n, 1)
    diff = np.array(a_invalid, dtype=float) - np.array(b_invalid, dtype=float)
    ci = bootstrap_ci(diff.tolist())
    return {"test_used": label, "p_value": p, "effect_size": effect, "confidence_interval": ci}


def paired_forward_incomplete(forward_records: list[dict[str, Any]], a: str, b: str) -> tuple[list[int], list[int]]:
    """Per (circuit, source) forward-incompleteness indicators for two slicers, aligned for a paired test."""
    def incomplete_map(slicer: str) -> dict[tuple[str, str, int], int]:
        return {
            (r["circuit"], r.get("corpus", ""), int(r["source"])): int(float(r["forward_influence_completeness"]) < 1.0 - 1e-9)
            for r in forward_records if r["slicer"] == slicer
        }
    am, bm = incomplete_map(a), incomplete_map(b)
    keys = sorted(set(am) & set(bm))
    return [am[k] for k in keys], [bm[k] for k in keys]


def wilcoxon_signed_rank(x: list[float], y: list[float]) -> dict[str, Any]:
    diffs = [a - b for a, b in zip(x, y) if abs(a - b) > 1e-12]
    if not diffs:
        return {"test_used": "Wilcoxon signed-rank test (zero-difference convention)", "p_value": 1.0, "effect_size": 0.0, "confidence_interval": [0.0, 0.0]}
    abs_sorted = sorted((abs(d), i) for i, d in enumerate(diffs))
    ranks = [0.0] * len(diffs)
    r = 1
    for _, i in abs_sorted:
        ranks[i] = float(r)
        r += 1
    w_plus = sum(rank for rank, d in zip(ranks, diffs) if d > 0)
    w_minus = sum(rank for rank, d in zip(ranks, diffs) if d < 0)
    w = min(w_plus, w_minus)
    n = len(diffs)
    mean = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0
    z = (w - mean) / math.sqrt(max(var, 1e-12))
    p = min(1.0, math.erfc(abs(z) / math.sqrt(2)))
    effect = (w_plus - w_minus) / max(w_plus + w_minus, 1e-12)
    return {"test_used": "Wilcoxon signed-rank test with normal approximation", "p_value": p, "effect_size": effect, "confidence_interval": bootstrap_ci(diffs)}


def bootstrap_ci(vals: list[float], reps: int = 1000) -> list[float]:
    if not vals:
        return [0.0, 0.0]
    if len(vals) == 1:
        return [float(vals[0]), float(vals[0])]
    rng = random.Random(RANDOM_SEED)
    means = []
    for _ in range(reps):
        sample = [vals[rng.randrange(len(vals))] for _ in vals]
        means.append(statistics.fmean(sample))
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def aggregate_backward(records: list[dict[str, Any]], forward_records: list[dict[str, Any]], method: str) -> dict[str, float]:
    b = [r for r in records if r["slicer"] == method]
    f = [r for r in forward_records if r["slicer"] == method]
    return {
        "invalid_slice_rate": finite_float(statistics.fmean([r["invalid"] for r in b]), f"{method}.invalid_slice_rate"),
        "target_state_fidelity": finite_float(statistics.fmean([r["fidelity"] for r in b]), f"{method}.target_state_fidelity"),
        "slice_size_fraction_of_ops": finite_float(statistics.fmean([r["slice_size_fraction"] for r in b]), f"{method}.slice_size_fraction"),
        "forward_influence_completeness": finite_float(statistics.fmean([r["forward_influence_completeness"] for r in f]), f"{method}.forward_completeness"),
    }


def aggregate_per_corpus(
    circuits: list[SimpleCircuit],
    backward_records: list[dict[str, Any]],
    forward_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Per-source-corpus breakdown of the same per-method metrics, for a per-corpus results table."""
    out: dict[str, Any] = {}
    for label in sorted({c.source for c in circuits if c.source}):
        b = [r for r in backward_records if r.get("corpus") == label]
        f = [r for r in forward_records if r.get("corpus") == label]
        out[label] = {
            "n_circuits": sum(1 for c in circuits if c.source == label),
            "metrics": aggregate_backward(b, f, "qpdg"),
            "baseline_comparison": {
                METHOD_LABELS["naive"]: aggregate_backward(b, f, "naive"),
                METHOD_LABELS["causal"]: aggregate_backward(b, f, "causal"),
            },
        }
    return out


def resolve_corpus_root(data_root: Path) -> Path:
    manifest_path = data_root / "fetch_manifest.json"
    if manifest_path.exists():
        try:
            return resolve_data_path("QASMBench (small)", str(data_root), required=True)
        except Exception as exc:
            print(f"Manifest resolution warning: {exc}; falling back to recursive corpus scan under {data_root}")
    return data_root


def run_experiments(circuits: list[SimpleCircuit]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    backward_records: list[dict[str, Any]] = []
    forward_records: list[dict[str, Any]] = []

    print("Running RQ1/RQ2 backward slices for QPDG, naive classical PDG, and causal classical PDG...")
    for ci, circuit in enumerate(circuits, start=1):
        print(f"  [{ci}/{len(circuits)}] [{circuit.source}] {circuit.name}: qubits={circuit.num_qubits}, ops={len(circuit.ops)}")
        for target in range(circuit.num_qubits):
            for slicer in ["qpdg", "naive", "causal"]:
                rec = evaluate_backward(circuit, target, slicer)  # exact oracle, no sampling
                rec["corpus"] = circuit.source
                backward_records.append(rec)

    print("Running RQ3 forward influence completeness with exact input perturbation oracle...")
    for circuit in circuits:
        for source in range(circuit.num_qubits):
            for slicer in ["qpdg", "naive", "causal"]:
                rec = forward_coverage(circuit, source, slicer)
                rec["corpus"] = circuit.source
                forward_records.append(rec)

    metrics_by_method = {m: aggregate_backward(backward_records, forward_records, m) for m in ["qpdg", "naive", "causal"]}
    per_corpus = aggregate_per_corpus(circuits, backward_records, forward_records)

    qpdg_invalid = [int(r["invalid"]) for r in backward_records if r["slicer"] == "qpdg"]
    naive_invalid = [int(r["invalid"]) for r in backward_records if r["slicer"] == "naive"]
    causal_invalid = [int(r["invalid"]) for r in backward_records if r["slicer"] == "causal"]

    df_back = pd.DataFrame(backward_records)
    q_sound = df_back[(df_back["slicer"] == "qpdg") & (df_back["invalid"] == 0)].copy()
    c_sound = df_back[(df_back["slicer"] == "causal") & (df_back["invalid"] == 0)].copy()
    paired = q_sound.merge(c_sound, on=["circuit", "target", "corpus"], suffixes=("_qpdg", "_causal"))
    if paired.empty:
        raise RuntimeError("No paired sound QPDG/causal slices were produced; cannot run RQ2 Wilcoxon test.")
    rq2_qpdg_size = paired["slice_size_fraction_qpdg"].astype(float).tolist()
    rq2_causal_size = paired["slice_size_fraction_causal"].astype(float).tolist()

    # RQ3 tests its own question: does QPDG cover entanglement-influenced ops the naive
    # classical forward slice misses? -> paired forward-incompleteness indicators, QPDG vs naive.
    qpdg_fwd_incomplete, naive_fwd_incomplete = paired_forward_incomplete(forward_records, "qpdg", "naive")

    results = {
        "RQ1": {
            "_question": QUESTIONS["RQ1"],
            "metrics": metrics_by_method["qpdg"],
            "baseline_comparison": {
                METHOD_LABELS["naive"]: metrics_by_method["naive"],
                METHOD_LABELS["causal"]: metrics_by_method["causal"],
            },
            "per_corpus": per_corpus,
            "statistical_tests": mcnemar_exact(qpdg_invalid, naive_invalid),
        },
        "RQ2": {
            "_question": QUESTIONS["RQ2"],
            "metrics": metrics_by_method["qpdg"],
            "baseline_comparison": {
                METHOD_LABELS["naive"]: metrics_by_method["naive"],
                METHOD_LABELS["causal"]: metrics_by_method["causal"],
            },
            "per_corpus": per_corpus,
            "statistical_tests": wilcoxon_signed_rank(rq2_qpdg_size, rq2_causal_size),
        },
        "RQ3": {
            "_question": QUESTIONS["RQ3"],
            "metrics": metrics_by_method["qpdg"],
            "baseline_comparison": {
                METHOD_LABELS["naive"]: metrics_by_method["naive"],
                METHOD_LABELS["causal"]: metrics_by_method["causal"],
            },
            "per_corpus": per_corpus,
            "statistical_tests": mcnemar_exact(
                qpdg_fwd_incomplete,
                naive_fwd_incomplete,
                label="exact McNemar test on paired forward-incompleteness indicators (QPDG vs naive classical)",
            ),
        },
    }
    return results, pd.DataFrame(backward_records), pd.DataFrame(forward_records)


def validate_results(results: dict[str, Any]) -> None:
    for rq in ["RQ1", "RQ2", "RQ3"]:
        for metric in METRICS:
            finite_float(results[rq]["metrics"].get(metric), f"{rq}.metrics.{metric}")
            for baseline in [METHOD_LABELS["naive"], METHOD_LABELS["causal"]]:
                finite_float(results[rq]["baseline_comparison"][baseline].get(metric), f"{rq}.{baseline}.{metric}")
        st = results[rq]["statistical_tests"]
        finite_float(st["p_value"], f"{rq}.p_value")
        finite_float(st["effect_size"], f"{rq}.effect_size")
        finite_float(st["confidence_interval"][0], f"{rq}.ci_low")
        finite_float(st["confidence_interval"][1], f"{rq}.ci_high")

    if abs(results["RQ1"]["metrics"]["invalid_slice_rate"]) > 1e-12:
        raise RuntimeError("Acceptance check failed: QPDG invalid rate == 0 was not satisfied.")
    if results["RQ1"]["baseline_comparison"][METHOD_LABELS["naive"]]["invalid_slice_rate"] <= 0:
        raise RuntimeError("Acceptance check failed: naive classical invalid rate > 0 was not satisfied.")
    if results["RQ2"]["metrics"]["slice_size_fraction_of_ops"] >= results["RQ2"]["baseline_comparison"][METHOD_LABELS["causal"]]["slice_size_fraction_of_ops"]:
        raise RuntimeError("Acceptance check failed: QPDG slice size < causal classical (sound pairs) was not satisfied.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run QPDG controlled experiments.")
    parser.add_argument("--data-root", default="data", help="Root directory containing QASMBench .qasm corpus.")
    parser.add_argument("--full", action="store_true", default=True, help="Run paper-grade path (default).")
    parser.add_argument("--smoke", action="store_true", help="Run fast CI subset; not paper-grade.")
    parser.add_argument("--max-circuits", type=int, default=None, help="Optional cap on circuits.")
    parser.add_argument("--max-qubits", type=int, default=int(os.environ.get("RP_QUANTUM_MAX_QUBITS", 10)), help="Maximum qubits for exact statevector simulation.")
    parser.add_argument("--max-ops", type=int, default=int(os.environ.get("RP_QUANTUM_MAX_GATES", 220)), help="Maximum parsed gate operations per circuit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    Path("results").mkdir(parents=True, exist_ok=True)
    Path("figures").mkdir(parents=True, exist_ok=True)

    data_root = Path(args.data_root)
    mode = "smoke" if args.smoke else "paper-grade"
    # Per-corpus cap: each of QASMBench/MQT/VeriQ contributes up to this many in-range circuits.
    max_per_corpus = args.max_circuits if args.max_circuits is not None else (8 if args.smoke else 80)
    min_total = 3 if args.smoke else 30
    # Exact statevector simulation: <=14 qubits is tractable (2^14 amplitudes); paper-grade default.
    max_qubits = min(args.max_qubits, 8) if args.smoke else max(args.max_qubits, 14)
    max_ops = min(args.max_ops, 120) if args.smoke else args.max_ops

    print("=" * 72)
    print(f"{'Smoke run mode' if args.smoke else 'Paper-grade run mode'}: max_per_corpus={max_per_corpus}, min_total={min_total}, repeats=1")
    print(f"Exact simulation caps: max_qubits={max_qubits}, max_ops={max_ops}")
    print("=" * 72)

    try:
        circuits = load_corpora(data_root, max_per_corpus=max_per_corpus, max_qubits=max_qubits, max_ops=max_ops, min_total=min_total)
        write_provenance(data_root, circuits, used_synthetic_rq3=False)
    except Exception:
        write_provenance(data_root, [], used_synthetic_rq3=False)
        raise

    # Corpus composition (per-source counts) for the metadata + a standalone corpus_meta.json.
    corpus_counts: dict[str, int] = {}
    for c in circuits:
        corpus_counts[c.source or "unknown"] = corpus_counts.get(c.source or "unknown", 0) + 1

    results, backward_df, forward_df = run_experiments(circuits)
    validate_results(results)

    backward_df.to_csv("results/slice_records.csv", index=False)
    forward_df.to_csv("results/forward_records.csv", index=False)
    write_json(Path("results/tvd_distributions.json"), backward_df.to_dict(orient="records"))
    write_json(Path("results/forward_influence_records.json"), forward_df.to_dict(orient="records"))
    write_json(Path("results/corpus_meta.json"), {"total": len(circuits), "by_corpus": corpus_counts,
                                                  "max_qubits": max_qubits, "max_ops": max_ops})
    write_json(
        Path("results/run_metadata.json"),
        {
            "mode": mode,
            "rows_or_items": len(circuits),
            "repeats": 1,
            "datasets": sorted(corpus_counts.keys()),
            "corpus_counts": corpus_counts,
            "paper_grade": bool((not args.smoke) and len(circuits) >= min_total),
            "max_qubits": max_qubits,
            "max_ops": max_ops,
            "experiments": ["RQ1-E1", "RQ2-E1", "RQ3-E1"],
        },
    )
    write_json(Path("results/results.json"), results)

    tab = []
    for rq, payload in results.items():
        tab.append({"rq": rq, "method": "QPDG", "corpus": "ALL", **payload["metrics"]})
        for baseline, vals in payload["baseline_comparison"].items():
            tab.append({"rq": rq, "method": baseline, "corpus": "ALL", **vals})
    pd.DataFrame(tab).to_csv("results/TAB1.csv", index=False)

    # Per-corpus breakdown table (QASMBench / MQT Bench / VeriQBench), pooled across slicing direction.
    corpus_tab = []
    for label, payload in (results["RQ1"].get("per_corpus") or {}).items():
        corpus_tab.append({"corpus": label, "n_circuits": payload["n_circuits"], "method": "QPDG", **payload["metrics"]})
        for baseline, vals in payload["baseline_comparison"].items():
            corpus_tab.append({"corpus": label, "n_circuits": payload["n_circuits"], "method": baseline, **vals})
    if corpus_tab:
        pd.DataFrame(corpus_tab).to_csv("results/TAB_per_corpus.csv", index=False)

    print("Wrote results/results.json, results/TAB1.csv, slice/forward record files.")
    from figures_qpdg import main as fig_main
    fig_main()


if __name__ == "__main__":
    main()