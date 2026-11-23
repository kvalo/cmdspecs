# Changelog

<!--
SPDX-FileCopyrightText: 2011-2017 Lars Wirzenius
SPDX-FileCopyrightText: 2025-2026 Kalle Valo
SPDX-License-Identifier: GPL-3.0-or-later
-->

All notable changes to cmdspecs are documented in this file.

The format is based on [Keep a Changelog][keepachangelog], and this
project adheres to [Semantic Versioning][semver].

Releases before 0.33 are of cmdtest and its yarn tool, from which
cmdspecs was forked.

## [Unreleased]

### Added

- cmdspecs now works on Windows, with the `sh` of Git for Windows or
  MSYS2 to run the scripts, and its tests run there in CI.

## [0.34.0] - 2026-11-19

### Added

- The new `-o`/`--timeout` option kills a test, or a setup or
  teardown script, which runs longer than the given number of
  seconds, and reports it as failed. Before, a hung test hung the
  whole run.
- The new `-s`/`--no-capture` option turns off the capturing of the
  output of setup and teardown scripts.
- cmdspecs now works on macOS, and its tests run there in CI.

### Changed

- The output of setup and teardown scripts is now captured and shown
  only when the script fails, as part of the failure. Before, it was
  written in the middle of the progress line.
- A directory without tests on the command line is now an error:
  cmdspecs reports it and exits with 5, as pytest does. Before, it
  exited with 0. The summary also counts such errors, and the errors
  of `setup_once` and `teardown_once` scripts, and is red when there
  are any.
- The exit statuses now follow pytest where that makes sense. An
  interrupt exits with 2 (was 130) and a usage error with 4 (was 2).
  An internal error in cmdspecs exits with 3 and shows a traceback,
  instead of looking like a failed test with 1, and an I/O error such
  as an unwritable temporary directory gives a short message and 1.

### Removed

- The `-c`/`--command` option, which cmdspecs accepted and ignored
  for compatibility with cmdtest. Using it is now a usage error.

### Fixed

- On macOS, an interrupt or a timeout was reported as a failure to
  run the test.

## [0.33] - 2026-11-15

### Added

- The new `--version` option prints the version of cmdspecs, and the
  header of the output shows it too.
- The new `--color` option and the `NO_COLOR` environment variable
  control the coloring of the output on a terminal.
- The new `-v` (`--verbose`) option shows the name and result of each
  test on its own line.
- The project's own tests now live under `tests/` and run with pytest
  via `./check`, which ends with a single pass/fail summary.

### Changed

- Forked from cmdtest and renamed to cmdspecs. The source was
  [cmdtest 0.32.14][cmdtest-src] from Debian.
- Python 3.10 or newer is now required.
- Ported to Python 3, and Python 2 support dropped. Changes made by
  Antonio Terceiro and Richard Ipsum, and mutilated by Lars
  Wirzenius.
- Replaced cliapp and ttystatus package dependencies with argparse
  and subprocess.
- The output now looks like pytest's: a header, a dot (or `F`) per
  test on a line per test directory, the failures at the end, and a
  summary such as `1 failed, 3 passed in 0.05s`. The output is
  colored on a terminal.

### Removed

- The yarn tool and its associated libraries (yarnlib, yarnutils).
  Yarn was a BDD-style testing tool that was developed alongside
  cmdtest.

### Fixed

- Undo HTML escaping of code blocks done by the Python Markdown
  parser.

## 0.32 - 2018-02-24

No changes. Want a new release to trigger an upload to Debian.

## 0.31 - 2017-04-30

### Added

- Add `yarnutil.Variables` methods: `save`, `append`, `get`.

## 0.30 - 2017-04-16

### Fixed

- Fix check for whether Python is used a shell. Previously the shell
  had to be exactly "python", not anything that contains that is
  enough. This is necessary to trigger `PYTHONPATH` manipulation when
  using python2 explicitly.

## 0.29 - 2017-04-11

### Added

- Add assertions and getting the next parameter match to `yarnutils`.

## 0.28 - 2017-03-28

### Added

- Add a new Python package `yarnutils` that can be imported into
  IMPLEMENTS written in Python to simplify things. This version
  provided persistent variables.

### Fixed

- Output from `--timings` is now properly formatted, rather than it
  all being on one line. Daniel Silverstone reported the bug.

## 0.27 - 2016-09-21

### Changed

- Debian packaging now provides the name `yarn` in addition to
  `cmdtest`.

### Fixed

- Fixed bug in writing out error messages that are not ASCII.

## 0.26 - 2016-07-23

### Fixed

- Debian packaging fix to correct section. Thanks, Ben Finney.

## 0.25 - 2016-07-18

### Fixed

- Fixed yarn manual page examples to say `DATADIR` instead of
  `TESTDIR`. Thanks to John Kozak for reporting it.

## 0.24 - 2016-04-18

### Fixed

- Fixed missing import.

## 0.23 - 2016-04-18

### Added

- Yarn now has the `--stop-on-first-fail` setting, which makes it
  stop if a scenario step fails, and not continue with the next
  scenario.

### Changed

- Yarn now adds `SRCDIR` to `PYTHONPATH`, if `--shell=python` is
  used.

## 0.22 - 2016-02-04

### Fixed

- Explicitly encode Unicode strings to the preferred locale encoding
  when writing to stdout, stderr.

## 0.21 - 2016-01-25

### Fixed

- Fixed another non-ASCII problem in yarns. Also found by Heikki
  Haapala. This time, environment variable values must be encoded
  (we do UTF-8).

## 0.20 - 2016-01-25

### Fixed

- Allow scenario and step names to have non-ASCII text. Thanks to
  Heikki Haapala for reporting the problem.

## 0.19 - 2016-01-09

### Added

- Yarn now supports `--shell` to choose the shell to execute
  IMPLEMENTS scripts, and `--shell-arg` to add arguments to shell.
  This can be used to use Python instead of sh:
  `--shell=/usr/bin/python2 --shell-arg=''`.
- Yarn now supports the `--cd-datadir` setting to have each step run
  in `DATADIR` instead of `SRCDIR`. The default remains `SRCDIR`, but
  at some point in the future, the default will probably change.

### Changed

- Yarn now gives an error if `--run` is given a scenario that doens't
  exist.

## 0.18 - 2015-11-06

### Added

- Code blocks that are examples are now supported.

### Changed

- Snapshot directories are now created only when `--snapshot` is
  used.

## 0.17 - 2015-09-21

### Added

- The `--require-assumptions` option has been added to tell Yarn to
  treat failing ASSUMPTIONS steps as errors.

### Changed

- Yarn now flushes outputs (stdout, stderr) whenever it writes
  anything. This should avoid some problems with programs that
  capture yarn output, such as CI systems, and get the timings
  differently from what would happen on a terminal.

## 0.16 - 2015-06-30

### Fixed

- Flush terminal status output whenever a new scenario or step is
  started. This ensures the terminal isn't showing an earlier, very
  fast step, when the actual current step is slow.

## 0.15 - 2015-06-29

### Added

- Failed scenarios are listed at the end of yarn output.

### Changed

- Steps are indented when yarn is run in `--verbose` mode.

## 0.14 - 2015-03-05

### Added

- Yarn now supports continuation lines: start a line with `...` and
  it continues the previous line.
- Yarn now works with UTF-8 input. No other character sets are
  supported; sorry (but patches welcome).

## 0.12 - 2014-03-28

### Fixed

- yarn: Do not fail a test suite if snapshotting `DATADIR` fails.

## 0.11 - 2014-03-15

### Added

- yarn: Report number of scenarios skipped due to an ASSUMING step
  failing.
- yarn: New option `--allow-missing-steps` to allow running a test
  suite with some steps missing. The scenarios with missing steps
  will be skipped. Suggested by Pete Fotheringham.

### Changed

- yarn: Yarn now sets `$HOME` to a directory in `$DATADIR`, and
  creates that directory. This means test suites can assume `$HOME`
  exists, but don't use the user's real home directory, which is
  important for test environment hygiene.

### Fixed

- yarn: Fix the error message for reporting scenarios without THEN
  steps to include the names of those scenarios only, rather than all
  scenarios. Patch by Pete Fotheringham.
- cmdtest: The `--test` (`-t`) option should now work again. Thank
  you to Kalle Valo for prodding me.

## 0.10 - 2013-10-05

### Added

- A new option, `--timings`, has been added to yarn to report how
  long each scenario and each step took.
- Yarn now reports scenarios skipped because of ASSUMING failing.
- Yarn manual page now documents `DATADIR` and `SRCDIR` environment
  variables.
- Yarn now complains if a scenario has no THEN steps. Suggested by
  Richard Maw.
- Yarn now gives an error if there are no scenarios. Suggested by
  Daniel Silverstone and others.
- Yarn now checks for duplicate scenario names.

### Changed

- Yarn now cleans the environment when it runs shell commands for the
  implementation steps. The `PATH` variable is kept from the user's
  environment, every other variable is either removed or hardcoded to
  a specific value. More variables can be added explicitly to the test
  environment with the new `--env NAME=VALUE` option. Additionally
  yarn sets the `SRCDIR` environment variable to point at the root of
  the source tree (the directory where yarn was invoked from).

### Fixed

- Yarn now always checks for IMPLEMENTS sections with
  case-insensitive matching. Reported, with test case, by Jannis
  Pohlmann.

## 0.9 - 2013-07-23

### Added

- Yarn now warns if an input file has no code blocks.
- There is now a yarn `--shell-library` option for the user to use,
  which includes a shell library when running any IMPLEMENTS section.
- The keyword ASSUMING has been added to yarn.
- New yarn option `--run` allows running selected tests only.
- New yarn option `--snapshot` makes snapshots of the test working
  directory after each step in a scenario. Combined with the, also
  new, option `--tempdir` this makes debugging failed tests easier.
- New yarn option `--verbose` (turned on automatically if there is
  not tty available, e.g., when running from cron), turns off
  ttystatus progress bar and produces a "wall of text" style output
  instead.
- FINALLY always worked in yarn, but has now been added to the manual
  page as well.

### Fixed

- Yarn now handles multiple input files correctly. Reported by Daniel
  Silverstone; fix based on his patch, but rewritten.

## 0.8.3 - 2013-06-21

### Fixed

- Properly install yarnlib. In other news, I hate distutils.

## 0.8.2 - 2013-06-21

### Fixed

- Install the yarnlib library as well. This is embarrassing.

## 0.8.1 - 2013-06-20

### Fixed

- Install the yarn binary in the package.

## 0.8 - 2013-06-19

### Changed

- Switch terminology to "scenario testing" from "story testing".
  Thanks to Rob Kendrick for the suggestion. Doing a quick release so
  the old terminology doesn't have time to get any use.

## 0.7 - 2013-06-15

### Added

- Added the new tool `yarn`, for doing story testing. It is still
  fresh and raw, but I want to make it available to get feedback.

## 0.6 - 2013-03-14

### Fixed

- Fixed cmdtest to diff outputs correctly. Reported by Kevin Lee.

## 0.5 - 2012-09-29

### Fixed

- Add missing copy of GPLv3. Reported by Michel Alexandre Salim.

Version 0.4 may or may not have released. If it was, it should have
had internal changes only.

## 0.3 - 2012-02-24

### Added

- Add `--keep` option to keep the temporary directory for failed
  tests.
- Add `--timings` option to show timings for various tests. Good for
  when test suites start getting slow and you want to speed them up.

## 0.2 - 2012-02-18

### Fixed

- The `-t testname` option now works.

[keepachangelog]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/spec/v2.0.0.html
[Unreleased]: https://github.com/kvalo/cmdspecs/compare/v0.34.0...HEAD
[0.34.0]: https://github.com/kvalo/cmdspecs/compare/v0.33...v0.34.0
[0.33]: https://github.com/kvalo/cmdspecs/releases/tag/v0.33
[cmdtest-src]: https://deb.debian.org/debian/pool/main/c/cmdtest/cmdtest_0.32.14.gcdfe14e.orig.tar.xz
