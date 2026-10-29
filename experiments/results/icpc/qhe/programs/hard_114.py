from qiskit.transpiler import CouplingMap

def create_and_modify_coupling_map():
    coupling_list = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]]
    cmap = CouplingMap(couplinglist=coupling_list)
    cmap.add_edge(5, 6)
    cmap.add_physical_qubit(7)
    return cmap
