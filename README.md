# cmdspecs

<!--
SPDX-FileCopyrightText: 2011-2017 Lars Wirzenius
SPDX-FileCopyrightText: 2025-2026 Kalle Valo
SPDX-License-Identifier: GPL-3.0-or-later
-->

`cmdspecs` tests command line programs by running small (or big, if
you prefer) shell scripts and comparing their output to files you
wrote beforehand. It works with any program you can run from a shell,
whatever language it is written in.

The testing is black box: `cmdspecs` knows nothing about how the
program is built, only what it does. It feeds the program input, then
checks what comes out: standard output, standard error and the exit
status. This is how users see the program, so the tests keep working
when you refactor or rewrite the internals.

Benefits:

- Writing a test is quick: a short script and a file with the
  expected output, and no test framework or code to learn.
- Any change in the output is easy to notice, because `cmdspecs`
  shows a diff of the expected and the actual output.
- The tests double as examples of how the program is used.
- The same tests work for any language, and for a rewrite of the
  program in another one.

## Example

A test case is a script plus files that describe what it should
produce. Say you want to test `sort`. Make a directory with these
files:

```text
sort-tests/
    sorts-fruit.script
    sorts-fruit.stdin
    sorts-fruit.stdout
```

`sorts-fruit.script` is the command to run:

```sh
#!/bin/sh
sort
```

Make the script executable with `chmod +x sorts-fruit.script`.

`sorts-fruit.stdin` is fed to the script as input. Here it is three
fruits in the wrong order:

```text
pear
apple
banana
```

`sorts-fruit.stdout` is the output you expect, the same lines sorted:

```text
apple
banana
pear
```

Then run:

```sh
cmdspecs sort-tests
```

If the output matches, the test passes. If not, `cmdspecs` shows a
diff of the expected and the actual output. Here is a run with six
tests, one of which fails because its expected output is wrong (`-v`
lists every test):

```text
$ cmdspecs -v sort-tests
=========================== cmdspecs session starts ===========================
platform linux -- Python 3.13.5, cmdspecs 0.33
srcdir: /home/user/project
datadir: /tmp/cmdspecs-tx45caju/data
keep: no
testdirs: sort-tests
collected 6 tests

sort-tests::empty-input PASSED                                           [ 16%]
sort-tests::missing-file PASSED                                          [ 33%]
sort-tests::numeric PASSED                                               [ 50%]
sort-tests::reverse PASSED                                               [ 66%]
sort-tests::sorts-fruit PASSED                                           [ 83%]
sort-tests::unique FAILED                                                [100%]

================================== FAILURES ===================================
___________________________________ unique ____________________________________
stdout diff:
--- sort-tests/unique.stdout 2026-11-19 09:14:53.946186 +0200
+++ sort-tests/unique.stdout-actual 2026-11-19 09:14:59.886134 +0200
@@ -1,3 +1,2 @@
 a
 b
-b
=========================== short test summary info ===========================
FAILED unique - stdout diff:
========================= 1 failed, 5 passed in 0.01s =========================
```

Besides `.stdin` and
`.stdout`, a test can check `.stderr` and the exit status (`.exit`),
and have `.setup` and `.teardown` scripts. The manual page
(`man -l cmdspecs.1`) describes all of them, plus the options for
running selected tests, timeouts and colored output.

## Requirements

`cmdspecs` runs on Linux, macOS, FreeBSD, OpenBSD, NetBSD and
Windows. It needs Python 3.10 or later and nothing beyond the standard
library.

On Windows it also needs the `sh` of
[Git for Windows](https://gitforwindows.org) or MSYS2 in `PATH`, as
that runs the scripts. Run `cmdspecs` from Git Bash, or from cmd or
PowerShell as `python path\to\cmdspecs`. Git for Windows checks out
text files with CRLF line endings by default, so mark your test files
with `-text` in `.gitattributes` to keep the expected output as you
committed it. The manual page has more about Windows.

## Installation

Install from the source directory:

```bash
pip install .
```

Add `--user` to install only for the current user.

Since `cmdspecs` is a single script, you can instead copy it to a
directory in your `PATH`:

```bash
install -m 755 cmdspecs ~/.local/bin/
```

The script is also attached to each release on the
[releases page](https://github.com/kvalo/cmdspecs/releases), so you
can download the latest release without the source directory:

```bash
curl -LO https://github.com/kvalo/cmdspecs/releases/latest/download/cmdspecs
install -m 755 cmdspecs ~/.local/bin/
```

## Development

`cmdspecs` has its own tests, which need [pytest](https://pytest.org).
Install it with:

```bash
pip install .[test]
```

Then run the tests with:

```bash
./check
```

`./check` runs the unit tests and runs `cmdspecs` itself on the
example specs in `tests/specs`. It passes its arguments on to pytest,
so `./check -x` stops at the first failure and `./check -k echo` runs
only the tests with `echo` in their name.

`./lint` checks the code and the documentation:

```bash
./lint
```

To run it, install these tools first. They are only needed for
`./lint`, not for `./check` or for using `cmdspecs`:

- `flake8` for the Python code
- `shellcheck` for the shell scripts
- `mdl` (markdownlint) for the Markdown files
- `groff` for checking the manual page for warnings
- `yamllint` for the GitHub workflow files (optional, skipped if
  missing)

GitHub Actions runs both `./check` and `./lint` for every push, and
`./check` also on macOS, Windows, FreeBSD, OpenBSD and NetBSD.

## Project

The project lives at <https://github.com/kvalo/cmdspecs>. Report
bugs and send patches there.

## License

Copyright 2011-2017 Lars Wirzenius

Copyright 2025-2026 Kalle Valo

`cmdspecs` is free software, licensed under the GNU General Public
License, version 3 or (at your option) any later version. See the
file `LICENSES/GPL-3.0-or-later.txt` for the full text.
