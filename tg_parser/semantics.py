from __future__ import annotations
from typing import Union
from .ast_nodes import (
    Program, GateDecl, CircuitDecl, SimulationCall,
    TransistorStmt, NodeDecl, WireDecl, InstanceStmt,
    SignalRef, NameRef, LitRef, SingleOutput, NamedOutputs,
)
from .errors import SemanticError

_POWER_NETS = frozenset({'VDD', 'GND'})


class SemanticAnalyzer:
    def __init__(self, program: Program):
        self.program = program
        self.components: dict[str, Union[GateDecl, CircuitDecl]] = {}

    def analyze(self) -> None:
        self._collect_declarations()
        self._validate_all()

    # ------------------------------------------------------------------ pass 1
    def _collect_declarations(self) -> None:
        for item in self.program.items:
            if isinstance(item, (GateDecl, CircuitDecl)):
                if item.name in ('VDD', 'GND'):
                    raise SemanticError(item.line, item.column,
                        f"'{item.name}' is a reserved power net name and cannot be used as a component name")
                if item.name in self.components:
                    existing = self.components[item.name]
                    raise SemanticError(
                        item.line, item.column,
                        f"component '{item.name}' already defined at line {existing.line}",
                    )
                self.components[item.name] = item

    # ------------------------------------------------------------------ pass 2
    def _validate_all(self) -> None:
        for item in self.program.items:
            if isinstance(item, GateDecl):
                self._validate_gate(item)
            elif isinstance(item, CircuitDecl):
                self._validate_circuit(item)
            elif isinstance(item, SimulationCall):
                self._validate_sim_call(item)
            # ParamDecl: consumed by elaborator before this stage; skip silently

    # -------------------- gate
    def _validate_gate(self, gate: GateDecl) -> None:
        local: set[str] = set()
        for p in gate.inputs:
            local.add(p.name)
        # GateDecl.output is a single PortDecl, not a list
        local.add(gate.output.name)
        for stmt in gate.body:
            if isinstance(stmt, NodeDecl):
                for name in stmt.names:
                    if name in local:
                        raise SemanticError(
                            stmt.line, stmt.column,
                            f"node '{name}' conflicts with port in gate '{gate.name}'",
                        )
                    local.add(name)
        for stmt in gate.body:
            if isinstance(stmt, TransistorStmt):
                for ref in (stmt.drain, stmt.gate, stmt.source):
                    self._check_gate_ref(ref, local, stmt.line, stmt.column)

    def _check_gate_ref(self, ref, local: set, line: int, col: int) -> None:
        if isinstance(ref, LitRef):
            return
        # Both NameRef and SignalRef have a .name attribute
        name = ref.name if isinstance(ref, (NameRef, SignalRef)) else None
        if name and name not in local and name not in _POWER_NETS:
            raise SemanticError(line, col, f"undefined net '{name}'")

    # -------------------- circuit
    def _validate_circuit(self, circuit: CircuitDecl) -> None:
        local: dict[str, object] = {}
        for p in circuit.inputs:
            local[p.name] = p
        for p in circuit.outputs:
            local[p.name] = p
        # WireDecl.ports is List[PortDecl]
        for stmt in circuit.body:
            if isinstance(stmt, WireDecl):
                for wd in stmt.ports:
                    if wd.name in local:
                        raise SemanticError(
                            stmt.line, stmt.column,
                            f"wire '{wd.name}' conflicts with port in circuit '{circuit.name}'",
                        )
                    local[wd.name] = wd
        for stmt in circuit.body:
            if isinstance(stmt, InstanceStmt):
                self._validate_instance(stmt, local)

    def _validate_instance(self, stmt: InstanceStmt, local: dict) -> None:
        if stmt.ref_name not in self.components:
            raise SemanticError(
                stmt.line, stmt.column,
                f"undefined component '{stmt.ref_name}'",
            )
        comp = self.components[stmt.ref_name]
        if isinstance(stmt.binding, SingleOutput):
            self._check_circuit_ref(stmt.binding.net, local, stmt.line, stmt.column)
        elif isinstance(stmt.binding, NamedOutputs):
            if isinstance(comp, GateDecl):
                raise SemanticError(
                    stmt.line, stmt.column,
                    f"named output binding used on gate '{stmt.ref_name}' (gates have one output)",
                )
            out_names = {p.name for p in comp.outputs}
            seen_bound = {}
            for pb in stmt.binding.bindings:
                if pb.port_name in seen_bound:
                    raise SemanticError(pb.line, pb.column,
                        f"duplicate output binding for port '{pb.port_name}' in '{stmt.ref_name}'")
                seen_bound[pb.port_name] = pb
                if pb.port_name not in out_names:
                    raise SemanticError(
                        pb.line, pb.column,
                        f"'{pb.port_name}' is not an output of circuit '{stmt.ref_name}'",
                    )
                self._check_circuit_ref(pb.net, local, pb.line, pb.column)
            bound_names = {pb.port_name for pb in stmt.binding.bindings}
            for p in comp.outputs:
                if p.name not in bound_names:
                    raise SemanticError(stmt.line, stmt.column,
                        f"output port '{p.name}' of '{stmt.ref_name}' is not bound in named output binding")

    def _check_circuit_ref(self, ref, local: dict, line: int, col: int) -> None:
        # NameRef has no line/column; use the parent statement's position
        if isinstance(ref, (NameRef, SignalRef)) and ref.name not in local:
            raise SemanticError(line, col, f"undefined wire or port '{ref.name}'")

    # -------------------- simulation call (name resolution only)
    def _validate_sim_call(self, call: SimulationCall) -> None:
        if call.ref_name not in self.components:
            raise SemanticError(
                call.line, call.column,
                f"undefined component '{call.ref_name}'",
            )
