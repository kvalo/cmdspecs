# Copyright 2026  Kalle Valo
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Integration tests: run the cmdspecs script on the spec dirs in specs/.
#
# Each spec dir is copied to a temporary directory first, because
# cmdspecs writes its -actual and -diff files next to the specs.


import importlib.machinery
import importlib.util
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest


TESTS = Path(__file__).resolve().parent
CMDSPECS = TESTS.parent / 'cmdspecs'
SPECS = TESTS / 'specs'

# cmdspecs is a script without a .py extension, so load it explicitly.
_loader = importlib.machinery.SourceFileLoader('cmdspecs', str(CMDSPECS))
_spec = importlib.util.spec_from_loader('cmdspecs', _loader)
cmdspecs = importlib.util.module_from_spec(_spec)
_loader.exec_module(cmdspecs)
EXIT_OK = cmdspecs.EXIT_OK
EXIT_FAILED = cmdspecs.EXIT_FAILED
EXIT_INTERRUPTED = cmdspecs.EXIT_INTERRUPTED
EXIT_USAGE = cmdspecs.EXIT_USAGE
EXIT_NO_TESTS = cmdspecs.EXIT_NO_TESTS


def run_cmdspecs(*args, cwd):
    # Wide enough that the long temp dirs of macOS don't wrap the dots.
    return subprocess.run([str(CMDSPECS), *map(str, args)], cwd=cwd,
                          env={**os.environ, 'COLUMNS': '300'},
                          capture_output=True, text=True)


def copy_spec(name, tmp_path):
    return shutil.copytree(SPECS / name, tmp_path / name)


def normalize(text):
    # Replace what varies between runs (machine, paths, timings, the
    # terminal width) with fixed placeholders so the whole output can be
    # compared exactly.
    text = re.sub(r'^platform .*$', 'platform PLATFORM', text, flags=re.M)
    text = re.sub(r'^srcdir: .*$', 'srcdir: SRCDIR', text, flags=re.M)
    text = re.sub(r'^datadir: .*$', 'datadir: DATADIR', text, flags=re.M)
    text = re.sub(r'^Test work area: .*$', 'Test work area: WORKDIR', text,
                  flags=re.M)
    text = re.sub(r'^( +)\d+\.\d (\S)', r'\1T \2', text, flags=re.M)
    text = re.sub(r': \d+\.\d s$', ': T s', text, flags=re.M)
    text = re.sub(r'\b\d+\.\d\ds\b', '0.00s', text)
    text = re.sub(r'\t\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+ [+-]\d{4}$',
                  '\tTIMESTAMP', text, flags=re.M)
    # "=== title ===" and "___ title ___" lines, whatever their width.
    text = re.sub(r'^([=_])\1* (.*?) \1+$', r'\1\1\1 \2 \1\1\1', text,
                  flags=re.M)
    # "name .F. [100%]" lines, whatever their padding.
    text = re.sub(r'^(\S+ \S*) +\[ *(\d+)%\]$', r'\1 [\2%]', text,
                  flags=re.M)
    return text


def assert_output(result, stdout='', stderr='', returncode=EXIT_OK):
    # Compare the exit code and both streams exactly (stdout after
    # normalize()), so that any extra output is a failure.
    assert (result.returncode, normalize(result.stdout), result.stderr) == (
        returncode, stdout, stderr)


def session(testdirs, collected, body, summary, keep='no', tests=None,
            timeout=None, trailer=''):
    # What cmdspecs prints, normalized: the header, the dot lines in
    # body and the summary. The tests and timeout lines are only there
    # with -t and -o.
    header = ('=== cmdspecs session starts ===\n'
              'platform PLATFORM\n'
              'srcdir: SRCDIR\n'
              'datadir: DATADIR\n'
              'keep: %s\n'
              'testdirs: %s\n' % (keep, testdirs))
    if tests:
        header += 'tests: %s\n' % tests
    if timeout:
        header += 'timeout: %s seconds\n' % timeout
    return (header + 'collected %s\n\n%s=== %s ===\n%s' %
            (collected, body, summary, trailer))


# argparse doesn't wrap the usage at COLUMNS=300.
USAGE = ('usage: cmdspecs [-h] [-t TEST] [-T] [-o SECONDS] [-k] [-s] [-v] '
         '[-C {auto,yes,no}] [-V] dirnames [dirnames ...]\n')


def failures(*items):
    # The FAILURES and short summary sections for failed (name, message)
    # tests; the summary shows just the first line of a message.
    out = '=== FAILURES ===\n'
    for name, message in items:
        out += '___ %s ___\n%s' % (name, message)
    out += '=== short test summary info ===\n'
    for name, message in items:
        out += 'FAILED %s - %s\n' % (name, message.split('\n')[0])
    return out


FAIL_DIFF = (
    '=== FAILURES ===\n'
    '___ fail ___\n'
    'stdout diff:\n'
    '--- /dev/null\tTIMESTAMP\n'
    '+++ fail/fail.stdout-actual\tTIMESTAMP\n'
    '@@ -0,0 +1 @@\n'
    '+this is not empty output to make test fail\n'
    '=== short test summary info ===\n'
    'FAILED fail - stdout diff:\n')


@pytest.mark.parametrize('name, tests', [('echo', 1), ('sort', 2),
                                         ('stderr', 1), ('exit', 1),
                                         ('env', 2)])
def test_passing_spec(name, tests, tmp_path):
    # Each spec dir whose tests are expected to pass makes cmdspecs
    # exit with 0 and print nothing but the session, the dots and the
    # summary.
    spec = copy_spec(name, tmp_path)
    result = run_cmdspecs(name, cwd=tmp_path)
    assert_output(result, session(
        name, '%d test%s' % (tests, 's' * (tests > 1)),
        '%s %s [100%%]\n' % (name, '.' * tests),
        '%d passed in 0.00s' % tests))
    assert not list(spec.glob('*-actual'))


def test_failing_spec_reports_diff(tmp_path):
    # A failing test makes cmdspecs exit with 1, show the stdout diff
    # and keep the -actual file.
    spec = copy_spec('fail', tmp_path)
    result = run_cmdspecs('fail', cwd=tmp_path)
    assert_output(result, session(
        'fail', '1 test', 'fail F [100%]\n\n' + FAIL_DIFF,
        '1 failed in 0.00s'), returncode=EXIT_FAILED)
    assert (spec / 'fail.stdout-actual').exists()


def write_script(path, body):
    path.write_text('#!/bin/sh\n' + body)
    path.chmod(0o755)


def test_hooks_run_in_order(tmp_path):
    # Setup_once, setup, <name>.setup, the script, <name>.teardown,
    # teardown and teardown_once run in that order.
    spec = copy_spec('hooks', tmp_path)
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == EXIT_OK, result.stdout + result.stderr
    assert (tmp_path / 'log').read_text().splitlines() == [
        'setup_once ',
        'setup a', 'a.setup', 'a.script', 'a.teardown', 'teardown a',
        'setup b', 'b.setup', 'b.script', 'b.teardown', 'teardown b',
        'teardown_once ',
    ]


def test_runs_tests_from_multiple_dirs(tmp_path):
    # Several dirs given on the command line are all run and counted
    # together.
    copy_spec('echo', tmp_path)
    copy_spec('sort', tmp_path)
    result = run_cmdspecs('echo', 'sort', cwd=tmp_path)
    assert_output(result, session(
        'echo, sort', '3 tests',
        'echo . [33%]\n'
        'sort .. [100%]\n',
        '3 passed in 0.00s'))


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
    assert_output(result, session(
        'one, two', '2 tests',
        'one . [50%]\n'
        'two . [100%]\n',
        '2 passed in 0.00s'))
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
    assert_output(result, session(
        'one, two', '2 tests',
        'one . [50%]\n'
        'two . [100%]\n',
        '2 passed in 0.00s'))


def test_test_option_runs_only_named_test(tmp_path):
    # -t runs only the named test, even when other dirs have more tests.
    copy_spec('echo', tmp_path)
    copy_spec('sort', tmp_path)
    result = run_cmdspecs('-t', 'hello', 'echo', 'sort', cwd=tmp_path)
    assert_output(result, session(
        'echo, sort', '1 test',
        'echo . [100%]\n',
        '1 passed in 0.00s', tests='hello'))


def test_timings_option_reports_timings(tmp_path):
    # --timings prints a timings section which includes the whole suite.
    copy_spec('echo', tmp_path)
    result = run_cmdspecs('--timings', 'echo', cwd=tmp_path)
    assert_output(result, session(
        'echo', '1 test', 'echo . [100%]\n', '1 passed in 0.00s',
        trailer='Timings (in seconds):\n'
                '  whole test suite: T s\n'
                '     T echo/setup_once\n'
                '  echo/hello: T s\n'
                '     T echo/hello.setup\n'))


def test_keep_option_keeps_work_area_on_failure(tmp_path):
    # --keep leaves the work area (with the DATADIR contents) in place
    # after a failure and tells where it is.
    copy_spec('fail', tmp_path)
    result = run_cmdspecs('--keep', 'fail', cwd=tmp_path)
    assert_output(result, session(
        'fail', '1 test', 'fail F [100%]\n\n' + FAIL_DIFF,
        '1 failed in 0.00s', keep='yes',
        trailer='Test work area: WORKDIR\n'), returncode=EXIT_FAILED)
    prefix = 'Test work area: '
    lines = [x for x in result.stdout.splitlines() if x.startswith(prefix)]
    assert len(lines) == 1
    workdir = Path(lines[0][len(prefix):])
    try:
        assert (workdir / 'data' / 'file.txt').exists()
    finally:
        shutil.rmtree(workdir)


@pytest.mark.parametrize('hook', ['setup_once', 'teardown_once'])
def test_keep_option_keeps_work_area_on_failing_hook(tmp_path, hook):
    # --keep also keeps the work area when a setup_once or teardown_once
    # script fails, even if no test failed.
    write_script(tmp_path / hook, 'touch "$DATADIR/left-over"\nexit 1\n')
    write_script(tmp_path / 'foo.script', '')
    result = run_cmdspecs('--keep', '.', cwd=tmp_path)
    assert result.returncode == EXIT_FAILED, result.stdout + result.stderr
    assert result.stderr == 'cmdspecs: ./%s: exited with 1\n' % hook
    prefix = 'Test work area: '
    lines = [x for x in result.stdout.splitlines() if x.startswith(prefix)]
    assert len(lines) == 1
    workdir = Path(lines[0][len(prefix):])
    try:
        assert (workdir / 'data' / 'left-over').exists()
    finally:
        shutil.rmtree(workdir)


def test_failing_hook_without_keep_removes_work_area(tmp_path):
    write_script(tmp_path / 'setup_once', 'exit 1\n')
    write_script(tmp_path / 'foo.script', '')
    result = run_cmdspecs('.', cwd=tmp_path)
    assert_output(result, session('.', '1 test', '', '1 error in 0.00s'),
                  'cmdspecs: ./setup_once: exited with 1\n', EXIT_FAILED)


def test_success_leaves_no_output_files(tmp_path):
    # Running passing tests does not add any files to the spec dir.
    spec = copy_spec('sort', tmp_path)
    before = sorted(spec.iterdir())
    result = run_cmdspecs(spec, cwd=tmp_path)
    assert result.returncode == EXIT_OK, result.stdout + result.stderr
    assert sorted(spec.iterdir()) == before


def test_counts_failed_tests_not_failures(tmp_path):
    # A test with several failures (output and exit code) counts as one
    # failed test.
    write_script(tmp_path / 'foo.script', 'echo unexpected\nexit 3\n')
    result = run_cmdspecs('.', cwd=tmp_path)
    assert_output(result, session(
        '.', '1 test', '. F [100%]\n\n'
        '=== FAILURES ===\n'
        '___ foo ___\n'
        'stdout diff:\n'
        '--- /dev/null\tTIMESTAMP\n'
        '+++ ./foo.stdout-actual\tTIMESTAMP\n'
        '@@ -0,0 +1 @@\n'
        '+unexpected\n'
        'got exit code 3, expected 0\n'
        '=== short test summary info ===\n'
        'FAILED foo - stdout diff:\n',
        '1 failed in 0.00s'), returncode=EXIT_FAILED)


def test_reports_missing_script(tmp_path):
    # A test with files but no .script is reported as failed, without a
    # traceback.
    (tmp_path / 'foo.stdout').write_text('hello\n')
    result = run_cmdspecs('.', cwd=tmp_path)
    assert_output(result, session(
        '.', '1 test', '. F [100%]\n\n'
        '=== FAILURES ===\n'
        '___ foo ___\n'
        'missing foo.script\n'
        '=== short test summary info ===\n'
        'FAILED foo - missing foo.script\n',
        '1 failed in 0.00s'), returncode=EXIT_FAILED)


def test_reports_failing_setup(tmp_path):
    # A failing dir-level setup fails every test of the dir and is
    # reported, without a traceback.
    write_script(tmp_path / 'setup', 'exit 1\n')
    write_script(tmp_path / 'foo.script', '')
    write_script(tmp_path / 'bar.script', '')
    result = run_cmdspecs('.', cwd=tmp_path)
    assert_output(result, session(
        '.', '2 tests', '. FF [100%]\n\n'
        '=== FAILURES ===\n'
        '___ bar ___\n'
        './setup: exited with 1\n'
        '___ foo ___\n'
        './setup: exited with 1\n'
        '=== short test summary info ===\n'
        'FAILED bar - ./setup: exited with 1\n'
        'FAILED foo - ./setup: exited with 1\n',
        '2 failed in 0.00s'), returncode=EXIT_FAILED)


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
    assert result.returncode == EXIT_FAILED, result.stdout + result.stderr
    assert result.stderr == 'cmdspecs: %s: exited with 2\n' % \
        (tmp_path / 'setup_once')
    assert list(tmpdir.iterdir()) == []


def test_reports_non_executable_script(tmp_path):
    # A script without the execute permission is reported as failed with
    # the reason, not a crash.
    script = tmp_path / 'foo.script'
    script.write_text('#!/bin/sh\n')
    result = run_cmdspecs('.', cwd=tmp_path)
    msg = 'could not run ./foo.script: Permission denied\n'
    assert_output(result, session(
        '.', '1 test', '. F [100%]\n\n'
        '=== FAILURES ===\n'
        '___ foo ___\n' + msg +
        '=== short test summary info ===\n'
        'FAILED foo - ' + msg,
        '1 failed in 0.00s'), returncode=EXIT_FAILED)


def test_reports_non_utf8_output(tmp_path):
    # Output which is not valid UTF-8 is reported as a diff without a
    # traceback.
    write_script(tmp_path / 'foo.script', "printf '\\377\\n'\n")
    result = run_cmdspecs('.', cwd=tmp_path)
    assert_output(result, session(
        '.', '1 test', '. F [100%]\n\n'
        '=== FAILURES ===\n'
        '___ foo ___\n'
        'stdout diff:\n'
        '--- /dev/null\tTIMESTAMP\n'
        '+++ ./foo.stdout-actual\tTIMESTAMP\n'
        '@@ -0,0 +1 @@\n'
        '+\\xff\n'
        '=== short test summary info ===\n'
        'FAILED foo - stdout diff:\n',
        '1 failed in 0.00s'), returncode=EXIT_FAILED)


def test_test_option_matches_exact_name(tmp_path):
    # -t foo does not also run foo.bar, because names are matched
    # exactly.
    write_script(tmp_path / 'foo.script', '')
    write_script(tmp_path / 'foo.bar.script', '')
    result = run_cmdspecs('-t', 'foo', '.', cwd=tmp_path)
    assert_output(result, session(
        '.', '1 test', '. . [100%]\n', '1 passed in 0.00s', tests='foo'))


def test_shows_header_and_dots(tmp_path):
    # The real output has the session header, the number of tests
    # collected and a dot line for the dir.
    copy_spec('sort', tmp_path)
    result = run_cmdspecs('sort', cwd=tmp_path)
    assert_output(result, session(
        'sort', '2 tests', 'sort .. [100%]\n', '2 passed in 0.00s'))
    # The separator lines fill the terminal width except the last column.
    lines = result.stdout.splitlines()
    assert len(lines[0]) == 299
    assert len(lines[-1]) == 299
    assert lines[8].startswith('sort .. ') and len(lines[8]) == 299


def test_header_shows_settings(tmp_path):
    # The header shows SRCDIR, DATADIR, whether --keep is enabled, the
    # test dirs and, when -t is given, the selected tests.
    copy_spec('sort', tmp_path)
    result = run_cmdspecs('-k', '-t', 'empty', 'sort', cwd=tmp_path)
    assert_output(result, session(
        'sort', '1 test', 'sort . [100%]\n', '1 passed in 0.00s',
        keep='yes', tests='empty'))
    lines = result.stdout.splitlines()
    assert 'srcdir: %s' % tmp_path in lines
    # The work area name says which program made it.
    assert re.fullmatch(r'datadir: .*/cmdspecs-[^/]+/data', lines[3])


def test_header_shows_keep_disabled(tmp_path):
    # Without -k the header says so, and no tests line is shown when
    # all tests are run.
    copy_spec('sort', tmp_path)
    result = run_cmdspecs('sort', cwd=tmp_path)
    assert_output(result, session(
        'sort', '2 tests', 'sort .. [100%]\n', '2 passed in 0.00s'))


def test_verbose_option_shows_test_names(tmp_path):
    # -v prints dir::name PASSED for each test.
    copy_spec('sort', tmp_path)
    result = run_cmdspecs('-v', 'sort', cwd=tmp_path)
    assert_output(result, session(
        'sort', '2 tests',
        'sort::empty PASSED [50%]\n'
        'sort::single-line PASSED [100%]\n',
        '2 passed in 0.00s'))


def test_color_option_colors_output(tmp_path):
    # --color=yes adds color even when output is not a terminal.
    copy_spec('echo', tmp_path)
    result = run_cmdspecs('--color=yes', 'echo', cwd=tmp_path)
    assert result.returncode == EXIT_OK
    assert result.stderr == ''
    bold, green, bold_green, reset = (
        '\x1b[1m', '\x1b[32m', '\x1b[32;1m', '\x1b[0m')

    def sep(title):
        # Centered in 299 columns, the one before the terminal width.
        n = 299 - len(title) - 2
        return '=' * (n // 2) + ' %s ' % title + '=' * (n - n // 2)

    stdout = result.stdout
    # The run-specific header lines carry no color.
    stdout = re.sub(r'^(platform |srcdir: |datadir: ).*\n', '', stdout,
                    flags=re.M)
    assert re.sub(r'\d\.\d\ds', '0.00s', stdout) == (
        bold + sep('cmdspecs session starts') + reset + '\n'
        'keep: no\n'
        'testdirs: echo\n'
        + bold + 'collected 1 test\n' + reset + '\n'
        'echo ' + green + '.' + reset + ' ' * 287 + green + '[100%]' + reset
        + '\n' + bold_green + sep('1 passed in 0.00s') + reset + '\n')


def test_no_colors_when_not_a_terminal(tmp_path):
    # By default no color is written when output is not a terminal.
    copy_spec('sort', tmp_path)
    result = run_cmdspecs('sort', cwd=tmp_path)
    assert_output(result, session(
        'sort', '2 tests', 'sort .. [100%]\n', '2 passed in 0.00s'))
    assert '\x1b' not in result.stdout


def test_reports_unknown_test(tmp_path):
    # -t with an unknown test name exits with 4 and an error on stderr,
    # before running anything.
    copy_spec('echo', tmp_path)
    result = run_cmdspecs('-t', 'hello', '-t', 'nosuch', 'echo',
                          cwd=tmp_path)
    assert_output(result, stderr=USAGE +
                  'cmdspecs: error: no such test: nosuch\n',
                  returncode=EXIT_USAGE)


@pytest.mark.parametrize('args', [(), ('-t', 'foo')])
def test_reports_missing_dir(args, tmp_path):
    # A nonexistent dir, with or without -t, exits with 4 and a clear
    # error, without a traceback.
    result = run_cmdspecs(*args, 'nosuch', cwd=tmp_path)
    assert_output(result, stderr=USAGE + 'cmdspecs: error: nosuch: '
                  'No such file or directory\n', returncode=EXIT_USAGE)


def test_script_does_not_read_stdin_of_cmdspecs(tmp_path):
    # Scripts and setup get empty stdin, not the stdin of cmdspecs
    # itself.
    write_script(tmp_path / 'setup', 'cat\n')
    write_script(tmp_path / 'foo.script', 'cat\n')
    result = subprocess.run([str(CMDSPECS), '.'], cwd=tmp_path,
                            input='surprise\n', capture_output=True,
                            text=True)
    assert_output(result, session(
        '.', '1 test', '. . [100%]\n', '1 passed in 0.00s'))


def test_runs_teardown_after_failing_test_setup(tmp_path):
    # Teardown still runs when the test setup failed, so partial setup
    # is cleaned up.
    write_script(tmp_path / 'teardown', 'touch "$SRCDIR/teardown-ran"\n')
    write_script(tmp_path / 'foo.setup', 'exit 1\n')
    write_script(tmp_path / 'foo.script', '')
    result = run_cmdspecs('.', cwd=tmp_path)
    assert_output(result, session(
        '.', '1 test', '. F [100%]\n\n' + failures(
            ('foo', './foo.setup: exited with 1\n')),
        '1 failed in 0.00s'), returncode=EXIT_FAILED)
    assert (tmp_path / 'teardown-ran').exists()


def test_failing_teardown_does_not_hide_diff(tmp_path):
    # A failing teardown is reported together with the output diff, not
    # instead of it.
    write_script(tmp_path / 'teardown', 'exit 1\n')
    write_script(tmp_path / 'foo.script', 'echo unexpected\n')
    result = run_cmdspecs('.', cwd=tmp_path)
    assert_output(result, session(
        '.', '1 test', '. F [100%]\n\n' + failures(
            ('foo', 'stdout diff:\n'
                    '--- /dev/null\tTIMESTAMP\n'
                    '+++ ./foo.stdout-actual\tTIMESTAMP\n'
                    '@@ -0,0 +1 @@\n'
                    '+unexpected\n'
                    './teardown: exited with 1\n')),
        '1 failed in 0.00s'), returncode=EXIT_FAILED)


def test_failing_teardown_once_keeps_results(tmp_path):
    # A failing teardown_once is reported on stderr, counted as an error
    # in the summary and exit 1, but the test results are still shown.
    write_script(tmp_path / 'teardown_once', 'exit 2\n')
    write_script(tmp_path / 'foo.script', '')
    result = run_cmdspecs('.', cwd=tmp_path)
    assert_output(result, session(
        '.', '1 test', '. . [100%]\n', '1 passed, 1 error in 0.00s'),
        'cmdspecs: ./teardown_once: exited with 2\n', EXIT_FAILED)


def test_reports_invalid_exit_file(tmp_path):
    # A non-numeric .exit file fails the test with a message, without a
    # traceback.
    write_script(tmp_path / 'foo.script', '')
    (tmp_path / 'foo.exit').write_text('zero\n')
    result = run_cmdspecs('.', cwd=tmp_path)
    assert result.returncode == EXIT_FAILED
    assert result.stderr == ''
    out = normalize(result.stdout)
    assert out.startswith(session(
        '.', '1 test', '. F [100%]\n\n', '').rsplit('===', 2)[0])
    assert re.search(r"^FAILED foo - invalid \./foo\.exit: .*zero.*$", out,
                     re.M)


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
    assert result.returncode == EXIT_OK, result.stdout + result.stderr
    assert result.stderr == ''
    assert list(tmpdir.iterdir()) == []


def test_timings_tell_tests_of_different_dirs_apart(tmp_path):
    # --timings names tests with their dir, so same-named tests in
    # different dirs are listed separately.
    for name in ['one', 'two']:
        (tmp_path / name).mkdir()
        write_script(tmp_path / name / 'foo.script', '')
    result = run_cmdspecs('--timings', 'one', 'two', cwd=tmp_path)
    assert_output(result, session(
        'one, two', '2 tests', 'one . [50%]\ntwo . [100%]\n',
        '2 passed in 0.00s',
        trailer='Timings (in seconds):\n'
                '  whole test suite: T s\n'
                '  one/foo: T s\n'
                '  two/foo: T s\n'))


def test_dir_without_tests_is_an_error(tmp_path):
    # A dir without tests is reported, shown as an error in the summary
    # and makes cmdspecs exit with 5.
    (tmp_path / 'empty').mkdir()
    result = run_cmdspecs('empty', cwd=tmp_path)
    assert_output(result, session(
        'empty', '0 tests', '', '1 error in 0.00s'),
        'cmdspecs: empty: no tests found\n', EXIT_NO_TESTS)


def test_empty_dir_does_not_stop_other_dirs(tmp_path):
    # The tests of the other dirs are still run, and a failure takes
    # precedence over the exit status 5.
    (tmp_path / 'empty').mkdir()
    copy_spec('echo', tmp_path)
    result = run_cmdspecs('empty', 'echo', cwd=tmp_path)
    assert_output(result, session(
        'empty, echo', '1 test', 'echo . [100%]\n',
        '1 passed, 1 error in 0.00s'),
        'cmdspecs: empty: no tests found\n', EXIT_NO_TESTS)
    copy_spec('fail', tmp_path)
    result = run_cmdspecs('empty', 'fail', cwd=tmp_path)
    assert_output(result, session(
        'empty, fail', '1 test', 'fail F [100%]\n\n' + FAIL_DIFF,
        '1 failed, 1 error in 0.00s'),
        'cmdspecs: empty: no tests found\n', EXIT_FAILED)


def test_test_option_ignores_dirs_without_the_test(tmp_path):
    # With --test only the named tests matter, so a dir which doesn't
    # have them is not an error.
    (tmp_path / 'empty').mkdir()
    copy_spec('echo', tmp_path)
    result = run_cmdspecs('-t', 'hello', 'empty', 'echo', cwd=tmp_path)
    assert_output(result, session(
        'empty, echo', '1 test', 'echo . [100%]\n', '1 passed in 0.00s',
        tests='hello'))


def test_interrupt_exits_with_interrupted_status(tmp_path):
    # Ctrl-C stops the run with a short message and no traceback.
    write_script(tmp_path / 'foo.script',
                 'kill -INT $PPID\nsleep 5\n')
    result = run_cmdspecs('.', cwd=tmp_path)
    # The interrupt comes while the dot line is unfinished.
    assert_output(result, session(
        '.', '1 test', '. ', '').rsplit('===', 2)[0].rstrip('\n'),
        '\ncmdspecs: interrupted\n', EXIT_INTERRUPTED)


def test_keep_option_keeps_work_area_on_interrupt(tmp_path):
    # --keep also keeps the work area when cmdspecs is interrupted, and
    # tells where it is on stderr as there is no summary.
    write_script(tmp_path / 'foo.script',
                 'touch "$DATADIR/left-over"\nkill -INT $PPID\nsleep 5\n')
    result = run_cmdspecs('--keep', tmp_path, cwd=tmp_path)
    assert result.returncode == EXIT_INTERRUPTED, \
        result.stdout + result.stderr
    prefix = 'Test work area: '
    lines = [x for x in result.stderr.splitlines() if x.startswith(prefix)]
    assert len(lines) == 1
    workdir = Path(lines[0][len(prefix):])
    try:
        assert (workdir / 'data' / 'left-over').exists()
    finally:
        shutil.rmtree(workdir)


def make_hook_dir(tmp_path, hook, body):
    d = tmp_path / 'hooks'
    d.mkdir()
    write_script(d / hook, body)
    write_script(d / 'foo.script', 'true\n')
    return d


def test_hook_output_is_captured_when_it_passes(tmp_path):
    make_hook_dir(tmp_path, 'setup', 'echo noisy-out\necho noisy-err >&2\n')
    result = run_cmdspecs('hooks', cwd=tmp_path)
    assert_output(result, session(
        'hooks', '1 test', 'hooks . [100%]\n', '1 passed in 0.00s'))


def test_failed_hook_output_is_shown_with_failure(tmp_path):
    make_hook_dir(tmp_path, 'setup',
                  'echo noisy-out\necho noisy-err >&2\nexit 3\n')
    result = run_cmdspecs('hooks', cwd=tmp_path)
    # The short summary has just the first line.
    assert_output(result, session(
        'hooks', '1 test', 'hooks F [100%]\n\n' + failures(
            ('foo', 'hooks/setup: exited with 3\nnoisy-out\nnoisy-err\n')),
        '1 failed in 0.00s'), returncode=EXIT_FAILED)


def test_failed_setup_once_output_is_reported(tmp_path):
    make_hook_dir(tmp_path, 'setup_once', 'echo noisy-out\nexit 1\n')
    result = run_cmdspecs('hooks', cwd=tmp_path)
    assert_output(result, session('hooks', '1 test', '', '1 error in 0.00s'),
                  'cmdspecs: hooks/setup_once: exited with 1\nnoisy-out\n\n',
                  EXIT_FAILED)


def test_no_capture_option_passes_hook_output_through(tmp_path):
    make_hook_dir(tmp_path, 'setup', 'echo noisy-out\n')
    result = run_cmdspecs('-s', 'hooks', cwd=tmp_path)
    assert_output(result, session(
        'hooks', '1 test', 'hooks noisy-out\n.  [100%]\n',
        '1 passed in 0.00s'))


def test_timeout_kills_hung_test_and_keeps_output(tmp_path):
    # A test which runs too long fails with a message, its children
    # are killed and the output so far is kept.
    write_script(tmp_path / 'foo.script',
                 'echo started\nsleep 60 &\necho $! > "$SRCDIR/pid"\n'
                 'wait\n')
    result = run_cmdspecs('--timeout=0.5', '.', cwd=tmp_path)
    assert_output(result, session(
        '.', '1 test', '. F [100%]\n\n' + failures(
            ('foo', 'timed out after 0.5 seconds\n'
                    'stdout diff:\n'
                    '--- /dev/null\tTIMESTAMP\n'
                    '+++ ./foo.stdout-actual\tTIMESTAMP\n'
                    '@@ -0,0 +1 @@\n'
                    '+started\n')),
        '1 failed in 0.00s', timeout='0.5'), returncode=EXIT_FAILED)
    assert (tmp_path / 'foo.stdout-actual').read_text() == 'started\n'
    pid = int((tmp_path / 'pid').read_text())
    with pytest.raises(ProcessLookupError):
        for _ in range(50):
            os.kill(pid, 0)
            time.sleep(0.1)


@pytest.mark.parametrize('hook', ['setup', 'foo.setup', 'foo.teardown',
                                  'teardown'])
def test_timeout_applies_to_hooks(tmp_path, hook):
    write_script(tmp_path / hook, 'echo noisy-out\nsleep 60\n')
    write_script(tmp_path / 'foo.script', '')
    result = run_cmdspecs('-o', '0.5', '.', cwd=tmp_path)
    # Only a failing foo.setup skips the script, the hooks around it
    # still run, so the failure is the one message.
    assert_output(result, session(
        '.', '1 test', '. F [100%]\n\n' + failures(
            ('foo', './%s: timed out after 0.5 seconds\nnoisy-out\n' % hook)),
        '1 failed in 0.00s', timeout='0.5'), returncode=EXIT_FAILED)


def test_timeout_applies_to_setup_once(tmp_path):
    write_script(tmp_path / 'setup_once', 'sleep 60\n')
    write_script(tmp_path / 'foo.script', '')
    result = run_cmdspecs('-o', '0.5', '.', cwd=tmp_path)
    assert_output(result, session(
        '.', '1 test', '', '1 error in 0.00s', timeout='0.5'),
        'cmdspecs: ./setup_once: timed out after 0.5 seconds\n',
        EXIT_FAILED)


def test_timeout_does_not_affect_fast_tests(tmp_path):
    copy_spec('echo', tmp_path)
    result = run_cmdspecs('-o', '30', 'echo', cwd=tmp_path)
    assert_output(result, session(
        'echo', '1 test', 'echo . [100%]\n', '1 passed in 0.00s',
        timeout='30'))


@pytest.mark.parametrize('value', ['0', '-1'])
def test_timeout_must_be_positive(tmp_path, value):
    result = run_cmdspecs('--timeout=' + value, '.', cwd=tmp_path)
    assert_output(result, stderr=USAGE + 'cmdspecs: error: argument '
                  '-o/--timeout: must be greater than 0\n',
                  returncode=EXIT_USAGE)


def test_interrupt_kills_children_of_script(tmp_path):
    write_script(tmp_path / 'foo.script',
                 'sleep 60 &\necho $! > "$SRCDIR/pid"\n'
                 'kill -INT $PPID\nwait\n')
    result = run_cmdspecs(tmp_path, cwd=tmp_path)
    assert result.returncode == EXIT_INTERRUPTED, \
        result.stdout + result.stderr
    pid = int((tmp_path / 'pid').read_text())
    with pytest.raises(ProcessLookupError):
        for _ in range(50):
            os.kill(pid, 0)
            time.sleep(0.1)
