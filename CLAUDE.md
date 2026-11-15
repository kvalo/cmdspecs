# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when
working with code in this repository.

## Layout

- `cmdspecs` is the whole program: a single executable Python 3
  script with no `.py` extension and no package. There are no runtime
  dependencies.
- `cmdspecs.1` is the manpage. Edit it directly; nothing generates
  it. View it with `man -l cmdspecs.1`. When you add or change a
  command line option, update its SYNOPSIS and OPTIONS sections.
- `pyproject.toml` holds all the packaging metadata, and there is no
  `setup.py`. cmdspecs is not published on PyPI and won't be, so don't
  add PyPI-only metadata (classifiers, keywords) or
  `pip install cmdspecs` instructions.

## Testing

- Tests use pytest (`pip install .[test]`). `./check` runs
  `python3 -m pytest` and passes its arguments through, e.g.
  `./check -k echo` or `./check -x`.
- `tests/test_cmdspecs.py` has the unit tests. `tests/test_specs.py`
  runs the `cmdspecs` script as a subprocess on each spec dir in
  `tests/specs/`. It copies each dir to `tmp_path` first so the repo
  stays clean. `tests/specs/fail` is *expected* to fail, and the test
  asserts that cmdspecs reports it.
- `./lint` runs flake8 (config in `.flake8`), shellcheck, and groff
  to check the manpage for warnings. It is separate from `./check`
  because those tools are optional. When you add a new script, add it
  to the file list in `./lint`, because `cmdspecs` and the test
  scripts have no file extensions to glob on.
- `tests/test_cmdspecs.py` loads the `cmdspecs` script with
  `importlib` because it has no `.py` extension.
- `test_manpage_documents_all_options` fails if an option from
  `CommandTester.make_parser()` is missing from the manpage's OPTIONS
  section.
- A test dir contains `<name>.script` plus optional `.stdin`,
  `.stdout`, `.stderr`, `.exit`, `.setup` and `.teardown` files, along
  with dir-level `setup`, `setup_once`, `teardown` and `teardown_once`
  scripts. On a mismatch, cmdspecs writes `<name>.stdout-actual`/`-diff`
  (and the stderr equivalents) into the test dir. Don't commit these
  files. You can run a spec by hand, e.g.
  `./cmdspecs tests/specs/echo`.

## Documentation

- Wrap all documentation files (README, NEWS, CLAUDE.md, Markdown,
  etc.) at 72 columns. Code spans and commands that can't be broken
  may exceed it.

## Commits

- Subject format is `area: short summary` (e.g.
  `gitignore: add .egg-info and dist`), with the body wrapped at about
  72 columns.
