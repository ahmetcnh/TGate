import subprocess, sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def run(path, component):
    return subprocess.run(
        [sys.executable, 'main.py', path, '--truth-table', component],
        cwd=ROOT, capture_output=True, text=True
    )


def test_nand2_truth_table():
    r = run('tg_parser/tests/valid/valid2_nand2.tg', 'NAND2')
    assert r.returncode == 0, r.stderr
    assert r.stdout == (
        'NAND2 truth table:\n'
        'a b | y\n'
        '0 0 | 1\n'
        '0 1 | 1\n'
        '1 0 | 1\n'
        '1 1 | 0\n'
    )


def test_half_adder_truth_table():
    r = run('tg_parser/tests/valid/valid3_half_adder.tg', 'HalfAdder')
    assert r.returncode == 0, r.stderr
    assert r.stdout == (
        'HalfAdder truth table:\n'
        'a b | sum carry\n'
        '0 0 | 0 0\n'
        '0 1 | 1 0\n'
        '1 0 | 1 0\n'
        '1 1 | 0 1\n'
    )


def test_inv_array_truth_table():
    r = run('tg_parser/tests/simulation/d3_program2_inv_array.tg', 'INV_ARRAY')
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    assert lines[0] == 'INV_ARRAY truth table:'
    assert lines[1] == 'a[0] a[1] a[2] a[3] | y[0] y[1] y[2] y[3]'
    assert lines[2] == '0 0 0 0 | 1 1 1 1'
    assert lines[-1] == '1 1 1 1 | 0 0 0 0'
    assert len(lines) == 18  # 2 header + 16 data rows


def test_missing_component_rejected():
    r = run('tg_parser/tests/valid/valid2_nand2.tg', 'MISSING')
    assert r.returncode != 0
    assert "component 'MISSING' not found for --truth-table" in r.stderr
