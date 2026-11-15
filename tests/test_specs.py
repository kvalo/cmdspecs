# Integration tests: run the cmdspecs script on the spec dirs in specs/.
#
# Each spec dir is copied to a temporary directory first, because
# cmdspecs writes its -actual and -diff files next to the specs.


import shutil
import subprocess
from pathlib import Path

import pytest


TESTS = Path(__file__).resolve().parent
CMDSPECS = TESTS.parent / 'cmdspecs'
SPECS = TESTS / 'specs'


def run_cmdspecs(*args, cwd):
    return subprocess.run([str(CMDSPECS), *map(str, args)], cwd=cwd,
                          capture_output=True, text=True)


def copy_spec(name, tmp_path):
    return shutil.copytree(SPECS / name, tmp_path / name)


@pytest.mark.parametrize('name', ['echo', 'sort'])
def test_passing_spec(name, tmp_path):
    spec = copy_spec(name, tmp_path)
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'tests OK, 0 failures' in result.stdout


def test_failing_spec_reports_diff(tmp_path):
    spec = copy_spec('fail', tmp_path)
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAIL: fail: stdout diff' in result.stdout
    assert 'FAIL' not in result.stderr
    assert '0/1 tests OK, 1 failures' in result.stdout
    assert (spec / 'fail.stdout-actual').exists()
