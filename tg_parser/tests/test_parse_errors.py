import subprocess, sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def run(path, *flags):
    args = [sys.executable, 'main.py', path] + list(flags)
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True)


def test_old_plus_or_rejected():
    r = run('tg_parser/tests/invalid/old_plus_or.tg', '--run')
    assert r.returncode != 0
    assert 'Syntax error' in r.stderr
    assert "'+' is not a valid logic operator" in r.stderr
    assert "use '|' for logical OR" in r.stderr


def test_old_positional_sim_call_rejected():
    r = run('tg_parser/tests/invalid/invalid5_top_level_instance_label.tg', '--run')
    assert r.returncode != 0
    assert 'Syntax error' in r.stderr


def test_bad_logic_literal_rejected():
    r = run('tg_parser/tests/invalid/bad_logic_literal.tg', '--run')
    assert r.returncode != 0
    assert 'Syntax error' in r.stderr or 'error' in r.stderr.lower()


def test_identifier_in_sim_expr_rejected():
    r = run('tg_parser/tests/invalid/identifier_in_simulation_expr.tg', '--run')
    assert r.returncode != 0


def test_generate_missing_from_keyword():
    r = run('tg_parser/tests/invalid/generate_missing_in.tg', '--run')
    assert r.returncode != 0
    assert 'Syntax error' in r.stderr or 'Semantic error' in r.stderr


def test_generate_missing_to_keyword():
    r = run('tg_parser/tests/invalid/generate_missing_range.tg', '--run')
    assert r.returncode != 0


def test_param_generate_valid():
    r = run('tg_parser/tests/edge_cases/param_generate_valid.tg', '--run')
    assert r.returncode == 0, r.stderr
    assert 'INV_PARAM(a=[0, 1, 0, 1]) -> y[0]=1, y[1]=0, y[2]=1, y[3]=0' in r.stdout
