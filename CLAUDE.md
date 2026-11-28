# CLAUDE.md

<!--
SPDX-FileCopyrightText: 2026 Kalle Valo
SPDX-License-Identifier: GPL-3.0-or-later
-->

This file provides guidance to Claude Code (claude.ai/code) when
working with code in this repository.

## Layout

- `cmdspecs` is the whole program: a single executable Python 3
  script with no `.py` extension and no package. There are no runtime
  dependencies except `sh` to run the scripts, which on Windows comes
  from Git for Windows or MSYS2.
- `TODO.md` lists planned work and known shortcomings which were
  deliberately left alone. Check it before "fixing" one of them.
- `cmdspecs.1` is the manpage. Edit it directly; nothing generates
  it. View it with `man -l cmdspecs.1`. When you add or change a
  command line option, update its SYNOPSIS and OPTIONS sections.
  Whenever you change or add an exit status, update its EXIT STATUS
  section too.
- `pyproject.toml` holds all the packaging metadata, and there is no
  `setup.py`. cmdspecs is not published on PyPI and won't be, so don't
  add PyPI-only metadata (classifiers, keywords) or
  `pip install cmdspecs` instructions.
- The version is in both `VERSION` in `cmdspecs` and `version` in
  `pyproject.toml`, and CHANGELOG.md has a heading for it. A release
  bump must update all three; unit tests check that they match.
- Between releases the version is `<release>+git` (a PEP 440 local
  version label), so git builds are not mistaken for the release.
  CHANGELOG.md then has an `## [Unreleased]` heading above the last
  release.

## Release process

The user pushes to `main` and tags. Claude prepares the commits,
creates the GitHub release with `gh` (after asking) and reminds the
user of the other steps. Version numbers look like `0.34.0` and tags
like `v0.34.0`.

1. Make the release commit, subject `cmdspecs vX.Y.Z`:
   - Replace the `+git` version with `X.Y.Z` in `VERSION` in
     `cmdspecs` and `version` in `pyproject.toml`.
   - In CHANGELOG.md, rename `[Unreleased]` to
     `[X.Y.Z] - YYYY-MM-DD`. Do not leave an empty `[Unreleased]`
     heading in the release commit.
   - Fix the link references at the bottom: remove `[Unreleased]` and
     add `[X.Y.Z]: https://github.com/kvalo/cmdspecs/compare/vPREV...vX.Y.Z`.
   - Run `./check` and `./lint`.
2. Push the release commit to `staging` and wait for CI with
   `gh run watch`. If the commit changes after that, e.g. by amending,
   the tag must point at the new hash.
3. The user signs and tags the exact commit that passed CI, e.g.
   `git tag -s vX.Y.Z <hash> -m "cmdspecs vX.Y.Z"`, and pushes the
   commit and the tag to `main`. Never push to `main` or create the
   tag; remind the user instead.
4. Once the tag is on origin, ask, then create the GitHub release:
   save the `[X.Y.Z]` section of CHANGELOG.md, without its heading,
   to a scratchpad file, and save the `cmdspecs` script of the tag
   (`git show vX.Y.Z:cmdspecs`, executable) to a scratchpad file named
   `cmdspecs`, so that the asset is the same as the tagged commit. Run
   `gh release create vX.Y.Z --verify-tag --title "cmdspecs vX.Y.Z"
   --notes-file <file> <scratchpad>/cmdspecs`. `--verify-tag` makes it
   fail when the tag has not been pushed. The script is attached as a
   release asset so that users can download it directly.
5. Once `origin/main` and the tag are on the release commit, make the
   post-release commit, subject `cmdspecs: mark version as
   X.Y.Z+git`: set the version to `X.Y.Z+git` in both files, add
   `## [Unreleased]` back above `[X.Y.Z]` in CHANGELOG.md and its
   `[Unreleased]: .../compare/vX.Y.Z...HEAD` link reference. Run
   `./check` and `./lint`, then push to `staging`.

## Testing

- Tests use pytest (`pip install .[test]`). `./check` runs
  `python3 -m pytest` and passes its arguments through, e.g.
  `./check -k echo` or `./check -x`.
- `./coverage [./check options]` runs the tests with pytest-cov
  (`pip install .[coverage]`) and prints the lines of `cmdspecs`
  which no test ran, also counting the subprocess runs of
  `tests/test_specs.py`. Its coverage config is a temp file, as
  `cmdspecs` has no `.py` extension for `--cov` to name. The Windows
  code shows as missed on other systems. There is no minimum
  coverage and CI does not run it.
- `tests/test_cmdspecs.py` has the unit tests. `tests/test_specs.py`
  runs the `cmdspecs` script as a subprocess on each spec dir in
  `tests/specs/`. It copies each dir to `tmp_path` first so the repo
  stays clean. `tests/specs/fail` is *expected* to fail, and the test
  asserts that cmdspecs reports it.
- `./lint` runs flake8 (config in `.flake8`), shellcheck, mdl
  (markdownlint, config in `.mdlrc`) on the Markdown files, groff
  to check the manpage for warnings, yamllint (config in
  `.yamllint`) on the GitHub workflows if it is installed, and
  `reuse lint` if it is installed. It is separate from `./check`
  because those tools are optional. `pip install .[lint]` gives
  flake8, shellcheck and reuse; mdl is a Ruby gem. When you add a new
  script, add it to the file list in `./lint`, because `cmdspecs` and
  the test scripts have no file extensions to glob on. The same goes
  for a new Markdown file.
- `MANIFEST.in` names the top-level files of the sdist (`check`,
  `lint`, Markdown files, lint configs). Add a new one there too.
- The tests load the `cmdspecs` script with `importlib` because it
  has no `.py` extension.
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
- CI also runs the tests on Python 3.10 to the newest release, and
  on Linux arm64, macOS, Windows, FreeBSD and OpenBSD, where there is
  no way to try them locally.
  Don't use syntax newer than Python 3.10. `.gitattributes` checks
  out all text files with LF, also on Windows, so that the specs
  match. Keep new tests portable: run cmdspecs with
  `sys.executable`, write the files of a test dir with
  `newline='\n'`, and expect the paths in cmdspecs output with
  `native()` from `tests/test_specs.py`. Skip a test which can't work
  on Windows with `skipif(sys.platform == 'win32')` and a reason.

## Documentation

- CHANGELOG.md follows [Keep a Changelog](https://keepachangelog.com)
  and is only for major user visible changes. Don't add entries for
  small tweaks, internal changes or test changes. Group entries under
  Added, Changed, Deprecated, Removed, Fixed and Security.
- Wrap all documentation files (README, CHANGELOG.md, CLAUDE.md,
  Markdown, etc.) at 72 columns. Code spans and commands that can't
  be broken may exceed it.

## Licensing

- cmdspecs is GPL-3.0-or-later and follows the
  [REUSE](https://reuse.software) specification. The license text is
  in `LICENSES/GPL-3.0-or-later.txt`.
- Every new file needs `SPDX-FileCopyrightText` and
  `SPDX-License-Identifier` tags in a header comment. In Markdown
  files, put them in an HTML comment after the first heading. The
  configuration dotfiles (`.flake8`, `.gitignore`, etc.) have no
  header, to keep them free of boilerplate, and the `.stdin`,
  `.stdout`, `.stderr` and `.exit` files of the specs can't have one,
  so they are annotated in `REUSE.toml` instead. Globs cover the spec
  files, so a new spec needs no change there, but a new dotfile does.
  All scripts, also the spec scripts (`.script`, `.setup`, `setup`,
  etc.), need the header after the shebang.

## Commits

- Subject format is `area: short summary` (e.g.
  `gitignore: add .egg-info and dist`), with the body wrapped at about
  72 columns.
