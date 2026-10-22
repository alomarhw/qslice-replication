"""Rebuttal Correction 4 (PROTOCOL_ICPC.md section 7.1): recompute the ibm_cleveland TVDs from the
captured jobs, comparing the classical bits the slice actually measures.

recompute_hardware_tvd.py (kept unchanged, it reproduces the ICSE table) has two defects:
  1. it reads only the first classical register of each pub, although some circuits have several
     one-bit registers (m2, m0, m1);
  2. it does not know the criterion: it guesses the slice bit whose marginal is closest to 1/2 and
     assumes the same bit position in the full circuit's register.
The job records hold the submitted circuits, so neither guess is needed. Rule used here: the bits B
measured in the slice pub (pub 1); the TVD between the joint distribution of B in the slice and the
joint marginal of B in the full circuit (pub 0); also the same TVD for the submitted circuits
simulated without noise, which separates slice unsoundness from hardware noise. For |B| = 1 this is the marginal TVD on the
criterion. Each bit of B is checked to measure the same virtual qubit in both pubs (via the
transpiler's initial layout and the measured physical qubit).

This is a Z-basis comparison and blind to phase (rebuttal). Output:
experiments/results/icpc/hardware/hardware_tvd_corrected.csv. Needs qiskit-ibm-runtime.
Usage: ~/venvs/qslice-icpc-hw/bin/python hardware/scripts/recompute_hardware_tvd_corrected.py
"""

import csv
import glob
import json
import os
from collections import Counter

from qiskit_ibm_runtime import RuntimeDecoder

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, "..", "data", "ibm_cleveland_jobs")
OUT = os.path.join(HERE, "..", "..", "experiments", "results", "icpc", "hardware")
DELTA = 0.05
LABELS = {"d8tle4cb": "teleport", "d8tle6dp": "teleport-T", "d8tle2kt": "wstate",
          "d8tje0lp": "wstate-T", "d8tle84b": "qaoa", "d8tlea4t": "qaoa-T"}


def measured(qc):
    """clbit index -> (physical qubit, virtual qubit) for every measurement in a transpiled circuit."""
    layout = qc.layout.initial_index_layout(filter_ancillas=True) if qc.layout is not None else list(range(qc.num_qubits))
    out = {}
    for inst in qc.data:
        if inst.operation.name == "measure":
            phys = qc.find_bit(inst.qubits[0]).index
            out[qc.find_bit(inst.clbits[0]).index] = (phys, layout.index(phys) if phys in layout else None)
    return out


def shot_bits(qc, pub_data, bits):
    """Counter over shots of the tuple of values of the given clbit indices, joining all registers."""
    per_reg = {}
    for reg in qc.cregs:
        per_reg[reg.name] = getattr(pub_data, reg.name).get_bitstrings()
    n = len(next(iter(per_reg.values())))
    where = {}
    for reg in qc.cregs:
        for j, b in enumerate(reg):
            where[qc.find_bit(b).index] = (reg.name, reg.size, j)
    c = Counter()
    for s in range(n):
        key = []
        for b in bits:
            name, size, j = where[b]
            key.append(per_reg[name][s][size - 1 - j])
        c[tuple(key)] += 1
    return c, n


def noise_free(qc, bits):
    """Exact distribution of the given clbits for the submitted circuit without noise: the circuit
    restricted to its active physical qubits, simulated as a statevector (no mid-circuit measurement
    in these circuits; measurements are terminal)."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector
    active = sorted({qc.find_bit(q).index for i in qc.data if i.operation.name not in ("barrier", "delay")
                     for q in i.qubits})
    m = {p: k for k, p in enumerate(active)}
    c, meas = QuantumCircuit(len(active)), {}
    for inst in qc.data:
        name = inst.operation.name
        if name in ("barrier", "delay"):
            continue
        if name == "measure":
            meas[qc.find_bit(inst.clbits[0]).index] = m[qc.find_bit(inst.qubits[0]).index]
            continue
        c.append(inst.operation, [m[qc.find_bit(q).index] for q in inst.qubits])
    out = Counter()
    for bitstr, v in Statevector(c).probabilities_dict().items():
        out[tuple(bitstr[::-1][meas[b]] for b in bits)] += v
    return out


def tvd(a, na, b, nb):
    return 0.5 * sum(abs(a.get(k, 0) / na - b.get(k, 0) / nb) for k in set(a) | set(b))


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for info in sorted(glob.glob(os.path.join(JOBS, "*-info.json"))):
        jid = os.path.basename(info).split("-info")[0]
        short = jid.replace("job-", "")[:8]
        pubs = json.load(open(info), cls=RuntimeDecoder)["params"]["pubs"]
        res = json.load(open(info.replace("-info", "-result")), cls=RuntimeDecoder)
        full_qc, slice_qc = (p[0] if isinstance(p, (list, tuple)) else p for p in pubs[:2])
        mf, ms = measured(full_qc), measured(slice_qc)
        bits = sorted(ms)
        same = all(b in mf and mf[b][1] == ms[b][1] for b in bits)
        cf, nf = shot_bits(full_qc, res[0].data, bits)
        cs, ns = shot_bits(slice_qc, res[1].data, bits)
        d = tvd(cf, nf, cs, ns)
        d0 = tvd(noise_free(full_qc, bits), 1.0, noise_free(slice_qc, bits), 1.0)
        p1 = lambda c, n, i: sum(v for k, v in c.items() if k[i] == "1") / n  # noqa: E731
        rows.append({"circuit": LABELS.get(short, short), "job_id": jid,
                     "slice_bits": ";".join(map(str, bits)),
                     "virtual_qubits": ";".join(str(ms[b][1]) for b in bits),
                     "same_virtual_qubit_in_full": same, "shots_full": nf, "shots_slice": ns,
                     "P_full_1": ";".join(f"{p1(cf, nf, i):.4f}" for i in range(len(bits))),
                     "P_slice_1": ";".join(f"{p1(cs, ns, i):.4f}" for i in range(len(bits))),
                     "TVD": round(d, 4), "within_delta": d < DELTA,
                     "TVD_noise_free": round(d0, 6)})
    rows.sort(key=lambda r: r["TVD"])
    path = os.path.join(OUT, "hardware_tvd_corrected.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ok = sum(r["within_delta"] for r in rows)
    print(f"ibm_cleveland (corrected): {ok}/{len(rows)} within TVD {DELTA}; "
          f"bit/qubit mapping consistent in {sum(r['same_virtual_qubit_in_full'] for r in rows)}/{len(rows)}; wrote {path}")


if __name__ == "__main__":
    main()
