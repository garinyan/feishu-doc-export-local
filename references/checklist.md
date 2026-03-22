# Checklist

## Before Export

- Confirm whether the doc is opened directly in Feishu or through a wrapper.
- Prefer the user’s already-loaded Chrome tab.
- If needed, connect through Chrome CDP on port `9222`.

## Extraction

- Prefer the single entrypoint:
  - `python3 scripts/run_feishu_local_export.py --url '...'`
- Export full clientvar sequence.
- Do not rely on `document.json` alone.
- If a user points out folded sections, verify them against clientvar sequence, not just DOM siblings.

## Build

- Rebuild the local HTML from the full clientvar sequence.
- Copy or localize all image assets.
- Preserve special blocks where possible.
- Replace non-exportable interactive embeds with static cards instead of dropping them.

## Audit

- Run completeness audit.
- Require `missing_exact_text_blocks = 0` before claiming text completeness.
- Count local image references.

## Browser Verification

- Open the local HTML in Chrome.
- Confirm all images load.
- Confirm the user’s key sections exist and have body content.
- Confirm navigation is populated.

## Delivery

Return:

- main HTML path
- images directory path
- completeness audit path

When describing status:

- say whether content is complete
- say whether images are localized
- say which differences are still only visual/runtime differences
