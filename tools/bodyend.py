"""Where the body of the paper ends, in columns, for the page limit (10 pages = 20 columns of body).

Compiles a copy of paper/ with the marker ZZBODYENDZZ inserted before \\bibliographystyle and reports the
marker's position as full columns before it plus the fraction of its column above it. The column's text block
is taken from a full body page (page 2).
Usage: python tools/bodyend.py [PAPER_DIR]
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

paper = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "paper")
LIMIT = 20

with tempfile.TemporaryDirectory() as tmp:
    work = Path(tmp) / "paper"
    shutil.copytree(paper, work)
    tex = (work / "main.tex").read_text()
    assert tex.count("\\bibliographystyle") == 1
    (work / "main.tex").write_text(tex.replace("\\bibliographystyle", "ZZBODYENDZZ\n\\bibliographystyle"))
    subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-silent", "main.tex"], cwd=work,
                   capture_output=True)
    html = subprocess.run(["pdftotext", "-bbox", str(work / "main.pdf"), "-"], capture_output=True, text=True).stdout

pages = html.split("<page ")[1:]
width = float(re.search(r'width="([\d.]+)"', pages[0]).group(1))
words = lambda pg: [(float(a), float(b), float(c), float(d), w) for a, b, c, d, w in
                    re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', pg)]
ref = words(pages[1])
top, bottom = min(w[1] for w in ref), max(w[3] for w in ref)
for p, pg in enumerate(pages, 1):
    hit = [w for w in words(pg) if "ZZBODYENDZZ" in w[4]]
    if hit:
        x, y = hit[0][0], hit[0][1]
        col = 0 if x < width / 2 else 1
        frac = (y - top) / (bottom - top)
        body = (p - 1) * 2 + col + frac
        print(f"page {p}, column {col + 1}, {frac:.2f} down: body = {body:.2f} columns; limit {LIMIT}; "
              f"over by {body - LIMIT:.2f} columns")
        break
else:
    sys.exit("marker not found")
