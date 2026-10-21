"""run_hardware.py — RQ1-E3: real IBM Quantum hardware proof-of-concept.

Runs the QSlice-full backward slice vs. the full circuit on a REAL IBM Quantum device and measures
the soundness (marginal TVD on the criterion qubit) on hardware. Writes
``results/hardware_results.json``, which plots.py turns into the hardware figure. If you never run
this, plots.py simply omits the hardware figure — nothing is simulated and labeled as hardware.

This is NOT run by main.py (which never has your credentials). Run it yourself:

    pip install "qiskit-ibm-runtime>=0.24"
    export QISKIT_IBM_TOKEN=<your IBM Quantum API token>        # from quantum.ibm.com
    # (channel default is ibm_quantum; pass --channel ibm_cloud / ibm_quantum_platform if migrated)
    python run_hardware.py --max-circuits 3 --shots 4096        # uses the least-busy real device

It picks the smallest corpus circuits (S3 stratum, <= --max-qubits) so the jobs are hardware-feasible.
Queue time on a shared device can be minutes-to-hours; the job ids are recorded so a run is auditable.
"""

import argparse
import json
import os
from pathlib import Path

from src.circuit_loader import load_corpus
from src.qdg import qdg_from_circuit
from src.slicer import slice_circuit, SlicerVariant
from src.simulate import compute_tvd, _ensure_measurements, SHOTS

RESULTS_DIR = Path("results")
DATA_DIR = Path("data")


def _marginal_p1(qc, q):
    """Noise-free P(criterion qubit == 1) via statevector — used to pick an INFORMATIVE criterion."""
    from qiskit.quantum_info import Statevector
    from src.simulate import _strip_measurements, _marginal_probs_statevector
    sv = Statevector(_strip_measurements(qc))
    return _marginal_probs_statevector(sv, q, qc.num_qubits).get("1", 0.0)


def _best_criterion(qc, qdg):
    """Pick the criterion qubit giving the most informative + reducing hardware test: a non-trivial
    marginal (0.15<=P(1)<=0.85, so TVD actually tests something) AND a slice strictly smaller than
    the full circuit. Returns (criterion, p1, ssr) or None."""
    best = None
    for q in range(qc.num_qubits):
        try:
            p1 = _marginal_p1(qc, q)
            sr = slice_circuit(qc, q, SlicerVariant.QSLICE_FULL, "probe", prebuilt_qdg=qdg)
        except Exception:
            continue
        if 0.15 <= p1 <= 0.85 and sr.ssr < 0.999:
            score = -abs(p1 - 0.5) - 0.25 * sr.ssr  # prefer marginal near 0.5 + more reduction
            if best is None or score > best[0]:
                best = (score, q, p1, sr.ssr)
    return None if best is None else (best[1], best[2], best[3])


def _select_circuits(max_qubits: int, limit: int, min_qubits: int = 3):
    """Pick hardware-feasible circuits where the criterion qubit has a NON-TRIVIAL marginal AND the
    QSlice slice strictly reduces the circuit — so the on-hardware TVD is a genuine soundness test
    rather than a trivially-zero match on a (near-)deterministic qubit. Returns (name, circuit,
    criterion) triples; falls back to GHZ+spectator circuits (informative + reducing by construction).
    """
    try:
        corpus = load_corpus(qasmbench_dir=DATA_DIR / "repos" / "pnnl_qasmbench",
                             openqasm3_dir=DATA_DIR / "repos" / "openqasm3")
    except Exception as e:
        print(f"[hardware] corpus load failed ({e}); using GHZ+spectator circuits")
        corpus = []

    cands = sorted([c for c in corpus if c.circuit is not None and min_qubits <= c.n_qubits <= max_qubits],
                   key=lambda c: (c.n_qubits, c.circuit.size()))
    chosen = []
    for c in cands:
        try:
            qdg = qdg_from_circuit(c.circuit, c.name)
            pick = _best_criterion(c.circuit, qdg)
        except Exception:
            continue
        if pick:
            crit, p1, ssr = pick
            chosen.append((c.name, c.circuit, crit))
            print(f"[hardware] candidate {c.name}: criterion q{crit}, P(1)={p1:.2f}, SSR={ssr:.2f}")
        if len(chosen) >= limit:
            break
    if chosen:
        return chosen

    print("[hardware] no informative corpus circuit found in range; using GHZ+spectator circuits.")
    # GHZ chain on q0..q_{n-2} + an independent spectator q_{n-1} with P(1)=0.5: the slice from the
    # spectator drops the GHZ block (SSR<1) and the criterion marginal is maximally informative.
    from qiskit import QuantumCircuit
    out = []
    for n in (4, 5, 6)[:limit]:
        qc = QuantumCircuit(n)
        qc.h(0)
        for i in range(n - 2):
            qc.cx(i, i + 1)
        qc.h(n - 1)
        out.append((f"ghz{n - 1}_plus_spectator_n{n}", qc, n - 1))
    return out


def _get_counts(pub_result):
    """Extract a counts dict from a SamplerV2 PUB result across runtime versions."""
    data = pub_result.data
    # Try the conventional register names first, then any BitArray field.
    for name in ("meas", "c", "cr"):
        reg = getattr(data, name, None)
        if reg is not None and hasattr(reg, "get_counts"):
            return reg.get_counts()
    for key in getattr(data, "keys", lambda: [])():
        reg = data[key]
        if hasattr(reg, "get_counts"):
            return reg.get_counts()
    raise RuntimeError("could not extract counts from SamplerV2 result")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None, help="IBM backend name; default = least busy real device")
    ap.add_argument("--channel", default=os.getenv("QISKIT_IBM_CHANNEL"),
                    help="ibm_quantum_platform (default) / ibm_cloud; omit to use your saved account")
    ap.add_argument("--token", default=os.getenv("QISKIT_IBM_TOKEN"))
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--max-circuits", type=int, default=6)
    ap.add_argument("--max-qubits", type=int, default=9)
    args = ap.parse_args()

    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    from qiskit import transpile

    # Build the service from whatever the user supplied; with neither token nor channel it uses the
    # account saved via QiskitRuntimeService.save_account(...). qiskit-ibm-runtime 0.45 defaults the
    # channel to ibm_quantum_platform (the legacy "ibm_quantum" channel was retired).
    svc_kwargs = {}
    if args.channel:
        svc_kwargs["channel"] = args.channel
    if args.token:
        svc_kwargs["token"] = args.token
    service = QiskitRuntimeService(**svc_kwargs)
    backend = (service.backend(args.backend) if args.backend
               else service.least_busy(operational=True, simulator=False))
    print(f"[hardware] backend: {backend.name}  shots: {args.shots}")

    circuits = _select_circuits(args.max_qubits, args.max_circuits)
    sampler = SamplerV2(mode=backend)
    per_circuit = []
    for name, qc, criterion in circuits:
        qdg = qdg_from_circuit(qc, name)
        sl = slice_circuit(qc, criterion, SlicerVariant.QSLICE_FULL, name, prebuilt_qdg=qdg)
        try:
            p1 = _marginal_p1(qc, criterion)   # noise-free marginal: confirms the test is non-trivial
        except Exception:
            p1 = None

        full_m = _ensure_measurements(qc)
        slice_m = _ensure_measurements(sl.slice_circuit)
        t_full = transpile(full_m, backend=backend, optimization_level=1)
        t_slice = transpile(slice_m, backend=backend, optimization_level=1)

        job = sampler.run([t_full, t_slice], shots=args.shots)
        print(f"[hardware] {name}: submitted job {job.job_id()} (n={qc.num_qubits}, criterion q{criterion}); waiting…")
        res = job.result()
        counts_full = _get_counts(res[0])
        counts_slice = _get_counts(res[1])
        tvd = compute_tvd(counts_full, counts_slice, criterion, qc.num_qubits)
        per_circuit.append({
            "circuit": name, "n_qubits": qc.num_qubits, "criterion_qubit": criterion,
            "criterion_p1_noisefree": p1, "tvd_hardware": tvd, "ssr": sl.ssr,
            "cx_reduction": sl.cx_reduction, "job_id": job.job_id(), "shots": args.shots,
        })
        p1s = f"{p1:.2f}" if p1 is not None else "?"
        print(f"[hardware] {name}: criterion P(1)={p1s}, SSR={sl.ssr:.2f}, TVD(sliced vs full)={tvd:.4f}")

    out = {
        "backend": backend.name,
        "channel": args.channel,
        "shots": args.shots,
        "delta_emp": max(0.05, 1.0 / (args.shots ** 0.5)),
        "source": "ibm_quantum_hardware",
        "per_circuit": per_circuit,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "hardware_results.json").write_text(json.dumps(out, indent=2))
    print(f"[hardware] wrote results/hardware_results.json ({len(per_circuit)} circuits on {backend.name})")


if __name__ == "__main__":
    main()
