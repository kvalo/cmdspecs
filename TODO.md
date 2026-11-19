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

## Support Windows

cmdspecs has not been tried on Windows. Reading the code shows what
would break. Without Windows, Wine or PowerShell on the development
machine, none of this is verified.

### Findings in cmdspecs

- Scripts are run directly with `subprocess.run([test.script])` in
  `run_command` and `run_script`, relying on the shebang and the exec
  bit. Windows ignores both, so every script fails with `WinError 193`.
  This is the only hard blocker.
- The `.script`, `.setup` and `.stdout` files are compared as bytes.
  With `core.autocrlf=true`, the default in Git for Windows, git
  checks them out with CRLF. Then `#!/bin/sh\r` fails with "bad
  interpreter" and the output comparisons fail. There is no
  `.gitattributes` yet.
- `diff()` is passed `/dev/null` for a missing expected file. On
  Windows it works only by accident, because the open fails with
  `FileNotFoundError`, which is swallowed. Use `os.devnull`.
- The `chmod` in `cleanup_tempdir` does nothing useful on Windows but
  is harmless. Exit codes of killed processes differ from the POSIX
  negative signal numbers.
- The specs need `sh`, `cat`, `sort`, `touch`, `printf`, `kill` and
  `sleep`, so they work under Git Bash or MSYS2 but not in plain `cmd`
  or PowerShell.

### Findings in the tests

- `tests/test_specs.py` runs `[str(CMDSPECS), ...]` directly, in
  `run_cmdspecs` and in three tests which call `subprocess.run`
  themselves. They need `[sys.executable, CMDSPECS, ...]`.
- `write_script` and `make_script` rely on `chmod(0o755)` and a
  `#!/bin/sh` line. Neither works without the shim below.
- `test_reports_non_executable_script` expects `Permission denied`,
  and `test_removes_work_area_with_read_only_dirs` uses `chmod 0` and
  `a-w` on dirs, which have no effect on NTFS. Skip both.
- `test_interrupt_exits_with_interrupted_status` and
  `test_keep_option_keeps_work_area_on_interrupt` use
  `kill -INT $PPID`. Under Git Bash `$PPID` is an MSYS pid, not the
  Windows pid of Python, so the signal does not arrive. Skip both.
- Assertions on `'/data'` and `'/cmdspecs-'` in paths fail with `\`
  separators.
- Tests which set `TMPDIR` to isolate the work area do not work,
  because `tempfile` on Windows reads `TMP` and `TEMP`.
- `test_cmdspecs.py` also passes `'/dev/null'` to `diff()`.
- `./check` and `./lint` are `#!/bin/sh` scripts, so on Windows run
  `python -m pytest` directly or use Git Bash.
- Whether `pip install` makes a working launcher for the extensionless
  `script-files = ["cmdspecs"]` entry on Windows is not verified.

### Options

- WSL: no work, it should already run as normal Linux Python.
- Native Windows with a POSIX `sh` (Git for Windows or MSYS2): a small
  shim, described below.
- Native `.bat` or `.ps1` scripts: not recommended. It needs a new
  convention for choosing the interpreter, and cmdspecs is meant for
  testing Unix command line tools.

### The shim

The "shim" in the plan is a small piece of code in cmdspecs, active
on `win32` only, which does what the Unix kernel does for a script
with a shebang.

On Linux and macOS, `subprocess.run([test.script])` makes the kernel
read the first line of the file, such as `#!/bin/sh`, and start
`/bin/sh` with the script as its argument. Windows has no such
mechanism: it ignores the `#!` line and has no `/bin/sh`, so the call
fails with `WinError 193`.

The shim would do the same itself:

1. Read the first line of the script.
2. If it starts with `#!`, take the interpreter from it, such as
   `/bin/sh`, `/usr/bin/env python3` or `/usr/bin/python3`.
3. Find that interpreter on Windows. For `/bin/sh` that is the `sh`
   found on PATH, which Git for Windows or MSYS2 provides. Use the
   basename of the interpreter, and for `/usr/bin/env` use its first
   argument.
4. Run `[interpreter, script]` instead of `[script]`.

A sketch, not final code:

```python
def command_for(script):
    if sys.platform != 'win32':
        return [script]
    with open(script, 'rb') as f:
        first = f.readline()
    if first.startswith(b'#!'):
        interpreter = first[2:].split()[0].decode()
        return [shutil.which(os.path.basename(interpreter)), script]
    return [script]
```

`run_command` and `run_script` would then call
`subprocess.run(command_for(test.script), ...)`. On other platforms
nothing changes.

Things to decide when implementing it:

- A script without a shebang. Run it directly, which fails on
  Windows, or default to `sh`? Defaulting to `sh` matches what a shell
  does for an executable file without a shebang.
- The interpreter is not on PATH. `shutil.which` returns `None`, so
  report a clear `ScriptError` or "could not run" failure which says
  to install Git for Windows or MSYS2, instead of a traceback.
- The script path is passed to `sh` as a Windows path with
  backslashes. MSYS `sh` generally accepts it, but check it.
- Keep the shim in a small function, so that it can be unit tested on
  Linux by monkeypatching `sys.platform` and `shutil.which`.

### Plan

1. On `win32` only, read the shebang of each script and run it
   through that interpreter, resolving `/bin/sh` to the `sh` found on
   PATH. This also helps specs with a Python shebang.
2. Make the tests portable: use `sys.executable`, add
   `skipif(sys.platform == 'win32')` to the chmod, kill and permission
   tests, and make the path assertions separator-agnostic. Use
   `os.devnull` in `diff()`.
3. Add `.gitattributes` with `* text eol=lf` for `tests/specs/`.
4. Add a GitHub Actions `windows-latest` job that runs the tests
   under Git Bash, which is preinstalled there. This is the only way
   to confirm that it works without a Windows machine.
5. Document the requirement (a POSIX `sh` on PATH, or WSL) in the
   README and the manpage.

Expect the `echo`, `sort`, `stderr`, `exit`, `env` and `hooks` specs to
pass under Git Bash once this is done. The `DATADIR` and `SRCDIR`
values reach `sh` as `C:\...` paths, which MSYS generally converts, but
check that.
