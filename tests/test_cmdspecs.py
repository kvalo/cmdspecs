# Copyright 2011  Lars Wirzenius
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import importlib.machinery
import importlib.util
import io
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
        ['FAIL: foo: got exit code 3, expected 0']


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
    assert errors[0].startswith('FAIL: foo: stderr diff:\n')
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


class FakeTerminal(io.StringIO):

    def isatty(self):
        return True


def make_status(output, names):
    tests = [cmdspecs.TestCase(name, name) for name in names]
    return tests, cmdspecs.SimpleTerminalStatus(tests, output)


def test_status_shows_test_number_and_name():
    output = FakeTerminal()
    tests, ts = make_status(output, ['foo', 'bar'])
    ts['test'] = tests[1]
    ts['test-name'] = 'bar'
    assert output.getvalue() == '\rtest 2/2: bar'


def test_status_overwrites_longer_previous_line():
    output = FakeTerminal()
    tests, ts = make_status(output, ['foobar', 'x'])
    for test in tests:
        ts['test'] = test
        ts['test-name'] = test.name
    assert output.getvalue() == ('\rtest 1/2: foobar'
                                 '\rtest 2/2: x     ')


def test_status_finish_wipes_line():
    output = FakeTerminal()
    tests, ts = make_status(output, ['foo'])
    ts['test'] = tests[0]
    ts['test-name'] = 'foo'
    ts.finish()
    assert output.getvalue() == '\rtest 1/1: foo\r' + ' ' * 13 + '\r'


def test_status_writes_nothing_when_not_a_terminal():
    output = io.StringIO()
    tests, ts = make_status(output, ['foo'])
    ts['test'] = tests[0]
    ts['test-name'] = 'foo'
    ts.clear()
    ts.finish()
    assert output.getvalue() == ''
