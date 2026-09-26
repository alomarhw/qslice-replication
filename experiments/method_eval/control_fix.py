"""Minimal patch to the method prototype's classical-control edges (PROTOCOL.md, section 3.2).

The prototype (described_method/qdg.py, `QDG._add_control_edges`) has two defects under its pinned
qiskit 2.3.0, found while debugging on dqc_teleportation before the protocol was frozen:
  1. A register condition is recognised by `hasattr(cond[0], "bits")`. qiskit 2 registers have no
     `.bits` attribute, so the register is looked up as if it were a bit, and no edge is added.
  2. Each classical bit is linked to its *last* measurement anywhere in the circuit, which may come
     after the conditioned operation.
As a result, measurement -> conditioned-operation CONTROL edges, which Sec. III describes, are never
built. This subclass replaces only that method: every conditioned operation gets a CONTROL edge from
the most recent earlier measurement of each classical bit its condition reads. Nothing else changes.
"""

from __future__ import annotations

from qiskit.circuit import Clbit

from qdg import QDG, EdgeType


class QDGControlFixed(QDG):
    def _add_control_edges(self) -> None:
        last_meas: dict[int, int] = {}
        for pos, inst in enumerate(self.qc.data):
            op = inst.operation
            if self._is_classical_control_op(op):
                cond = getattr(op, "condition", None)
                if cond is not None:
                    bits = [cond[0]] if isinstance(cond[0], Clbit) else list(cond[0])
                    for cb in bits:
                        ci = self.cbit_to_idx.get(cb, -1)
                        if ci in last_meas and not self.graph.has_edge(last_meas[ci], pos):
                            self.graph.add_edge(last_meas[ci], pos, edge_type=EdgeType.CONTROL, cbit=ci)
            if op.name == "measure":
                for cb in inst.clbits:
                    last_meas[self.cbit_to_idx[cb]] = pos
