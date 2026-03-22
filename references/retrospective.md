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

### 2. Inspecting Feishu runtime globals

Key findings:

- `window.DATA.clientVars.data.block_map` contained only the initial subset.
- `window.docxClientvarFetchManager` held the real chunked clientvar data.

Critical fields:

- `_token`
- `_remainInfo.cursorL`
- `_clientvarMap`
- per-chunk `data.block_sequence`
- per-chunk `data.block_map`

### 3. Reconstructing document order from clientvar chunks

Why it mattered:

- Chunk insertion order in the map was not always document order.
- The correct order came from:
  - main token first
  - then `_remainInfo.cursorL`

That produced a stable full sequence of all chunked blocks and text content.

### 4. Building the local HTML from full clientvar sequence

Why it worked:

- Text order came from the full runtime sequence.
- Structured live HTML still supplied useful markup for:
  - images
  - some special blocks
  - some grid/table wrappers

### 5. Auditing completeness separately from styling

Why it worked:

- It forced a precise definition of success:
  - content completeness
  - not visual sameness

The final text audit reached:

- `missing_exact_text_blocks = 0`

## Final Proven Strategy

1. Use live Chrome CDP on the already-loaded tab.
2. Access the Feishu iframe.
3. Export the complete clientvar sequence from `docxClientvarFetchManager`.
4. Use that sequence as the content baseline.
5. Use structured HTML only as a helper for special blocks and images.
6. Localize images into a sibling `images/` folder.
7. Rebuild a readable offline HTML package.
8. Audit completeness against the full clientvar sequence.
9. Verify image loading and restored sections in Chrome.

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
- Separate content audit from layout review.
- When a block has no text but visible semantic value, represent it explicitly instead of dropping it.
