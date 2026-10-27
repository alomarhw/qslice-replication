"""Columns of body text per section and per float, for planning cuts. Compiles a temporary copy of paper/
with a marker at the start of every \\section, \\subsection and \\paragraph*, and reports the distance in
columns between consecutive markers (floats on the same pages are included in the span they interrupt)."""
import re, shutil, subprocess, sys, tempfile
from pathlib import Path
paper = Path(__file__).resolve().parents[1] / "paper"
with tempfile.TemporaryDirectory() as tmp:
    w = Path(tmp) / "paper"; shutil.copytree(paper, w)
    names = []
    for f in sorted((w / "sections").glob("*.tex")):
        s = f.read_text()
        def mark(m):
            names.append(m.group(2)[:40]); return f"ZZM{len(names) - 1}ZZ " + m.group(0)
        s = re.sub(r"\\(section|subsection|paragraph\*)\{([^}]*)\}", lambda m: m.group(0) + f" ZZM{(names.append((m.group(1)[0] + ':' + m.group(2))[:45]) or len(names)) - 1}ZZ", s)
        f.write_text(s)
    t = (w / "main.tex").read_text().replace("\\bibliographystyle", "ZZEND\\bibliographystyle")
    (w / "main.tex").write_text(t)
    subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-silent", "main.tex"], cwd=w, capture_output=True)
    html = subprocess.run(["pdftotext", "-bbox", str(w / "main.pdf"), "-"], capture_output=True, text=True).stdout
pages = html.split("<page ")[1:]
width = float(re.search(r'width="([\d.]+)"', pages[0]).group(1))
W = lambda pg: [(float(a), float(b), x) for a, b, x in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>([^<]*)</word>', pg)]
ref = [(a, b) for a, b, _ in W(pages[1])]
top, bot = min(b for _, b in ref), max(b for _, b in ref) + 10
pos = {}
for p, pg in enumerate(pages):
    for x, y, t in W(pg):
        m = re.match(r"ZZM(\d+)ZZ", t)
        if m: pos[int(m.group(1))] = p * 2 + (x >= width / 2) + (y - top) / (bot - top)
        if t.startswith("ZZEND"): pos["end"] = p * 2 + (x >= width / 2) + (y - top) / (bot - top)
order = sorted([k for k in pos if k != "end"], key=lambda k: pos[k]) + ["end"]
for a, b in zip(order, order[1:]):
    print(f"{pos[b] - pos[a]:5.2f}  {names[a]}")
print(f"body ends at {pos['end']:.2f} columns")
