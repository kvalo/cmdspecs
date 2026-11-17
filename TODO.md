# TODO

Known shortcomings of cmdspecs which have been looked at but
deliberately left alone, mostly because fixing them needs a design
decision or changes the behaviour users may rely on. The function
names refer to the `cmdspecs` script.

## The --keep option does not keep the data on every failure

The manpage and `--help` describe `-k`/`--keep` as "keep temporary
data on failure", but `CommandTester.run()` decides it like this:

    failed = self.run_tests(testdirs)
    keep_tempdir = bool(failed) and args.keep

`failed` is the list of failed tests only, so the temporary directory
is kept only when at least one test failed. It is removed in these
cases even with `--keep`, although the run did not succeed:

- A `setup_once` script fails. The failure goes to
  `CommandTester.errors`, not to `failed`, and `run_tests()` stops
  there. If no test failed before that, which is always the case
  when it is the `setup_once` of the first directory, the directory
  is removed and cmdspecs exits with 1. This is the case where the
  data is needed the most: the script may have left half-made files
  in `DATADIR`, and its exit status is the only other clue.
- A `teardown_once` script fails while all the tests passed. Same
  as above, the failure is only in `CommandTester.errors`.
- cmdspecs is interrupted with Ctrl-C, or an unexpected exception is
  raised while the tests run. `keep_tempdir` is still `False` when
  the `finally` clause runs, so the directory is removed. A user who
  interrupts a hanging test (see "No timeout for tests") to look at
  what it left behind finds nothing.

The behaviour is also inconsistent: a failing `setup_once` in the
second directory keeps the data if a test in the first directory
happened to fail, and removes it otherwise.

Options:

- Keep the directory whenever cmdspecs is going to exit with 1, that
  is `bool(failed or self.errors) and args.keep`. Small change which
  makes the code match the documentation. Users who run with
  `--keep` all the time get more directories left in `/tmp`, but
  only from runs which failed anyway.
- As above, and also keep it on interrupt and on unexpected
  exceptions. `keep_tempdir` has to be decided before the tests run
  rather than after, and the `Test work area:` line has to be
  printed from the interrupt path too, or the user does not know
  where the directory is. The line goes to stdout after the summary
  today; on interrupt there is no summary, so stderr next to the
  `cmdspecs: interrupted` message is the natural place.
- Keep the directory always when `--keep` is given, also when
  everything passed. The simplest rule to explain, and useful when
  writing new tests, but it changes the meaning of the option and
  fills `/tmp` for those who always use it.
- Leave the code alone and change the manpage and `--help` to say
  "when a test fails". No behaviour change, but the option stays
  useless for debugging `setup_once`.

A fix needs a spec or unit test for a failing `setup_once` with
`--keep`, and the description of `--keep` in the OPTIONS section of
the manpage should say exactly when the directory is kept.

## Output of setup and teardown scripts is not captured

`CommandTester.run_script()` runs the `setup_once`, `setup`,
`foo.setup`, `foo.teardown`, `teardown` and `teardown_once` scripts
with `subprocess.check_call()` and does not redirect their output,
so anything they print goes straight to the stdout and stderr of
cmdspecs. Only the output of `foo.script` is captured.

The output lands in the middle of the progress line, for example:

    setup-once runs
    tests/specs/echo hello.setup runs
    .                                            [ 33%]

`Reporter` does not know about the extra text, so `Reporter.line_len`
is wrong and the `[ NN%]` column is misaligned or the line wraps at
the wrong place. It also makes the output hard to parse, and the
ordering of stdout and stderr is unpredictable when they are
redirected to different places.

On the other hand, when a script fails, its output is the only clue
about what went wrong: the message of `ScriptError` is just
`<script>: exited with N`. So the output must not simply be thrown
away.

Options:

- Capture stdout and stderr of the scripts, and show them only when
  the script fails, in the FAILURES section together with the exit
  status. This is what pytest does with fixtures and is the cleanest
  output. Scripts which print progress on purpose become silent.
- As above, but also show the captured output with `-v`, or add an
  option like pytest's `-s` to turn the capturing off.
- Redirect the output to files in the temporary directory and
  mention the file names on failure. Only useful with `--keep`.

`setup_once` and `teardown_once` failures are not tied to any test,
so they need a place in the report too; today they are printed to
stderr after the summary. A script which starts a background daemon
that keeps the pipe open would make cmdspecs wait forever if the
output is read through a pipe, so capture to a temporary file rather
than a pipe.

## No timeout for tests

`CommandTester.run_command()` uses `subprocess.run()` and
`CommandTester.run_script()` uses `subprocess.check_call()`, both
without a timeout. A test or a setup script which hangs, for
example because it waits for a lock, a network connection or a
child process, hangs the whole run until somebody kills it. In CI
that means waiting for the timeout of the whole job and getting no
report at all about which test hung.

Options:

- A `--timeout=SECONDS` option which applies to every test. Easy to
  use, but one slow test forces a long timeout for all of them.
- A per-test `foo.timeout` file with the number of seconds, in the
  style of `foo.exit`. Needs adding `timeout` to
  `TestDir.per_test_suffixes` and to the manpage.
- Both, with the file overriding the option.

Things to solve in the implementation:

- The test scripts are usually shell scripts, and killing only the
  shell leaves its children running, and they may keep the output
  files open. The script has to be started in its own session or
  process group (`start_new_session=True`) and the whole group
  killed, first with SIGTERM and after a grace period with SIGKILL.
- With its own process group the script no longer gets the SIGINT
  when the user presses Ctrl-C, so cmdspecs has to kill the group
  itself on `KeyboardInterrupt`.
- Should `foo.teardown` and `teardown` still run after a timeout?
  Probably yes, as they do after other failures, and they need a
  timeout as well.
- How to report it: a failure such as `timed out after 10 seconds`,
  and the output collected so far should still be kept in the
  `-actual` files as it helps in finding where the script hung.
- Whether the timeout covers `foo.script` only or also the setup
  and teardown scripts of the test.

## The -c option is accepted and ignored

`CommandTester.make_parser()` defines `-c`/`--command` only so that
command lines written for cmdtest, from which cmdspecs was forked,
keep working. The value is never used. In cmdtest the option gave
the command to test, and it was made available to the test scripts.

Accepting an option and silently ignoring it is misleading: a user
who gives `-c` expects it to have an effect, and nothing tells them
otherwise except the manpage.

Options:

- Keep it as is. No work, and old command lines keep working.
- Print a deprecation warning to stderr when the option is used,
  and remove it in a later release. This is the usual path, but the
  warning may break users who compare the stderr of cmdspecs.
- Remove it now. cmdspecs is a renamed fork, so everybody has to
  change their command lines anyway to call `cmdspecs` instead of
  `cmdtest`.

Removing or deprecating it needs updates to the SYNOPSIS and OPTIONS
sections of the manpage and a NEWS entry.
`test_manpage_documents_all_options` only checks that the options
of the parser are in the manpage, not the other way round, so a
stale entry in the manpage would not be noticed.

## A script killed by a signal is reported as a negative exit code

`subprocess.run()` returns `-N` as the return code when the process
was killed by signal `N`, and `CommandTester.run_test()` compares
that number as is with the content of `foo.exit`. A crashing test
is reported as:

    got exit code -11, expected 0

This is cryptic for anybody who does not know the convention of the
Python subprocess module, and it is different from what a shell
shows in `$?` for the same thing, which is 139 (128 + 11). A test
which is expected to die from a signal, such as a test of a signal
handler, can only be written by putting `-11` in `foo.exit`, which
is undocumented.

In practice it is rare, because `foo.script` is normally a shell
script, and the shell itself exits normally with 128 + N when the
command it ran was killed. The negative code is seen only when the
script itself is killed, or when it ends with `exec`.

Options:

- Keep the comparison but improve the message, for example
  `killed by signal SIGSEGV, expected exit code 0`, using
  `signal.Signals(N).name`.
- Map the code to 128 + N before comparing, like the shell does.
  Then `foo.exit` works the same no matter whether the script uses
  `exec`. This breaks any existing `foo.exit` file with a negative
  number.
- Do both, and document in the manpage what `foo.exit` has to
  contain for a signal.

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
