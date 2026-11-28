# TODO

<!--
SPDX-FileCopyrightText: 2026 Kalle Valo
SPDX-License-Identifier: GPL-3.0-or-later
-->

Planned tasks, and known shortcomings of cmdspecs which have been
looked at but deliberately left alone, mostly because fixing them
needs a design decision or changes the behaviour users may rely on.
The function names refer to the `cmdspecs` script.

## Running tests in parallel

The tests are run one at a time in `CommandTester.run_tests()`.
The time is spent almost completely in the scripts, so running
several tests at once, with an option such as `-j N`, is the only
way to make a large test suite substantially faster.

It is not done because the current design assumes serial execution
in several places:

- All tests share one `DATADIR`. The tests of a directory commonly
  rely on it: `setup_once` creates files which all tests use, and
  `setup` and `teardown` create and remove files with fixed names
  for each test. Two tests running at once would step on each other.
  Each parallel worker would need its own data directory, and then
  `setup_once` would have to run once for each worker, or the tests
  of one directory would have to stay serial.
- The order is documented: `setup_once`, then for each test
  `setup`, `foo.setup`, `foo.script`, `foo.teardown`, `teardown`,
  and `teardown_once` last. Tests can depend on running in the
  alphabetical order, even though they should not.
- `Reporter` prints a dot when each test finishes and groups the
  dots by directory, and in verbose mode prints the name of the test
  before running it. With parallel tests the results come in any
  order, so the reporting would need to buffer the results or change
  the format.
- The timings would need to be collected from the workers.

The least intrusive design is to parallelise over directories only:
each directory given on the command line gets its own `DATADIR` and
its tests run serially in the documented order, but several
directories run at the same time. That speeds up only suites which
are split into many directories, and it changes `DATADIR` from one
for the run to one for each directory, which is visible to the
scripts which share data between directories.

## Windows

cmdspecs runs on Windows with the `sh` of Git for Windows or MSYS2,
and CI tests it there from PowerShell and from Git Bash. These were
left out:

- Native Windows programs write CRLF, so the expected files of their
  tests need CRLF too. An option which turns CRLF into LF in the
  output before comparing would let one set of expected files work
  everywhere, but it changes what a test checks.
- pip makes no `.exe` launcher for the extensionless script, so
  outside Git Bash cmdspecs is run as `python path\to\cmdspecs`. A
  launcher needs a `[project.scripts]` entry point, which needs an
  importable module instead of the single script.
- A process which a script starts before cmdspecs has put the script
  in its job object escapes the job and is not killed. `sh` takes
  longer than that to start anything, so it has not been seen. Closing
  the gap needs the script to start suspended, which `subprocess`
  can't do.

Not tested on Windows:

- Ctrl-C from a console, as CI has none, and the tests where a script
  interrupts cmdspecs with `kill -INT $PPID` are skipped there. A test
  could start cmdspecs in a console of its own and send it
  `CTRL_C_EVENT`.
- Colors in a console, which need VT processing, and in mintty, where
  `isatty()` is false.
- A symlink to a directory which a test leaves in the work area,
  which `cleanup_tempdir()` must not follow, as creating symlinks
  needs privileges there.
- WSL, which should work like Linux.
