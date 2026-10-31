"""Fetch QASMBench at the commit the study used, and verify every data file of the package.

QASMBench (https://github.com/pnnl/QASMBench, BSD-style licence of Battelle Memorial Institute) is 1.3 GB, so it is
downloaded rather than shipped, into data/QASMBench-master/QASMBench-master/. Its few compressed circuits are
unpacked where they lie, as they were for the study: a .zip or .tar.gz into a folder of the archive's name without
its extension, a .qasm.gz into the .qasm beside it. Archives are read as data (regular files only, no absolute or
parent paths). Every OpenQASM file is then checked against data/qasmbench_files.sha256.tsv.
The other corpora ship in data/ and are checked against MANIFEST.sha256.tsv.

Usage:  python fetch_data.py            # fetch QASMBench, then verify everything
        python fetch_data.py --verify   # verify only
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
QB = DATA / "QASMBench-master" / "QASMBench-master"
COMMIT = "357b942396d5c2b7cbc1c229c585a6ef5ccaebac"
ZIP = f"https://codeload.github.com/pnnl/QASMBench/zip/{COMMIT}"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _safe(name: str) -> bool:
    parts = Path(name).parts
    return not Path(name).is_absolute() and ".." not in parts


def unpack(root: Path) -> None:
    for a in sorted(p for p in root.rglob("*") if p.is_file()):
        low = a.name.lower()
        if low.endswith(".zip"):
            out = a.with_suffix("")
            if not (out / ".extracted").exists():
                out.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(a) as z:
                    for m in z.infolist():
                        if not m.is_dir() and _safe(m.filename):
                            z.extract(m, out)
                (out / ".extracted").write_text("ok\n")
        elif low.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2")):
            out = a.with_suffix("").with_suffix("")
            if not (out / ".extracted").exists():
                out.mkdir(parents=True, exist_ok=True)
                with tarfile.open(a) as t:
                    for m in t.getmembers():
                        if m.isfile() and _safe(m.name):
                            t.extract(m, out, filter="data")
                (out / ".extracted").write_text("ok\n")
        elif low.endswith(".qasm.gz"):
            out = a.with_suffix("")
            if not out.exists():
                with gzip.open(a, "rb") as s, out.open("wb") as d:
                    shutil.copyfileobj(s, d)


def fetch() -> None:
    if QB.is_dir():
        return
    with tempfile.TemporaryDirectory() as tmp:
        z = Path(tmp) / "qasmbench.zip"
        print(f"downloading QASMBench @ {COMMIT[:12]} ...", flush=True)
        urllib.request.urlretrieve(ZIP, z)
        with zipfile.ZipFile(z) as zf:
            for m in zf.infolist():
                if _safe(m.filename):
                    zf.extract(m, tmp)
        QB.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(Path(tmp) / f"QASMBench-{COMMIT}"), str(QB))
    unpack(QB)


def verify() -> int:
    bad = 0
    for row in csv.DictReader(open(DATA / "qasmbench_files.sha256.tsv"), delimiter="\t"):
        p = QB / row["path"]
        if not p.is_file() or sha256(p) != row["sha256"]:
            print("MISMATCH QASMBench", row["path"])
            bad += 1
    for row in csv.DictReader(open(HERE / "MANIFEST.sha256.tsv"), delimiter="\t"):
        p = HERE / row["path"]
        if not p.is_file() or sha256(p) != row["sha256"]:
            print("MISMATCH", row["path"])
            bad += 1
    print("data verified" if not bad else f"{bad} mismatches")
    return bad


if __name__ == "__main__":
    if "--verify" not in sys.argv:
        fetch()
    sys.exit(1 if verify() else 0)
