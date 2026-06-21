import subprocess, sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def run(path):
    return subprocess.run(
        [sys.executable, 'main.py', path, '--run'],
        cwd=ROOT, capture_output=True, text=True
    )

def test_scalar_indexed_raises_type_error():
    r = run('tg_parser/tests/type_errors/scalar_indexed.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert 'scalar' in r.stderr.lower() or 'index' in r.stderr.lower()

def test_array_as_scalar_raises_type_error():
    r = run('tg_parser/tests/type_errors/array_as_scalar_arg.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr

def test_scalar_as_array_raises_type_error():
    r = run('tg_parser/tests/type_errors/scalar_as_array_arg.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr

def test_index_out_of_range_raises_type_error():
    r = run('tg_parser/tests/type_errors/index_out_of_range.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert 'out of range' in r.stderr

def test_multi_index_raises_type_error():
    r = run('tg_parser/tests/type_errors/multi_index.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert 'multi-index' in r.stderr.lower() or 'one-dimensional' in r.stderr.lower()

def test_wrong_arity_instance_raises_type_error():
    r = run('tg_parser/tests/type_errors/wrong_arity_instance.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr

def test_wrong_arity_sim_call_raises_type_error():
    r = run('tg_parser/tests/type_errors/wrong_arity_sim_call.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert "missing argument 'b'" in r.stderr

def test_sim_call_unknown_arg_raises_type_error():
    r = run('tg_parser/tests/type_errors/sim_call_unknown_arg.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert "unknown argument 'x'" in r.stderr
    assert "valid input ports" in r.stderr

def test_sim_call_duplicate_arg_raises_type_error():
    r = run('tg_parser/tests/type_errors/sim_call_duplicate_arg.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert "duplicate argument 'a'" in r.stderr

def test_sim_call_vector_length_mismatch_raises_type_error():
    r = run('tg_parser/tests/type_errors/sim_call_vector_length_mismatch.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert '2 bits' in r.stderr
    assert 'logic[4]' in r.stderr

def test_undefined_param_raises_error():
    r = run('tg_parser/tests/type_errors/undefined_param.tg')
    assert r.returncode != 0
    assert "undefined param 'N'" in r.stderr

def test_logic1_vs_logic_mismatch():
    r = run('tg_parser/tests/type_errors/logic1_vs_logic_mismatch.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert 'logic[1]' in r.stderr

def test_logic4_vs_logic8_mismatch():
    r = run('tg_parser/tests/type_errors/logic4_vs_logic8_mismatch.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert 'logic[4]' in r.stderr and 'logic[8]' in r.stderr

def test_single_output_on_multi_output_circuit():
    r = run('tg_parser/tests/type_errors/single_output_multi_output.tg')
    assert r.returncode != 0
    assert 'Type error' in r.stderr
    assert 'single-output' in r.stderr or 'named binding' in r.stderr
