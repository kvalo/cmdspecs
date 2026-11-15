# Copyright 2011  Lars Wirzenius
# Copyright 2025-2026  Kalle Valo
#
# SPDX-License-Identifier: GPL-3.0-or-later


import importlib.machinery
import importlib.util
import io
import re
from pathlib import Path


# cmdspecs is a script without a .py extension, so load it explicitly.
_path = str(Path(__file__).resolve().parent.parent / 'cmdspecs')
_loader = importlib.machinery.SourceFileLoader('cmdspecs', _path)
_spec = importlib.util.spec_from_loader('cmdspecs', _loader)
cmdspecs = importlib.util.module_from_spec(_spec)
_loader.exec_module(cmdspecs)


def test_scan_finds_nothing_for_empty_directory():
    td = cmdspecs.TestDir()
    td.scan('tests', filenames=[])
    assert td.setup_once is None
    assert td.setup is None
    assert td.tests == []
    assert td.teardown is None
    assert td.teardown_once is None


def test_scan_finds_setup_and_teardown_files():
    td = cmdspecs.TestDir()
    td.scan('tests', filenames=['setup_once', 'setup', 'teardown',
                                'teardown_once'])
    assert td.setup_once == 'tests/setup_once'
    assert td.setup == 'tests/setup'
    assert td.tests == []
    assert td.teardown == 'tests/teardown'
    assert td.teardown_once == 'tests/teardown_once'


def test_scan_finds_tests():
    td = cmdspecs.TestDir()
    td.scan('tests', filenames=['foo.script'])
    assert len(td.tests) == 1
    test = td.tests[0]
    assert test.name == 'foo'
    assert test.script == 'tests/foo.script'
    assert test.stdin is None


def test_scan_finds_all_per_test_files():
    td = cmdspecs.TestDir()
    suffixes = cmdspecs.TestDir.per_test_suffixes
    td.scan('tests', filenames=['foo.' + x for x in suffixes])
    assert len(td.tests) == 1
    test = td.tests[0]
    for suffix in suffixes:
        assert getattr(test, suffix) == 'tests/foo.' + suffix


def test_scan_ignores_output_files():
    td = cmdspecs.TestDir()
    td.scan('tests', filenames=['foo.script', 'bar.stdout-actual',
                                'bar.stdout-diff', 'bar.stderr-actual',
                                'bar.stderr-diff'])
    assert [x.name for x in td.tests] == ['foo']


def test_finds_prefix_with_dot():
    td = cmdspecs.TestDir()
    assert td.find_prefixes(['foo.bar.script']) == ['foo.bar']


def test_finds_no_prefixes_when_there_are_none():
    assert cmdspecs.TestDir().find_prefixes(['setup']) == []


def test_finds_single_prefix():
    td = cmdspecs.TestDir()
    assert td.find_prefixes(['setup', 'foo.setup']) == ['foo']


def test_finds_two_prefixes():
    td = cmdspecs.TestDir()
    assert (td.find_prefixes(['setup', 'foo.setup', 'bar.script'])
            == ['bar', 'foo'])


def test_cat_returns_empty_string_for_nonexistent_file(tmp_path):
    assert cmdspecs.cat(str(tmp_path / 'file.txt')) == ''


def test_cat_returns_contents_of_file(tmp_path):
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
    td = cmdspecs.TestDir()
    td.scan(str(tmp_path))
    return [str(e) for e in tester.run_test(td.tests[0])]


def test_run_test_reports_actual_exit_code(tmp_path):
    make_script(tmp_path, 'foo', 'exit 3\n')
    assert run_single_test(tmp_path) == \
        ['got exit code 3, expected 0']


def test_run_test_accepts_expected_exit_code(tmp_path):
    make_script(tmp_path, 'foo', 'exit 3\n')
    (tmp_path / 'foo.exit').write_text(' 3 \n')
    assert run_single_test(tmp_path) == []


def test_run_test_feeds_stdin(tmp_path):
    make_script(tmp_path, 'foo', 'cat\n')
    (tmp_path / 'foo.stdin').write_text('hello\n')
    (tmp_path / 'foo.stdout').write_text('hello\n')
    assert run_single_test(tmp_path) == []


def test_run_test_reports_stderr_diff(tmp_path):
    make_script(tmp_path, 'foo', 'echo oops 1>&2\n')
    errors = run_single_test(tmp_path)
    assert len(errors) == 1
    assert errors[0].startswith('stderr diff:\n')
    assert '+oops' in errors[0]


def test_run_test_removes_output_files_on_success(tmp_path):
    make_script(tmp_path, 'foo', '')
    assert run_single_test(tmp_path) == []
    assert sorted(x.name for x in tmp_path.iterdir()) == ['foo.script']


def test_run_test_keeps_output_files_on_failure(tmp_path):
    make_script(tmp_path, 'foo', 'echo hello\n')
    run_single_test(tmp_path)
    assert (tmp_path / 'foo.stdout-actual').read_text() == 'hello\n'
    assert (tmp_path / 'foo.stdout-diff').exists()


def test_diff_puts_each_line_on_its_own_line(tmp_path):
    expected = tmp_path / 'expected'
    expected.write_text('broken\n')
    actual = tmp_path / 'actual'
    actual.write_text('hello\n')
    diff = cmdspecs.CommandTester().diff(str(expected), str(actual),
                                         str(tmp_path / 'diff'))
    assert diff.splitlines()[2:] == ['@@ -1 +1 @@', '-broken', '+hello']
    assert diff.endswith('\n')


def test_diff_returns_empty_string_for_identical_files(tmp_path):
    expected = tmp_path / 'expected'
    expected.write_text('hello\n')
    actual = tmp_path / 'actual'
    actual.write_text('hello\n')
    diff_name = tmp_path / 'diff'
    diff = cmdspecs.CommandTester().diff(str(expected), str(actual),
                                         str(diff_name))
    assert diff == ''
    assert diff_name.read_text() == ''


def test_diff_treats_missing_expected_file_as_empty(tmp_path):
    actual = tmp_path / 'actual'
    actual.write_text('hello\n')
    diff = cmdspecs.CommandTester().diff(str(tmp_path / 'missing'),
                                         str(actual),
                                         str(tmp_path / 'diff'))
    assert diff.splitlines()[2:] == ['@@ -0,0 +1 @@', '+hello']


def test_diff_compares_bytes(tmp_path):
    expected = tmp_path / 'expected'
    expected.write_text('\\xff\n')
    actual = tmp_path / 'actual'
    actual.write_bytes(b'\xff\n')
    diff = cmdspecs.CommandTester().diff(str(expected), str(actual),
                                         str(tmp_path / 'diff'))
    assert diff.splitlines()[2:] == ['@@ -1 +1 @@', '-\\xff', '+\\xff']


def test_diff_reports_missing_newline_at_end(tmp_path):
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
    for name in ['foo.script', 'foo.stdout', 'bar.script', 'setup',
                 'teardown_once']:
        (tmp_path / name).write_text('')
    tester = cmdspecs.CommandTester()
    tester.settings = {'test': ['foo']}
    filenames = tester.find_requested_tests(str(tmp_path))
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


def run_reporter(tests, reporter, failing=()):
    failed = []
    for test in tests:
        reporter.test_started(test)
        failures = []
        if test.name in failing:
            failures = [cmdspecs.TestFailure(test, 'stdout diff:\n+x\n')]
            failed.append((test, failures))
        reporter.test_finished(test, failures)
    reporter.finish(failed, len(tests) - len(failed), 0.5)


def test_reporter_start_shows_header():
    output = io.StringIO()
    reporter = cmdspecs.Reporter(output, width=40)
    reporter.start([cmdspecs.TestCase('foo', 'd/foo')])
    lines = output.getvalue().splitlines()
    assert lines[0] == '========= test session starts ========='
    assert lines[1].startswith('platform ')
    assert lines[1].endswith(', cmdspecs %s' % cmdspecs.VERSION)
    assert lines[2:] == ['collected 1 test', '']


def test_reporter_shows_dots_per_dir():
    tests, output, reporter = make_reporter(
        [('a', 'one/a'), ('b', 'one/b'), ('c', 'two/c')])
    run_reporter(tests, reporter)
    assert output.getvalue().splitlines() == [
        'one ..                           [ 66%]',
        'two .                            [100%]',
        '========== 3 passed in 0.50s ==========',
    ]


def test_reporter_wraps_long_dot_lines():
    names = [('t%d' % i, 'd/t%d' % i) for i in range(40)]
    tests, output, reporter = make_reporter(names)
    run_reporter(tests, reporter)
    lines = output.getvalue().splitlines()
    assert lines[0] == 'd ' + '.' * 30 + ' [ 75%]'
    assert lines[1] == '.' * 10 + ' ' * 23 + '[100%]'


def test_reporter_shows_failures():
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
    tests, output, reporter = make_reporter([('a', 'd/a'), ('b', 'd/b')],
                                            verbose=True)
    run_reporter(tests, reporter, failing=['b'])
    assert output.getvalue().splitlines()[:2] == [
        'd::a PASSED                      [ 50%]',
        'd::b FAILED                      [100%]',
    ]


def test_reporter_reports_no_tests():
    tests, output, reporter = make_reporter([])
    run_reporter(tests, reporter)
    assert output.getvalue() == '======== no tests ran in 0.50s ========\n'


def test_reporter_colors_output():
    tests, output, reporter = make_reporter([('a', 'd/a')], color=True)
    run_reporter(tests, reporter)
    assert '\x1b[32m.\x1b[0m' in output.getvalue()


def test_reporter_writes_no_colors_by_default():
    tests, output, reporter = make_reporter([('a', 'd/a')])
    run_reporter(tests, reporter)
    assert '\x1b' not in output.getvalue()


def test_manpage_documents_all_options():
    manpage = Path(_path).with_name('cmdspecs.1').read_text()
    options = manpage.split('\n.SH OPTIONS\n')[1].split('\n.SH ')[0]
    parser = cmdspecs.CommandTester().make_parser()
    for action in parser._actions:
        for option in action.option_strings:
            assert option.replace('-', '\\-') in options, option


def test_version_matches_pyproject():
    pyproject = Path(_path).with_name('pyproject.toml').read_text()
    match = re.search(r'^version = "(.*)"$', pyproject, re.MULTILINE)
    assert match.group(1) == cmdspecs.VERSION


def test_version_matches_news():
    news = Path(_path).with_name('NEWS').read_text()
    assert 'Version %s,' % cmdspecs.VERSION in news
