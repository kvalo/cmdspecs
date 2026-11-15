# Integration tests: run the cmdspecs script on the spec dirs in specs/.
#
# Each spec dir is copied to a temporary directory first, because
# cmdspecs writes its -actual and -diff files next to the specs.


import os
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


@pytest.mark.parametrize('name', ['echo', 'sort', 'stderr', 'exit',
                                  'env'])
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


def write_script(path, body):
    path.write_text('#!/bin/sh\n' + body)
    path.chmod(0o755)


def test_hooks_run_in_order(tmp_path):
    spec = copy_spec('hooks', tmp_path)
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / 'log').read_text().splitlines() == [
        'setup_once ',
        'setup a', 'a.setup', 'a.script', 'a.teardown', 'teardown a',
        'setup b', 'b.setup', 'b.script', 'b.teardown', 'teardown b',
        'teardown_once ',
    ]


def test_runs_tests_from_multiple_dirs(tmp_path):
    echo = copy_spec('echo', tmp_path)
    sort = copy_spec('sort', tmp_path)
    result = run_cmdspecs(echo, sort, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '3/3 tests OK, 0 failures' in result.stdout


def test_test_option_runs_only_named_test(tmp_path):
    echo = copy_spec('echo', tmp_path)
    sort = copy_spec('sort', tmp_path)
    result = run_cmdspecs('-t', 'hello', echo, sort, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1/1 tests OK, 0 failures' in result.stdout


def test_timings_option_reports_timings(tmp_path):
    spec = copy_spec('echo', tmp_path)
    result = run_cmdspecs('--timings', spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Timings (in seconds):' in result.stdout
    assert 'whole test suite' in result.stdout


def test_keep_option_keeps_work_area_on_failure(tmp_path):
    spec = copy_spec('fail', tmp_path)
    result = run_cmdspecs('--keep', spec, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    prefix = 'Test work area: '
    lines = [x for x in result.stdout.splitlines() if x.startswith(prefix)]
    assert len(lines) == 1
    workdir = Path(lines[0][len(prefix):])
    try:
        assert (workdir / 'data' / 'file.txt').exists()
    finally:
        shutil.rmtree(workdir)


def test_success_leaves_no_output_files(tmp_path):
    spec = copy_spec('sort', tmp_path)
    before = sorted(spec.iterdir())
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(spec.iterdir()) == before


def test_counts_failed_tests_not_failures(tmp_path):
    write_script(tmp_path / 'foo.script', 'echo unexpected\nexit 3\n')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert '0/1 tests OK, 1 failures' in result.stdout


def test_reports_missing_script(tmp_path):
    (tmp_path / 'foo.stdout').write_text('hello\n')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAIL: foo: missing foo.script' in result.stdout
    assert 'Traceback' not in result.stderr


def test_reports_failing_setup(tmp_path):
    write_script(tmp_path / 'setup', 'exit 1\n')
    write_script(tmp_path / 'foo.script', '')
    write_script(tmp_path / 'bar.script', '')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAIL: foo: %s: exited with 1' % (tmp_path / 'setup') \
        in result.stdout
    assert '0/2 tests OK, 2 failures' in result.stdout
    assert 'Traceback' not in result.stderr


def test_failing_setup_once_aborts_and_cleans_up(tmp_path):
    write_script(tmp_path / 'setup_once', 'exit 2\n')
    write_script(tmp_path / 'foo.script', '')
    tmpdir = tmp_path / 'tmp'
    tmpdir.mkdir()
    result = subprocess.run([str(CMDSPECS), str(tmp_path)], cwd=tmp_path,
                            env={**os.environ, 'TMPDIR': str(tmpdir)},
                            capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == 'cmdspecs: %s: exited with 2\n' % \
        (tmp_path / 'setup_once')
    assert list(tmpdir.iterdir()) == []


def test_reports_non_executable_script(tmp_path):
    script = tmp_path / 'foo.script'
    script.write_text('#!/bin/sh\n')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout == ('FAIL: foo: could not run %s: '
                             'Permission denied\n'
                             '0/1 tests OK, 1 failures\n' % script)


def test_reports_non_utf8_output(tmp_path):
    write_script(tmp_path / 'foo.script', "printf '\\377\\n'\n")
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAIL: foo: stdout diff' in result.stdout
    assert '\n+\\xff\n' in result.stdout
    assert 'Traceback' not in result.stderr


def test_test_option_matches_exact_name(tmp_path):
    write_script(tmp_path / 'foo.script', '')
    write_script(tmp_path / 'foo.bar.script', '')
    result = run_cmdspecs('-t', 'foo', tmp_path, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1/1 tests OK, 0 failures' in result.stdout
