from __future__ import annotations
import itertools
from typing import Optional, Union
from .ast_nodes import (
    Program, GateDecl, CircuitDecl, SimulationCall, SimArgBinding, VectorLit,
    TransistorStmt, NodeDecl, WireDecl, InstanceStmt,
    SignalRef, NameRef, LitRef, IndexLit,
    SingleOutput, NamedOutputs,
    LitExpr, NotExpr, AndExpr, OrExpr,
)
from .errors import SimulationError

NetVal = Optional[Union[int, str]]  # None=floating, 'X'=conflict, 0|1=driven


# ---------------------------------------------------------------------------
# Logic expression evaluator
# ---------------------------------------------------------------------------

def eval_expr(expr) -> int:
    if isinstance(expr, LitExpr):
        return expr.value
    if isinstance(expr, NotExpr):
        return 1 - eval_expr(expr.operand)
    if isinstance(expr, AndExpr):
        return eval_expr(expr.left) & eval_expr(expr.right)
    if isinstance(expr, OrExpr):
        return eval_expr(expr.left) | eval_expr(expr.right)
    raise SimulationError(f"unexpected expression type: {type(expr).__name__}")


# ---------------------------------------------------------------------------
# Net helpers
# ---------------------------------------------------------------------------

def _net_key(ref) -> Optional[str]:
    if isinstance(ref, NameRef):
        return ref.name
    if isinstance(ref, SignalRef):
        if not ref.indices:
            return ref.name
        idx = ref.indices[0]
        val = idx.value if isinstance(idx, IndexLit) else idx.name
        return f"{ref.name}[{val}]"
    return None  # LitRef — not addressable


def _get(nets: dict, ref) -> NetVal:
    if isinstance(ref, LitRef):
        return ref.value
    key = _net_key(ref)
    return nets.get(key) if key else None


def _merge(a: NetVal, b: NetVal) -> tuple:
    if a == 'X' or b == 'X':
        return 'X', 'X'
    if a is None and b is None:
        return None, None
    if a is None:
        return b, b
    if b is None:
        return a, a
    if a == b:
        return a, b
    return 'X', 'X'


def _set_net(nets: dict, ref, val: NetVal) -> bool:
    key = _net_key(ref)
    if key is None:
        return False
    if nets.get(key) == val:
        return False
    nets[key] = val
    return True


# ---------------------------------------------------------------------------
# Gate simulator
# ---------------------------------------------------------------------------

def simulate_gate(gate: GateDecl, input_nets: dict) -> dict:
    nets: dict = {'VDD': 1, 'GND': 0, **input_nets}

    out = gate.output
    if out.size is None:
        nets[out.name] = None
    else:
        for i in range(out.size):
            nets[f"{out.name}[{i}]"] = None

    for stmt in gate.body:
        if isinstance(stmt, NodeDecl):
            for name in stmt.names:
                nets[name] = None

    changed = True
    while changed:
        changed = False
        for stmt in gate.body:
            if not isinstance(stmt, TransistorStmt):
                continue
            gate_val = _get(nets, stmt.gate)
            if gate_val is None or gate_val == 'X':
                continue
            is_on = (stmt.kind == 'pmos' and gate_val == 0) or \
                    (stmt.kind == 'nmos' and gate_val == 1)
            if not is_on:
                continue
            d = _get(nets, stmt.drain)
            s = _get(nets, stmt.source)
            new_d, new_s = _merge(d, s)
            if new_d != d and _set_net(nets, stmt.drain, new_d):
                changed = True
            if new_s != s and _set_net(nets, stmt.source, new_s):
                changed = True

    result: dict = {}
    if out.size is None:
        result[out.name] = nets.get(out.name)
    else:
        for i in range(out.size):
            result[f"{out.name}[{i}]"] = nets.get(f"{out.name}[{i}]")

    for key, val in result.items():
        if val is None:
            raise SimulationError(f"floating output '{key}' in gate '{gate.name}'")
        if val == 'X':
            raise SimulationError(f"short-circuit conflict at output '{key}' in gate '{gate.name}'")

    return result


# ---------------------------------------------------------------------------
# Circuit simulator
# ---------------------------------------------------------------------------

def simulate_circuit(
    circuit,
    components: dict,
    input_nets: dict,
) -> dict:
    wires: dict = {}

    # Initialize output ports
    for p in circuit.outputs:
        if p.size is None:
            wires[p.name] = None
        else:
            for i in range(p.size):
                wires[f"{p.name}[{i}]"] = None

    # Initialize wire declarations
    for stmt in circuit.body:
        if isinstance(stmt, WireDecl):
            for wd in stmt.ports:
                if wd.size is None:
                    wires[wd.name] = None
                else:
                    for i in range(wd.size):
                        wires[f"{wd.name}[{i}]"] = None

    # Merge in input nets
    wires.update(input_nets)

    # Simulate instances in declaration order
    for stmt in circuit.body:
        if not isinstance(stmt, InstanceStmt):
            continue
        comp = components[stmt.ref_name]
        inst_inputs = _build_inst_inputs(comp, stmt.args, wires)

        if isinstance(comp, GateDecl):
            out_vals = simulate_gate(comp, inst_inputs)
        else:
            out_vals = simulate_circuit(comp, components, inst_inputs)

        _assign_binding(stmt.binding, out_vals, wires, comp)

    # Collect output values
    result: dict = {}
    for p in circuit.outputs:
        if p.size is None:
            result[p.name] = wires.get(p.name)
        else:
            for i in range(p.size):
                result[f"{p.name}[{i}]"] = wires.get(f"{p.name}[{i}]")
    return result


def _build_inst_inputs(comp, args: list, wires: dict) -> dict:
    """Map args (NetRef list, one per port) into {key: val} for the child component."""
    inst_inputs: dict = {}
    for port, arg in zip(comp.inputs, args):
        if port.size is None:
            key = _net_key(arg)
            inst_inputs[port.name] = wires.get(key) if key else _get(wires, arg)
        else:
            # Array port: arg is SignalRef(name, []) — spread elements
            base = _net_key(arg)
            for i in range(port.size):
                src_key = f"{base}[{i}]"
                inst_inputs[f"{port.name}[{i}]"] = wires.get(src_key)
    return inst_inputs


def _assign_binding(binding, out_vals: dict, wires: dict, comp) -> None:
    if isinstance(binding, SingleOutput):
        key = _net_key(binding.net)
        if key is None:
            return
        if len(out_vals) == 1:
            # Scalar output: assign directly
            wires[key] = next(iter(out_vals.values()))
        else:
            # Array output: spread element-by-element using suffix
            for out_key, val in out_vals.items():
                if '[' in out_key:
                    suffix = out_key[out_key.index('['):]  # '[0]', '[1]', etc.
                    wires[f"{key}{suffix}"] = val
                else:
                    wires[key] = val
    elif isinstance(binding, NamedOutputs):
        for pb in binding.bindings:
            val = out_vals.get(pb.port_name)
            key = _net_key(pb.net)
            if key:
                wires[key] = val


def _fmt(val) -> str:
    if val is None or val == 'X':
        return 'X'
    return str(val)


def _input_cols(comp) -> list:
    """Return flat list of net keys for all input ports (array ports expanded)."""
    cols = []
    for port in comp.inputs:
        if port.size is None:
            cols.append(port.name)
        else:
            cols.extend(f"{port.name}[{i}]" for i in range(port.size))
    return cols


def _output_keys(comp) -> list:
    """Return a deterministic list of output net keys for a component."""
    if isinstance(comp, GateDecl):
        out = comp.output
        if out.size is None:
            return [out.name]
        return [f"{out.name}[{i}]" for i in range(out.size)]
    keys = []
    for p in comp.outputs:
        if p.size is None:
            keys.append(p.name)
        else:
            keys.extend(f"{p.name}[{i}]" for i in range(p.size))
    return keys


def print_truth_table(comp_name: str, components: dict) -> None:
    if comp_name not in components:
        raise SimulationError(f"component '{comp_name}' not found for --truth-table")
    comp = components[comp_name]

    in_cols = _input_cols(comp)
    out_keys = _output_keys(comp)
    in_header = ' '.join(in_cols)
    out_header = ' '.join(out_keys)

    print(f"{comp_name} truth table:")
    print(f"{in_header} | {out_header}" if in_cols else f"| {out_header}")

    for vals in itertools.product(range(2), repeat=len(in_cols)):
        input_nets = dict(zip(in_cols, vals))
        if isinstance(comp, GateDecl):
            out_vals = simulate_gate(comp, input_nets)
        else:
            out_vals = simulate_circuit(comp, components, input_nets)
        in_str = ' '.join(str(v) for v in vals)
        out_str = ' '.join(_fmt(out_vals.get(k)) for k in out_keys)
        print(f"{in_str} | {out_str}" if in_str else f"| {out_str}")


def _named_args_to_nets(comp, bindings: list) -> dict:
    """Map SimArgBinding list -> {portname: val} or {portname[i]: val}."""
    nets: dict = {}
    for binding in bindings:
        if isinstance(binding.value, VectorLit):
            for i, bit in enumerate(binding.value.bits):
                nets[f"{binding.name}[{i}]"] = bit
        else:
            nets[binding.name] = eval_expr(binding.value)
    return nets


def _fmt_sim_arg(binding) -> str:
    if isinstance(binding.value, VectorLit):
        bits_str = ', '.join(str(b) for b in binding.value.bits)
        return f"{binding.name}=[{bits_str}]"
    return f"{binding.name}={eval_expr(binding.value)}"


def run_simulation(program, components: dict) -> None:
    for item in program.items:
        if not isinstance(item, SimulationCall):
            continue
        comp = components[item.ref_name]
        input_nets = _named_args_to_nets(comp, item.args)
        args_str = ', '.join(_fmt_sim_arg(b) for b in item.args)

        if isinstance(comp, GateDecl):
            out_vals = simulate_gate(comp, input_nets)
        else:
            out_vals = simulate_circuit(comp, components, input_nets)

        out_str = ', '.join(f"{k}={_fmt(v)}" for k, v in out_vals.items())
        print(f"{item.ref_name}({args_str}) -> {out_str}")
