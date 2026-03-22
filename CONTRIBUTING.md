# Contributing

Thanks for contributing.

## Scope

This project focuses on exporting Feishu docs, including docs embedded in third-party pages, into a local HTML package with:

- maximum content completeness
- localized image assets
- explicit completeness auditing

Changes that improve reliability, portability, readability, or verification are in scope.

## Before You Start

- Read [README.md](README.md)
- Read [SKILL.md](SKILL.md)
- Read [references/checklist.md](references/checklist.md)

## Development Setup

Install dependencies:

```bash
npm install
python3 -m pip install -r requirements.txt
```

If you need to run the full export flow locally, start Chrome with CDP enabled:

```bash
open -na "Google Chrome" --args \
  --remote-debugging-port=9222 \
  --user-data-dir="$PWD/.chrome-cdp"
```

## Coding Guidelines

- Keep scripts portable. Do not introduce machine-specific absolute paths.
- Keep workflow docs tool-agnostic unless a file is intentionally adapter-specific, such as `SKILL.md` or `CLAUDE.md`.
- Prefer content completeness over superficial visual parity.
- Keep generated outputs under `exports/`; do not commit them.
- Preserve the distinction between:
  - content completeness
  - visual/runtime parity

## Validation

Before opening a PR, at minimum:

```bash
python3 scripts/run_feishu_local_export.py --help
python3 -m py_compile scripts/run_feishu_local_export.py scripts/build_full_live_v2.py scripts/audit_v2_content_completeness.py
node --check scripts/export_feishu_full_live.mjs
node --check scripts/export_feishu_live_structured_html.mjs
node --check scripts/export_full_clientvar_sequence.mjs
node --check scripts/export_missing_intro_sections_from_clientvars.mjs
node --check scripts/verify_v2_sections_in_chrome_cdp.mjs
```

If your change affects the export pipeline, also describe:

- which page type you tested
- what changed in the output
- whether completeness audit still reaches zero missing text blocks

## Pull Requests

Include:

- what changed
- why it changed
- any known limitations
- test or validation notes

## Issues

For export bugs, include:

- target page type: Feishu direct or wrapped page
- whether Chrome CDP was enabled
- whether the page was fully loaded
- which output file was wrong
- what content was missing or incorrect
