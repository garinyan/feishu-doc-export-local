---
name: feishu-doc-export-local
description: Export a Feishu/Lark doc or Feishu-wrapped doc to a local readable HTML package with maximum content completeness. Use when the user wants to save a Feishu doc opened in a browser, restore folded sections, localize images, or compare the local export against the live page. Prefer live Chrome CDP + Feishu runtime clientvar data over raw HTML snapshots, MHTML, or print-to-PDF.
---

# Feishu Doc Export Local

This file is the Codex/OpenAI adapter for the repository. The tool-agnostic workflow lives in `AGENTS.md`.

## Use This Skill When

- The user wants to export a Feishu/Lark doc to a local file.
- The doc is opened through a third-party embedded page.
- The user cares about content completeness more than exact original runtime styling.
- The user wants folded sections restored.
- The user wants a local HTML package with images and a completeness audit.

## Do Not Start Here

- Do not treat raw saved DOM HTML as the final export. It often renders blank offline.
- Do not rely on `MHTML` or `printToPDF` for Feishu docs embedded through third-party pages. Cross-origin iframe capture is unreliable.
- Do not assume visible DOM equals full content. Folded sections can be absent from DOM but present in runtime clientvar chunks.
- Do not use `document.json` as the only source if a live browser session is available. It can miss folded sections and later chunks.

## Preferred Workflow

Preferred single entrypoint:

- Use `scripts/run_feishu_local_export.py` from this skill when possible.
- Example:
  - `python3 scripts/run_feishu_local_export.py --url 'https://example.invalid/embedded-feishu-link' --section 'Heading One' --section 'Heading Two'`

1. Use the user’s live Chrome tab via CDP.
- Ask the user to start Chrome with `--remote-debugging-port=9222` only if needed.
- Prefer the already-loaded tab where images and gated content are visible.

2. Identify the accessible Feishu frame.
- If the page is a wrapper, access the embedded Feishu iframe.
- Confirm the document token and title from runtime data.

3. Preprocess the live page before extraction.
- Run a full scroll pass inside the Feishu frame to trigger lazy loading.
- Try generic expand actions for likely folded or collapsed blocks.
- Retry visible failed image placeholders before the main export.
- Treat "tab is open" and "page is export-ready" as different states.

4. Export the full runtime clientvar sequence.
- Use `scripts/export_full_clientvar_sequence.mjs`.
- This is the primary content baseline.
- It produces `exports/cdp-export/v2-work/full-clientvar-sequence.json`.

5. Restore known folded content.
- If specific folded sections are missing, use `scripts/export_missing_intro_sections_from_clientvars.mjs`.
- This is only a supplement. Once full clientvar sequence is available, prefer rebuilding from that full sequence.

6. Build the local HTML package.
- Use `scripts/build_full_live_v2.py`.
- This rebuilds `exports/cdp-export/full-live-export-v2/document-v2.html`.
- It uses:
  - full clientvar sequence as the text-order baseline
  - structured live HTML for special blocks and images
  - localized image assets from `exports/cdp-export/full-live-export/images`

7. Audit text completeness.
- Use `scripts/audit_v2_content_completeness.py`.
- This compares the local HTML text against the live clientvar sequence.
- The goal is `missing_exact_text_blocks = 0`.

8. Audit image completeness separately.
- Compare source image block count against local HTML image refs.
- Do not assume text completeness implies image completeness.
- If specific sections still miss images, drive the page by heading or catalogue and retry image export/localization.
- For images hidden behind virtualized section placeholders, jump to the nearest heading and scan within that section until the real image block renders.
- Only use section-level screenshots as a fallback after direct original-image backfill has failed.

9. Verify in Chrome.
- Use `scripts/verify_v2_sections_in_chrome_cdp.mjs`.
- Confirm:
  - all images load
  - target sections exist
  - restored folded content appears after the headings

## Output Standard

Deliver a local folder that contains:

- Main HTML:
  - `exports/cdp-export/full-live-export-v2/document-v2.html`
- Local images directory:
  - `exports/cdp-export/full-live-export-v2/images`
- Completeness audit:
  - `exports/cdp-export/full-live-export-v2/content-completeness-audit.json`

## Validation Rules

- Treat the live clientvar sequence as the source of truth for content completeness.
- Require `missing_exact_text_blocks = 0` before claiming text completeness.
- Require all local images to load before claiming image completeness.
- Reconcile source image blocks against rendered local image refs before claiming image completeness.
- Distinguish clearly:
  - `content completeness`
  - `image completeness`
  - `fallback screenshot completeness`
  - `visual/runtime parity`

## Remaining Acceptable Differences

These are acceptable only after content completeness is verified:

- Interactive embed behavior is replaced by static cards.
- Wrapped third-party widgets are represented by placeholders or metadata cards.
- Original Feishu runtime styling is simplified for offline readability.

## Failure Modes

- Using wrapper-page DOM only: misses folded sections and runtime-loaded chunks.
- Using `document.json` only: can miss later clientvar slices and folded text.
- Using MHTML/PDF from an embedded host page: often blank or incomplete because of iframe isolation.
- Treating special blocks as plain text too early: loses table/grid/quote grouping.
- Ignoring clientvar chunk order: can splice section content into the wrong heading.
- Assuming missing images can always be fetched directly from tokens: some images only become accessible after section-targeted rendering in the active session.

## Important Files

- Skill entrypoint:
  - `scripts/run_feishu_local_export.py`
- Preprocess live page:
  - `scripts/preprocess_feishu_live_page.mjs`
- Main exporter:
  - `scripts/export_full_clientvar_sequence.mjs`
- Folded-section supplement:
  - `scripts/export_missing_intro_sections_from_clientvars.mjs`
- Live image export:
  - `scripts/export_feishu_full_live.mjs`
- Missing-image backfill:
  - `scripts/backfill_missing_images_from_live_sections.mjs`
- Structured live HTML export:
  - `scripts/export_feishu_live_structured_html.mjs`
- Live scroll/image exporter uses env caps:
  - `FEISHU_EXPORT_MAX_ROUNDS`
  - `FEISHU_EXPORT_MAX_IDLE_ROUNDS`
- HTML builder:
  - `scripts/build_full_live_v2.py`
- Completeness audit:
  - `scripts/audit_v2_content_completeness.py`
- Image completeness audit:
  - `scripts/audit_image_completeness.py`
- Browser verification:
  - `scripts/verify_v2_sections_in_chrome_cdp.mjs`

## References

- Read [references/retrospective.md](references/retrospective.md) for the full postmortem and lessons learned.
- Read [references/checklist.md](references/checklist.md) before delivering a future export.
