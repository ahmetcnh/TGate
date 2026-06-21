import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from tg_parser.lexer import Lexer
from tg_parser.parser import Parser
from tg_parser.ast_nodes import GenerateStmt, InstanceStmt, NodeDecl, TransistorStmt, SignalRef, IndexLit

def parse(src):
    return Parser(Lexer(src).tokenize()).parse_program()

def test_basic_circuit_generate_expands_labels_and_indices():
    from tg_parser.elaborator import Elaborator
    src = open(os.path.join(ROOT, 'tg_parser/tests/edge_cases/generate_basic_valid.tg')).read()
    program = parse(src)
    elab = Elaborator(program).elaborate()
    circuit = elab.items[0]
    assert not any(isinstance(s, GenerateStmt) for s in circuit.body)
    assert len(circuit.body) == 4
    labels = [s.label for s in circuit.body]
    assert labels == ['g_0', 'g_1', 'g_2', 'g_3']
    # Check index substitution: first instance arg should be a[0]
    first_arg = circuit.body[0].args[0]
    assert isinstance(first_arg, SignalRef)
    assert isinstance(first_arg.indices[0], IndexLit)
    assert first_arg.indices[0].value == 0

def test_gate_generate_expands_node_names():
    from tg_parser.elaborator import Elaborator
    src = """
gate G(in a[2]; out y[2]) {
    generate i from 0 to 1 {
        node mid_i;
        pmos drain=y[i], gate=a[i], source=VDD;
        nmos drain=mid_i, gate=a[i], source=GND;
    }
}
"""
    program = parse(src)
    elab = Elaborator(program).elaborate()
    gate = elab.items[0]
    node_decls = [s for s in gate.body if isinstance(s, NodeDecl)]
    assert len(node_decls) == 2
    assert node_decls[0].names == ['mid_0']
    assert node_decls[1].names == ['mid_1']

def test_identifier_range_bound_raises_semantic_error():
    from tg_parser.elaborator import Elaborator
    from tg_parser.errors import SemanticError
    src = """
circuit C(in a[4]; out y[4]) {
    generate i from 0 to N {
        NAND2 g_i(a[i]) -> y[i];
    }
}
"""
    program = parse(src)
    try:
        Elaborator(program).elaborate()
        assert False, "should have raised SemanticError"
    except SemanticError as e:
        assert "unresolved generate range bound" in str(e)
        assert "'N'" in str(e)
