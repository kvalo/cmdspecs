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

## Support Windows

cmdspecs does not run on Windows yet. The findings below come from
reading the code and from a temporary probe job on GitHub's
`windows-latest` runner on 2026-11-23: Windows build 26100, Git for
Windows 2.56.1 with bash 5.3 and Python 3.13.17 (workflow run
45126360825). What the probe did not test is marked *unverified*.

### Findings in cmdspecs

- Scripts are run directly with `subprocess.Popen([script])` in
  `run_process`, relying on the shebang and the exec bit. Windows
  ignores both. A `.script` file fails with WinError 193, "%1 is not a
  valid Win32 application". An extensionless `setup_once` fails with
  "The system cannot find the file specified", because `CreateProcess`
  adds `.exe` to a name without an extension. This is what
  `cmdspecs tests/specs/echo` reports, as an error.
- `kill_group` uses `os.killpg` and `signal.SIGKILL`, which Windows
  does not have, and `start_new_session=True` is silently ignored
  there. Every timeout ends in an `AttributeError` and an internal
  error with exit 3, and by reading the code, so does an interrupt
  while a script runs. This is the second hard blocker.
- Under Git for Windows a background child of `sh` is a separate
  Windows process. `proc.kill()` kills only the process cmdspecs
  started, and for `Git\bin\sh.exe` that is a launcher, not even the
  shell, which is `Git\usr\bin\sh.exe`. `taskkill /T /F` kills the
  shell but not its background children, as MSYS does not keep the
  Windows parent links, and after the script has exited it finds
  nothing at all. Two things worked: `CTRL_BREAK_EVENT` sent to a
  script started with `CREATE_NEW_PROCESS_GROUP` killed the shell and
  its children, and a job object, which the script was assigned to
  just after it started, killed the children left running after it
  exited.
- Windows can't remove a file which a process has open. A background
  child which keeps `foo.stdout-actual` open makes `remove()` raise
  `PermissionError`, "The process cannot access the file because it is
  being used by another process", and that ends the whole run with
  exit 1. One which keeps a file in `DATADIR` open makes
  `cleanup_tempdir` print "could not remove". On Unix such children
  are harmless after a normal exit, so cmdspecs kills them only on a
  timeout or an interrupt.
- An MSYS `sh` killed by signal N exits with N * 256, e.g. 2304 for
  `kill -KILL $$`, where cmdspecs shows 137 on Unix. Exit codes are
  never negative on Windows. `describe_exit` names 128 and 129
  `CTRL_C_EVENT` and `CTRL_BREAK_EVENT`, as `signal.Signals` has them
  on Windows, and has no name for 137, as there is no `SIGKILL`.
- `diff()` is passed `/dev/null` for a missing expected file. The open
  fails and the file reads as empty, so the diff is right, but
  `mtime()` fails too, and the header is `--- /dev/null` without the
  timestamp that Linux shows.
- Git for Windows sets `core.autocrlf=true` in its system gitconfig,
  so the expected output files are checked out with CRLF. MSYS bash
  ignores the CRs in scripts, even after `#!/bin/sh`, so the scripts
  run, but their output has LF, and the `echo`, `env` and `stderr`
  specs fail. There is no `.gitattributes` yet.
- Native Windows programs write CRLF. A `#!/usr/bin/env python3`
  script which prints `hi` fails against a `foo.stdout` with `hi` and
  LF. The output of a tool under test will often have CRLF too.
- Paths are shown with backslashes or mixed separators, e.g.
  `tests/specs/echo\setup_once` and `--- .\foo.stdout`. MSYS `sh`
  accepted the script path in every form: mixed, `.\`, and absolute
  on both `C:` and `D:`.
- `DATADIR` and `SRCDIR` are Windows paths, such as
  `C:\Users\RUNNER~1\AppData\Local\Temp\cmdspecs-xyz\data` with an 8.3
  short name. Writing files there, `ls` and `cd` work in `sh`, but
  `pwd` prints `/d/a/...`, so a script must not compare paths as text.
- `tempfile` reads `TMPDIR` first on Windows too, so setting it
  isolates the work area as on Unix.
- pip installs `Scripts\cmdspecs` with the shebang changed to the
  venv's python, but makes no `.exe` launcher, so it can't be run by
  name from cmd or PowerShell. `python venv\Scripts\cmdspecs` works,
  and so does running it by name from Git Bash, as MSYS follows the
  shebang. A launcher needs a `[project.scripts]` entry point, which
  needs an importable module.
- ANSI colors need a console with VT processing, and under mintty
  `isatty()` is false. *Unverified*, as CI has no terminal.

### Findings in the tests

- On the runner 90 tests fail and 41 pass. All 75 in
  `tests/test_specs.py` fail with WinError 193, as they run
  `[str(CMDSPECS), ...]` directly in `run_cmdspecs` and in three tests
  which call `subprocess.run` themselves. They need
  `[sys.executable, CMDSPECS, ...]`.
- In `tests/test_cmdspecs.py` 12 tests fail because they run scripts,
  and 3 `scan` tests because they expect `tests/setup_once` and get
  `tests\setup_once`.
- Under MSYS a file which starts with `#!` counts as executable, and
  `exec` ran a file without one or the exec bit too. So
  `test_reports_non_executable_script` and the
  `test_non_executable_*` hook tests can't pass. Skip them.
- The timeout and interrupt tests check that a background child is
  gone with `os.kill(pid, 0)`. On Windows 0 is `CTRL_C_EVENT`, so the
  call checks nothing: it sends a Ctrl-C, which reached the caller and
  not the target. The pid is also an MSYS pid from `$!`, and the
  Windows one is in `/proc/PID/winpid`. `kill -0 PID` run in `sh`
  should work on both. *Unverified.*
- *Unverified*: `test_removes_work_area_with_read_only_dirs` uses
  `chmod 0` and `a-w` on dirs, and the interrupt tests use
  `kill -INT $PPID`. What `chmod` does on NTFS, and whether `$PPID` of
  a script started by a native Python is a process MSYS can signal,
  is not known.
- Assertions on `/data`, `/cmdspecs-` and diff headers such as
  `./foo.stdout-actual` need to accept `\`.
- `./check` and `./lint` are `#!/bin/sh` scripts, so on Windows run
  `python -m pytest` directly or use Git Bash.

### Options

- WSL: no work, it should already run as normal Linux Python.
  *Unverified.*
- Native Windows with Git for Windows or MSYS2: the shim and the
  process handling below. This is the recommended one.
- Native `.bat` or `.ps1` scripts: not recommended. It needs a new
  convention for choosing the interpreter, and cmdspecs is meant for
  testing Unix command line tools.

### The shim

On Unix, `Popen([script])` makes the kernel read the `#!` line and
start the interpreter. Windows has nothing like it, but the MSYS
runtime of Git for Windows does, so on `win32` let `sh` do it:

```python
def command_for(script):
    if sys.platform != 'win32':
        return [script]
    return [find_sh(), '-c', 'exec "$0"', script]
```

The probe ran `sh -c 'exec "$0"'` on scripts with `#!/bin/sh`,
`#!/bin/bash`, `#!/usr/bin/env python3`, `#!/usr/bin/env python` and
no shebang, and each ran with the right interpreter. MSYS resolves
`/bin/sh` and `/usr/bin/env` as on Unix and runs a script without a
shebang with `sh`, so cmdspecs need not parse the shebang itself.

The alternative is to read the shebang in Python and run
`[shutil.which(basename), script]`. The probe ran all the specs that
way, and on an LF checkout each one except `fail` passed, from both
PowerShell and Git Bash. But it looks the interpreter up in the
Windows PATH, which may have the wrong one: `bash` may be
`C:\Windows\System32\bash.exe`, the WSL launcher, and `python3` may
be the Microsoft Store stub in `WindowsApps`. Neither happened on the
runner, where Git and Python come first in PATH. *Unverified.*

Finding `sh`:

- From PowerShell on the runner, `shutil.which('sh')` gives
  `C:\Program Files\Git\bin\sh.exe`. That is a launcher which puts
  `/ucrt64/bin` and `/usr/bin` first in PATH, so the scripts get GNU
  `sort` and `find`, not the ones in `C:\Windows\system32`. From Git
  Bash it gives `Git\usr\bin\sh.exe`, and PATH is already right.
- `Git\usr\bin\sh.exe` started from PowerShell leaves PATH as it is.
  The scripts still got GNU `sort` on the runner, but only because
  `Git\bin` comes before `system32` in its PATH.
- A default Git for Windows install may put only `Git\cmd` in PATH,
  and then there is no `sh` outside Git Bash. *Unverified.* When there
  is no `sh`, fail with a message which says to install Git for
  Windows or to run cmdspecs from Git Bash, not with a traceback.

Things to decide when implementing it:

- Keep the shim in a small function, so that it can be unit tested on
  Linux by monkeypatching `sys.platform`.
- How much the extra `sh` costs for each script. *Unverified.*

### Killing the scripts

On `win32`, instead of `start_new_session` and `os.killpg`:

1. Start each script with `CREATE_NEW_PROCESS_GROUP`, and assign it
   to a new job object with ctypes (`CreateJobObjectW`,
   `AssignProcessToJobObject`). A child started before the assignment
   would escape the job, which the probe did not see happen.
2. On a timeout or an interrupt, send `CTRL_BREAK_EVENT` in place of
   `SIGTERM`, wait `KILL_GRACE` seconds and then call
   `TerminateJobObject` in place of `SIGKILL`.
3. Terminate the job after every script, too, as children left
   running would hold the output files open. This differs from Unix,
   where they are left running after a normal exit.

A new process group ignores Ctrl-C from the console, as the new
session does on Unix, so cmdspecs gets the `KeyboardInterrupt` and
kills the script. That is from the Windows documentation. Ctrl-C from
a console is *unverified*, as CI has none. Also *unverified* is
whether a script which traps INT or TERM survives `CTRL_BREAK_EVENT`;
the job object kills it anyway.

### Plan

1. On `win32`, run scripts with `sh -c 'exec "$0"'`, and give a clear
   error when there is no `sh`.
2. Kill the scripts with a process group and a job object as above.
   Map an exit code of N * 256 from MSYS to 128 + N, and name only the
   `SIG*` signals in `describe_exit`.
3. Stop reading `/dev/null` in `diff()`. Treat a missing expected file
   as empty and give it a fixed timestamp, so that the header is the
   same on every platform. That changes the output on Unix a little.
4. Make the tests portable: use `sys.executable`, make the path
   assertions separator-agnostic, check for live processes with
   `kill -0` in `sh`, and skip the exec bit, chmod and `$PPID` tests
   on `win32`.
5. Add a `.gitattributes` with `eol=lf` for `tests/specs/`.
6. Decide what to do about CRLF output from native programs: an
   option which turns CRLF into LF before comparing, or expected files
   with CRLF.
7. Add a `windows-latest` job to CI, which has Git for Windows and
   Python. Run `python -m pytest` from PowerShell, and the specs from
   Git Bash too.
8. Document the requirements (Git for Windows or MSYS2, or WSL), how
   to run cmdspecs (`python path\to\cmdspecs`, or by name from Git
   Bash) and the advice about CRLF in the README and the manpage.
