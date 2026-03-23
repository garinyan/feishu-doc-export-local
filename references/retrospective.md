# Retrospective

## Goal

Build a local version of a Feishu doc with:

- maximum content completeness
- localized images
- readable offline HTML
- explicit verification against the live page

The document used during experimentation was opened through a third-party page that embedded a Feishu doc in a restricted container.

## What Failed

### 1. Raw DOM snapshot HTML

Problem:

- The saved rendered HTML depended on Feishu runtime CSS and JS.
- Opening it offline produced large blank areas.

Lesson:

- Raw live DOM is useful as evidence, not as the final offline artifact.

### 2. Wrapper-page MHTML and print-to-PDF

Problem:

- The source page was a wrapper with a cross-origin Feishu iframe.
- `MHTML` and browser print paths often captured the wrong layer or blank output.

Lesson:

- For Feishu docs embedded through third-party pages, treat `MHTML` and `printToPDF` as unreliable for primary export.

### 3. Plain copy/paste to Notion

Problem:

- Text mostly survived.
- Images pointed at Feishu stream endpoints and later failed with `401/403`.

Lesson:

- Notion import is downstream; first solve durable local export and image localization.

### 4. Using `document.json` as the main baseline

Problem:

- It missed folded sections and later chunked content.
- The seven requested sections appeared as headings only.

Lesson:

- `document.json` is not a sufficient truth source when live runtime data is available.

### 5. Blind DOM expansion for folded headings

Problem:

- Clicking headings did not yield reliable sibling DOM content.
- Placeholder nodes existed, but real content was virtualized or chunk-loaded elsewhere.

Lesson:

- Folded content must be recovered from runtime data, not inferred only from nearby DOM siblings.

## What Worked

### 1. CDP connection to the user’s live Chrome tab

Why it worked:

- Reused the real logged-in, fully loaded tab.
- Avoided the broken new-session path.

### 2. Preprocessing the live page before extraction

Why it mattered:

- Some folded content stayed hidden until the page received real user-like interaction.
- Some images did not render until their sections were scrolled into view.
- A first-pass export from a "loaded but not fully walked" page under-counted images.

What proved useful:

- Run a full scroll pass inside the Feishu frame to trigger lazy loading.
- Try generic expand actions before export:
  - folded controls
  - collapsed toggles
  - short-text affordances such as "expand" / "show more"
- Retry failed image placeholders before starting the main export.

Lesson:

- Treat "page is open" and "page is export-ready" as different states.
- A preprocessing pass should happen before content extraction.

### 3. Inspecting Feishu runtime globals

Key findings:

- `window.DATA.clientVars.data.block_map` contained only the initial subset.
- `window.docxClientvarFetchManager` held the real chunked clientvar data.

Critical fields:

- `_token`
- `_remainInfo.cursorL`
- `_clientvarMap`
- per-chunk `data.block_sequence`
- per-chunk `data.block_map`

### 4. Reconstructing document order from clientvar chunks

Why it mattered:

- Chunk insertion order in the map was not always document order.
- The correct order came from:
  - main token first
  - then `_remainInfo.cursorL`

That produced a stable full sequence of all chunked blocks and text content.

### 5. Building the local HTML from full clientvar sequence

Why it worked:

- Text order came from the full runtime sequence.
- Structured live HTML still supplied useful markup for:
  - images
  - some special blocks
  - some grid/table wrappers

### 6. Image completeness required its own pass

What happened:

- Text completeness reached zero-loss before image completeness did.
- Some image blocks were present in the clientvar sequence but absent from the current DOM snapshot.
- Specific folded sections still missed images after the first full export.

Key lesson:

- Do not assume `missing_exact_text_blocks = 0` means the export is fully complete.
- Image completeness must be checked separately against source image blocks.

### 7. Section-targeted navigation could unlock missing images

What happened:

- Some missing images became accessible only after navigating to their section from the catalogue or table of contents.
- Knowing the image token alone was not always enough.
- Direct stream fetches could still return `401` until the target section was rendered in the active session.

Lesson:

- When image counts do not match, navigate by heading or catalogue entry to force section rendering, then retry image export.

### 8. Auditing completeness separately from styling

Why it worked:

- It forced a precise definition of success:
  - content completeness
  - not visual sameness

The final text audit reached:

- `missing_exact_text_blocks = 0`

Image-related follow-up still remained necessary:

- compare source image block count with local HTML image refs
- re-render missing-image sections
- retry localization

### 9. Section screenshots are a valid completeness fallback

Why they matter:

- Some stubborn image-backed sections may still fail native localization after repeated retries.
- In those cases, section screenshots preserve information even if the original image node cannot be exported cleanly.

Lesson:

- If exact image extraction is still incomplete, add section-level screenshot supplements instead of silently dropping that information.

### 10. Raw image-block counts can overstate real losses

What happened:

- A later audit still reported missing images even when the user could visually confirm the page looked complete.
- The remaining ids were `image` blocks in the clientvar sequence with no token, no dimensions, no mime, and no usable source metadata.

Lesson:

- Do not treat every `image` block in the clientvar sequence as a confirmed missing asset.
- Some are only empty placeholder records.
- Image completeness must distinguish:
  - raw image blocks
  - confirmed image assets
  - rendered local image refs

### 11. Earlier successful exports can repair a later clean rerun

What happened:

- A fresh clean export still missed several step-by-step screenshots in one section.
- Those exact block ids had already been localized in an earlier export directory.
- Reconciling assets by block id restored the section immediately.

Lesson:

- Before declaring a true image loss, compare current results against earlier successful export directories.
- Block-id based asset reconciliation is a valid recovery path, not a hack.

### 12. User-reported local gaps beat aggregate metrics

What happened:

- Aggregate counts looked acceptable, but the user pointed to one exact sentence whose following screenshots were visibly incomplete.
- Inspecting the neighboring local HTML blocks around that sentence revealed the gap immediately.

Lesson:

- When the user points to a specific sentence, paragraph, or heading, verify that exact neighborhood in the final local HTML.
- Do not rely only on document-level counts once the user has identified a concrete visible discrepancy.

## Final Proven Strategy

1. Use live Chrome CDP on the already-loaded tab.
2. Access the Feishu iframe.
3. Preprocess the page:
   - full scroll for lazy loading
   - expand likely folded controls
   - retry failed image placeholders
4. Export the complete clientvar sequence from `docxClientvarFetchManager`.
5. Use that sequence as the content baseline.
6. Use structured HTML only as a helper for special blocks and images.
7. Localize images into a sibling `images/` folder.
8. Rebuild a readable offline HTML package.
9. Audit text completeness against the full clientvar sequence.
10. Audit image completeness separately.
11. Distinguish raw image-block counts from confirmed image assets.
12. Reconcile earlier successful localized assets by block id when a rerun misses previously recovered images.
13. For missing images, navigate by heading/catalogue and retry localization.
14. If the user points to a specific visible gap, inspect that exact neighborhood in the final local HTML.
15. If needed, preserve section-level screenshots as a fallback layer.
16. Verify image loading and restored sections in Chrome.

## Known Boundary

Even after full content recovery, these may remain non-identical to the live page:

- embedded widgets
- interactive runtime controls
- exact Feishu editor chrome
- exact animation/stateful behavior

That is acceptable if:

- text completeness is zero-loss
- images are localized
- important embeds are represented by static cards instead of disappearing

## Reusable Heuristics

- Prefer runtime chunk data over visible DOM.
- Prefer ordered clientvar chunks over arbitrary object iteration.
- Preprocess first: expand and scroll before extraction.
- Separate content audit from layout review.
- Separate text completeness from image completeness.
- Separate raw image-block counts from confirmed image assets.
- If images are missing, drive the page by heading or catalogue before retrying.
- If a user points to one exact line or paragraph, inspect the local HTML sequence around that point directly.
- Reconcile prior successful export assets by block id before declaring an image truly missing.
- Use screenshot supplements instead of dropping unresolved sections.
- When a block has no text but visible semantic value, represent it explicitly instead of dropping it.
