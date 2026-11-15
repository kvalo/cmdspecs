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


def test_run_test_reports_actual_exit_code(tmp_path):
    script = tmp_path / 'foo.script'
    script.write_text('#!/bin/sh\nexit 3\n')
    script.chmod(0o755)
    tester = cmdspecs.CommandTester()
    tester.datadir = str(tmp_path)
    td = cmdspecs.TestDir()
    td.scan(str(tmp_path))
    errors = tester.run_test(td.tests[0])
    assert [str(e) for e in errors] == \
        ['FAIL: foo: got exit code 3, expected 0']


def test_diff_puts_each_line_on_its_own_line(tmp_path):
    expected = tmp_path / 'expected'
    expected.write_text('broken\n')
    actual = tmp_path / 'actual'
    actual.write_text('hello\n')
    diff = cmdspecs.CommandTester().diff(str(expected), str(actual),
                                         str(tmp_path / 'diff'))
    assert diff.splitlines()[2:] == ['@@ -1 +1 @@', '-broken', '+hello']
    assert diff.endswith('\n')
