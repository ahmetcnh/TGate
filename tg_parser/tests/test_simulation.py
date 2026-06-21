import os, sys, subprocess
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

def run_sim(path):
    return subprocess.run(
        [sys.executable, 'main.py', path, '--run'],
        cwd=ROOT, capture_output=True, text=True
    )

def test_inv_truth_table():
    r = run_sim('tg_parser/tests/valid/valid1_inv.tg')
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0] == 'INV(a=0) -> y=1'
    assert lines[1] == 'INV(a=1) -> y=0'

def test_nand2_truth_table():
    r = run_sim('tg_parser/tests/valid/valid2_nand2.tg')
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0] == 'NAND2(a=0, b=0) -> y=1'
    assert lines[1] == 'NAND2(a=0, b=1) -> y=1'
    assert lines[2] == 'NAND2(a=1, b=1) -> y=0'

def test_half_adder_truth_table():
    r = run_sim('tg_parser/tests/valid/valid3_half_adder.tg')
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0] == 'HalfAdder(a=0, b=0) -> sum=0, carry=0'
    assert lines[1] == 'HalfAdder(a=0, b=1) -> sum=1, carry=0'
    assert lines[2] == 'HalfAdder(a=1, b=1) -> sum=0, carry=1'

def test_d3_program2_inv_array():
    r = run_sim('tg_parser/tests/simulation/d3_program2_inv_array.tg')
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0] == 'INV_ARRAY(a=[0, 1, 0, 1]) -> y[0]=1, y[1]=0, y[2]=1, y[3]=0'

def test_d3_program3_nand_array():
    r = run_sim('tg_parser/tests/simulation/d3_program3_nand_array.tg')
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0] == 'NAND_ARRAY(a=[0, 0, 0, 1], b=[1, 0, 1, 1]) -> y[0]=1, y[1]=1, y[2]=1, y[3]=0'
