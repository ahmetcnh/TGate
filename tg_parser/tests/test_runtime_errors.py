import subprocess, sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def run(path):
    return subprocess.run(
        [sys.executable, 'main.py', path, '--run'],
        cwd=ROOT, capture_output=True, text=True
    )

def test_floating_output_raises_simulation_error():
    r = run('tg_parser/tests/runtime_errors/floating_output.tg')
    assert r.returncode != 0
    assert 'Simulation error' in r.stderr
    assert "floating output 'y'" in r.stderr

def test_short_circuit_raises_simulation_error():
    r = run('tg_parser/tests/runtime_errors/short_circuit.tg')
    assert r.returncode != 0
    assert 'Simulation error' in r.stderr
    assert "short-circuit" in r.stderr
