# Copyright 2011  Lars Wirzenius
# Copyright 2025-2026  Kalle Valo
#
# SPDX-License-Identifier: GPL-3.0-or-later


import importlib.machinery
import importlib.util
import io
import os
import re
import sys
import time
from pathlib import Path

import pytest


# cmdspecs is a script without a .py extension, so load it explicitly.
_path = str(Path(__file__).resolve().parent.parent / 'cmdspecs')
_loader = importlib.machinery.SourceFileLoader('cmdspecs', _path)
_spec = importlib.util.spec_from_loader('cmdspecs', _loader)
cmdspecs = importlib.util.module_from_spec(_spec)
_loader.exec_module(cmdspecs)


def test_scan_finds_nothing_for_empty_directory():
    # Scanning a directory with no files leaves every hook unset and the
    # test list empty.
    td = cmdspecs.TestDir()
    td.scan('tests', filenames=[])
    assert td.setup_once is None
    assert td.setup is None
    assert td.tests == []
    assert td.teardown is None
    assert td.teardown_once is None


def test_scan_finds_setup_and_teardown_files():
    # The dir-level setup_once, setup, teardown and teardown_once files
    # are recognised and stored with their paths.
    td = cmdspecs.TestDir()
    td.scan('tests', filenames=['setup_once', 'setup', 'teardown',
                                'teardown_once'])
    assert td.setup_once == 'tests/setup_once'
    assert td.setup == 'tests/setup'
    assert td.tests == []
    assert td.teardown == 'tests/teardown'
    assert td.teardown_once == 'tests/teardown_once'


def test_scan_finds_tests():
    # A <name>.script file becomes a test called <name>, with the
    # optional files unset.
    td = cmdspecs.TestDir()
    td.scan('tests', filenames=['foo.script'])
    assert len(td.tests) == 1
    test = td.tests[0]
    assert test.name == 'foo'
    assert test.script == 'tests/foo.script'
    assert test.stdin is None


def test_scan_finds_all_per_test_files():
    # Every per-test file suffix (script, stdin, stdout, ...) is
    # attached to the test of the same name.
    td = cmdspecs.TestDir()
    suffixes = cmdspecs.TestDir.per_test_suffixes
    td.scan('tests', filenames=['foo.' + x for x in suffixes])
    assert len(td.tests) == 1
    test = td.tests[0]
    for suffix in suffixes:
        assert getattr(test, suffix) == 'tests/foo.' + suffix


def test_scan_ignores_output_files():
    # The -actual and -diff files left by an earlier failed run are not
    # mistaken for tests.
    td = cmdspecs.TestDir()
    td.scan('tests', filenames=['foo.script', 'bar.stdout-actual',
                                'bar.stdout-diff', 'bar.stderr-actual',
                                'bar.stderr-diff'])
    assert [x.name for x in td.tests] == ['foo']


def test_finds_prefix_with_dot():
    # Only the last dot separates the test name from the suffix, so a
    # name may contain dots.
    td = cmdspecs.TestDir()
    assert td.find_prefixes(['foo.bar.script']) == ['foo.bar']


def test_finds_no_prefixes_when_there_are_none():
    # Dir-level files such as setup do not yield a test name.
    assert cmdspecs.TestDir().find_prefixes(['setup']) == []


def test_finds_single_prefix():
    # A per-test file (foo.setup) yields its test name while the
    # dir-level setup is skipped.
    td = cmdspecs.TestDir()
    assert td.find_prefixes(['setup', 'foo.setup']) == ['foo']


def test_finds_two_prefixes():
    # Several tests are found and returned sorted by name.
    td = cmdspecs.TestDir()
    assert (td.find_prefixes(['setup', 'foo.setup', 'bar.script'])
            == ['bar', 'foo'])


def test_cat_returns_empty_string_for_nonexistent_file(tmp_path):
    # A missing file is treated as empty instead of raising an error.
    assert cmdspecs.cat(str(tmp_path / 'file.txt')) == ''


def test_cat_returns_contents_of_file(tmp_path):
    # Cat returns the contents of an existing file.
    filename = tmp_path / 'file.txt'
    filename.write_text('foobar')
    assert cmdspecs.cat(str(filename)) == 'foobar'


def make_script(tmp_path, name, body):
    script = tmp_path / (name + '.script')
    script.write_text('#!/bin/sh\n' + body)
    script.chmod(0o755)


def run_single_test(tmp_path):
    tester = cmdspecs.CommandTester()
    tester.datadir = str(tmp_path)
    tester.tempdir = str(tmp_path)
    tester.capture = True
    td = cmdspecs.TestDir()
    td.scan(str(tmp_path))
    return [str(e) for e in tester.run_test(td.tests[0])]


def test_run_test_reports_actual_exit_code(tmp_path):
    # Without a .exit file the script is expected to exit with 0, and a
    # different exit code is reported.
    make_script(tmp_path, 'foo', 'exit 3\n')
    assert run_single_test(tmp_path) == \
        ['got exit code 3, expected 0']


def test_run_test_reports_signal_as_shell_exit_code(tmp_path):
    # A script killed by a signal gets 128 + N, like in a shell, and
    # the signal is named.
    make_script(tmp_path, 'foo', 'kill -KILL $$\n')
    assert run_single_test(tmp_path) == \
        ['got exit code 137 (SIGKILL), expected 0']


def test_run_test_accepts_signal_exit_code(tmp_path):
    make_script(tmp_path, 'foo', 'kill -KILL $$\n')
    (tmp_path / 'foo.exit').write_text('137\n')
    assert run_single_test(tmp_path) == []


def test_run_test_reports_signal_killed_setup(tmp_path):
    make_script(tmp_path, 'foo', 'true\n')
    setup = tmp_path / 'foo.setup'
    setup.write_text('#!/bin/sh\nkill -KILL $$\n')
    setup.chmod(0o755)
    assert run_single_test(tmp_path) == \
        ['%s: exited with 137 (SIGKILL)' % setup]


@pytest.mark.parametrize('platform, returncode, code', [
    ('linux', 3, 3), ('linux', -9, 137), ('win32', 3, 3),
    ('win32', 255, 255), ('win32', 9 * 256, 137),
    ('win32', 0xC000013A, 0xC000013A)])
def test_shell_exit_code(monkeypatch, platform, returncode, code):
    # A signal death is -N from subprocess on Unix and N * 256 from MSYS
    # on Windows, and both become 128 + N.
    monkeypatch.setattr(cmdspecs.sys, 'platform', platform)
    assert cmdspecs.shell_exit_code(returncode) == code


@pytest.mark.parametrize('platform', [sys.platform, 'win32'])
def test_describe_exit_names_signals(monkeypatch, platform):
    # On Windows the names come from MSYS, as the signal module there
    # has no SIGKILL and calls 0 and 1 CTRL_C_EVENT and CTRL_BREAK_EVENT.
    monkeypatch.setattr(cmdspecs.sys, 'platform', platform)
    assert cmdspecs.describe_exit(137) == '137 (SIGKILL)'
    assert cmdspecs.describe_exit(3) == '3'
    assert cmdspecs.describe_exit(128) == '128'


def test_script_command_runs_script_directly_on_unix(monkeypatch):
    monkeypatch.setattr(cmdspecs.sys, 'platform', 'linux')
    assert cmdspecs.CommandTester().script_command('d/foo.script') == \
        ['d/foo.script']


def test_script_command_uses_sh_on_windows(monkeypatch):
    # Windows ignores the #! line, so sh runs the script and its exec
    # handles the #! line.
    monkeypatch.setattr(cmdspecs.sys, 'platform', 'win32')
    monkeypatch.setattr(cmdspecs.shutil, 'which',
                        lambda name: r'C:\Git\bin\sh.exe')
    assert cmdspecs.CommandTester().script_command(r'd\foo.script') == \
        [r'C:\Git\bin\sh.exe', '-c', 'exec "$0"', r'd\foo.script']


def test_missing_sh_on_windows_is_one_error(monkeypatch, capsys):
    # Without sh nothing can run, so cmdspecs says so once and exits with
    # 1, before running any tests.
    def broken(self, testdirs):
        raise AssertionError('tests were run')

    monkeypatch.setattr(cmdspecs.sys, 'platform', 'win32')
    monkeypatch.setattr(cmdspecs.shutil, 'which', lambda name: None)
    monkeypatch.setattr(cmdspecs.CommandTester, 'run_tests', broken)
    monkeypatch.setattr(cmdspecs.sys, 'argv', ['cmdspecs', 'tests/specs/echo'])
    with pytest.raises(SystemExit) as excinfo:
        cmdspecs.main()
    assert excinfo.value.code == cmdspecs.EXIT_FAILED
    assert capsys.readouterr().err == (
        'cmdspecs: sh not found in PATH; on Windows cmdspecs needs the sh '
        'of Git for Windows or MSYS2\n')


def test_run_test_accepts_expected_exit_code(tmp_path):
    # A .exit file sets the expected exit code, and surrounding
    # whitespace in it is ignored.
    make_script(tmp_path, 'foo', 'exit 3\n')
    (tmp_path / 'foo.exit').write_text(' 3 \n')
    assert run_single_test(tmp_path) == []


def test_run_test_feeds_stdin(tmp_path):
    # The contents of the .stdin file are given to the script as its
    # standard input.
    make_script(tmp_path, 'foo', 'cat\n')
    (tmp_path / 'foo.stdin').write_text('hello\n')
    (tmp_path / 'foo.stdout').write_text('hello\n')
    assert run_single_test(tmp_path) == []


def test_run_test_reports_stderr_diff(tmp_path):
    # Unexpected output on stderr is reported as a stderr diff.
    make_script(tmp_path, 'foo', 'echo oops 1>&2\n')
    errors = run_single_test(tmp_path)
    assert len(errors) == 1
    lines = errors[0].splitlines()
    assert lines[0] == 'stderr diff:'
    assert lines[1].startswith('--- /dev/null\t')
    assert lines[2].startswith('+++ ') and \
        lines[2].split('\t')[0].endswith('foo.stderr-actual')
    assert lines[3:] == ['@@ -0,0 +1 @@', '+oops']


def test_run_test_removes_output_files_on_success(tmp_path):
    # A passing test leaves no -actual or -diff files behind.
    make_script(tmp_path, 'foo', '')
    assert run_single_test(tmp_path) == []
    assert sorted(x.name for x in tmp_path.iterdir()) == ['foo.script']


def test_run_test_keeps_output_files_on_failure(tmp_path):
    # A failing stream leaves its -actual and -diff files for
    # inspection.
    make_script(tmp_path, 'foo', 'echo hello\n')
    run_single_test(tmp_path)
    assert (tmp_path / 'foo.stdout-actual').read_text() == 'hello\n'
    assert (tmp_path / 'foo.stdout-diff').exists()


def test_run_test_keeps_output_files_of_failed_stream_only(tmp_path):
    # Only the stream which differs keeps its files, not the streams
    # which matched.
    make_script(tmp_path, 'foo', 'echo hello\nexit 3\n')
    run_single_test(tmp_path)
    assert sorted(x.name for x in tmp_path.iterdir()) == \
        ['foo.script', 'foo.stdout-actual', 'foo.stdout-diff']


def test_run_test_treats_missing_stdin_as_empty(tmp_path):
    # A test without a .stdin file gets empty input (EOF) rather than
    # hanging or failing.
    make_script(tmp_path, 'foo', 'cat\n')
    assert run_single_test(tmp_path) == []


def test_run_test_reports_invalid_exit_file(tmp_path):
    # A non-numeric .exit file is reported as an error and the script is
    # not run at all.
    make_script(tmp_path, 'foo', 'touch "$DATADIR/ran"\n')
    (tmp_path / 'foo.exit').write_text('zero\n')
    errors = run_single_test(tmp_path)
    assert len(errors) == 1
    assert errors[0].startswith('invalid %s: ' % (tmp_path / 'foo.exit'))
    assert not (tmp_path / 'ran').exists()


def test_run_test_runs_teardown_and_keeps_diff_when_it_fails(tmp_path):
    # A failing teardown is reported in addition to the output diff of
    # the test, not instead of it.
    make_script(tmp_path, 'foo', 'echo hello\n')
    teardown = tmp_path / 'foo.teardown'
    teardown.write_text('#!/bin/sh\nexit 4\n')
    teardown.chmod(0o755)
    errors = run_single_test(tmp_path)
    assert len(errors) == 2
    assert errors[0].startswith('stdout diff:\n')
    assert errors[1] == '%s: exited with 4' % teardown


def test_run_test_removes_output_files_when_script_cannot_run(tmp_path):
    # When the script cannot be started, the error is reported and no
    # output files are left behind.
    (tmp_path / 'foo.script').write_text('#!/bin/sh\n')
    errors = run_single_test(tmp_path)
    assert len(errors) == 1
    assert errors[0].startswith('could not run ')
    assert sorted(x.name for x in tmp_path.iterdir()) == ['foo.script']


def test_diff_puts_each_line_on_its_own_line(tmp_path):
    # The diff has one line per diff line, each ending in a newline.
    expected = tmp_path / 'expected'
    expected.write_text('broken\n')
    actual = tmp_path / 'actual'
    actual.write_text('hello\n')
    diff = cmdspecs.CommandTester().diff(str(expected), str(actual),
                                         str(tmp_path / 'diff'))
    assert diff.splitlines()[2:] == ['@@ -1 +1 @@', '-broken', '+hello']
    assert diff.endswith('\n')


def test_diff_returns_empty_string_for_identical_files(tmp_path):
    # Identical files give an empty diff and no diff file is written.
    expected = tmp_path / 'expected'
    expected.write_text('hello\n')
    actual = tmp_path / 'actual'
    actual.write_text('hello\n')
    diff_name = tmp_path / 'diff'
    diff = cmdspecs.CommandTester().diff(str(expected), str(actual),
                                         str(diff_name))
    assert diff == ''
    assert not diff_name.exists()


def test_diff_removes_stale_diff_file(tmp_path):
    # A diff file from an earlier run is deleted when the output now
    # matches.
    expected = tmp_path / 'expected'
    expected.write_text('hello\n')
    diff_name = tmp_path / 'diff'
    diff_name.write_text('stale\n')
    cmdspecs.CommandTester().diff(str(expected), str(expected),
                                  str(diff_name))
    assert not diff_name.exists()


def test_diff_shows_timestamps_with_utc_offset(tmp_path):
    # The diff header shows modification times with microseconds and a
    # UTC offset.
    expected = tmp_path / 'expected'
    expected.write_text('broken\n')
    actual = tmp_path / 'actual'
    actual.write_text('hello\n')
    os.utime(expected, (0, 86400))
    diff = cmdspecs.CommandTester().diff(str(expected), str(actual),
                                         str(tmp_path / 'diff'))
    stamp = time.strftime('%Y-%m-%d %H:%M:%S.000000 %z',
                          time.localtime(86400))
    assert diff.splitlines()[0] == '--- %s\t%s' % (expected, stamp)


def test_diff_writes_raw_bytes_to_diff_file(tmp_path):
    # Non-UTF-8 output is written to the diff file byte for byte, not
    # mangled.
    actual = tmp_path / 'actual'
    actual.write_bytes(b'\xff\n')
    diff_name = tmp_path / 'diff'
    cmdspecs.CommandTester().diff('/dev/null', str(actual), str(diff_name))
    assert diff_name.read_bytes().endswith(b'\n+\xff\n')


def test_diff_treats_missing_expected_file_as_empty(tmp_path):
    # A missing expected file means the test expects no output, so all
    # actual output is shown as added.
    actual = tmp_path / 'actual'
    actual.write_text('hello\n')
    diff = cmdspecs.CommandTester().diff(str(tmp_path / 'missing'),
                                         str(actual),
                                         str(tmp_path / 'diff'))
    assert diff.splitlines()[2:] == ['@@ -0,0 +1 @@', '+hello']


def test_diff_compares_bytes(tmp_path):
    # Files are compared as bytes, so a literal backslash-x text differs
    # from a real 0xff byte.
    expected = tmp_path / 'expected'
    expected.write_text('\\xff\n')
    actual = tmp_path / 'actual'
    actual.write_bytes(b'\xff\n')
    diff = cmdspecs.CommandTester().diff(str(expected), str(actual),
                                         str(tmp_path / 'diff'))
    assert diff.splitlines()[2:] == ['@@ -1 +1 @@', '-\\xff', '+\\xff']


def test_diff_reports_missing_newline_at_end(tmp_path):
    # A missing final newline is a difference and is marked with "\ No
    # newline at end of file".
    expected = tmp_path / 'expected'
    expected.write_text('hello\n')
    actual = tmp_path / 'actual'
    actual.write_text('hello')
    diff = cmdspecs.CommandTester().diff(str(expected), str(actual),
                                         str(tmp_path / 'diff'))
    assert diff.splitlines()[2:] == ['@@ -1 +1 @@', '-hello', '+hello',
                                     '\\ No newline at end of file']
    assert diff.endswith('\n')


def test_find_requested_tests_includes_dir_scripts(tmp_path):
    # Selecting a test keeps its own files and the dir-level hooks, and
    # drops the files of other tests.
    for name in ['foo.script', 'foo.stdout', 'bar.script', 'setup',
                 'teardown_once']:
        (tmp_path / name).write_text('')
    tester = cmdspecs.CommandTester()
    filenames = tester.find_requested_tests(os.listdir(tmp_path), ['foo'])
    assert sorted(filenames) == ['foo.script', 'foo.stdout', 'setup',
                                 'teardown_once']


def make_reporter(names, **kwargs):
    tests = [cmdspecs.TestCase(name, path) for name, path in names]
    output = io.StringIO()
    reporter = cmdspecs.Reporter(output, width=40, **kwargs)
    reporter.start(tests)
    output.seek(0)
    output.truncate()
    return tests, output, reporter


def run_reporter(tests, reporter, failing=(), errors=0):
    failed = []
    for test in tests:
        reporter.test_started(test)
        failures = []
        if test.name in failing:
            failures = [cmdspecs.TestFailure(test, 'stdout diff:\n+x\n')]
            failed.append((test, failures))
        reporter.test_finished(test, failures)
    reporter.finish(failed, len(tests) - len(failed), 0.5, errors)


def test_reporter_start_shows_header():
    # The session header shows the platform, the cmdspecs version and
    # the number of tests collected.
    output = io.StringIO()
    reporter = cmdspecs.Reporter(output, width=40)
    reporter.start([cmdspecs.TestCase('foo', 'd/foo')])
    lines = output.getvalue().splitlines()
    assert lines[0] == '======= cmdspecs session starts ======='
    assert lines[1].startswith('platform ')
    assert lines[1].endswith(', cmdspecs %s' % cmdspecs.version_string())
    assert lines[2:] == ['collected 1 test', '']


def test_reporter_start_shows_settings():
    # The settings are shown as name: value lines between the platform
    # line and the number of tests collected.
    output = io.StringIO()
    reporter = cmdspecs.Reporter(output, width=40)
    reporter.start([cmdspecs.TestCase('foo', 'd/foo')],
                   [('srcdir', '/src'), ('keep', 'no')])
    lines = output.getvalue().splitlines()
    assert lines[2:] == ['srcdir: /src', 'keep: no', 'collected 1 test',
                         '']


def test_reporter_shows_dots_per_dir():
    # Results are printed as dots on one line per directory, with a
    # running percentage.
    tests, output, reporter = make_reporter(
        [('a', 'one/a'), ('b', 'one/b'), ('c', 'two/c')])
    run_reporter(tests, reporter)
    assert output.getvalue().splitlines() == [
        'one ..                           [ 66%]',
        'two .                            [100%]',
        '========== 3 passed in 0.50s ==========',
    ]


def test_reporter_wraps_long_dot_lines():
    # A line with more dots than fit the terminal width is wrapped, with
    # the percentage on each line.
    names = [('t%d' % i, 'd/t%d' % i) for i in range(40)]
    tests, output, reporter = make_reporter(names)
    run_reporter(tests, reporter)
    lines = output.getvalue().splitlines()
    assert lines[0] == 'd ' + '.' * 30 + ' [ 75%]'
    assert lines[1] == '.' * 10 + ' ' * 23 + '[100%]'


def test_reporter_shows_failures():
    # A failed test shows F, a FAILURES section with its details and a
    # short summary line.
    tests, output, reporter = make_reporter([('a', 'd/a'), ('b', 'd/b')])
    run_reporter(tests, reporter, failing=['b'])
    assert output.getvalue().splitlines() == [
        'd .F                             [100%]',
        '',
        '============== FAILURES ===============',
        '__________________ b __________________',
        'stdout diff:',
        '+x',
        '======= short test summary info =======',
        'FAILED b - stdout diff:',
        '===== 1 failed, 1 passed in 0.50s =====',
    ]


def test_reporter_verbose_shows_test_names():
    # Verbose mode prints one PASSED or FAILED line per test instead of
    # dots.
    tests, output, reporter = make_reporter([('a', 'd/a'), ('b', 'd/b')],
                                            verbose=True)
    run_reporter(tests, reporter, failing=['b'])
    assert output.getvalue().splitlines()[:2] == [
        'd::a PASSED                      [ 50%]',
        'd::b FAILED                      [100%]',
    ]


def test_reporter_reports_no_tests():
    # A run without any tests says "no tests ran" instead of "0 passed".
    tests, output, reporter = make_reporter([])
    run_reporter(tests, reporter)
    assert output.getvalue() == '======== no tests ran in 0.50s ========\n'


def test_reporter_counts_errors():
    # Errors which belong to no test are counted in the summary, even
    # when no test ran.
    tests, output, reporter = make_reporter([])
    run_reporter(tests, reporter, errors=2)
    assert output.getvalue() == '========== 2 errors in 0.50s ==========\n'
    tests, output, reporter = make_reporter([('a', 'd/a')])
    run_reporter(tests, reporter, errors=1)
    assert output.getvalue() == (
        'd .                              [100%]\n'
        '===== 1 passed, 1 error in 0.50s ======\n')


def test_reporter_colors_output():
    # With color enabled the dots, the failures and the summaries are
    # colored: green for passing, red for failing, bold for the failure
    # and summary lines, cyan for the short summary heading.
    green, red, reset = '\x1b[32m', '\x1b[31m', '\x1b[0m'
    tests, output, reporter = make_reporter([('a', 'd/a'), ('b', 'd/b')],
                                            color=True)
    run_reporter(tests, reporter, failing=['b'])
    assert output.getvalue() == (
        'd %s.%s%sF%s                             %s[100%%]%s\n'
        '\n'
        '============== FAILURES ===============\n'
        '\x1b[31;1m__________________ b __________________%s\n'
        'stdout diff:\n'
        '+x\n'
        '\x1b[36m======= short test summary info =======%s\n'
        '%sFAILED%s b - stdout diff:\n'
        '\x1b[31;1m===== 1 failed, 1 passed in 0.50s =====%s\n' % (
            green, reset, red, reset, red, reset, reset, reset, red, reset,
            reset))


def test_reporter_colors_verbose_names():
    green, red, reset = '\x1b[32m', '\x1b[31m', '\x1b[0m'
    tests, output, reporter = make_reporter([('a', 'd/a'), ('b', 'd/b')],
                                            color=True, verbose=True)
    run_reporter(tests, reporter, failing=['b'])
    assert output.getvalue().splitlines()[:2] == [
        'd::a %sPASSED%s                      %s[ 50%%]%s' % (
            green, reset, green, reset),
        'd::b %sFAILED%s                      %s[100%%]%s' % (
            red, reset, red, reset)]


def test_reporter_colors_summaries_without_failures():
    # The summary is green when everything passed, red when there are
    # errors and bold yellow when no tests ran.
    tests, output, reporter = make_reporter([], color=True)
    run_reporter(tests, reporter)
    assert output.getvalue() == (
        '\x1b[33;1m======== no tests ran in 0.50s ========\x1b[0m\n')
    tests, output, reporter = make_reporter([], color=True)
    run_reporter(tests, reporter, errors=2)
    assert output.getvalue() == (
        '\x1b[31;1m========== 2 errors in 0.50s ==========\x1b[0m\n')
    tests, output, reporter = make_reporter([('a', 'd/a')], color=True)
    run_reporter(tests, reporter, errors=1)
    assert output.getvalue().splitlines()[-1] == (
        '\x1b[31;1m===== 1 passed, 1 error in 0.50s ======\x1b[0m')


def test_reporter_writes_no_colors_by_default():
    # Without color enabled the output has no escape codes.
    tests, output, reporter = make_reporter([('a', 'd/a')])
    run_reporter(tests, reporter)
    assert '\x1b' not in output.getvalue()


def test_manpage_documents_all_options():
    # Every command line option is documented in the OPTIONS section of
    # the manpage.
    manpage = Path(_path).with_name('cmdspecs.1').read_text()
    options = manpage.split('\n.SH OPTIONS\n')[1].split('\n.SH ')[0]
    parser = cmdspecs.CommandTester().make_parser()
    for action in parser._actions:
        for option in action.option_strings:
            # The option must not be just part of another one, such as
            # -t of --test.
            escaped = re.escape(option.replace('-', '\\-'))
            assert re.search(r'(?<![\\\-\w])%s(?![\\\-\w])' % escaped,
                             options), option


def test_version_matches_pyproject():
    # VERSION in cmdspecs and version in pyproject.toml are the same.
    pyproject = Path(_path).with_name('pyproject.toml').read_text()
    match = re.search(r'^version = "(.*)"$', pyproject, re.MULTILINE)
    assert match.group(1) == cmdspecs.VERSION


def test_version_string_release(monkeypatch):
    # A release version is shown as is.
    monkeypatch.setattr(cmdspecs, 'VERSION', '1.2')
    assert cmdspecs.version_string() == '1.2'


def test_version_string_git_build(monkeypatch, tmp_path):
    # A git build gets a short hash of the script, which changes with
    # the script's contents.
    script = tmp_path / 'script'
    monkeypatch.setattr(cmdspecs, '__file__', str(script))
    monkeypatch.setattr(cmdspecs, 'VERSION', '1.2+git')
    script.write_text('one')
    first = cmdspecs.version_string()
    assert re.fullmatch(r'1\.2\+git\.[0-9a-f]{8}', first)
    assert cmdspecs.version_string() == first
    script.write_text('two')
    assert cmdspecs.version_string() != first


def test_version_string_unreadable_script(monkeypatch, tmp_path):
    # Without a readable script the hash is replaced by "nohash".
    monkeypatch.setattr(cmdspecs, '__file__', str(tmp_path / 'missing'))
    monkeypatch.setattr(cmdspecs, 'VERSION', '1.2+git')
    assert cmdspecs.version_string() == '1.2+git.nohash'


def test_version_matches_changelog():
    # CHANGELOG.md has a heading for the current version, or for
    # Unreleased if the version is a git build.
    changelog = Path(_path).with_name('CHANGELOG.md').read_text()
    if cmdspecs.VERSION.endswith('+git'):
        heading = '## [Unreleased]\n'
    else:
        heading = '## [%s] - ' % cmdspecs.VERSION
    assert re.search('^%s' % re.escape(heading), changelog, re.MULTILINE)


def test_manpage_documents_all_exit_statuses():
    # The EXIT STATUS section of the manpage lists exactly the statuses
    # which the EXIT_* constants define.
    manpage = Path(_path).with_name('cmdspecs.1').read_text()
    section = manpage.split('\n.SH "EXIT STATUS"\n')[1].split('\n.SH ')[0]
    documented = {int(x) for x in re.findall(r'^\.B (\d+)$', section,
                                             re.MULTILINE)}
    defined = {value for name, value in vars(cmdspecs).items()
               if name.startswith('EXIT_')}
    assert documented == defined


def test_internal_error_exits_with_internal_status(monkeypatch, capsys):
    # A bug in cmdspecs shows a traceback and exits with 3, which is
    # different from a failed test.
    def broken(self, testdirs):
        raise RuntimeError('boom')

    monkeypatch.setattr(cmdspecs.CommandTester, 'run_tests', broken)
    monkeypatch.setattr(cmdspecs.sys, 'argv', ['cmdspecs', 'tests/specs/echo'])
    with pytest.raises(SystemExit) as excinfo:
        cmdspecs.main()
    assert excinfo.value.code == cmdspecs.EXIT_INTERNAL
    err = capsys.readouterr().err
    assert 'Traceback' in err
    assert 'cmdspecs: internal error: RuntimeError: boom\n' in err


def test_io_error_exits_with_failed_status(monkeypatch, capsys):
    # An I/O error in cmdspecs itself, here a tempdir which can't be
    # created, gives a one-line message and status 1, not a traceback.
    def broken(prefix):
        raise PermissionError(13, 'Permission denied', '/nosuch')

    monkeypatch.setattr(cmdspecs.tempfile, 'mkdtemp', broken)
    monkeypatch.setattr(cmdspecs.sys, 'argv', ['cmdspecs', 'tests/specs/echo'])
    with pytest.raises(SystemExit) as excinfo:
        cmdspecs.main()
    assert excinfo.value.code == cmdspecs.EXIT_FAILED
    assert capsys.readouterr().err == \
        'cmdspecs: /nosuch: Permission denied\n'


def test_command_option_is_a_usage_error(monkeypatch, capsys):
    # -c/--command was accepted and ignored, now it is removed.
    monkeypatch.setattr(cmdspecs.sys, 'argv',
                        ['cmdspecs', '-c', 'x', 'tests/specs/echo'])
    with pytest.raises(SystemExit) as excinfo:
        cmdspecs.main()
    assert excinfo.value.code == cmdspecs.EXIT_USAGE
    assert 'unrecognized arguments: -c' in capsys.readouterr().err
