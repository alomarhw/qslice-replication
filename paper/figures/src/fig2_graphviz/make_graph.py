#!/usr/bin/env python3
"""Lay out and route the Fig. 2(b) dependence graph with Graphviz, then emit TikZ.

Usage:  python3 make_graph.py [--spec graph_spec.json] [--out-dir DIR] [--no-compile]

Reads graph_spec.json (default: next to this script) and preamble.tex (next to this
script), writes into --out-dir (default: this script's folder):
  graph.dot, graph_graphviz_cpdg.dot   the two Graphviz inputs
  graph_body.tikz                      tikzpicture contents only, for \\input
  graph_graphviz.tex/.pdf/.png         standalone check rendering

Layout: dot (rankdir=TB, compound clusters). The classical-PDG-only edges are left out
of the dot run, so they cannot move anything, and are routed afterwards on the frozen
layout with neato -n2.
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- geometry
TT_EM = 0.5            # monospace char width in em
SUB_EM = 0.47          # Times italic average char width in em (digits are 0.5)
LBL_PT, LBL_BL = 8.2, 8.6
SUB_PT, SUB_BL = 6.9, 7.3
CL_PT = 7.6            # the preamble's cl style sets classical statements at 7.6pt
PADX, PADY = 3.0, 1.4  # inner padding, TeX pt
TEXPT_PER_IN = 72.27
BP_PER_IN = 72.0
CM_PER_IN = 2.54
MAX_W_CM, MAX_H_CM = 10.6, 11.5

# Representative head node for each classical edge that ends on a loop box (lhead
# clips the spline at the box border, so the node only decides where it lands).
HEADS = {('cqc', 'cluster_layer0'): 'm2', ('cqc', 'cluster_layer1'): 'm12',
         ('cfor', 'cluster_layer0'): 'm0', ('cfor', 'cluster_layer1'): 'm8',
         ('crng', 'cluster_layer0'): 'm0', ('crng', 'cluster_layer1'): 'm9'}

# Waypoints: invisible point nodes a spec edge is routed through (its dot legs are
# joined back into one path). They pin the side an edge passes on, which dot's
# mincross otherwise decides unstably once clusters are involved:
#   w712       keeps cx q1,q2 -> ry q2 (iter 1) inside the layer-1 box, right of its label
#   w68/w1418  keep the q0 quantum edges straight down the q0 column
#   'flat'/'flatL'  final leg on the head's rank, entering the box horizontally
#                   from the right/left side
WAYPOINTS = {('m7', 'm12'): ('w712', 'cluster_layer1', None),
             ('m6', 'm8'): ('w68', 'cluster_layer0', 'q0'),
             ('m14', 'm18'): ('w1418', 'cluster_layer1', 'q0'),
             ('cqc', 'cluster_layer1'): [('wqc2', None, None, 'flatL')],
             ('cfor', 'cluster_layer1'): [('wfor2', None, None, 'flat')],
             ('crng', 'cluster_layer1'): [('wrng2', None, None, 'flat')]}
WP_ROWS = [('lbl_cluster_layer1', 'w712', 'm10', 'm8'), ('m15', 'w1418')]
CPDG_PORTS = {('m1', 'm8'): ('e', 'ne'), ('m9', 'm18'): ('e', 'ne'), ('m6', 'm10'): ('sw', 'ne')}
EXTRA = {('cfor', 'cluster_layer1'): ['tailport=e']}

NODESEP, RANKSEP = 0.13, 0.09   # inches
CMARGIN = 10                    # cluster margin, bp
CPDG_ESEP = 1                   # neato obstacle margin for the cpdg edges, bp

PARTS = {}   # spec edge id -> dot edge ids it was split into ('~' = reversed leg)


def tex_esc(s):
    return s.replace('_', r'\_')


def text_width(label, sub, lpt=None):
    w = max(len(label) * TT_EM * (lpt or LBL_PT), len(sub) * SUB_EM * SUB_PT)
    return w + 2 * PADX


def node_size(n):
    """Return (width, height) in TeX pt for a spec node."""
    lab = re.sub(r'\\,\\textrightarrow\\,', ' > ', n['label_tex'])  # arrow ~ 3 chars
    sub = n['sub_tex'].replace('--', '-')
    return text_width(lab, sub), LBL_BL + SUB_BL + 2 * PADY


def bp2cm(v):
    return v / BP_PER_IN * CM_PER_IN


def tp2cm(v):
    return v / TEXPT_PER_IN * CM_PER_IN


def qubit_group(n):
    lab = n['label']
    if lab.startswith('cx'):
        return 'g01' if 'q0,q1' in lab else 'g12'
    m = re.search(r'q(\d)', lab)
    return 'q' + m.group(1) if m else None


# ---------------------------------------------------------------- build dot
def emit_split(L, a, b, tgt, attrs, name):
    """Route spec edge a->b through invisible waypoint(s); False if it has none."""
    attrs = attrs + EXTRA.get((a, b), [])
    wp = WAYPOINTS.get((a, b))
    if not wp:
        return False
    wps = wp if isinstance(wp, list) else [wp]
    flat = len(wps[-1]) > 3 and wps[-1][3] == 'flat'
    flat_left = len(wps[-1]) > 3 and wps[-1][3] == 'flatL'
    for w, cluster, group in [x[:3] for x in wps]:
        decl = '%s [shape=point, width=0.01, height=0.01, style=invis%s];' % (
            w, ', group=%s' % group if group else '')
        L.append('  subgraph %s { %s }' % (cluster, decl) if cluster else '  ' + decl)
    first = [x for x in attrs if not x.startswith('lhead') and not x.startswith('headport')]
    mid = [x for x in first if not x.startswith('tailport')]
    second = [x for x in attrs if not x.startswith('tailport')]
    chain = [a] + [x[0] for x in wps]
    ids = []
    for j, (u, w) in enumerate(zip(chain, chain[1:])):
        ids.append('%s_%d' % (name, j))
        L.append('  %s -> %s [%s];' % (u, w, ', '.join((first if j == 0 else mid) +
                                                       ['id=' + ids[-1], 'arrowhead=none'])))
    w = chain[-1]
    ids.append('%s_%d' % (name, len(chain) - 1))
    if flat:
        # last waypoint on the head's rank, right of the box: the last leg is a
        # horizontal edge drawn backwards (tgt -> w, dir=back), entering from the side
        second = [x.replace('lhead', 'ltail') for x in second if not x.startswith('weight')]
        L.append('  %s -> %s [%s];' % (tgt, w, ', '.join(second + ['id=' + ids[-1], 'dir=back',
                                                                   'arrowhead=none', 'arrowtail=normal'])))
        L.append('  { rank=same; %s; %s; }' % (tgt, w))
        ids[-1] = '~' + ids[-1]
    else:
        L.append('  %s -> %s [%s];' % (w, tgt, ', '.join(second + ['id=' + ids[-1]])))
        if flat_left:  # waypoint beside the box on the left, horizontal last leg
            L.append('  { rank=same; %s; %s; }' % (w, tgt))
    PARTS[name] = ids
    return True


def build(spec):
    PARTS.clear()
    nodes = {n['id']: n for n in spec['nodes']}
    cls = {c['id']: c for c in spec['classical_nodes']}
    sizes = {nid: node_size(n) for nid, n in nodes.items()}
    for cid, c in cls.items():
        sizes[cid] = (text_width(tex_esc(c['label']), 'line %d' % c['line'], CL_PT),
                      LBL_BL + SUB_BL + 2 * PADY)

    def nd(nid, extra=''):
        w, h = sizes[nid]
        return '  %s [width=%.4f, height=%.4f%s];' % (nid, w / TEXPT_PER_IN, h / TEXPT_PER_IN, extra)

    L = ['digraph G {',
         '  graph [rankdir=TB, compound=true, newrank=true, splines=spline, nodesep=%.3f, '
         'ranksep="%.3f", remincross=false, margin=0, pad=0, outputorder=edgesfirst, '
         'fontname="Courier", fontsize=7];' % (NODESEP, RANKSEP),
         '  node [shape=box, fixedsize=true, label="", margin=0];',
         '  edge [arrowsize=0.34, arrowhead=normal, penwidth=0.6];']

    # classical statements, two rows above the clusters
    L.append('  { rank=same; cn; cly; crng; }')
    L.append('  { rank=same; cqc; cfor; }')
    for cid in ['cn', 'cly', 'crng', 'cqc', 'cfor']:
        L.append(nd(cid))

    # Columns, left to right: q2 | q1 | q0 (q0 on the right, above the criterion).
    # q2's chain starts one rank lower; the freed top-left cell holds the box label.
    ranks = {'cluster_layer0': [('m2', 'm0'), ('m4', 'm3', 'm1')],
             'cluster_layer1': [('m10', 'm8'), ('m12', 'm11', 'm9')]}
    below = {'cluster_layer0': 'm4', 'cluster_layer1': 'm12'}
    lane_top = {'cluster_layer0': 'm0', 'cluster_layer1': 'm14'}
    for cname, cl in spec['clusters'].items():
        L.append('  subgraph %s {' % cname)
        L.append('    graph [label="", margin=%.2f, style=dashed];' % CMARGIN)
        for nid in sorted(cl['nodes'], key=lambda i: nodes[i]['program_order']):
            g = qubit_group(nodes[nid])
            if g == 'g01':
                g = 'q0'   # cx q0,q1 sits in the q0 column
            L.append('  ' + nd(nid, ', group=%s' % g if g else ''))
        # placeholder that reserves the top-left cell for the box label
        ph = 'lbl_' + cname
        L.append('    %s [style=invis, group=q2, width=%.4f, height=%.4f];' %
                 (ph, sizes['m4'][0] / TEXPT_PER_IN, sizes['m4'][1] / TEXPT_PER_IN))
        for r in [(ph,) + ranks[cname][0]] + ranks[cname][1:]:
            L.append('    { rank=same; %s; }' % '; '.join(r))
            for a, b in zip(r, r[1:]):
                L.append('    %s -> %s [style=invis];' % (a, b))
        if cname == 'cluster_layer0':
            # mirrors the waypoint w712 of layer 1, so both boxes share their columns
            L.append('    sp0 [shape=point, width=0.01, height=0.01, style=invis];')
            L.append('    { rank=same; m4; sp0; m3; } m4 -> sp0 [style=invis]; sp0 -> m3 [style=invis];')
        # empty lane right of the q0 column, for the classical-PDG-only edges
        top = lane_top[cname]
        L.append('    lane_%s [shape=point, width=0.01, height=0.01, style=invis];' % cname)
        L.append('    { rank=same; %s; lane_%s; } %s -> lane_%s [style=invis, minlen=1];'
                 % (top, cname, top, cname))
        L.append('    %s -> %s [style=invis, weight=20];' % (ph, below[cname]))
        L.append('  }')

    row = spec['after_loops_row']
    L.append('  { rank=same; %s; }' % '; '.join(row))
    for nid in row:
        L.append(nd(nid, ', group=q0' if nid == 'm18' else ''))
    L.append('  m15 -> m16 [style=invis, weight=0];')
    L.append('  cn -> cly [style=invis]; cly -> crng [style=invis];')
    L.append('  cqc -> cfor [style=invis];')

    # spec edges
    eid = 0
    emap = {}
    for e in spec['edges']:
        a, b, k = e['src'], e['dst'], e['kind']
        name = 'e%d' % eid
        eid += 1
        emap[name] = (a, b, k, None)
        if k == 'cpdg_only':
            continue  # routed afterwards on the frozen layout, see route_cpdg()
        same_q = qubit_group(nodes[a]) == qubit_group(nodes[b])
        in_q0 = {qubit_group(nodes[a]), qubit_group(nodes[b])} <= {'q0', 'g01'}
        attrs = ['weight=%d' % (8 if (same_q or in_q0) else 2)]
        if k == 'control':
            attrs.append('weight=1')
        if emit_split(L, a, b, b, attrs, name):
            continue
        attrs += EXTRA.get((a, b), []) + ['id=%s' % name]
        L.append('  %s -> %s [%s];' % (a, b, ', '.join(attrs)))

    # classical edges; cluster heads go to a representative node, clipped by lhead
    for e in spec['classical_edges']:
        a, b, k = e['src'], e['dst'], e['kind']
        lhead = None
        if b in spec['clusters']:
            lhead = b
            tgt = HEADS[(a, b)]
            attrs = ['lhead=%s' % b, 'weight=%d' % (1 if b == 'cluster_layer1' else 2)]
        else:
            tgt = b
            attrs = ['weight=3']
        name = 'e%d' % eid
        eid += 1
        emap[name] = (a, b, k, lhead)
        if emit_split(L, a, b, tgt, attrs, name):
            continue
        attrs += EXTRA.get((a, b), []) + ['id=%s' % name]
        L.append('  %s -> %s [%s];' % (a, tgt, ', '.join(attrs)))

    # rows that fix the left-to-right order of waypoints and real nodes
    for row in WP_ROWS:
        L.append('  { rank=same; %s; }' % '; '.join(row))
        for u, w in zip(row, row[1:]):
            L.append('  %s -> %s [style=invis];' % (u, w))
    L.append('}')
    return '\n'.join(L) + '\n', sizes, emap


# ---------------------------------------------------------------- cpdg pass
def route_cpdg(lay, emap, cpdg_dot):
    """Route the classical-PDG-only edges on the frozen dot layout with neato -n2.
    Every node, label placeholder and waypoint is an obstacle at its dot position."""
    L = ['digraph R {',
         '  graph [splines=true, outputorder=edgesfirst, esep="+%s"];' % CPDG_ESEP,
         '  node [shape=box, fixedsize=true, label=""];',
         '  edge [arrowsize=0.34];']
    for o in lay['objects']:
        if 'pos' not in o or o['name'].startswith('lane_'):
            continue
        L.append('  "%s" [pos="%s!", width=%s, height=%s];' % (o['name'], o['pos'], o['width'], o['height']))
    for name, (a, b, k, _) in emap.items():
        if k == 'cpdg_only':
            ports = CPDG_PORTS.get((a, b))
            pa = ', tailport=%s, headport=%s' % ports if ports else ''
            L.append('  %s -> %s [id=%s%s];' % (a, b, name, pa))
    L.append('}')
    src = '\n'.join(L) + '\n'
    open(cpdg_dot, 'w').write(src)
    r = json.loads(subprocess.run(['neato', '-n2', '-Tjson'], input=src, check=True,
                                  capture_output=True, text=True).stdout)
    lay['edges'] = [e for e in lay.get('edges', [])
                    if emap.get(e.get('id'), ('', '', ''))[2] != 'cpdg_only']
    lay['edges'] += [dict(id=e['id'], pos=e['pos']) for e in r['edges']]


# ---------------------------------------------------------------- dot -> TikZ
def parse_pos(pos):
    end = start = None
    pts = []
    for tok in pos.split():
        if tok.startswith('e,'):
            _, x, y = tok.split(',')
            end = (float(x), float(y))
        elif tok.startswith('s,'):
            _, x, y = tok.split(',')
            start = (float(x), float(y))
        else:
            x, y = tok.split(',')
            pts.append((float(x), float(y)))
    return start, pts, end


def smooth_join(A, B):
    """Join two cubic legs at their common waypoint with G1 continuity."""
    J = ((A[-1][0] + B[0][0]) / 2, (A[-1][1] + B[0][1]) / 2)
    ta = (J[0] - A[-2][0], J[1] - A[-2][1])
    tb = (B[1][0] - J[0], B[1][1] - J[1])
    na = max(1e-6, (ta[0] ** 2 + ta[1] ** 2) ** .5)
    nb = max(1e-6, (tb[0] ** 2 + tb[1] ** 2) ** .5)
    d = (ta[0] / na + tb[0] / nb, ta[1] / na + tb[1] / nb)
    nd_ = max(1e-6, (d[0] ** 2 + d[1] ** 2) ** .5)
    d = (d[0] / nd_, d[1] / nd_)
    A[-1] = J
    A[-2] = (J[0] - d[0] * na, J[1] - d[1] * na)
    B[0] = J
    B[1] = (J[0] + d[0] * nb, J[1] + d[1] * nb)


def emit_body(spec, lay, sizes, emap):
    """Return the tikzpicture contents (lines), drawn node ids, drawn edges.
    Origin: top-left corner of the graph's bounding box; y grows upwards (negative)."""
    nodes = {n['id']: n for n in spec['nodes']}
    cls = {c['id']: c for c in spec['classical_nodes']}
    bb = [float(v) for v in lay['bb'].split(',')]
    H = bb[3]

    def P(x, y):
        return '(%.3f,%.3f)' % (bp2cm(x), bp2cm(y - H))

    out = []
    objs = lay['objects']
    # loop boxes
    for o in objs:
        if o.get('name', '').startswith('cluster_'):
            x0, y0, x1, y1 = [float(v) for v in o['bb'].split(',')]
            out.append(r'\draw[loopbox] %s rectangle %s;' % (P(x0, y0), P(x1, y1)))
            out.append(r'\node[boxlbl, anchor=north west] at %s {%s};' %
                       (P(x0 + 2.0, y1 - 1.6), spec['clusters'][o['name']]['label']))
    # edges (below the nodes), lightest kind first
    style = {'data': 'dataE', 'control': 'controlE', 'quantum': 'quantumE', 'cpdg_only': 'cpdgE'}
    order = {'cpdg_only': 0, 'data': 1, 'control': 2, 'quantum': 3}
    bypart = {e['id']: e for e in lay['edges'] if 'id' in e}
    edges = [e for e in lay['edges'] if e.get('id') in emap]
    edges += [dict(id=name, parts=parts) for name, parts in PARTS.items()]
    edges.sort(key=lambda e: order[emap[e['id']][2]])
    drawn_edges = []
    for e in edges:
        a, b, k, _ = emap[e['id']]
        segs, tip = [], None
        for part in e.get('parts') or [None]:
            if part is None:
                start, pts, end = parse_pos(e['pos'])
            elif part.startswith('~'):
                start, pts, end = parse_pos(bypart[part[1:]]['pos'])
                pts, start, end = pts[::-1], end, start
            else:
                start, pts, end = parse_pos(bypart[part]['pos'])
            assert (len(pts) - 1) % 3 == 0, pts
            segs.append(pts)
            tip = end
        for j in range(1, len(segs)):
            smooth_join(segs[j - 1], segs[j])
        pts = [segs[0][0]]
        for sg in segs:
            pts += sg[1:]
        path = P(*pts[0])
        for i in range(1, len(pts), 3):
            path += ' .. controls %s and %s .. %s' % (P(*pts[i]), P(*pts[i + 1]), P(*pts[i + 2]))
        if tip is not None:
            path += ' -- %s' % P(*tip)   # straight last bit; the TikZ arrow tip ends here
        out.append(r'\draw[%s] %s;' % (style[k], path))
        drawn_edges.append((a, b, k))
    # nodes
    drawn_nodes = []
    for o in objs:
        nid = o.get('name')
        if nid not in sizes or 'pos' not in o:
            continue
        x, y = [float(v) for v in o['pos'].split(',')]
        w, h = sizes[nid]
        assert abs(float(o['width']) * TEXPT_PER_IN - w) < 0.6, (nid, o['width'], w)
        if nid in nodes:
            n = nodes[nid]
            st = n['style'] + (', crit' if n['criterion_last_write'] else '')
            lab, sub, fpt = n['label_tex'], n['sub_tex'], LBL_PT
        else:
            c = cls[nid]
            st, lab, sub, fpt = 'cl', tex_esc(c['label']), 'line %d' % c['line'], CL_PT
        out.append(r'\node[%s, inner sep=0pt, minimum width=%.3fcm, minimum height=%.3fcm, '
                   r'font=\ttfamily\fontsize{%.1f}{%.1f}\selectfont] (%s) at %s '
                   r'{%s\\[-0.6pt]{\rmfamily\itshape\fontsize{%.1f}{%.1f}\selectfont %s}};' %
                   (st, tp2cm(w), tp2cm(h), fpt, LBL_BL, nid, P(x, y), lab, SUB_PT, SUB_BL, sub))
        drawn_nodes.append(nid)
    # summary note, centred under the graph
    out.append(r'\node[font=\footnotesize, align=center, anchor=north, inner sep=0pt] '
               r'at (%.3f,%.3f) {%s};' % (bp2cm((bb[0] + bb[2]) / 2), -bp2cm(H) - 0.22,
                                          spec['summary_note_tex']))
    return out, drawn_nodes, drawn_edges


def check(spec, drawn_nodes, drawn_edges):
    want_nodes = sorted([n['id'] for n in spec['nodes']] + [c['id'] for c in spec['classical_nodes']])
    assert len(set(drawn_nodes)) == len(drawn_nodes), 'node drawn twice'
    assert sorted(drawn_nodes) == want_nodes, (sorted(drawn_nodes), want_nodes)
    want = collections.Counter((e['src'], e['dst'], e['kind'])
                               for e in spec['edges'] + spec['classical_edges'])
    got = collections.Counter(drawn_edges)
    assert got == want, ('extra', got - want, 'missing', want - got)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', default=os.path.join(HERE, 'graph_spec.json'))
    ap.add_argument('--out-dir', default=HERE)
    ap.add_argument('--no-compile', action='store_true')
    args = ap.parse_args()
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    spec = json.load(open(args.spec))
    preamble = open(os.path.join(HERE, 'preamble.tex')).read()
    assert preamble.rstrip().endswith(r'\begin{document}')

    dot_src, sizes, emap = build(spec)
    dotfile = os.path.join(out_dir, 'graph.dot')
    open(dotfile, 'w').write(dot_src)
    lay = json.loads(subprocess.run(['dot', '-Tjson', dotfile], check=True,
                                    capture_output=True, text=True).stdout)
    route_cpdg(lay, emap, os.path.join(out_dir, 'graph_graphviz_cpdg.dot'))
    body, dn, de = emit_body(spec, lay, sizes, emap)
    check(spec, dn, de)

    hdr = ('% Generated by make_graph.py (Graphviz dot layout + routing). Do not edit by hand.\n'
           '% Contents of a tikzpicture: uses only the styles of preamble.tex and its TikZ\n'
           '% libraries (arrows.meta, calc, patterns); no extra style or library needed.\n'
           '% Origin = top-left of the graph; everything lies at x >= 0, y <= 0.\n')
    open(os.path.join(out_dir, 'graph_body.tikz'), 'w').write(hdr + '\n'.join(body) + '\n')
    stem = os.path.join(out_dir, 'graph_graphviz')
    open(stem + '.tex', 'w').write(preamble.rstrip() + '\n\\begin{tikzpicture}[line cap=round]\n'
                                   + '\n'.join('  ' + l for l in body)
                                   + '\n\\end{tikzpicture}\n\\end{document}\n')
    print('wrote graph_body.tikz and graph_graphviz.tex in %s (%d nodes, %d edges)'
          % (out_dir, len(dn), len(de)))
    if args.no_compile:
        return
    r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
                        'graph_graphviz.tex'], cwd=out_dir, capture_output=True, text=True)
    log = open(stem + '.log', errors='replace').read()
    if r.returncode != 0:
        sys.exit('pdflatex failed:\n' + log[-3000:])
    bad = [l for l in log.splitlines() if 'Overfull' in l or 'Underfull' in l]
    assert not bad, bad
    subprocess.run(['pdftoppm', '-r', '200', '-png', '-singlefile', stem + '.pdf', stem], check=True)
    for ext in ('.aux', '.log'):
        os.remove(stem + ext)
    info = subprocess.run(['pdfinfo', stem + '.pdf'], capture_output=True, text=True).stdout
    m = re.search(r'Page size:\s+([\d.]+) x ([\d.]+) pts', info)
    # standalone border=2pt on each side is not part of the picture
    wcm = (float(m.group(1)) - 4) / 72 * 2.54
    hcm = (float(m.group(2)) - 4) / 72 * 2.54
    print('natural size of the tikzpicture: %.2f cm x %.2f cm' % (wcm, hcm))
    if wcm > MAX_W_CM or hcm > MAX_H_CM:
        sys.exit('too large: limit %.1f x %.1f cm' % (MAX_W_CM, MAX_H_CM))


if __name__ == '__main__':
    main()
