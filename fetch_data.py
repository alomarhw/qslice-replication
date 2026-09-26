"""Fetch and verify the three benchmark corpora used by the evaluation.

What ships in data/ (see data/README.md; hashes in MANIFEST.sha256.tsv):
  data/mqtbench/     all 78 MQT Bench circuits, as used (8 MB)
  data/veriqbench/   all 966 VeriQBench circuits, as used (36 MB)
  data/qasmbench/    only the 39 QASMBench circuits within the exact-simulation caps (<= 14 qubits,
                     <= 220 operations); this is all the RQ1-RQ3 evaluation reads

The RQ5 structural scalability study (experiments/rq5_scalability/run.py) also reads the full QASMBench suite, in
the two layouts that were on disk when Table VII was produced:
  data/QASMBench-master/QASMBench-master/   the suite at the exact commit used
  data/qasmbench/<size>/<benchmark>.qasm    134 circuits flattened from it (layout: data/qasmbench_layout.tsv)
This script downloads that commit, unpacks its .tar.gz circuits with the evaluation loader's own
extract_archives_in_place, and rebuilds both layouts, checking every flattened file's SHA-256:
  QASMBench   https://github.com/pnnl/QASMBench   commit 357b942396d5c2b7cbc1c229c585a6ef5ccaebac

MQT Bench and VeriQBench are not re-fetched, because the exact files are shipped. Their origins:
  MQT Bench   circuits exported from MQT Bench (https://github.com/cda-tum/mqt-bench); the generator
              source that was on disk is at commit a10a74b4926826d5ac8250393dfe7bd895fc5ecd
              (v2.2.2-26). The export options were not recorded, so re-generation is not guaranteed
              to be byte-identical; use the shipped files.
  VeriQBench  combinational / dynamic / sequential / variational families of the VeriQBench suite
              (https://github.com/Veri-Q/Benchmark). The upstream commit was not recorded; use the
              shipped files.

Usage:  python fetch_data.py            # fetch full QASMBench, then verify every corpus file
        python fetch_data.py --verify   # only verify shipped corpus files against MANIFEST.sha256.tsv
"""

from __future__ import annotations

import csv
import hashlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
QASMBENCH_COMMIT = "357b942396d5c2b7cbc1c229c585a6ef5ccaebac"
QASMBENCH_ZIP = f"https://codeload.github.com/pnnl/QASMBench/zip/{QASMBENCH_COMMIT}"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_shipped() -> int:
    bad = 0
    with open(HERE / "MANIFEST.sha256.tsv", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if not row["path"].startswith("data/"):
                continue
            p = HERE / row["path"]
            if not p.exists() or sha256(p) != row["sha256"]:
                print(f"MISMATCH {row['path']}")
                bad += 1
    print(f"verified shipped corpus files: {'OK' if not bad else f'{bad} mismatches'}")
    return bad


def fetch_qasmbench() -> int:
    dest = DATA / "QASMBench-master" / "QASMBench-master"
    if not dest.is_dir():
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "qasmbench.zip"
            print(f"downloading QASMBench @ {QASMBENCH_COMMIT[:12]} ...", flush=True)
            urllib.request.urlretrieve(QASMBENCH_ZIP, archive)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(tmp)
            top = Path(tmp) / f"QASMBench-{QASMBENCH_COMMIT}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(top), str(dest))
    # A few large upstream circuits are stored as .tar.gz. Unpack them exactly as the evaluation loader
    # did on first use (its unchanged extract_archives_in_place), so the flattened copies can be checked.
    sys.path.insert(0, str(HERE / "selection"))
    from qasm_loader import extract_archives_in_place
    extract_archives_in_place(DATA / "QASMBench-master")
    bad = 0
    with open(DATA / "qasmbench_layout.tsv", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    for row in rows:
        src, target = dest / row["upstream_path"], HERE / row["package_path"]
        if not src.is_file() or sha256(src) != row["sha256"]:
            print(f"MISMATCH upstream {row['upstream_path']}")
            bad += 1
            continue
        if target.exists() and sha256(target) != row["sha256"]:
            print(f"MISMATCH shipped {row['package_path']}")
            bad += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(src, target)
    print(f"QASMBench @ {QASMBENCH_COMMIT[:12]}: {len(rows) - bad}/{len(rows)} circuits verified in data/qasmbench")
    return bad


if __name__ == "__main__":
    bad = 0 if "--verify" in sys.argv else fetch_qasmbench()
    bad += verify_shipped()
    sys.exit(1 if bad else 0)
