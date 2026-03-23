# Feishu Export Workflow

Use this repository when the task is to export a Feishu/Lark document, or a Feishu document embedded inside another page, into a local HTML package with maximum content completeness.

## Goals

- preserve text content with minimal loss
- localize image assets
- preserve attachment materials such as PPT, video, HTML files, whiteboards, and interactive cards
- rebuild a readable offline HTML package
- verify completeness against live runtime data

## Prefer This Workflow

1. Reuse the user's already-loaded Chrome tab.
2. Connect through Chrome CDP on port `9222`.
3. Access the embedded Feishu frame if the page is hosted inside another site.
4. Preprocess the live page before extraction:
   - full scroll to trigger lazy loading
   - expand likely folded controls
   - retry visible failed image placeholders
5. Export the full ordered runtime chunk sequence from `docxClientvarFetchManager`.
6. Export live images and structured block HTML.
7. Rebuild the final offline HTML package.
8. Run text completeness audit.
9. Audit image completeness separately.
10. Audit material completeness separately for file/view/isv/whiteboard blocks.
11. If images are still missing, navigate by heading or catalogue and retry localization.
12. For images hidden behind virtual section placeholders, scan inside the section after jumping to the nearest heading.
13. If some image-backed sections still fail, bundle section screenshots as a fallback.
14. Verify images, material cards, and key sections in Chrome.

## Avoid These Shortcuts

- raw DOM snapshots as the final artifact
- `MHTML` or print-to-PDF as the main export path
- using `document.json` alone when runtime chunk data is available
- assuming visible DOM already contains all folded content
- assuming text completeness automatically means image completeness

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

Export Markdown:

```bash
python3 scripts/run_feishu_local_export.py \
  --url 'https://d16rg8unadx.feishu.cn/docx/EXAMPLE' \
  --export-md
```

Export Markdown and import into Obsidian:

```bash
python3 scripts/run_feishu_local_export.py \
  --url 'https://d16rg8unadx.feishu.cn/docx/EXAMPLE' \
  --export-md \
  --import-obsidian
```

## Important Files

- `scripts/run_feishu_local_export.py`
- `scripts/export_html_package_to_markdown.py`
- `scripts/preprocess_feishu_live_page.mjs`
- `scripts/export_feishu_full_live.mjs`
- `scripts/export_feishu_live_structured_html.mjs`
- `scripts/export_full_clientvar_sequence.mjs`
- `scripts/export_missing_intro_sections_from_clientvars.mjs`
- `scripts/backfill_missing_images_from_live_sections.mjs`
- `scripts/build_full_live_v2.py`
- `scripts/audit_v2_content_completeness.py`
- `scripts/audit_image_completeness.py`
- `scripts/audit_material_completeness.py`
- `scripts/verify_v2_sections_in_chrome_cdp.mjs`

## Expected Output

- `exports/cdp-export/full-live-export-v2/document-v2.html`
- `exports/cdp-export/full-live-export-v2/images/`
- `exports/cdp-export/full-live-export-v2/content-completeness-audit.json`
- `exports/cdp-export/full-live-export-v2/image-completeness-final.json`
- `exports/cdp-export/full-live-export-v2/material-completeness-audit.json`
- `exports/cdp-export/full-live-export-v2/material-manifest.json`

## Success Criteria

- `missing_exact_text_blocks = 0`
- localized images load successfully
- source image blocks are reconciled against local image refs
- source material units are represented in local HTML and linked to local assets when available
- requested folded sections are present
- remaining differences are visual/runtime differences, not missing content
