"""Step 1 of the OpenQASM 2 front-end validation: every OpenQASM 2 file of the corpora is marked up, the markup
parsed as XML, and its text compared with the file byte for byte (srcML's lossless property).
-> results/icpc/qasm_srcml/lossless.csv (file, bytes, ok, seconds, error)"""
import csv, glob, os, re, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tool.qasm_srcml import unit_parts, QasmSyntaxError  # noqa: E402

files = sorted({os.path.realpath(f) for d in ("../qslice-icpc/data", "data") for f in glob.glob(str(ROOT / d) + "/**/*.qasm", recursive=True)})
out = ROOT / "experiments/results/icpc/qasm_srcml/lossless.csv"
with open(out, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["file", "bytes", "version", "ok", "seconds", "error"])
    for f in files:
        t = open(f, errors="replace", newline="").read()
        m = re.search(r"OPENQASM\s+([\d.]+)", t)
        ver = m.group(1) if m else "none"
        if ver.startswith("3"):
            w.writerow([f, len(t), ver, "", "", "OpenQASM 3, out of scope"]); continue
        t0 = time.time()
        try:
            parts = unit_parts(t, f)
            head = next(parts)
            got = []
            if len(t) < 20_000_000:
                x = head + "".join(parts)
                got = "".join(ET.fromstring(x.encode()).itertext())
                ok = got == t
            else:                                   # stream: check each statement's text in turn
                pieces = [head]
                ok = True; acc = []
                for s in parts:
                    acc.append("".join(ET.fromstring(("<w xmlns:pos='p' xmlns='%s'>" % "http://www.srcML.org/srcML/src") + s.replace("</unit>", "") + "</w>").itertext()))
                ok = "".join(acc) == t
            w.writerow([f, len(t), ver, ok, f"{time.time() - t0:.3f}", ""])
        except QasmSyntaxError as e:
            w.writerow([f, len(t), ver, False, f"{time.time() - t0:.3f}", str(e)[:200]])
        except Exception as e:
            w.writerow([f, len(t), ver, False, f"{time.time() - t0:.3f}", f"{type(e).__name__}: {str(e)[:200]}"])
        fh.flush()
print("done", out)
