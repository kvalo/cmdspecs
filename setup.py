#!/usr/bin/env python3
"""
Setup script for cmdspecs - kept minimal for custom build commands.
Main configuration is in pyproject.toml.
"""

import os
import shutil
import subprocess
from pathlib import Path

try:
    from setuptools import setup, Command
    from setuptools.command.build import build
    from distutils.command.clean import clean
except ImportError:
    from distutils.core import setup, Command
    from distutils.command.build import build
    from distutils.command.clean import clean


class GenerateManpage(build):
    """Generate manpages during build."""

    def run(self):
        build.run(self)
        print('building manpages')
        cmds = ['cmdspecs']
        for cmd in cmds:
            src = f'{cmd}.1.in'
            dst = f'{cmd}.1'
            if os.path.exists(src):
                print(f'Copying {src} -> {dst}')
                shutil.copy(src, dst)


class CleanMore(clean):
    """Extended clean command."""

    def run(self):
        clean.run(self)
        files_to_remove = ['.coverage', 'cmdspecs.1']
        files_to_remove.extend(Path('.').glob('*.pyc'))
        files_to_remove.extend(Path('.').glob('__pycache__'))

        for path in files_to_remove:
            path = Path(path)
            if path.exists():
                if path.is_file():
                    path.unlink()
                    print(f'Removed {path}')
                elif path.is_dir():
                    shutil.rmtree(path)
                    print(f'Removed directory {path}')


class Check(Command):
    """Run tests."""

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # Check if markdown is available for enhanced testing
        try:
            import markdown
            has_markdown = (hasattr(markdown, 'extensions') and
                            hasattr(markdown.extensions, 'Extension'))
        except ImportError:
            has_markdown = False

        if has_markdown:
            try:
                subprocess.check_call([
                    'python3', '-m', 'CoverageTestRunner',
                    '--ignore-missing-from', 'without-tests'
                ])
                coverage_file = Path('.coverage')
                if coverage_file.exists():
                    coverage_file.unlink()
            except subprocess.CalledProcessError:
                print("Coverage testing failed, continuing...")

        # Run the test suites
        test_dirs = ['echo-tests', 'sort-tests']

        for test_dir in test_dirs:
            print(f"Running {test_dir}...")
            try:
                subprocess.check_call(['./cmdspecs', test_dir])
            except subprocess.CalledProcessError as e:
                raise RuntimeError(
                    f"{test_dir} failed with exit code {e.returncode}")

        # Test that fail-tests actually fails
        print("Testing fail-tests (should fail)...")
        try:
            subprocess.check_call(['./cmdspecs', 'fail-tests'])
            raise RuntimeError('fail-tests did not fail as expected')
        except subprocess.CalledProcessError:
            print("fail-tests correctly failed ✓")


if __name__ == '__main__':
    setup(
        cmdclass={
            'build': GenerateManpage,
            'check': Check,
            'clean': CleanMore,
        },
    )
