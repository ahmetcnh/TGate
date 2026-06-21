from __future__ import annotations
from typing import Optional
from .ast_nodes import (
    Program, GateDecl, CircuitDecl, SimulationCall, SimArgBinding,
    TransistorStmt, NodeDecl, WireDecl, InstanceStmt,
    PortDecl, SignalRef, NameRef, LitRef, IndexLit,
    SingleOutput, NamedOutputs, VectorLit,
)
from .errors import TypeCheckError

_POWER_NETS = frozenset({'VDD', 'GND'})


class TypeChecker:
    def __init__(self, program: Program, components: dict):
        self.program = program
        self.components = components

    def check(self) -> None:
        for item in self.program.items:
            if isinstance(item, GateDecl):
                self._check_gate(item)
            elif isinstance(item, CircuitDecl):
                self._check_circuit(item)
            elif isinstance(item, SimulationCall):
                self._check_sim_call(item)

    def _build_local_types(self, ports: list, extra_node_names: list = None) -> dict:
        local = {}
        for p in ports:
            local[p.name] = p
        if extra_node_names:
            for name in extra_node_names:
                local[name] = PortDecl(name=name, size=None, line=0, column=0)
        return local

    def _resolve_type(self, ref, local: dict, line: int, col: int) -> Optional[int]:
        """Returns None for scalar (logic), N for array (logic[N]).
        Raises TypeCheckError on type violations."""
        if isinstance(ref, LitRef):
            return None
        if isinstance(ref, NameRef):
            name = ref.name
            if name in _POWER_NETS:
                return None
            if name not in local:
                return None  # undefined — semantic analyzer already reported this
            return local[name].size
        if isinstance(ref, SignalRef):
            name = ref.name
            if name in _POWER_NETS:
                return None
            if name not in local:
                return None  # undefined — semantic analyzer already reported this
            pd = local[name]
            base_size = pd.size
            n_indices = len(ref.indices)
            if n_indices == 0:
                return base_size
            if n_indices > 1:
                raise TypeCheckError(line, col,
                    f"multi-index access on '{name}' is not allowed; "
                    f"TGate supports only one-dimensional arrays")
            # exactly one index
            if base_size is None:
                raise TypeCheckError(line, col,
                    f"cannot index scalar '{name}' (it has type logic, not logic[N])")
            idx = ref.indices[0]
            if isinstance(idx, IndexLit):
                if idx.value >= base_size:
                    raise TypeCheckError(line, col,
                        f"index {idx.value} out of range for '{name}' of size {base_size}")
            return None  # after one index, result is scalar
        return None

    def _check_gate(self, gate: GateDecl) -> None:
        node_names = []
        for stmt in gate.body:
            if isinstance(stmt, NodeDecl):
                node_names.extend(stmt.names)
        # GateDecl.output is a single PortDecl, not a list
        all_ports = gate.inputs + [gate.output]
        local = self._build_local_types(all_ports, node_names)
        for stmt in gate.body:
            if isinstance(stmt, TransistorStmt):
                for ref in (stmt.drain, stmt.gate, stmt.source):
                    t = self._resolve_type(ref, local, stmt.line, stmt.column)
                    if t is not None:
                        name = getattr(ref, 'name', str(ref))
                        raise TypeCheckError(stmt.line, stmt.column,
                            f"transistor terminal must be scalar logic, "
                            f"got logic[{t}] for '{name}'")

    def _check_circuit(self, circuit: CircuitDecl) -> None:
        local: dict[str, PortDecl] = {}
        for p in circuit.inputs + circuit.outputs:
            local[p.name] = p
        for stmt in circuit.body:
            if isinstance(stmt, WireDecl):
                for wd in stmt.ports:
                    local[wd.name] = wd
        for stmt in circuit.body:
            if isinstance(stmt, InstanceStmt):
                self._check_instance(stmt, local)

    def _check_instance(self, stmt: InstanceStmt, local: dict) -> None:
        if stmt.ref_name not in self.components:
            return  # semantic analyzer already reported this
        comp = self.components[stmt.ref_name]
        # Check arg count vs number of input ports
        if len(stmt.args) != len(comp.inputs):
            raise TypeCheckError(stmt.line, stmt.column,
                f"component '{stmt.ref_name}' expects {len(comp.inputs)} input port(s), "
                f"got {len(stmt.args)} arguments")
        # Check each arg type vs port type
        for i, (arg, port) in enumerate(zip(stmt.args, comp.inputs)):
            arg_type = self._resolve_type(arg, local, stmt.line, stmt.column)
            port_type = port.size
            if arg_type != port_type:
                arg_str = 'logic' if arg_type is None else f'logic[{arg_type}]'
                port_str = 'logic' if port_type is None else f'logic[{port_type}]'
                raise TypeCheckError(stmt.line, stmt.column,
                    f"argument {i} to '{stmt.ref_name}': expected {port_str}, got {arg_str}")
        # Check output binding
        if isinstance(stmt.binding, SingleOutput):
            if isinstance(comp, GateDecl):
                outputs = [comp.output]
            else:
                outputs = comp.outputs
            if len(outputs) != 1:
                raise TypeCheckError(stmt.line, stmt.column,
                    f"single-output binding used on '{stmt.ref_name}' "
                    f"which has {len(outputs)} outputs; use named binding")
            out_type = outputs[0].size
            net_type = self._resolve_type(stmt.binding.net, local, stmt.line, stmt.column)
            if net_type != out_type:
                out_str = 'logic' if out_type is None else f'logic[{out_type}]'
                net_str = 'logic' if net_type is None else f'logic[{net_type}]'
                raise TypeCheckError(stmt.line, stmt.column,
                    f"output binding type mismatch: component output is {out_str}, "
                    f"target wire is {net_str}")

    def _check_sim_call(self, call: SimulationCall) -> None:
        if call.ref_name not in self.components:
            return  # semantic analyzer already reported undefined component

        comp = self.components[call.ref_name]

        # Check for duplicate argument names
        seen: dict = {}
        for binding in call.args:
            if binding.name in seen:
                raise TypeCheckError(call.line, call.column,
                    f"duplicate argument '{binding.name}' in simulate '{call.ref_name}'")
            seen[binding.name] = binding

        # Check for unknown argument names
        port_map = {p.name: p for p in comp.inputs}
        for binding in call.args:
            if binding.name not in port_map:
                valid = ', '.join(f"'{n}'" for n in port_map)
                raise TypeCheckError(call.line, call.column,
                    f"unknown argument '{binding.name}' for '{call.ref_name}'; "
                    f"valid input ports: {valid}")

        # Check for missing arguments
        for port in comp.inputs:
            if port.name not in seen:
                raise TypeCheckError(call.line, call.column,
                    f"missing argument '{port.name}' in simulate '{call.ref_name}'")

        # Check each argument's type vs its port type
        for binding in call.args:
            port = port_map[binding.name]
            if isinstance(binding.value, VectorLit):
                if port.size is None:
                    raise TypeCheckError(call.line, call.column,
                        f"argument '{binding.name}' is a vector literal "
                        f"but port '{binding.name}' is scalar logic; "
                        f"pass a single bit value instead")
                if len(binding.value.bits) != port.size:
                    raise TypeCheckError(call.line, call.column,
                        f"argument '{binding.name}' has {len(binding.value.bits)} bits "
                        f"but port expects logic[{port.size}]")
            else:
                if port.size is not None:
                    raise TypeCheckError(call.line, call.column,
                        f"argument '{binding.name}' is a scalar expression "
                        f"but port expects logic[{port.size}]; "
                        f"use a vector literal e.g. "
                        f"[{', '.join(['0'] * port.size)}]")
