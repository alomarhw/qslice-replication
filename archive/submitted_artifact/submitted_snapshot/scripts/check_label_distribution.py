"""Auto-generated data validation script (the toolkit Data Processor lane)."""

import csv, json, os, sys
from pathlib import Path

PROCESSED = Path("data/processed")
REPORTS = Path("data/reports"); REPORTS.mkdir(parents=True, exist_ok=True)

def _load_rows():
    """Yield dict rows from the first CSV/JSONL under data/processed (pandas not required)."""
    files = sorted(list(PROCESSED.glob("*.csv")) + list(PROCESSED.glob("*.jsonl")))
    if not files:
        print("no processed data files found under data/processed", file=sys.stderr); return []
    path = files[0]
    if path.suffix == ".jsonl":
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    with path.open() as f:
        return list(csv.DictReader(f))

LABEL = "label"

def main():
    rows = _load_rows()
    counts = {}
    for r in rows:
        counts[str(r.get(LABEL))] = counts.get(str(r.get(LABEL)), 0) + 1
    total = sum(counts.values()) or 1
    dist = {k: v / total for k, v in counts.items()}
    degenerate = len(counts) <= 1 or (counts and max(dist.values()) > 0.99)
    report = {"label": LABEL, "counts": counts, "distribution": dist,
              "degenerate": degenerate, "ok": not degenerate}
    (REPORTS / "label_distribution.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
