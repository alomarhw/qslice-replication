#!/usr/bin/env python3
"""
Preprocess controlled-experiment outputs for the Quantum PDG slicing study.

Inputs
------
By default this script searches the input directory for CSV/JSON/JSONL files produced by
main.py/analysis.py/rp_data_runtime.py and normalizes them into analysis-ready tables.
It is intentionally schema-tolerant because generated runs may name result files differently.

Expected record granularity
---------------------------
Primary long-form table: one row per circuit x baseline/method x slice query/repeat.
Circuit-level metadata rows are merged when available.

Outputs
-------
  processed/analysis_long.csv        Long-form validated metrics table
  processed/analysis_wide.csv        One row per circuit/query with method-specific metrics pivoted
  processed/circuit_summary.csv      Circuit-level metadata and aggregate metrics
  processed/data_quality_report.json Validation report, exclusions, warnings

Usage
-----
  python preprocess_qpdg_data.py --input data --output processed
  python preprocess_qpdg_data.py --input results --output processed --strict
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

METRICS = [
    "invalid_slice_rate",
    "target_state_fidelity",
    "slice_size_fraction_of_ops",
    "forward_influence_completeness",
]
METHOD_CANONICAL = {
    "qpdg": "QPDG",
    "quantum_pdg": "QPDG",
    "quantum pdg": "QPDG",
    "naive": "Naive classical PDG",
    "naive_classical_pdg": "Naive classical PDG",
    "naive classical pdg": "Naive classical PDG",
    "def-use port": "Naive classical PDG",
    "def_use_port": "Naive classical PDG",
    "causal": "Causal classical PDG",
    "causal_classical_pdg": "Causal classical PDG",
    "causal classical pdg": "Causal classical PDG",
    "data+control light cone": "Causal classical PDG",
    "data_control_light_cone": "Causal classical PDG",
}
ALLOWED_METHODS = ["QPDG", "Naive classical PDG", "Causal classical PDG"]
NUMERIC_RANGE_0_1 = METRICS + [
    "coverage", "valid_slice_rate", "slice_ops_fraction", "completeness"
]
INTEGER_NONNEG = [
    "n_qubits", "num_qubits", "qubits", "n_ops", "num_ops", "ops", "slice_ops",
    "slice_size_ops", "target_qubit", "target_op_index", "repeat", "query_id", "parse_failures",
    "oversized", "max_qubits", "max_ops"
]

COLUMN_SYNONYMS = {
    "circuit": "circuit_id",
    "circuit_name": "circuit_id",
    "program": "circuit_id",
    "benchmark": "circuit_id",
    "file": "source_file",
    "filepath": "source_file",
    "path": "source_file",
    "method_name": "method",
    "baseline": "method",
    "pdg_type": "method",
    "algorithm": "method",
    "num_qubits": "n_qubits",
    "qubits": "n_qubits",
    "num_ops": "n_ops",
    "ops": "n_ops",
    "gate_count": "n_ops",
    "operation_count": "n_ops",
    "slice_size_ops": "slice_ops",
    "slice_n_ops": "slice_ops",
    "slice_ops_count": "slice_ops",
    "slice_fraction": "slice_size_fraction_of_ops",
    "slice_ops_fraction": "slice_size_fraction_of_ops",
    "fidelity": "target_state_fidelity",
    "target_fidelity": "target_state_fidelity",
    "invalid_rate": "invalid_slice_rate",
    "is_invalid": "invalid_slice_indicator",
    "invalid": "invalid_slice_indicator",
    "influence_completeness": "forward_influence_completeness",
    "completeness": "forward_influence_completeness",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Preprocess Quantum PDG controlled experiment outputs.")
    p.add_argument("--input", type=Path, default=Path("."), help="Directory containing raw outputs or result files")
    p.add_argument("--output", type=Path, default=Path("processed"), help="Directory for cleaned datasets")
    p.add_argument("--strict", action="store_true", help="Fail on validation warnings instead of writing outputs")
    p.add_argument("--recursive", action="store_true", default=True, help="Recursively search input directory")
    p.add_argument("--min-circuits", type=int, default=37, help="Expected minimum unique circuits for paper-grade run")
    return p.parse_args()


def flatten_json(obj: Any, parent: str = "", sep: str = "_") -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{parent}{sep}{k}" if parent else str(k)
            if isinstance(v, dict):
                items.update(flatten_json(v, key, sep=sep))
            else:
                items[key] = v
    else:
        items[parent or "value"] = obj
    return items


def read_json_records(path: Path) -> pd.DataFrame:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Try JSONL
        records = []
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(flatten_json(json.loads(line)))
                except Exception:
                    continue
        return pd.DataFrame(records)

    if isinstance(raw, list):
        return pd.DataFrame([flatten_json(x) for x in raw])
    if isinstance(raw, dict):
        # Prefer list-valued keys that look like result records.
        frames = []
        for key, value in raw.items():
            if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                df = pd.DataFrame([flatten_json(x) for x in value])
                df["_json_section"] = key
                frames.append(df)
        if frames:
            return pd.concat(frames, ignore_index=True, sort=False)
        return pd.DataFrame([flatten_json(raw)])
    return pd.DataFrame()


def discover_files(input_dir: Path, recursive: bool = True) -> List[Path]:
    patterns = ["*.csv", "*.tsv", "*.json", "*.jsonl", "*.ndjson"]
    files: List[Path] = []
    for pat in patterns:
        files.extend(input_dir.rglob(pat) if recursive else input_dir.glob(pat))
    excluded_parts = {".git", "__pycache__", "processed", "venv", ".venv"}
    return sorted([f for f in files if not excluded_parts.intersection(set(f.parts))])


def load_tables(files: Iterable[Path]) -> Tuple[pd.DataFrame, List[str]]:
    frames: List[pd.DataFrame] = []
    warnings: List[str] = []
    for path in files:
        try:
            if path.suffix.lower() == ".csv":
                df = pd.read_csv(path)
            elif path.suffix.lower() == ".tsv":
                df = pd.read_csv(path, sep="\t")
            elif path.suffix.lower() in {".json", ".jsonl", ".ndjson"}:
                df = read_json_records(path)
            else:
                continue
            if df.empty:
                continue
            df["_source_result_file"] = str(path)
            frames.append(df)
        except Exception as e:
            warnings.append(f"Could not read {path}: {e}")
    if not frames:
        return pd.DataFrame(), warnings
    return pd.concat(frames, ignore_index=True, sort=False), warnings


def snake(s: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(s).strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s.lower()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        c = snake(col)
        rename[col] = COLUMN_SYNONYMS.get(c, c)
    out = df.rename(columns=rename)
    # If duplicate names were created, coalesce left-to-right.
    if out.columns.duplicated().any():
        new = pd.DataFrame(index=out.index)
        for col in dict.fromkeys(out.columns):
            same = out.loc[:, out.columns == col]
            new[col] = same.bfill(axis=1).iloc[:, 0]
        out = new
    return out


def infer_method_from_file(row: pd.Series) -> Optional[str]:
    text = " ".join(str(row.get(c, "")) for c in ["method", "_source_result_file", "_json_section"] if c in row.index).lower()
    for key, val in METHOD_CANONICAL.items():
        if key in text:
            return val
    return None


def canonicalize_method(x: Any) -> Optional[str]:
    if pd.isna(x):
        return None
    key = str(x).strip().lower()
    key = re.sub(r"[\s\-]+", "_", key)
    if key in METHOD_CANONICAL:
        return METHOD_CANONICAL[key]
    key2 = key.replace("_", " ")
    return METHOD_CANONICAL.get(key2, str(x).strip())


def coerce_bool_indicator(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.astype(float)
    mapped = s.astype(str).str.strip().str.lower().map({
        "true": 1.0, "t": 1.0, "yes": 1.0, "y": 1.0, "1": 1.0,
        "false": 0.0, "f": 0.0, "no": 0.0, "n": 0.0, "0": 0.0,
    })
    numeric = pd.to_numeric(s, errors="coerce")
    return mapped.fillna(numeric)


def build_long_table(raw: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    warnings: List[str] = []
    df = normalize_columns(raw)

    # Identify circuit id if absent.
    if "circuit_id" not in df.columns:
        if "source_file" in df.columns:
            df["circuit_id"] = df["source_file"].astype(str).map(lambda p: Path(p).stem)
        elif "_source_result_file" in df.columns:
            df["circuit_id"] = df["_source_result_file"].astype(str).map(lambda p: Path(p).stem)
        else:
            df["circuit_id"] = np.arange(len(df)).astype(str)
            warnings.append("No circuit identifier found; generated row-index circuit_id values.")

    # Canonical method.
    if "method" in df.columns:
        df["method"] = df["method"].map(canonicalize_method)
    else:
        df["method"] = None
    missing_method = df["method"].isna()
    if missing_method.any():
        df.loc[missing_method, "method"] = df[missing_method].apply(infer_method_from_file, axis=1)

    # Create invalid_slice_rate from indicator when needed.
    if "invalid_slice_rate" not in df.columns and "invalid_slice_indicator" in df.columns:
        df["invalid_slice_rate"] = coerce_bool_indicator(df["invalid_slice_indicator"])

    # Coerce numerics.
    for col in set(METRICS + INTEGER_NONNEG + ["runtime_sec", "elapsed_sec"]):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Fill slice fraction from counts if possible.
    if "slice_size_fraction_of_ops" not in df.columns and {"slice_ops", "n_ops"}.issubset(df.columns):
        df["slice_size_fraction_of_ops"] = df["slice_ops"] / df["n_ops"].replace({0: np.nan})
    elif "slice_size_fraction_of_ops" in df.columns and df["slice_size_fraction_of_ops"].isna().any() and {"slice_ops", "n_ops"}.issubset(df.columns):
        derived = df["slice_ops"] / df["n_ops"].replace({0: np.nan})
        df["slice_size_fraction_of_ops"] = df["slice_size_fraction_of_ops"].fillna(derived)

    # If data are wide by method (e.g., qpdg_invalid_slice_rate), unpivot into long rows.
    method_metric_cols = []
    for col in df.columns:
        for metric in METRICS:
            if col.endswith("_" + metric):
                prefix = col[: -(len(metric) + 1)]
                method_metric_cols.append((col, prefix, metric))
    if method_metric_cols and df["method"].isna().all():
        id_cols = [c for c in df.columns if c not in [x[0] for x in method_metric_cols]]
        rows = []
        for prefix in sorted(set(p for _, p, _ in method_metric_cols)):
            tmp = df[id_cols].copy()
            tmp["method"] = canonicalize_method(prefix)
            for col, pfx, metric in method_metric_cols:
                if pfx == prefix:
                    tmp[metric] = df[col]
            rows.append(tmp)
        df = pd.concat(rows, ignore_index=True, sort=False)

    # Keep rows that have at least one metric or meaningful method/circuit metadata.
    present_metrics = [m for m in METRICS if m in df.columns]
    if present_metrics:
        df = df[df[present_metrics].notna().any(axis=1) | df["method"].notna()].copy()
    else:
        warnings.append("No expected metric columns found in raw files.")

    # Standard columns.
    defaults = {
        "repeat": 1,
        "query_id": np.nan,
        "target_qubit": np.nan,
        "target_op_index": np.nan,
        "source_file": np.nan,
        "n_qubits": np.nan,
        "n_ops": np.nan,
        "slice_ops": np.nan,
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    # Missing metric handling: do not impute inferential metrics; keep NA and flag.
    for m in METRICS:
        if m not in df.columns:
            df[m] = np.nan
            warnings.append(f"Metric column missing and filled with NA: {m}")
        df[f"{m}_missing"] = df[m].isna()

    # Validation clipping/flagging. Values outside [0,1] are invalid and set NA.
    for m in METRICS:
        bad = df[m].notna() & ((df[m] < 0) | (df[m] > 1))
        if bad.any():
            warnings.append(f"{bad.sum()} rows have out-of-range {m}; set to NA.")
            df.loc[bad, m] = np.nan

    for col in ["n_qubits", "n_ops", "slice_ops", "target_qubit", "target_op_index", "repeat", "query_id"]:
        if col in df.columns:
            bad = df[col].notna() & (df[col] < 0)
            if bad.any():
                warnings.append(f"{bad.sum()} rows have negative {col}; set to NA.")
                df.loc[bad, col] = np.nan

    if "slice_ops" in df.columns and "n_ops" in df.columns:
        bad = df["slice_ops"].notna() & df["n_ops"].notna() & (df["slice_ops"] > df["n_ops"])
        if bad.any():
            warnings.append(f"{bad.sum()} rows have slice_ops > n_ops; set slice_ops and slice fraction to NA.")
            df.loc[bad, ["slice_ops", "slice_size_fraction_of_ops"]] = np.nan

    # Drop exact duplicate rows.
    before = len(df)
    subset = [c for c in ["circuit_id", "method", "repeat", "query_id", "target_qubit", "target_op_index"] if c in df.columns]
    if subset:
        metric_subset = subset + METRICS
        df = df.drop_duplicates(subset=[c for c in metric_subset if c in df.columns])
    if len(df) < before:
        warnings.append(f"Dropped {before - len(df)} exact duplicate result rows.")

    # Exclusion flag rather than silent row removal.
    df["analysis_exclude"] = False
    df["analysis_exclude_reason"] = ""
    no_method = df["method"].isna() | ~df["method"].isin(ALLOWED_METHODS)
    df.loc[no_method, "analysis_exclude"] = True
    df.loc[no_method, "analysis_exclude_reason"] += "missing_or_unknown_method;"
    no_metric = df[METRICS].isna().all(axis=1)
    df.loc[no_metric, "analysis_exclude"] = True
    df.loc[no_metric, "analysis_exclude_reason"] += "no_metrics;"

    # Stable sort and column order.
    ordered = [
        "circuit_id", "source_file", "method", "repeat", "query_id", "target_qubit", "target_op_index",
        "n_qubits", "n_ops", "slice_ops",
        *METRICS,
        *[f"{m}_missing" for m in METRICS],
        "analysis_exclude", "analysis_exclude_reason", "_source_result_file",
    ]
    other = [c for c in df.columns if c not in ordered]
    df = df[[c for c in ordered if c in df.columns] + other]
    df = df.sort_values([c for c in ["circuit_id", "query_id", "repeat", "method"] if c in df.columns]).reset_index(drop=True)
    return df, warnings


def make_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    clean = long_df[~long_df["analysis_exclude"]].copy()
    if clean.empty:
        return pd.DataFrame()
    idx = [c for c in ["circuit_id", "source_file", "repeat", "query_id", "target_qubit", "target_op_index", "n_qubits", "n_ops"] if c in clean.columns]
    wide = clean.pivot_table(index=idx, columns="method", values=METRICS, aggfunc="mean")
    wide.columns = [f"{snake(method)}__{metric}" for metric, method in wide.columns]
    wide = wide.reset_index()
    return wide


def make_circuit_summary(long_df: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["circuit_id"]
    agg: Dict[str, Any] = {}
    for col in ["source_file", "n_qubits", "n_ops"]:
        if col in long_df.columns:
            agg[col] = "first"
    for m in METRICS:
        agg[m + "_mean"] = (m, "mean")
        agg[m + "_n"] = (m, "count")
    clean = long_df[~long_df["analysis_exclude"]].copy()
    if clean.empty:
        return pd.DataFrame()
    # Named aggregation mixed with regular dict is awkward; construct explicitly.
    summary = clean.groupby(group_cols).agg(
        source_file=("source_file", "first") if "source_file" in clean.columns else ("circuit_id", "first"),
        n_qubits=("n_qubits", "first") if "n_qubits" in clean.columns else ("circuit_id", "size"),
        n_ops=("n_ops", "first") if "n_ops" in clean.columns else ("circuit_id", "size"),
        n_result_rows=("method", "size"),
        n_methods=("method", "nunique"),
        invalid_slice_rate_mean=("invalid_slice_rate", "mean"),
        target_state_fidelity_mean=("target_state_fidelity", "mean"),
        slice_size_fraction_of_ops_mean=("slice_size_fraction_of_ops", "mean"),
        forward_influence_completeness_mean=("forward_influence_completeness", "mean"),
    ).reset_index()
    return summary


def quality_report(long_df: pd.DataFrame, warnings: List[str], files: List[Path], min_circuits: int) -> Dict[str, Any]:
    clean = long_df[~long_df["analysis_exclude"]] if not long_df.empty and "analysis_exclude" in long_df else pd.DataFrame()
    report: Dict[str, Any] = {
        "n_input_files": len(files),
        "input_files": [str(f) for f in files[:200]],
        "n_raw_or_long_rows": int(len(long_df)),
        "n_analysis_rows": int(len(clean)),
        "n_excluded_rows": int(long_df["analysis_exclude"].sum()) if "analysis_exclude" in long_df else 0,
        "n_unique_circuits": int(clean["circuit_id"].nunique()) if "circuit_id" in clean else 0,
        "n_unique_methods": int(clean["method"].nunique()) if "method" in clean else 0,
        "methods_observed": sorted(clean["method"].dropna().unique().tolist()) if "method" in clean else [],
        "metric_missing_counts": {m: int(clean[m].isna().sum()) for m in METRICS if m in clean},
        "warnings": warnings,
    }
    if report["n_unique_circuits"] < min_circuits:
        report["warnings"].append(
            f"Observed {report['n_unique_circuits']} unique circuits, below expected minimum {min_circuits}."
        )
    missing_methods = sorted(set(ALLOWED_METHODS) - set(report["methods_observed"]))
    if missing_methods:
        report["warnings"].append(f"Expected methods not observed: {missing_methods}")
    return report


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    files = discover_files(args.input, args.recursive)
    raw, warnings = load_tables(files)
    if raw.empty:
        report = {
            "n_input_files": len(files),
            "n_raw_or_long_rows": 0,
            "n_analysis_rows": 0,
            "warnings": warnings + ["No readable CSV/JSON/JSONL result tables found."],
        }
        (args.output / "data_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    long_df, w2 = build_long_table(raw)
    warnings.extend(w2)
    wide_df = make_wide(long_df)
    summary_df = make_circuit_summary(long_df)
    report = quality_report(long_df, warnings, files, args.min_circuits)

    long_df.to_csv(args.output / "analysis_long.csv", index=False)
    wide_df.to_csv(args.output / "analysis_wide.csv", index=False)
    summary_df.to_csv(args.output / "circuit_summary.csv", index=False)
    (args.output / "data_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    if args.strict and report.get("warnings"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
