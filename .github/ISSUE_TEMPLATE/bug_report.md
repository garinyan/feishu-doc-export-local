---
name: Bug report
about: Report an export bug, missing content, broken images, or incorrect output
title: "[Bug] "
labels: bug
assignees: ""
---

## Summary

Describe the problem briefly.

## Page Type

- [ ] Direct Feishu/Lark page
- [ ] Wrapped Feishu page

## Environment

- OS:
- Chrome version:
- Node version:
- Python version:

## Reproduction

1. Start Chrome with CDP
2. Open the target page
3. Run:
   ```bash
   python3 scripts/run_feishu_local_export.py --url '...'
   ```
4. Observe the problem

## Expected

What should have happened?

## Actual

What happened instead?

## Completeness

- Did `content-completeness-audit.json` report missing text blocks?
- Did images fail to load?
- Did folded sections fail to restore?

## Notes

Add any useful output paths, logs, or screenshots.
