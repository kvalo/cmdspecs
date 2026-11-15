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
import os
import shutil
import tempfile
import unittest


# cmdspecs is a script without a .py extension, so load it explicitly.
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                     'cmdspecs')
_loader = importlib.machinery.SourceFileLoader('cmdspecs', _path)
_spec = importlib.util.spec_from_loader('cmdspecs', _loader)
cmdspecs = importlib.util.module_from_spec(_spec)
_loader.exec_module(cmdspecs)

CommandTester = cmdspecs.CommandTester
TestDir = cmdspecs.TestDir
cat = cmdspecs.cat


class TestDirTests(unittest.TestCase):

    def test_finds_nothing_for_empty_directory(self):
        td = TestDir()
        td.scan('tests', filenames=[])
        self.assertEqual(td.setup_once, None)
        self.assertEqual(td.setup, None)
        self.assertEqual(td.tests, [])
        self.assertEqual(td.teardown, None)
        self.assertEqual(td.teardown_once, None)

    def test_finds_setup_and_teardown_files(self):
        td = TestDir()
        td.scan('tests', filenames=['setup_once', 'setup', 'teardown',
                                    'teardown_once'])
        self.assertEqual(td.setup_once, 'tests/setup_once')
        self.assertEqual(td.setup, 'tests/setup')
        self.assertEqual(td.tests, [])
        self.assertEqual(td.teardown, 'tests/teardown')
        self.assertEqual(td.teardown_once, 'tests/teardown_once')

    def test_finds_tests(self):
        td = TestDir()
        td.scan('tests', filenames=['foo.script'])
        self.assertEqual(len(td.tests), 1)
        test = td.tests[0]
        self.assertEqual(test.name, 'foo')
        self.assertEqual(test.script, 'tests/foo.script')
        self.assertEqual(test.stdin, None)

    def test_finds_no_prefixes_when_there_are_none(self):
        td = TestDir()
        self.assertEqual(td.find_prefixes(['setup']), [])

    def test_finds_single_prefix(self):
        td = TestDir()
        self.assertEqual(td.find_prefixes(['setup', 'foo.setup']), ['foo'])

    def test_finds_two_prefixes(self):
        td = TestDir()
        self.assertEqual(
            td.find_prefixes(['setup', 'foo.setup', 'bar.script']),
            ['bar', 'foo'])


class CatTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_returns_empty_string_for_nonexistent_file(self):
        filename = os.path.join(self.tempdir, 'file.txt')
        self.assertEqual(cat(filename), '')

    def test_returns_contents_of_file(self):
        filename = os.path.join(self.tempdir, 'file.txt')
        with open(filename, 'w') as f:
            f.write('foobar')
        self.assertEqual(cat(filename), 'foobar')


class RunTestTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.tester = CommandTester()
        self.tester.datadir = self.tempdir

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_reports_actual_exit_code(self):
        script = os.path.join(self.tempdir, 'foo.script')
        with open(script, 'w') as f:
            f.write('#!/bin/sh\nexit 3\n')
        os.chmod(script, 0o755)
        td = TestDir()
        td.scan(self.tempdir)
        errors = self.tester.run_test(td.tests[0])
        self.assertEqual([str(e) for e in errors],
                         ['FAIL: foo: got exit code 3, expected 0'])
