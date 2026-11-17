# Copyright 2026  Kalle Valo
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
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
    # Each spec dir whose tests are expected to pass (echo, sort,
    # stderr, exit, env) makes cmdspecs exit with 0.
    spec = copy_spec(name, tmp_path)
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ' passed in ' in result.stdout
    assert 'failed' not in result.stdout


def test_failing_spec_reports_diff(tmp_path):
    # A failing test makes cmdspecs exit with 1, show the stdout diff
    # and keep the -actual file.
    spec = copy_spec('fail', tmp_path)
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAILED fail - stdout diff:' in result.stdout
    assert 'FAIL' not in result.stderr
    assert ' 1 failed in ' in result.stdout
    assert (spec / 'fail.stdout-actual').exists()


def write_script(path, body):
    path.write_text('#!/bin/sh\n' + body)
    path.chmod(0o755)


def test_hooks_run_in_order(tmp_path):
    # Setup_once, setup, <name>.setup, the script, <name>.teardown,
    # teardown and teardown_once run in that order.
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
    # Several dirs given on the command line are all run and counted
    # together.
    echo = copy_spec('echo', tmp_path)
    sort = copy_spec('sort', tmp_path)
    result = run_cmdspecs(echo, sort, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ' 3 passed in ' in result.stdout


def test_each_dir_uses_its_own_hooks(tmp_path):
    # The hooks of each dir run only for that dir, and its setup_once
    # and teardown_once surround its tests.
    for name in ['one', 'two']:
        d = tmp_path / name
        d.mkdir()
        for hook in ['setup_once', 'setup', 'teardown', 'teardown_once']:
            write_script(d / hook, 'echo "%s/%s $TESTNAME" >> "%s"\n' %
                         (name, hook, tmp_path / 'log'))
        write_script(d / (name + '-test.script'), '')
    result = run_cmdspecs('one', 'two', cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / 'log').read_text().splitlines() == [
        'one/setup_once ',
        'one/setup one-test', 'one/teardown one-test',
        'one/teardown_once ',
        'two/setup_once ',
        'two/setup two-test', 'two/teardown two-test',
        'two/teardown_once ',
    ]


def test_dirs_share_datadir(tmp_path):
    # The manpage promises one DATADIR for the whole run, shared by all
    # dirs and not emptied between them: a file written by a test in
    # the first dir must still be there for a test in the second dir.
    for name in ['one', 'two']:
        (tmp_path / name).mkdir()
    write_script(tmp_path / 'one' / 'write.script',
                 'echo hello > "$DATADIR/file"\n')
    write_script(tmp_path / 'two' / 'read.script', 'cat "$DATADIR/file"\n')
    (tmp_path / 'two' / 'read.stdout').write_text('hello\n')
    result = run_cmdspecs('one', 'two', cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ' 2 passed in ' in result.stdout


def test_test_option_runs_only_named_test(tmp_path):
    # -t runs only the named test, even when other dirs have more tests.
    echo = copy_spec('echo', tmp_path)
    sort = copy_spec('sort', tmp_path)
    result = run_cmdspecs('-t', 'hello', echo, sort, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ' 1 passed in ' in result.stdout


def test_timings_option_reports_timings(tmp_path):
    # --timings prints a timings section which includes the whole suite.
    spec = copy_spec('echo', tmp_path)
    result = run_cmdspecs('--timings', spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Timings (in seconds):' in result.stdout
    assert 'whole test suite' in result.stdout


def test_keep_option_keeps_work_area_on_failure(tmp_path):
    # --keep leaves the work area (with the DATADIR contents) in place
    # after a failure and tells where it is.
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
    # Running passing tests does not add any files to the spec dir.
    spec = copy_spec('sort', tmp_path)
    before = sorted(spec.iterdir())
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(spec.iterdir()) == before


def test_counts_failed_tests_not_failures(tmp_path):
    # A test with several failures (output and exit code) counts as one
    # failed test.
    write_script(tmp_path / 'foo.script', 'echo unexpected\nexit 3\n')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ' 1 failed in ' in result.stdout


def test_reports_missing_script(tmp_path):
    # A test with files but no .script is reported as failed, without a
    # traceback.
    (tmp_path / 'foo.stdout').write_text('hello\n')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAILED foo - missing foo.script' in result.stdout
    assert 'Traceback' not in result.stderr


def test_reports_failing_setup(tmp_path):
    # A failing dir-level setup fails every test of the dir and is
    # reported, without a traceback.
    write_script(tmp_path / 'setup', 'exit 1\n')
    write_script(tmp_path / 'foo.script', '')
    write_script(tmp_path / 'bar.script', '')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAILED foo - %s: exited with 1' % (tmp_path / 'setup') \
        in result.stdout
    assert ' 2 failed in ' in result.stdout
    assert 'Traceback' not in result.stderr


def test_failing_setup_once_aborts_and_cleans_up(tmp_path):
    # A failing setup_once aborts the run with an error and removes the
    # temporary work area.
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
    # A script without the execute permission is reported as failed with
    # the reason, not a crash.
    script = tmp_path / 'foo.script'
    script.write_text('#!/bin/sh\n')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ('FAILED foo - could not run %s: Permission denied\n' %
            script) in result.stdout
    assert ' 1 failed in ' in result.stdout


def test_reports_non_utf8_output(tmp_path):
    # Output which is not valid UTF-8 is reported as a diff without a
    # traceback.
    write_script(tmp_path / 'foo.script', "printf '\\377\\n'\n")
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAILED foo - stdout diff:' in result.stdout
    assert '\n+\\xff\n' in result.stdout
    assert 'Traceback' not in result.stderr


def test_test_option_matches_exact_name(tmp_path):
    # -t foo does not also run foo.bar, because names are matched
    # exactly.
    write_script(tmp_path / 'foo.script', '')
    write_script(tmp_path / 'foo.bar.script', '')
    result = run_cmdspecs('-t', 'foo', tmp_path, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ' 1 passed in ' in result.stdout


def test_shows_header_and_dots(tmp_path):
    # The real output has the session header, the number of tests
    # collected and a dot line for the dir.
    spec = copy_spec('sort', tmp_path)
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert 'test session starts' in lines[0]
    assert 'collected 2 tests' in lines
    assert any(x.startswith('%s .. ' % spec) and x.endswith('[100%]')
               for x in lines)


def test_header_shows_settings(tmp_path):
    # The header shows SRCDIR, DATADIR, whether --keep is enabled, the
    # test dirs and, when -t is given, the selected tests.
    spec = copy_spec('sort', tmp_path)
    result = run_cmdspecs('-k', '-t', 'empty', spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert 'srcdir: %s' % tmp_path in lines
    assert any(x.startswith('datadir: ') and x.endswith('/data')
               for x in lines)
    assert 'keep: yes' in lines
    assert 'testdirs: %s' % spec in lines
    assert 'tests: empty' in lines


def test_header_shows_keep_disabled(tmp_path):
    # Without -k the header says so, and no tests line is shown when
    # all tests are run.
    spec = copy_spec('sort', tmp_path)
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert 'keep: no' in lines
    assert not any(x.startswith('tests: ') for x in lines)


def test_verbose_option_shows_test_names(tmp_path):
    # -v prints dir::name PASSED for each test.
    spec = copy_spec('sort', tmp_path)
    result = run_cmdspecs('-v', spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '%s::empty PASSED' % spec in result.stdout
    assert '%s::single-line PASSED' % spec in result.stdout


def test_color_option_colors_output(tmp_path):
    # --color=yes adds color even when output is not a terminal.
    spec = copy_spec('sort', tmp_path)
    result = run_cmdspecs('--color=yes', spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '\x1b[' in result.stdout


def test_no_colors_when_not_a_terminal(tmp_path):
    # By default no color is written when output is not a terminal.
    spec = copy_spec('sort', tmp_path)
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '\x1b' not in result.stdout


def test_reports_unknown_test(tmp_path):
    # -t with an unknown test name exits with 2 and an error on stderr,
    # before running anything.
    spec = copy_spec('echo', tmp_path)
    result = run_cmdspecs('-t', 'hello', '-t', 'nosuch', spec, cwd=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert 'cmdspecs: error: no such test: nosuch\n' in result.stderr
    assert result.stdout == ''


@pytest.mark.parametrize('args', [(), ('-t', 'foo')])
def test_reports_missing_dir(args, tmp_path):
    # A nonexistent dir, with or without -t, exits with 2 and a clear
    # error, without a traceback.
    result = run_cmdspecs(*args, 'nosuch', cwd=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert 'cmdspecs: error: nosuch: No such file or directory\n' \
        in result.stderr
    assert 'Traceback' not in result.stderr


def test_script_does_not_read_stdin_of_cmdspecs(tmp_path):
    # Scripts and setup get empty stdin, not the stdin of cmdspecs
    # itself.
    write_script(tmp_path / 'setup', 'cat\n')
    write_script(tmp_path / 'foo.script', 'cat\n')
    result = subprocess.run([str(CMDSPECS), str(tmp_path)], cwd=tmp_path,
                            input='surprise\n', capture_output=True,
                            text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'surprise' not in result.stdout


def test_runs_teardown_after_failing_test_setup(tmp_path):
    # Teardown still runs when the test setup failed, so partial setup
    # is cleaned up.
    write_script(tmp_path / 'teardown', 'touch "$SRCDIR/teardown-ran"\n')
    write_script(tmp_path / 'foo.setup', 'exit 1\n')
    write_script(tmp_path / 'foo.script', '')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAILED foo - %s: exited with 1' % (tmp_path / 'foo.setup') \
        in result.stdout
    assert (tmp_path / 'teardown-ran').exists()


def test_failing_teardown_does_not_hide_diff(tmp_path):
    # A failing teardown is reported together with the output diff, not
    # instead of it.
    write_script(tmp_path / 'teardown', 'exit 1\n')
    write_script(tmp_path / 'foo.script', 'echo unexpected\n')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAILED foo - stdout diff:' in result.stdout
    assert '%s: exited with 1\n' % (tmp_path / 'teardown') in result.stdout


def test_failing_teardown_once_keeps_results(tmp_path):
    # A failing teardown_once is reported on stderr and exit 1, but the
    # test results are still shown.
    write_script(tmp_path / 'teardown_once', 'exit 2\n')
    write_script(tmp_path / 'foo.script', '')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ' 1 passed in ' in result.stdout
    assert result.stderr == 'cmdspecs: %s: exited with 2\n' % \
        (tmp_path / 'teardown_once')


def test_reports_invalid_exit_file(tmp_path):
    # A non-numeric .exit file fails the test with a message, without a
    # traceback.
    write_script(tmp_path / 'foo.script', '')
    (tmp_path / 'foo.exit').write_text('zero\n')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FAILED foo - invalid %s: ' % (tmp_path / 'foo.exit') \
        in result.stdout
    assert 'Traceback' not in result.stderr


def test_removes_work_area_with_read_only_dirs(tmp_path):
    # The temporary work area is fully removed even if a test left
    # read-only dirs in DATADIR.
    write_script(tmp_path / 'foo.script',
                 'mkdir -p "$DATADIR/a/b"\n'
                 'touch "$DATADIR/a/b/file"\n'
                 'chmod 0 "$DATADIR/a/b"\n'
                 'chmod a-w "$DATADIR/a"\n')
    tmpdir = tmp_path / 'tmp'
    tmpdir.mkdir()
    result = subprocess.run([str(CMDSPECS), str(tmp_path)], cwd=tmp_path,
                            env={**os.environ, 'TMPDIR': str(tmpdir)},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ''
    assert list(tmpdir.iterdir()) == []


def test_timings_tell_tests_of_different_dirs_apart(tmp_path):
    # --timings names tests with their dir, so same-named tests in
    # different dirs are listed separately.
    for name in ['one', 'two']:
        (tmp_path / name).mkdir()
        write_script(tmp_path / name / 'foo.script', '')
    result = run_cmdspecs('--timings', 'one', 'two', cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '  one/foo: ' in result.stdout
    assert '  two/foo: ' in result.stdout
