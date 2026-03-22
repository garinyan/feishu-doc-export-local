# Feishu Export Workflow

Use this repository when the task is to export a Feishu/Lark document, or a Feishu document embedded inside another page, into a local HTML package with maximum content completeness.

## Goals

- preserve text content with minimal loss
- localize image assets
- rebuild a readable offline HTML package
- verify completeness against live runtime data

## Prefer This Workflow

1. Reuse the user's already-loaded Chrome tab.
2. Connect through Chrome CDP on port `9222`.
3. Access the embedded Feishu frame if the page is hosted inside another site.
4. Export the full ordered runtime chunk sequence from `docxClientvarFetchManager`.
5. Export live images and structured block HTML.
6. Rebuild the final offline HTML package.
7. Run completeness audit.
8. Verify images and key sections in Chrome.

## Avoid These Shortcuts

- raw DOM snapshots as the final artifact
- `MHTML` or print-to-PDF as the main export path
- using `document.json` alone when runtime chunk data is available
- assuming visible DOM already contains all folded content

## Main Entrypoint

```bash
python3 scripts/run_feishu_local_export.py \
  --url 'https://example.invalid/embedded-feishu-link'
```

Optional section verification:

```bash
python3 scripts/run_feishu_local_export.py \
  --url 'https://example.invalid/embedded-feishu-link' \
  --section 'Heading One' \
  --section 'Heading Two'
```

## Important Files

- `scripts/run_feishu_local_export.py`
- `scripts/export_feishu_full_live.mjs`
- `scripts/export_feishu_live_structured_html.mjs`
- `scripts/export_full_clientvar_sequence.mjs`
- `scripts/export_missing_intro_sections_from_clientvars.mjs`
- `scripts/build_full_live_v2.py`
- `scripts/audit_v2_content_completeness.py`
- `scripts/verify_v2_sections_in_chrome_cdp.mjs`

## Expected Output

- `exports/cdp-export/full-live-export-v2/document-v2.html`
- `exports/cdp-export/full-live-export-v2/images/`
- `exports/cdp-export/full-live-export-v2/content-completeness-audit.json`

## Success Criteria

- `missing_exact_text_blocks = 0`
- localized images load successfully
- requested folded sections are present
- remaining differences are visual/runtime differences, not missing content
