# cmdspecs

`cmdspecs` tests command line programs by running small shell scripts
and comparing their output to files you wrote beforehand. It works
with any program you can run from a shell, whatever language it is
written in.

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
diff of the expected and the actual output. Besides `.stdin` and
`.stdout`, a test can check `.stderr` and the exit status (`.exit`),
and have `.setup` and `.teardown` scripts. The manual page
(`man -l cmdspecs.1`) describes all of them, plus the options for
running selected tests, timeouts and colored output.

## Requirements

`cmdspecs` runs on Linux and macOS. It needs Python 3.10 or later and
nothing beyond the standard library.

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

## Project

The project lives at <https://github.com/kvalo/cmdspecs>. Report
bugs and send patches there.

## License

Copyright 2011-2017 Lars Wirzenius

Copyright 2025-2026 Kalle Valo

`cmdspecs` is free software, licensed under the GNU General Public
License, version 3 or (at your option) any later version. See the
file `COPYING` for the full text.
