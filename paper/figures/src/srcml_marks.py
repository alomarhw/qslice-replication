"""How the figures mark srcML: the text of srcML's markup as rows of tokens, each token marked by what the quantum
layer reads in it (gate names, qubit arguments, bit arguments and conditions, loops, positions). Used by
make_fig_b_tool.py. Joining a figure's rows gives srcML's text back.
"""

from __future__ import annotations

import re

WRAP = 109  # display columns before a row is wrapped
CH = 0.1510  # width of one srcML character (cm), 9pt
GATES = ("cx", "measure", "x")



def tex(s: str) -> str:
    return (s.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("{", r"\{").replace("}", r"\}")
            .replace("#", r"\#").replace("%", r"\%").replace("&", r"\&").replace("~", r"\textasciitilde{}"))


COMMENT = re.compile(r"\s*<comment type=\"line\"[^>]*>[^<]*</comment>")
POS = re.compile(r' pos:(?:start|end)="[^"]*"')



QUBIT_INDEX_IS_D = False  # make_fig_b_tool.py: an index into a qubit argument stays a qubit argument (d)


def marked_tokens(shown: str):
    """(token, mark) over a fragment; marks as in the module docstring."""
    toks = re.findall(r"<[^>]+>|[^<]+", shown)
    out, lists, depth, in_index = [], [], 0, 0
    callee = None
    for i, t in enumerate(toks):
        m = None
        if t.startswith("<"):
            if t.startswith("<for"):
                m = "a"
            elif t.startswith("<with"):
                m = "f"
            if "pos:start" in t:
                m = "g"
            if t == "<argument_list>":
                lists.append({"callee": callee, "arg": -1, "depth": depth})
            elif t == "</argument_list>":
                lists.pop()
            elif t == "<argument>":
                depth += 1
                if lists and depth == lists[-1]["depth"] + 1:
                    lists[-1]["arg"] += 1
            elif t == "</argument>":
                depth -= 1
            elif t == "<index>":
                in_index += 1
            elif t == "</index>":
                in_index -= 1
        else:
            word = t.strip("(),:[] ")
            if word and toks[i - 1] == "<name>" and i + 1 < len(toks) and toks[i + 1] == "</name>":
                callee = word
            if word and not t.isspace():
                nxt = toks[i + 1:i + 4]
                if word == "for" and toks[i - 1].startswith("<for"):
                    m = "a"  # the <for> tag carries the position (g), so the keyword carries a
                elif word in GATES + ("if_test",) and nxt[:2] == ["</name>", "</name>"] and nxt[2] == "<argument_list>":
                    m = "c" if word in GATES else "f"
                elif lists:
                    top = lists[-1]
                    if top["callee"] == "range":
                        m = "b"
                    elif top["callee"] == "if_test":
                        m = "e" if word == "clbits" or in_index else None  # the bit, not qc or the value
                    elif top["callee"] == "measure":
                        m = "d" if top["arg"] == 0 else "e"
                    elif top["callee"] in GATES:
                        m = "d"
                if in_index and m and not (QUBIT_INDEX_IS_D and m == "d"):
                    m = "e"
        out.append((t, m))
    return out


def render(row_tokens, state) -> str:
    """A display row; the letter of a mark is printed on the first token of each run of that mark."""
    out = []
    for t, m in row_tokens:
        if t.startswith("<"):
            if m == "g":
                p = re.search(r'pos:start="[^"]*"', t).group(0)
                body = r"\textcolor{tagC}{" + tex(t).replace(tex(p), r"\hlbox{" + tex(p) + "}") + "}"
            else:
                body = r"\textcolor{tagC}{" + tex(t) + "}"
        else:
            body = r"\textcolor{idC}{\bfseries " + tex(t) + "}"
        if m:
            body = r"\hlbox{" + body + "}" if m != "g" else body
            if m != state["last"]:
                body += r"\hlm{" + m + "}"
            state["last"] = m
        elif not t.startswith("<") and re.search(r"\w", t):
            state["last"] = None
        out.append(body)
    return "".join(out)


def rows_of(shown: str):
    """Display rows (indent, tokens, first-of-source-line) whose join gives `shown` back."""
    toks = []
    for t, m in marked_tokens(shown):
        for k, part in enumerate(t.split("\n")):
            if k:
                toks.append(("\n", None))
            if part:
                toks.append((part, m))
    rows, cur, indent, first = [], [], 0, True

    def width(ts):
        return sum(len(t) for t, _ in ts)
    for t, m in toks:
        if t == "\n":
            rows.append((indent, cur, first))
            cur, first, indent = [], True, 0
            continue
        if not cur and first and not t.startswith("<") and t.strip() == "":
            indent = len(t)
            continue
        if not cur and first and not t.startswith("<") and t != t.lstrip(" "):
            indent = len(t) - len(t.lstrip(" "))
            t = t.lstrip(" ")
        if cur and width(cur) + len(t) > WRAP - indent:
            rows.append((indent, cur, first))
            cur, first = [], False
        cur.append((t, m))
    rows.append((indent, cur, first))
    rebuilt = "\n".join(" " * ind + "".join(t for t, _ in ts) if fs else "\x00" + "".join(t for t, _ in ts)
                        for ind, ts, fs in rows).replace("\n\x00", "")
    assert rebuilt == shown, "display rows do not reproduce srcML"
    return rows
