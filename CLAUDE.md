# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when
working with code in this repository.

## Layout

- `cmdspecs` is the whole program: a single executable Python 3
  script with no `.py` extension and no package. There are no runtime
  dependencies.
- `cmdspecs.1.in` is the manpage source. The build copies it to
  `cmdspecs.1`, which is gitignored, so edit the `.in` file.

## Testing

- `./check` runs everything: unit tests
  (`python3 -m unittest discover -p '*tests.py'`), then
  `./cmdspecs echo-tests`, `./cmdspecs sort-tests`, and finally
  `fail-tests`, which is *expected* to fail.
- `cmdspecslib_tests.py` loads the `cmdspecs` script with `importlib`
  because it has no `.py` extension; there is no `cmdspecslib` module.
- A test dir contains `<name>.script` plus optional `.stdin`,
  `.stdout`, `.stderr`, `.exit`, `.setup` and `.teardown` files, along
  with dir-level `setup`, `setup_once`, `teardown` and `teardown_once`
  scripts. On a mismatch, cmdspecs writes `<name>.stdout-actual`/`-diff`
  (and the stderr equivalents) into the test dir. Don't commit these
  files.

## Documentation

- Wrap all documentation files (README, NEWS, CLAUDE.md, Markdown,
  etc.) at 72 columns. Code spans and commands that can't be broken
  may exceed it.

## Commits

- Subject format is `area: short summary` (e.g.
  `gitignore: add .egg-info and dist`), with the body wrapped at about
  72 columns.
