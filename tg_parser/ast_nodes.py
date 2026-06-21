from __future__ import annotations
from dataclasses import dataclass, field
from typing import Union, List, Optional


# ---------------------------------------------------------------------------
# Net references  (used inside gate/circuit bodies and instance arguments)
# ---------------------------------------------------------------------------

@dataclass
class NameRef:
    name: str

    def dump(self, _indent: int = 0) -> str:
        return self.name


@dataclass
class LitRef:
    value: int

    def dump(self, _indent: int = 0) -> str:
        return str(self.value)


NetRef = Union['SignalRef', NameRef, LitRef]


# ---------------------------------------------------------------------------
# Port declarations  (used in gate/circuit port specs and wire declarations)
# ---------------------------------------------------------------------------

@dataclass
class PortDecl:
    name: str
    # str means param name; resolved to int by elaborator
    size: Optional[Union[int, str]]
    line: int
    column: int

    def dump(self, _indent: int = 0) -> str:
        if self.size is not None:
            return f"{self.name}[{self.size}]"
        return self.name


# ---------------------------------------------------------------------------
# Indexed signal references  (used in instance args, output bindings, net refs)
# ---------------------------------------------------------------------------

@dataclass
class IndexLit:
    value: int

    def dump(self) -> str:
        return str(self.value)


@dataclass
class IndexName:
    name: str

    def dump(self) -> str:
        return self.name


IndexExpr = Union[IndexLit, IndexName]
RangeBound = Union[int, str]   # int = integer literal, str = identifier


@dataclass
class SignalRef:
    name: str
    indices: List[IndexExpr]
    line: int
    column: int

    def dump(self, _indent: int = 0) -> str:
        idx = ''.join(f"[{i.dump()}]" for i in self.indices)
        return f"{self.name}{idx}"


# ---------------------------------------------------------------------------
# Logic expressions  (used only in simulation call arguments)
# ---------------------------------------------------------------------------

@dataclass
class LitExpr:
    value: int

    def dump(self, _indent: int = 0) -> str:
        return str(self.value)


@dataclass
class NameExpr:
    name: str

    def dump(self, _indent: int = 0) -> str:
        return self.name


@dataclass
class NotExpr:
    operand: LogicExpr

    def dump(self, _indent: int = 0) -> str:
        return f"(! {self.operand.dump()})"


@dataclass
class AndExpr:
    left: LogicExpr
    right: LogicExpr

    def dump(self, _indent: int = 0) -> str:
        return f"(& {self.left.dump()} {self.right.dump()})"


@dataclass
class OrExpr:
    left: LogicExpr
    right: LogicExpr

    def dump(self, _indent: int = 0) -> str:
        return f"(| {self.left.dump()} {self.right.dump()})"


LogicExpr = Union[LitExpr, NameExpr, NotExpr, AndExpr, OrExpr]


@dataclass
class VectorLit:
    """A vector literal [0, 1, 0, 1] used as a named simulation argument value."""
    bits: List[int]
    line: int
    column: int

    def dump(self, _indent: int = 0) -> str:
        return '[' + ', '.join(str(b) for b in self.bits) + ']'


SimArgValue = Union[LitExpr, NameExpr, NotExpr, AndExpr, OrExpr, VectorLit]


@dataclass
class SimArgBinding:
    """A named argument in a simulate call: name=value or name=[bits]."""
    name: str
    value: 'SimArgValue'
    line: int
    column: int

    def dump(self, _indent: int = 0) -> str:
        return f"{self.name}={self.value.dump()}"


# ---------------------------------------------------------------------------
# Output bindings  (right-hand side of '->' in instance statements)
# ---------------------------------------------------------------------------

@dataclass
class PortBinding:
    port_name: str
    net: NetRef
    line: int
    column: int

    def dump(self, _indent: int = 0) -> str:
        return f"{self.port_name}={self.net.dump()}"


@dataclass
class SingleOutput:
    net: NetRef

    def dump(self, _indent: int = 0) -> str:
        return self.net.dump()


@dataclass
class NamedOutputs:
    bindings: List[PortBinding]

    def dump(self, _indent: int = 0) -> str:
        inner = ', '.join(b.dump() for b in self.bindings)
        return '{' + inner + '}'


OutputBinding = Union[SingleOutput, NamedOutputs]


# ---------------------------------------------------------------------------
# Gate body items
# ---------------------------------------------------------------------------

@dataclass
class NodeDecl:
    names: List[str]
    line: int
    column: int

    def dump(self, indent: int = 0) -> str:
        pad = '  ' * indent
        return f"{pad}(NodeDecl {' '.join(self.names)})"


@dataclass
class TransistorStmt:
    kind: str        # 'pmos' or 'nmos'
    drain: NetRef
    gate: NetRef
    source: NetRef
    line: int
    column: int

    def dump(self, indent: int = 0) -> str:
        pad = '  ' * indent
        k = self.kind.upper()
        return (f"{pad}({k} drain={self.drain.dump()} "
                f"gate={self.gate.dump()} source={self.source.dump()})")


# ---------------------------------------------------------------------------
# Circuit body items
# ---------------------------------------------------------------------------

@dataclass
class WireDecl:
    ports: List[PortDecl]
    line: int
    column: int

    def dump(self, indent: int = 0) -> str:
        pad = '  ' * indent
        p = ' '.join(d.dump() for d in self.ports)
        return f"{pad}(WireDecl {p})"


@dataclass
class InstanceStmt:
    ref_name: str
    label: str
    args: List[NetRef]
    binding: OutputBinding
    line: int
    column: int

    def dump(self, indent: int = 0) -> str:
        pad = '  ' * indent
        args_str = ' '.join(a.dump() for a in self.args)
        return (f"{pad}(Instance {self.ref_name} {self.label} "
                f"(args {args_str}) -> {self.binding.dump()})")


# ---------------------------------------------------------------------------
# Generate statement  (gate body or circuit body, distinguished by context)
# ---------------------------------------------------------------------------

@dataclass
class GenerateStmt:
    var_name: str
    start: Union[int, str]   # int for integer literal, str for identifier
    end: Union[int, str]
    body: list
    context: str             # "gate" or "circuit"
    line: int
    column: int

    def dump(self, indent: int = 0) -> str:
        pad = '  ' * indent
        ctx = self.context.capitalize()
        start_s = str(self.start)
        end_s = str(self.end)
        lines = [f"{pad}({ctx}Generate {self.var_name} from {start_s} to {end_s} @{self.line}:{self.column}"]
        for item in self.body:
            lines.append(item.dump(indent + 1))
        lines.append(f"{pad})")
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Top-level declarations
# ---------------------------------------------------------------------------

@dataclass
class GateDecl:
    name: str
    inputs: List[PortDecl]
    output: PortDecl
    body: list
    line: int
    column: int

    def dump(self, indent: int = 0) -> str:
        pad = '  ' * indent
        inp = ' '.join(p.dump() for p in self.inputs)
        lines = [
            f"{pad}(GateDecl {self.name} @{self.line}:{self.column}",
            f"{pad}  (inputs {inp})",
            f"{pad}  (output {self.output.dump()})",
            f"{pad}  (body",
        ]
        for item in self.body:
            lines.append(item.dump(indent + 3))
        lines.append(f"{pad}  ))")
        return '\n'.join(lines)


@dataclass
class CircuitDecl:
    name: str
    inputs: List[PortDecl]
    outputs: List[PortDecl]
    body: list
    line: int
    column: int

    def dump(self, indent: int = 0) -> str:
        pad = '  ' * indent
        inp = ' '.join(p.dump() for p in self.inputs)
        out = ' '.join(p.dump() for p in self.outputs)
        lines = [
            f"{pad}(CircuitDecl {self.name} @{self.line}:{self.column}",
            f"{pad}  (inputs {inp})",
            f"{pad}  (outputs {out})",
            f"{pad}  (body",
        ]
        for item in self.body:
            lines.append(item.dump(indent + 3))
        lines.append(f"{pad}  ))")
        return '\n'.join(lines)


@dataclass
class SimulationCall:
    ref_name: str
    args: List[SimArgBinding]
    line: int
    column: int

    def dump(self, indent: int = 0) -> str:
        pad = '  ' * indent
        args_str = ' '.join(a.dump() for a in self.args)
        return f"{pad}(SimulationCall {self.ref_name} (args {args_str}))"


@dataclass
class ParamDecl:
    """A top-level compile-time constant: param N = 4;"""
    name: str
    value: int
    line: int
    column: int

    def dump(self, indent: int = 0) -> str:
        pad = '  ' * indent
        return f"{pad}(ParamDecl {self.name} = {self.value})"


# ---------------------------------------------------------------------------
# Program root
# ---------------------------------------------------------------------------

@dataclass
class Program:
    items: list

    def dump(self, indent: int = 0) -> str:
        inner = '\n'.join(item.dump(indent + 1) for item in self.items)
        return f"(Program\n{inner})"
