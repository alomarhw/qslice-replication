from qiskit_ibm_runtime.fake_provider import FakeKyoto
from qiskit.circuit.library import GraphState
import networkx as nx
from qiskit.circuit import QuantumCircuit

def get_graph_state():
    backend = FakeKyoto()
    coupling_map = backend.coupling_map
    G = nx.Graph()
    G.add_edges_from(coupling_map)
    adj_matrix = nx.adjacency_matrix(G).todense()
    gr_state_circ = GraphState(adjacency_matrix=adj_matrix)
    return gr_state_circ
