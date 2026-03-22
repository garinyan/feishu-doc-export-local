import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const TARGET_URL =
  process.env.FEISHU_EXPORT_TARGET_URL || "";
const OUT_DIR = path.resolve("exports", "cdp-export", "full-live-export");
const MAX_ROUNDS = Number(process.env.FEISHU_EXPORT_MAX_ROUNDS || 180);
const MAX_IDLE_ROUNDS = Number(process.env.FEISHU_EXPORT_MAX_IDLE_ROUNDS || 10);

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function extForMime(mime) {
  if (mime === "image/png") return "png";
  if (mime === "image/jpeg") return "jpg";
  if (mime === "image/webp") return "webp";
  if (mime === "image/gif") return "gif";
  return "bin";
}

async function findPage(browser) {
  for (const context of browser.contexts()) {
    for (const page of context.pages()) {
      if (page.url().includes(TARGET_URL)) return page;
    }
  }
  throw new Error("Target page not found");
}

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
}

async function main() {
  await ensureDir(OUT_DIR);
  const imagesDir = path.join(OUT_DIR, "images");
  await ensureDir(imagesDir);

  const browser = await chromium.connectOverCDP("http://127.0.0.1:9222");
  const page = await findPage(browser);
  const iframe = page.locator("iframe").first();
  const handle = await iframe.elementHandle();
  const frame = await handle?.contentFrame();
  if (!frame) throw new Error("Feishu frame not accessible");

  const meta = await frame.evaluate(() => {
    const root = document.querySelector(".bear-web-x-container") || document.scrollingElement || document.body;
    return {
      title: document.title,
      scrollHeight: root?.scrollHeight || 0,
      clientHeight: root?.clientHeight || 0,
    };
  });

  const blocks = new Map();
  const images = new Map();
  let y = 0;
  let rounds = 0;
  let idleRounds = 0;
  let lastImageCount = 0;
  let lastBlockCount = 0;

  while (y < meta.scrollHeight + meta.clientHeight) {
    await frame.evaluate((scrollTop) => {
      const root = document.querySelector(".bear-web-x-container") || document.scrollingElement || document.body;
      if (root) root.scrollTop = scrollTop;
      window.scrollTo(0, scrollTop);
    }, y);
    await frame.waitForTimeout(900);

    const snapshot = await frame.evaluate(async () => {
      const nodes = Array.from(document.querySelectorAll(".block[data-record-id]"));
      const seen = [];
      for (const node of nodes) {
        const type = node.getAttribute("data-block-type") || "";
        const id = node.getAttribute("data-record-id") || "";
        if (!id) continue;
        const text = (node.innerText || node.textContent || "")
          .replace(/\u200b/g, "")
          .replace(/\s+/g, " ")
          .trim();

        const entry = { id, type, text };
        if (type === "image") {
          const img = node.querySelector("img.docx-image.success");
          if (img && img.currentSrc && img.complete && img.naturalWidth > 0) {
            const currentSrc = img.currentSrc;
            const file = await fetch(currentSrc).then((res) => res.blob());
            const buffer = await file.arrayBuffer();
            const bytes = Array.from(new Uint8Array(buffer));
            entry.image = {
              mime: file.type || "application/octet-stream",
              bytes,
              naturalWidth: img.naturalWidth,
              naturalHeight: img.naturalHeight,
            };
          }
        }
        seen.push(entry);
      }
      return seen;
    });

    for (const block of snapshot) {
      const existing = blocks.get(block.id);
      if (!existing) {
        blocks.set(block.id, { id: block.id, type: block.type, text: block.text || "" });
      } else if ((block.text || "").length > (existing.text || "").length) {
        existing.text = block.text || "";
      }

      if (block.type === "image" && block.image && !images.has(block.id)) {
        const ext = extForMime(block.image.mime);
        const fileName = `${block.id}.${ext}`;
        await fs.writeFile(path.join(imagesDir, fileName), Buffer.from(block.image.bytes));
        images.set(block.id, {
          id: block.id,
          fileName,
          mime: block.image.mime,
          naturalWidth: block.image.naturalWidth,
          naturalHeight: block.image.naturalHeight,
        });
      }
    }

    const changed = images.size !== lastImageCount || blocks.size !== lastBlockCount;
    if (!changed) idleRounds += 1;
    else idleRounds = 0;
    lastImageCount = images.size;
    lastBlockCount = blocks.size;

    y += Math.max(450, Math.floor(meta.clientHeight * 0.6));
    rounds += 1;
    if (idleRounds > MAX_IDLE_ROUNDS) break;
    if (rounds > MAX_ROUNDS) break;
  }

  const ordered = Array.from(blocks.values());
  const keepTypes = new Set([
    "heading1",
    "heading2",
    "heading3",
    "heading4",
    "heading5",
    "text",
    "callout",
    "quote_container",
    "image",
    "table",
    "bullet",
    "ordered",
    "page",
  ]);

  const filtered = [];
  for (const block of ordered) {
    if (!keepTypes.has(block.type)) continue;
    if (block.type === "image" && !images.has(block.id)) continue;
    const prev = filtered[filtered.length - 1];
    if (
      prev &&
      prev.text &&
      block.text &&
      prev.text === block.text &&
      (prev.type === block.type ||
        (["callout", "quote_container", "table"].includes(prev.type) && block.type === "text"))
    ) {
      continue;
    }
    filtered.push(block);
  }

  const htmlBlocks = [];
  for (const block of filtered) {
    const text = escapeHtml(block.text || "");
    if (block.type === "heading1") htmlBlocks.push(`<h1>${text}</h1>`);
    else if (block.type === "heading2") htmlBlocks.push(`<h2>${text}</h2>`);
    else if (block.type === "heading3") htmlBlocks.push(`<h3>${text}</h3>`);
    else if (block.type === "heading4") htmlBlocks.push(`<h4>${text}</h4>`);
    else if (block.type === "heading5") htmlBlocks.push(`<h5>${text}</h5>`);
    else if (block.type === "table") htmlBlocks.push(`<pre>${text}</pre>`);
    else if (block.type === "bullet") htmlBlocks.push(`<p>• ${text}</p>`);
    else if (block.type === "ordered") htmlBlocks.push(`<p>1. ${text}</p>`);
    else if (block.type === "callout") htmlBlocks.push(`<section class="callout"><p>${text}</p></section>`);
    else if (block.type === "quote_container") htmlBlocks.push(`<blockquote>${text}</blockquote>`);
    else if (block.type === "image") {
      const img = images.get(block.id);
      const caption = escapeHtml(block.text || "Feishu image");
      htmlBlocks.push(
        `<figure class="image-block"><img src="./images/${img.fileName}" alt="${caption}"/><figcaption>${caption}</figcaption></figure>`,
      );
    } else if (block.type !== "page" && text) {
      htmlBlocks.push(`<p>${text}</p>`);
    }
  }

  const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(meta.title)}</title>
  <style>
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:920px;margin:40px auto;padding:0 24px;line-height:1.7;color:#222}
    h1,h2,h3,h4,h5{margin-top:28px}
    .callout{background:#fff5eb;border-left:4px solid #f59e0b;padding:12px 16px;margin:18px 0}
    blockquote{border-left:4px solid #ccc;padding:10px 16px;background:#fafafa;margin:18px 0}
    .image-block{margin:20px 0}
    .image-block img{max-width:100%;height:auto;border:1px solid #ddd;background:#fafafa}
    figcaption{font-size:14px;color:#666;margin-top:8px}
    pre{white-space:pre-wrap;background:#fafafa;border:1px solid #ddd;padding:12px}
  </style>
</head>
<body>
  <h1>${escapeHtml(meta.title)}</h1>
  <p style="color:#666;font-size:14px">Recovered images from live page: ${images.size}</p>
  ${htmlBlocks.join("\n")}
</body>
</html>`;

  const manifest = {
    title: meta.title,
    blocksCollected: blocks.size,
    blocksExported: filtered.length,
    imagesRecovered: images.size,
    imageIds: Array.from(images.keys()),
  };

  await fs.writeFile(path.join(OUT_DIR, "document.json"), JSON.stringify(filtered, null, 2), "utf8");
  await fs.writeFile(path.join(OUT_DIR, "manifest.json"), JSON.stringify(manifest, null, 2), "utf8");
  await fs.writeFile(path.join(OUT_DIR, "document.html"), html, "utf8");
  console.log(JSON.stringify(manifest, null, 2));
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
