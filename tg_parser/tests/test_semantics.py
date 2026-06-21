import subprocess, sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def run(path):
    return subprocess.run(
        [sys.executable, 'main.py', path, '--run'],
        cwd=ROOT, capture_output=True, text=True
    )

def test_undefined_component():
    r = run('tg_parser/tests/semantic/undefined_component.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert "undefined component 'UnknownGate'" in r.stderr

def test_duplicate_component():
    r = run('tg_parser/tests/semantic/duplicate_component.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert 'already defined' in r.stderr

def test_undefined_node():
    r = run('tg_parser/tests/semantic/undefined_node.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert "undefined net 'ghost'" in r.stderr

def test_undefined_wire():
    r = run('tg_parser/tests/semantic/undefined_wire.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert "undefined wire or port 'ghost'" in r.stderr

def test_previously_deferred_unknown_component():
    r = run('tg_parser/tests/edge_cases/unknown_component_semantic_deferred_valid.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr

def test_previously_deferred_wrong_arity():
    # wrong_arity_semantic_deferred_valid.tg calls NAND2(0) with no NAND2 defined,
    # so SemanticAnalyzer raises undefined-component first (before TypeChecker runs).
    r = run('tg_parser/tests/edge_cases/wrong_arity_semantic_deferred_valid.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr

def test_forward_component_reference():
    r = run('tg_parser/tests/edge_cases/forward_reference_valid.tg')
    assert r.returncode == 0, r.stderr
    assert 'UseINV(x=0) -> z=1' in r.stdout
    assert 'UseINV(x=1) -> z=0' in r.stdout

def test_vdd_component_name_rejected():
    r = run('tg_parser/tests/semantic/vdd_component_name.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert 'VDD' in r.stderr and 'reserved' in r.stderr

def test_gnd_component_name_rejected():
    r = run('tg_parser/tests/semantic/gnd_component_name.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert 'GND' in r.stderr and 'reserved' in r.stderr

def test_incomplete_named_output_rejected():
    r = run('tg_parser/tests/semantic/incomplete_named_output.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert 'carry' in r.stderr and 'not bound' in r.stderr

def test_duplicate_named_output_rejected():
    r = run('tg_parser/tests/semantic/duplicate_named_output.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert 'duplicate' in r.stderr and 'sum' in r.stderr

def test_nested_genvar_shadowing_rejected():
    r = run('tg_parser/tests/edge_cases/genvar_shadowing_invalid.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert 'shadows' in r.stderr

def test_generated_duplicate_label_rejected():
    r = run('tg_parser/tests/edge_cases/generated_duplicate_label.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert 'duplicate' in r.stderr and 'label' in r.stderr

def test_genvar_leakage_rejected():
    r = run('tg_parser/tests/edge_cases/genvar_leakage.tg')
    assert r.returncode != 0 and 'Semantic error' in r.stderr
    assert "undefined wire or port 'j'" in r.stderr
