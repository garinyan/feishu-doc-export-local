# Checklist

## Before Export

- Confirm whether the doc is opened directly in Feishu or through a wrapper.
- Prefer the user’s already-loaded Chrome tab.
- If needed, connect through Chrome CDP on port `9222`.
- Confirm the correct inner Feishu frame is accessible.

## Preprocess The Live Page

- Run a full scroll pass inside the Feishu frame to trigger lazy loading.
- Try to expand likely folded or collapsed blocks before extraction.
- Retry failed image placeholders if they are visible.
- Do not start the main export until the page is in an export-ready state.

## Extraction

- Prefer the single entrypoint:
  - `python3 scripts/run_feishu_local_export.py --url '...'`
- Export full clientvar sequence.
- Do not rely on `document.json` alone.
- If a user points out folded sections, verify them against clientvar sequence, not just DOM siblings.
- Keep structured live HTML as a helper layer for images and special blocks.
- If image blocks are still missing after the first pass, run section-targeted image backfill before rebuilding the final HTML.

## Build

- Rebuild the local HTML from the full clientvar sequence.
- Copy or localize all image assets.
- Preserve special blocks where possible.
- Replace non-exportable interactive embeds with static cards instead of dropping them.
- Build explicit material cards for file/view/isv/whiteboard blocks instead of letting them disappear.
- Link local attachment assets from the final HTML when local preview or fallback files exist.

## Audit

- Run completeness audit.
- Require `missing_exact_text_blocks = 0` before claiming text completeness.
- Count local image references.
- Compare source image block count against local HTML image refs.
- Separate raw clientvar image-block counts from confirmed image assets.
- If a reported missing image id has no token, no dimensions, and no source metadata, treat it as an empty placeholder until proven otherwise.
- If images are still missing, group them by heading or section before retrying.
- Navigate to missing-image sections through the catalogue or headings and retry localization.
- For virtualized sections, scan inside the section placeholder after jumping to the nearest heading.
- Before declaring an image truly missing, compare current results against older successful export directories and reconcile any matching block ids.
- Use section screenshots only after direct live-image backfill has failed.
- Run a separate material audit for attachment units.
- Check `file`, `view`, `isv`, and `whiteboard` blocks explicitly.
- Confirm PPT, video, HTML attachments, whiteboards, and interactive cards are either localized or represented by metadata cards with links.

## Browser Verification

- Open the local HTML in Chrome.
- Confirm all images load.
- Confirm material cards are populated.
- Confirm local attachment links exist for exported assets.
- Confirm the user’s key sections exist and have body content.
- Confirm navigation is populated.
- If the user points to a specific sentence or paragraph, inspect the exact following local HTML blocks and verify the expected image sequence there.
- If screenshots were needed as fallback, confirm they are linked or bundled clearly.

## Delivery

Return:

- main HTML path
- images directory path
- completeness audit path

When describing status:

- say whether content is complete
- say whether images are localized
- say whether any image completeness still relies on section screenshot fallback
- say which differences are still only visual/runtime differences
