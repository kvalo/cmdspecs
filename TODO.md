# TODO

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

## Measure the code coverage of the tests

Measure how much of the `cmdspecs` script the pytest suite runs, to
find code which no test covers. This is about the tests of this
project, not about a coverage feature in cmdspecs itself.

The obvious tool is `pytest-cov`, which uses `coverage.py`. It would
be added to the `test` extra in `pyproject.toml` and the run would be
something like `./check --cov`. Points to look at:

- `cmdspecs` has no `.py` extension, and `tests/test_cmdspecs.py`
  loads it with `importlib`, so the source for `--cov` has to be given
  as a path or the file has to be listed in the `coverage.py` config.
  Whether the report works for such a file is not verified.
- `tests/test_specs.py` runs the script as a subprocess, so the
  coverage of those runs is lost unless `coverage.py` is set up to
  measure subprocesses too. Without that, only the unit tests count
  and the report understates the coverage.
- Decide whether to add a minimum coverage that fails the run, and
  whether CI should run it, or whether the report is only for
  reading.

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
- WSL, which should work like Linux.
