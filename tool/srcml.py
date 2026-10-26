"""srcML access: parse a Python file with positions and read elements (srcML 1.1, Python)."""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

NS = "http://www.srcML.org/srcML/src"
POS = "http://www.srcML.org/srcML/position"
S = "{%s}" % NS


class SrcMLError(Exception):
    pass


def parse_file(path: Path) -> ET.Element:
    r = subprocess.run(["srcml", "--position", "-l", "Python", str(path)], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise SrcMLError(f"srcml failed on {path}: {r.stderr.strip()[:300]}")
    return ET.fromstring(r.stdout)


def tag(e: ET.Element) -> str:
    return e.tag.replace(S, "")


def text(e: Optional[ET.Element]) -> str:
    """The exact source text of an element (srcML keeps every character of the source)."""
    return "".join(e.itertext()) if e is not None else ""


def line(e: ET.Element) -> int:
    p = e.get("{%s}start" % POS)
    if p:
        return int(p.split(":")[0])
    for c in e.iter():
        p = c.get("{%s}start" % POS)
        if p:
            return int(p.split(":")[0])
    return 0


def end_line(e: ET.Element) -> int:
    p = e.get("{%s}end" % POS)
    return int(p.split(":")[0]) if p else line(e)


def child(e: ET.Element, name: str) -> Optional[ET.Element]:
    return e.find(S + name)


def children(e: ET.Element, name: str):
    return e.findall(S + name)


def statements(block: ET.Element):
    """The statements of a <unit> or a <block>: the children of its <block_content>, or of the unit itself."""
    bc = block.find(S + "block_content")
    for c in (bc if bc is not None else block):
        if tag(c) not in ("comment",):
            yield c
