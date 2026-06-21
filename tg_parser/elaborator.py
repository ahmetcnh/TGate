from __future__ import annotations
from .ast_nodes import (
    Program, GateDecl, CircuitDecl, SimulationCall, ParamDecl,
    GenerateStmt, TransistorStmt, NodeDecl, WireDecl, InstanceStmt,
    SignalRef, NameRef, LitRef, IndexName, IndexLit,
    PortDecl, SingleOutput, NamedOutputs, PortBinding,
)
from .errors import SemanticError


def _eval_bound(bound, params: dict, line: int, col: int) -> int:
    """Evaluate a range bound: int, param name, or 'NAME±offset' string."""
    if isinstance(bound, int):
        return bound
    s = str(bound)
    if '-' in s:
        name, _, offset_s = s.partition('-')
        try:
            offset = -int(offset_s.strip())
        except ValueError:
            raise SemanticError(line, col,
                f"invalid range bound syntax '{bound}'")
    elif '+' in s:
        name, _, offset_s = s.partition('+')
        try:
            offset = int(offset_s.strip())
        except ValueError:
            raise SemanticError(line, col,
                f"invalid range bound syntax '{bound}'")
    else:
        name = s
        offset = 0
    name = name.strip()
    if name not in params:
        raise SemanticError(line, col,
            f"unresolved generate range bound '{bound}'")
    return params[name] + offset


# Port sizes support only param name references (e.g. a[N]), not arithmetic expressions.
def _resolve_port_size(port: PortDecl, params: dict) -> PortDecl:
    """Resolve a string port size (param name) to a concrete integer."""
    if isinstance(port.size, str):
        name = port.size
        if name not in params:
            raise SemanticError(port.line, port.column,
                f"undefined param '{name}' used in port size")
        return PortDecl(name=port.name, size=params[name],
                        line=port.line, column=port.column)
    return port


def _sub_ident(name: str, env: dict) -> str:
    """Replace any '_'-separated segment that matches a genvar name."""
    parts = name.split('_')
    return '_'.join(str(env[p]) if p in env else p for p in parts)


def _sub_ref(ref, env: dict):
    """Substitute genvar in a NetRef (SignalRef, NameRef, or LitRef)."""
    if isinstance(ref, SignalRef):
        new_name = _sub_ident(ref.name, env)
        new_idx = [
            IndexLit(value=env[idx.name])
            if isinstance(idx, IndexName) and idx.name in env
            else idx
            for idx in ref.indices
        ]
        return SignalRef(name=new_name, indices=new_idx,
                        line=ref.line, column=ref.column)
    if isinstance(ref, NameRef):
        return NameRef(name=_sub_ident(ref.name, env))
    return ref  # LitRef: unchanged


def _sub_binding(binding, env: dict):
    if isinstance(binding, SingleOutput):
        return SingleOutput(net=_sub_ref(binding.net, env))
    if isinstance(binding, NamedOutputs):
        return NamedOutputs(bindings=[
            PortBinding(port_name=pb.port_name,
                        net=_sub_ref(pb.net, env),
                        line=pb.line, column=pb.column)
            for pb in binding.bindings
        ])
    return binding


def _sub_stmt(stmt, env: dict):
    """Deep-substitute genvar into a single concrete statement."""
    if not env:
        return stmt
    if isinstance(stmt, TransistorStmt):
        return TransistorStmt(
            kind=stmt.kind,
            drain=_sub_ref(stmt.drain, env),
            gate=_sub_ref(stmt.gate, env),
            source=_sub_ref(stmt.source, env),
            line=stmt.line, column=stmt.column,
        )
    if isinstance(stmt, InstanceStmt):
        return InstanceStmt(
            ref_name=stmt.ref_name,
            label=_sub_ident(stmt.label, env),
            args=[_sub_ref(a, env) for a in stmt.args],
            binding=_sub_binding(stmt.binding, env),
            line=stmt.line, column=stmt.column,
        )
    if isinstance(stmt, NodeDecl):
        return NodeDecl(
            names=[_sub_ident(n, env) for n in stmt.names],
            line=stmt.line, column=stmt.column,
        )
    if isinstance(stmt, WireDecl):
        new_ports = [
            PortDecl(name=_sub_ident(pd.name, env), size=pd.size,
                     line=pd.line, column=pd.column)
            for pd in stmt.ports
        ]
        return WireDecl(ports=new_ports, line=stmt.line, column=stmt.column)
    return stmt


def _elab_body(body: list, env: dict, params: dict, seen_labels: set = None) -> list:
    if seen_labels is None:
        seen_labels = set()
    result = []
    for stmt in body:
        if isinstance(stmt, GenerateStmt):
            if stmt.var_name in env:
                raise SemanticError(stmt.line, stmt.column,
                    f"genvar '{stmt.var_name}' shadows an outer generate variable")
            start = _eval_bound(stmt.start, params, stmt.line, stmt.column)
            end = _eval_bound(stmt.end, params, stmt.line, stmt.column)
            for v in range(start, end + 1):
                child_env = {**env, stmt.var_name: v}
                result.extend(_elab_body(stmt.body, child_env, params, seen_labels))
        else:
            elaborated = _sub_stmt(stmt, env)
            if isinstance(elaborated, InstanceStmt):
                if elaborated.label in seen_labels:
                    raise SemanticError(elaborated.line, elaborated.column,
                        f"duplicate instance label '{elaborated.label}'")
                seen_labels.add(elaborated.label)
            result.append(elaborated)
    return result


class Elaborator:
    def __init__(self, program: Program):
        self.program = program

    def elaborate(self) -> Program:
        # Pass 1: collect param declarations
        params: dict = {}
        for item in self.program.items:
            if isinstance(item, ParamDecl):
                if item.name in params:
                    raise SemanticError(item.line, item.column,
                        f"duplicate param '{item.name}'")
                params[item.name] = item.value

        # Pass 2: elaborate components (resolve params, expand generates)
        new_items = []
        for item in self.program.items:
            if isinstance(item, GateDecl):
                new_items.append(GateDecl(
                    name=item.name,
                    inputs=[_resolve_port_size(p, params) for p in item.inputs],
                    output=_resolve_port_size(item.output, params),
                    body=_elab_body(item.body, {}, params),
                    line=item.line, column=item.column,
                ))
            elif isinstance(item, CircuitDecl):
                new_items.append(CircuitDecl(
                    name=item.name,
                    inputs=[_resolve_port_size(p, params) for p in item.inputs],
                    outputs=[_resolve_port_size(p, params) for p in item.outputs],
                    body=_elab_body(item.body, {}, params),
                    line=item.line, column=item.column,
                ))
            elif isinstance(item, ParamDecl):
                pass  # consumed; do not include in elaborated output
            else:
                new_items.append(item)
        return Program(items=new_items)
