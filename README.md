# README for cmdspecs

This project provides `cmdspecs`, a black box testing tool for Unix
command line tools.

## cmdspecs

`cmdspecs` black box tests Unix command line tools.
Given some test scripts, their inputs, and expected outputs,
it verifies that the command line produces the expected output.
If not, it reports problems, and shows the differences.

`cmdspecs` runs on Linux and macOS.

See the manual page for details on how to use the program.

## Installation

### From Source

Install from the source directory:

```bash
pip install .
```

For development (editable install):

```bash
pip install -e .
```

### Per-user Installation

To install only for the current user:

```bash
pip install --user .
```

### Copying the Script

`cmdspecs` is a single Python 3 script with no dependencies beyond
the standard library, so you can also install it by copying it to a
directory in your `PATH`:

```bash
install -m 755 cmdspecs ~/.local/bin/
```

This does not install the manual page; read it with
`man -l cmdspecs.1` or copy it to a `man1` directory in your
`MANPATH`.

## Manual page

The manual page source is `cmdspecs.1`, which `pip install` installs
under `share/man/man1`. To read it from the source tree without
installing:

```bash
man -l cmdspecs.1
```

## Legalese

Copyright 2011-2017 Lars Wirzenius\
Copyright 2025-2026 Kalle Valo

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
