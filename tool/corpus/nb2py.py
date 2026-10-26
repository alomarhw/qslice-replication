"""Notebook -> script, by reading the notebook JSON (code cells joined in order; IPython magics and shell
lines dropped). Nothing is executed. Usage: python -m tool.corpus.nb2py SRC_DIR OUT_DIR"""
import json, sys
from pathlib import Path


def convert(nb: Path) -> str:
    d = json.loads(nb.read_text(encoding="utf-8", errors="replace"))
    out = []
    for c in d.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = c.get("source", "")
        src = "".join(src) if isinstance(src, list) else src
        for ln in src.splitlines():
            s = ln.lstrip()
            out.append("" if s.startswith(("%", "!", "?")) else ln)
        out.append("")
    return "\n".join(out) + "\n"


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    n = 0
    for nb in sorted(src.rglob("*.ipynb")):
        rel = nb.relative_to(src).with_suffix(".py")
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        (dst / rel).write_text(convert(nb))
        n += 1
    print(f"{n} notebooks -> {dst}")


if __name__ == "__main__":
    main()
