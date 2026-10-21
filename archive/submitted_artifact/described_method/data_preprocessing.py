
#!/usr/bin/env python3
"""
preprocess.py — Data Preprocessing & Validation Pipeline
QDG Slicing Study: Quantum Dependency Graph Analysis
=======================================================
Validates, cleans, and prepares all collected metrics from the quantum
circuit benchmark study for downstream statistical analysis.
"""

import json
import math
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import zscore

# ─────────────────────────────────────────────────────────────────────────────
# 0. Configuration
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR        = Path("data")
RESULTS_DIR     = Path("results")
CLEAN_DIR       = Path("results/clean")
MANIFEST_FILE   = DATA_DIR / "fetch_manifest.json"
RAW_RESULTS     = RESULTS_DIR / "raw_results.json"   # written by main.py / analysis.py
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# Validation thresholds
TVD_RANGE          = (0.0, 1.0)
FIDELITY_RANGE     = (0.0, 1.0)
DEPTH_MIN          = 1
GATE_COUNT_MIN     = 1
QUBIT_MIN          = 1
QUBIT_MAX          = 127          # largest publicly available superconducting QPU
DENSITY_RANGE      = (0.0, 1.0)
ZSCORE_THRESHOLD   = 4.0          # flag (not drop) extreme outliers beyond ±4 σ
MISSING_THRESHOLD  = 0.30         # drop column if > 30 % values missing

STRATA            = {"S1", "S2", "S3", "other"}
REQUIRED_COLUMNS  = [
    "circuit_id", "stratum", "n_qubits", "gate_count", "circuit_depth",
    "entanglement_density", "tvd_sliced", "tvd_baseline",
    "fidelity_sliced", "fidelity_baseline",
    "simulation_time_sliced_s", "simulation_time_baseline_s",
]

# ─────────────────────────────────────────────────────────────────────────────
# 1. Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[preprocess] {msg}", flush=True)


def _warn(msg: str) -> None:
    warnings.warn(f"[preprocess] {msg}", UserWarning, stacklevel=2)


def load_raw_results(path: Path) -> pd.DataFrame:
    """Load raw JSON results produced by analysis.py / main.py."""
    if not path.exists():
        raise FileNotFoundError(
            f"Raw results file not found: {path}\n"
            "Run main.py first to generate results."
        )
    with open(path) as fh:
        data = json.load(fh)

    # Support both list-of-records and dict-of-records formats
    if isinstance(data, list):
        df = pd.DataFrame(data)
    elif isinstance(data, dict):
        # Try common wrapper keys
        for key in ("records", "results", "data", "rows"):
            if key in data and isinstance(data[key], list):
                df = pd.DataFrame(data[key])
                break
        else:
            # Flat dict keyed by circuit_id
            df = pd.DataFrame.from_dict(data, orient="index").reset_index()
            df.rename(columns={"index": "circuit_id"}, inplace=True)
    else:
        raise ValueError(f"Unexpected JSON structure in {path}")

    _log(f"Loaded {len(df)} raw records from {path}")
    return df


def load_manifest(path: Path) -> dict:
    """Load the fetch manifest for provenance checks."""
    if not path.exists():
        _warn(f"Manifest not found at {path}; skipping provenance check.")
        return {}
    with open(path) as fh:
        return json.load(fh)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Schema validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all required columns are present; add NaN columns if absent."""
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        _warn(f"Missing expected columns (will be filled with NaN): {missing_cols}")
        for col in missing_cols:
            df[col] = np.nan
    extra_cols = [c for c in df.columns if c not in REQUIRED_COLUMNS]
    if extra_cols:
        _log(f"Extra columns detected (retained): {extra_cols}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 3. Type coercion
# ─────────────────────────────────────────────────────────────────────────────

def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Cast columns to their expected dtypes; coerce errors to NaN."""
    int_cols = ["n_qubits", "gate_count", "circuit_depth"]
    float_cols = [
        "entanglement_density",
        "tvd_sliced", "tvd_baseline",
        "fidelity_sliced", "fidelity_baseline",
        "simulation_time_sliced_s", "simulation_time_baseline_s",
    ]
    str_cols = ["circuit_id", "stratum"]

    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    _log("Type coercion complete.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. Range validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clamp or nullify values outside physically meaningful ranges.
    Adds boolean flag columns for each violation.
    """
    violations = pd.DataFrame(index=df.index)

    def _check(col, lo, hi, nullify=True):
        if col not in df.columns:
            return
        mask = df[col].notna() & ((df[col] < lo) | (df[col] > hi))
        violations[f"flag_{col}_oob"] = mask
        n = mask.sum()
        if n:
            _warn(f"  {n} out-of-range values in '{col}' [{lo}, {hi}] — {'nullified' if nullify else 'flagged only'}")
        if nullify:
            df.loc[mask, col] = np.nan

    _check("tvd_sliced",                   *TVD_RANGE)
    _check("tvd_baseline",                 *TVD_RANGE)
    _check("fidelity_sliced",              *FIDELITY_RANGE)
    _check("fidelity_baseline",            *FIDELITY_RANGE)
    _check("entanglement_density",         *DENSITY_RANGE)
    _check("n_qubits",                     QUBIT_MIN, QUBIT_MAX, nullify=False)
    _check("gate_count",                   GATE_COUNT_MIN, 1e7, nullify=False)
    _check("circuit_depth",                DEPTH_MIN, 1e6, nullify=False)
    _check("simulation_time_sliced_s",     0.0, 86400.0, nullify=False)
    _check("simulation_time_baseline_s",   0.0, 86400.0, nullify=False)

    # Validate stratum membership
    bad_strata = ~df["stratum"].isin(STRATA)
    if bad_strata.any():
        _warn(f"  {bad_strata.sum()} records have unrecognised stratum values; set to 'other'.")
        df.loc[bad_strata, "stratum"] = "other"
        violations["flag_stratum_unknown"] = bad_strata

    df = pd.concat([df, violations], axis=1)
    _log(f"Range validation complete. Flag columns added: {list(violations.columns)}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 5. Duplicate detection
# ─────────────────────────────────────────────────────────────────────────────

def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate rows; warn on duplicate circuit_ids."""
    n_before = len(df)
    df = df.drop_duplicates()
    n_exact = n_before - len(df)
    if n_exact:
        _warn(f"Dropped {n_exact} exact duplicate rows.")

    dup_ids = df[df.duplicated(subset=["circuit_id"], keep=False)]["circuit_id"].unique()
    if len(dup_ids):
        _warn(
            f"{len(dup_ids)} circuit_ids appear more than once after dedup "
            f"(e.g. {dup_ids[:3]}). Keeping first occurrence."
        )
        df = df.drop_duplicates(subset=["circuit_id"], keep="first")

    _log(f"Duplicate removal: {n_before} → {len(df)} records.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 6. Missing-value handling
# ─────────────────────────────────────────────────────────────────────────────

def handle_missing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strategy:
      • Drop columns with > MISSING_THRESHOLD fraction missing.
      • For key metric columns, impute with per-stratum median (documented).
      • Add _imputed boolean flag for each imputed cell.
      • Drop rows where circuit_id or stratum is missing (non-recoverable).
    """
    # Drop rows with missing identifiers
    id_missing = df["circuit_id"].isna() | (df["circuit_id"] == "nan")
    if id_missing.any():
        _warn(f"Dropping {id_missing.sum()} rows with missing circuit_id.")
        df = df[~id_missing].copy()

    # Drop columns exceeding missing threshold
    miss_frac = df.isnull().mean()
    drop_cols = miss_frac[miss_frac > MISSING_THRESHOLD].index.tolist()
    # Never drop required identifier columns
    drop_cols = [c for c in drop_cols if c not in ("circuit_id", "stratum")]
    if drop_cols:
        _warn(f"Dropping columns with >{MISSING_THRESHOLD*100:.0f}% missing: {drop_cols}")
        df.drop(columns=drop_cols, inplace=True)

    # Per-stratum median imputation for numeric metric columns
    impute_cols = [
        c for c in [
            "tvd_sliced", "tvd_baseline",
            "fidelity_sliced", "fidelity_baseline",
            "entanglement_density",
            "simulation_time_sliced_s", "simulation_time_baseline_s",
            "n_qubits", "gate_count", "circuit_depth",
        ]
        if c in df.columns
    ]

    for col in impute_cols:
        flag_col = f"{col}_imputed"
        df[flag_col] = False
        missing_mask = df[col].isna()
        if not missing_mask.any():
            continue
        # Compute per-stratum medians
        stratum_medians = df.groupby("stratum")[col].median()
        global_median   = df[col].median()

        def _fill(row):
            if pd.isna(row[col]):
                med = stratum_medians.get(row["stratum"], global_median)
                return med if not (isinstance(med, float) and math.isnan(med)) else global_median
            return row[col]

        df.loc[missing_mask, col] = df[missing_mask].apply(_fill, axis=1)
        df.loc[missing_mask, flag_col] = True
        n_imp = missing_mask.sum()
        _log(f"  Imputed {n_imp} missing values in '{col}' via per-stratum median.")

    _log("Missing-value handling complete.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 7. Outlier flagging
# ─────────────────────────────────────────────────────────────────────────────

def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag (do NOT remove) statistical outliers using z-score within each stratum.
    Adds 'outlier_zscore' boolean column and 'outlier_cols' listing which columns
    triggered the flag.
    """
    numeric_cols = [
        "tvd_sliced", "tvd_baseline",
        "fidelity_sliced", "fidelity_baseline",
        "entanglement_density",
        "simulation_time_sliced_s", "simulation_time_baseline_s",
        "gate_count", "circuit_depth",
    ]
    numeric_cols = [c for c in numeric_cols if c in df.columns]

    df["outlier_zscore"]  = False
    df["outlier_cols"]    = ""

    for stratum, grp in df.groupby("stratum"):
        if len(grp) < 3:
            continue  # z-score meaningless for tiny groups
        sub = grp[numeric_cols].apply(pd.to_numeric, errors="coerce")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            zs = sub.apply(zscore, nan_policy="omit")
        extreme = zs.abs() > ZSCORE_THRESHOLD
        any_extreme = extreme.any(axis=1)
        df.loc[grp.index[any_extreme], "outlier_zscore"] = True
        for idx in grp.index[any_extreme]:
            local_idx = grp.index.get_loc(idx)
            flagged = extreme.iloc[local_idx]
            df.at[idx, "outlier_cols"] = ",".join(flagged[flagged].index.tolist())

    n_out = df["outlier_zscore"].sum()
    _log(f"Outlier flagging: {n_out} records flagged (|z| > {ZSCORE_THRESHOLD}) — retained for analysis.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 8. Derived / engineered features
# ─────────────────────────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived metrics used in statistical analysis."""

    # TVD improvement: positive = sliced is better (lower TVD)
    if {"tvd_sliced", "tvd_baseline"}.issubset(df.columns):
        df["tvd_delta"]            = df["tvd_baseline"] - df["tvd_sliced"]
        df["tvd_relative_change"]  = df["tvd_delta"] / df["tvd_baseline"].replace(0, np.nan)

    # Fidelity improvement: positive = sliced is better (higher fidelity)
    if {"fidelity_sliced", "fidelity_baseline"}.issubset(df.columns):
        df["fidelity_delta"]           = df["fidelity_sliced"] - df["fidelity_baseline"]
        df["fidelity_relative_change"] = df["fidelity_delta"] / df["fidelity_baseline"].replace(0, np.nan)

    # Simulation speedup ratio
    if {"simulation_time_baseline_s", "simulation_time_sliced_s"}.issubset(df.columns):
        df["speedup_ratio"] = (
            df["simulation_time_baseline_s"] /
            df["simulation_time_sliced_s"].replace(0, np.nan)
        )

    # Gate density (gates per qubit)
    if {"gate_count", "n_qubits"}.issubset(df.columns):
        df["gate_density"] = (
            df["gate_count"].astype(float) /
            df["n_qubits"].astype(float).replace(0, np.nan)
        )

    # Log-transformed depth and gate count (for regression)
    if "circuit_depth" in df.columns:
        df["log_circuit_depth"] = np.log1p(df["circuit_depth"].astype(float))
    if "gate_count" in df.columns:
        df["log_gate_count"] = np.log1p(df["gate_count"].astype(float))

    # Stratum as ordered categorical
    stratum_order = ["S1", "S2", "S3", "other"]
    df["stratum_cat"] = pd.Categorical(df["stratum"], categories=stratum_order, ordered=True)
    df["stratum_code"] = df["stratum_cat"].cat.codes   # numeric encoding for models

    _log("Feature engineering complete.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 9. Stratified corpus validation (RQ1-E1)
# ─────────────────────────────────────────────────────────────────────────────

def validate_corpus_stratification(df: pd.DataFrame) -> None:
    """Print stratification summary and assert minimum per-stratum counts."""
    _log("── Corpus Stratification Summary ──────────────────────────────")
    counts = df["stratum"].value_counts().to_dict()
    for s in ["S1", "S2", "S3", "other"]:
        _log(f"  {s}: {counts.get(s, 0)} circuits")

    # Soft assertions (warn, don't crash)
    for s in ["S1", "S2", "S3"]:
        n = counts.get(s, 0)
        if n < 4:
            _warn(f"Stratum {s} has only {n} circuits — statistical power may be limited.")

    if "entanglement_density" in df.columns:
        s1_mean = df.loc[df["stratum"] == "S1", "entanglement_density"].mean()
        _log(f"  S1 mean entanglement density: {s1_mean:.3f}")
        if not math.isnan(s1_mean) and s1_mean < 0.5:
            _warn("S1 mean entanglement density < 0.5; verify S1 labelling logic.")


# ─────────────────────────────────────────────────────────────────────────────
# 10. Provenance & manifest cross-check
# ─────────────────────────────────────────────────────────────────────────────

def cross_check_manifest(df: pd.DataFrame, manifest: dict) -> None:
    """Warn if circuit_ids in results are not traceable to the fetch manifest."""
    if not manifest:
        return
    # Manifest may list source repos; extract known filenames if available
    known_files = set()
    for entry in manifest.get("sources", []):
        for f in entry.get("files", []):
            known_files.add(Path(f).stem)

    if not known_files:
        _log("Manifest present but contains no file-level provenance; skipping cross-check.")
        return

    result_ids = set(df["circuit_id"].dropna().astype(str))
    untraced   = result_ids - known_files
    if untraced:
        _warn(f"{len(untraced)} circuit_ids not found in fetch manifest: {list(untraced)[:5]} …")
    else:
        _log("All circuit_ids traced to fetch manifest. ✓")


# ─────────────────────────────────────────────────────────────────────────────
# 11. Export clean datasets
# ─────────────────────────────────────────────────────────────────────────────

def export_clean(df: pd.DataFrame) -> None:
    """Write clean datasets: full, per-stratum, and analysis-ready subsets."""

    # Full clean dataset
    full_path = CLEAN_DIR / "circuits_clean.csv"
    df.to_csv(full_path, index=False)
    _log(f"Full clean dataset → {full_path}  ({len(df)} rows × {len(df.columns)} cols)")

    # Per-stratum splits
    for stratum in df["stratum"].unique():
        sub = df[df["stratum"] == stratum]
        out = CLEAN_DIR / f"circuits_{stratum}.csv"
        sub.to_csv(out, index=False)
        _log(f"  Stratum {stratum} → {out}  ({len(sub)} rows)")

    # Analysis-ready subset: no outliers, no imputed key metrics
    key_imputed = [c for c in df.columns if c.endswith("_imputed") and
                   any(k in c for k in ("tvd", "fidelity"))]
    imputed_mask = df[key_imputed].any(axis=1) if key_imputed else pd.Series(False, index=df.index)
    analysis_df  = df[~df["outlier_zscore"] & ~imputed_mask].copy()
    analysis_path = CLEAN_DIR / "circuits_analysis_ready.csv"
    analysis_df.to_csv(analysis_path, index=False)
    _log(f"Analysis-ready subset → {analysis_path}  ({len(analysis_df)} rows)")

    # Summary statistics JSON
    summary = {}
    for col in ["tvd_sliced", "tvd_baseline", "fidelity_sliced", "fidelity_baseline",
                "entanglement_density", "speedup_ratio", "tvd_delta", "fidelity_delta"]:
        if col in df.columns:
            s = df[col].describe().to_dict()
            summary[col] = {k: (None if (isinstance(v, float) and math.isnan(v)) else round(v, 6))
                            for k, v in s.items()}
    with open(CLEAN_DIR / "summary_stats.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    _log(f"Summary statistics → {CLEAN_DIR / 'summary_stats.json'}")

    # Preprocessing report
    report = {
        "total_records":        len(df),
        "analysis_ready":       len(analysis_df),
        "outliers_flagged":     int(df["outlier_zscore"].sum()),
        "strata_counts":        df["stratum"].value_counts().to_dict(),
        "columns_final":        list(df.columns),
        "missing_after_impute": df[REQUIRED_COLUMNS].isnull().sum().to_dict(),
    }
    with open(CLEAN_DIR / "preprocessing_report.json", "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    _log(f"Preprocessing report → {CLEAN_DIR / 'preprocessing_report.json'}")


# ─────────────────────────────────────────────────────────────────────────────
# 12. Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline() -> pd.DataFrame:
    _log("=" * 60)
    _log("QDG Slicing Study — Preprocessing Pipeline")
    _log("=" * 60)

    # Load inputs
    df       = load_raw_results(RAW_RESULTS)
    manifest = load_manifest(MANIFEST_FILE)

    # Pipeline stages
    df = validate_schema(df)
    df = coerce_types(df)
    df = remove_duplicates(df)
    df = validate_ranges(df)
    df = handle_missing(df)
    df = flag_outliers(df)
    df = engineer_features(df)

    # Validation checks
    validate_corpus_stratification(df)
    cross_check_manifest(df, manifest)

    # Export
    export_clean(df)

    _log("=" * 60)
    _log(f"Preprocessing complete. Clean data in: {CLEAN_DIR}/")
    _log("=" * 60)
    return df


if __name__ == "__main__":
    try:
        run_pipeline()
    except FileNotFoundError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        sys.exit(2)
