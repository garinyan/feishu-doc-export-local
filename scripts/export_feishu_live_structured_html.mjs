import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const TARGET_URL =
  process.env.FEISHU_EXPORT_TARGET_URL || "";
const OUT_DIR = path.resolve("exports", "cdp-export", "structured-live-export");
const WORK_DIR = path.resolve("exports", "cdp-export", "v2-work");
const IMAGE_DIR = path.resolve("exports", "cdp-export", "full-live-export", "images");
const MAX_ROUNDS = Number(process.env.FEISHU_EXPORT_MAX_ROUNDS || 180);

async function findPage(browser) {
  for (const context of browser.contexts()) {
    for (const page of context.pages()) {
      if (page.url().includes(TARGET_URL)) return page;
    }
  }
  throw new Error("Target page not found");
}

await fs.mkdir(OUT_DIR, { recursive: true });
await fs.mkdir(WORK_DIR, { recursive: true });
const imageFiles = await fs.readdir(IMAGE_DIR);
const imageMap = new Map(
  imageFiles
    .filter((name) => /\.(png|jpg|webp|gif|bin)$/i.test(name))
    .map((name) => [name.replace(/\.[^.]+$/, ""), name]),
);

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
    scrollHeight: root?.scrollHeight || document.body.scrollHeight || 0,
    clientHeight: root?.clientHeight || window.innerHeight || 0,
    head: Array.from(document.head.querySelectorAll("meta, link[rel='stylesheet'], style"))
      .map((node) => node.outerHTML)
      .join("\n"),
  };
});

const blocks = new Map();
let y = 0;
let rounds = 0;

while (y < meta.scrollHeight + meta.clientHeight) {
  await frame.evaluate((scrollTop) => {
    const root = document.querySelector(".bear-web-x-container") || document.scrollingElement || document.body;
    if (root) root.scrollTop = scrollTop;
    window.scrollTo(0, scrollTop);
  }, y);
  await frame.waitForTimeout(700);

  const snapshot = await frame.evaluate(() => {
    return Array.from(document.querySelectorAll(".block[data-record-id]")).map((node) => ({
      id: node.getAttribute("data-record-id") || "",
      type: node.getAttribute("data-block-type") || "",
      html: node.outerHTML,
      textLength: (node.innerText || node.textContent || "").length,
    }));
  });

  for (const block of snapshot) {
    if (!block.id || !block.type) continue;
    const prev = blocks.get(block.id);
    if (!prev || block.textLength > prev.textLength) {
      blocks.set(block.id, block);
    }
  }

  y += Math.max(450, Math.floor(meta.clientHeight * 0.6));
  rounds += 1;
  if (rounds > MAX_ROUNDS) break;
}

const ordered = Array.from(blocks.values());
const rewritten = ordered.map((block) => {
  let html = block.html;
  if (block.type === "image" && imageMap.has(block.id)) {
    const fileName = imageMap.get(block.id);
    html = html.replace(/src="blob:[^"]+"/g, `src="../full-live-export/images/${fileName}"`);
  }
  return { ...block, html };
});

const body = rewritten.map((block) => block.html).join("\n");
const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>${meta.title}</title>
  ${meta.head}
  <style>
    body{margin:0;background:#fff}
    .gpf-biz-action-manager-forbidden-placeholder{display:none !important}
  </style>
</head>
<body>
  <div class="feishu-static-root">
    ${body}
  </div>
</body>
</html>`;

const summary = {
  title: meta.title,
  totalBlocks: ordered.length,
  imageBlocks: ordered.filter((b) => b.type === "image").length,
  tableBlocks: ordered.filter((b) => b.type === "table").length,
};
const frameUrl = frame.url();
let feishuCanonicalUrl = frameUrl;
try {
  const parsed = new URL(frameUrl);
  feishuCanonicalUrl = `${parsed.origin}${parsed.pathname}`;
} catch {}
const sourceContext = {
  wrapperUrl: page.url(),
  feishuFrameUrl: frameUrl,
  feishuCanonicalUrl,
  title: meta.title,
};

await fs.writeFile(path.join(OUT_DIR, "document-structured.html"), html, "utf8");
await fs.writeFile(path.join(OUT_DIR, "summary.json"), JSON.stringify(summary, null, 2), "utf8");
await fs.writeFile(path.join(WORK_DIR, "source-context.json"), JSON.stringify(sourceContext, null, 2), "utf8");
console.log(JSON.stringify(summary, null, 2));
await browser.close();
