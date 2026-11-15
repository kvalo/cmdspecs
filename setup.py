#!/usr/bin/env python3
"""
Setup script for cmdspecs - kept minimal for custom build commands.
Main configuration is in pyproject.toml.
"""

import os
import shutil
from pathlib import Path

try:
    from setuptools import setup
    from setuptools.command.build import build
    from distutils.command.clean import clean
except ImportError:
    from distutils.core import setup
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


if __name__ == '__main__':
    setup(
        cmdclass={
            'build': GenerateManpage,
            'clean': CleanMore,
        },
    )
