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

ID_FIELD = null

def main():
    rows = _load_rows()
    keys = [str(r.get(ID_FIELD)) if ID_FIELD else json.dumps(r, sort_keys=True, default=str) for r in rows]
    seen, dups = set(), 0
    for k in keys:
        if k in seen: dups += 1
        seen.add(k)
    report = {"rows": len(rows), "unique": len(seen), "duplicates": dups, "ok": dups == 0}
    (REPORTS / "duplicates.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
