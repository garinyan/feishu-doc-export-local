import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const TARGET_URL = process.env.FEISHU_EXPORT_TARGET_URL || "";
const OUT = path.resolve("exports", "cdp-export", "v2-work", "preprocess-summary.json");
const MAX_SCROLL_ROUNDS = Number(process.env.FEISHU_PREPROCESS_MAX_SCROLL_ROUNDS || 240);
const SCROLL_PAUSE_MS = Number(process.env.FEISHU_PREPROCESS_SCROLL_PAUSE_MS || 700);

async function findPage(browser) {
  for (const context of browser.contexts()) {
    for (const page of context.pages()) {
      if (page.url().includes(TARGET_URL)) return page;
    }
  }
  throw new Error("Target page not found");
}

async function getFeishuFrame(page) {
  const iframe = page.locator("iframe").first();
  const handle = await iframe.elementHandle();
  const frame = await handle?.contentFrame();
  if (!frame) throw new Error("Feishu frame not accessible");
  return frame;
}

async function main() {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:9222");
  const page = await findPage(browser);
  const frame = await getFeishuFrame(page);

  const initial = await frame.evaluate(() => {
    const root = document.querySelector(".bear-web-x-container") || document.scrollingElement || document.body;
    return {
      title: document.title,
      scrollHeight: root?.scrollHeight || 0,
      clientHeight: root?.clientHeight || 0,
    };
  });

  const clickExpanders = async () =>
    frame.evaluate(() => {
      const selectors = [
        '[aria-expanded="false"]',
        ".collapsed",
        ".folded",
        ".fold-icon",
        ".docx-folded-block",
        ".catalog-fold-icon",
      ];
      let count = 0;
      for (const selector of selectors) {
        for (const node of document.querySelectorAll(selector)) {
          if (!(node instanceof HTMLElement)) continue;
          try {
            node.click();
            count += 1;
          } catch {}
        }
      }
      const textMatchers = ["展开", "显示更多", "更多", "继续阅读", "show more", "expand"];
      for (const node of document.querySelectorAll("button, span, div, a")) {
        if (!(node instanceof HTMLElement)) continue;
        const text = (node.innerText || node.textContent || "").trim().toLowerCase();
        if (!text) continue;
        if (textMatchers.some((value) => text === value || text.includes(value))) {
          try {
            node.click();
            count += 1;
          } catch {}
        }
      }
      return count;
    });

  const retryFailedImages = async () =>
    frame.evaluate(() => {
      let count = 0;
      const textMatchers = ["点击重试", "重新加载", "重试", "retry"];
      for (const node of document.querySelectorAll("button, span, div")) {
        if (!(node instanceof HTMLElement)) continue;
        const text = (node.innerText || node.textContent || "").trim().toLowerCase();
        if (!text) continue;
        if (textMatchers.some((value) => text === value || text.includes(value))) {
          try {
            node.click();
            count += 1;
          } catch {}
        }
      }
      return count;
    });

  const firstExpand = await clickExpanders();
  await frame.waitForTimeout(500);

  let y = 0;
  let rounds = 0;
  let stableRounds = 0;
  let lastHeight = initial.scrollHeight;

  while (rounds < MAX_SCROLL_ROUNDS) {
    await frame.evaluate((scrollTop) => {
      const root = document.querySelector(".bear-web-x-container") || document.scrollingElement || document.body;
      if (root) root.scrollTop = scrollTop;
      window.scrollTo(0, scrollTop);
    }, y);
    await frame.waitForTimeout(SCROLL_PAUSE_MS);

    const meta = await frame.evaluate(() => {
      const root = document.querySelector(".bear-web-x-container") || document.scrollingElement || document.body;
      return {
        scrollHeight: root?.scrollHeight || 0,
        clientHeight: root?.clientHeight || 0,
      };
    });

    if (meta.scrollHeight === lastHeight) stableRounds += 1;
    else stableRounds = 0;
    lastHeight = meta.scrollHeight;

    y += Math.max(500, Math.floor(meta.clientHeight * 0.75));
    rounds += 1;
    if (y >= meta.scrollHeight + meta.clientHeight && stableRounds >= 2) break;
  }

  const secondExpand = await clickExpanders();
  await frame.waitForTimeout(500);
  const failedRetryCount = await retryFailedImages();
  await frame.waitForTimeout(800);
  await frame.evaluate(() => {
    const root = document.querySelector(".bear-web-x-container") || document.scrollingElement || document.body;
    if (root) root.scrollTop = 0;
    window.scrollTo(0, 0);
  });

  const finalMeta = await frame.evaluate(() => {
    const root = document.querySelector(".bear-web-x-container") || document.scrollingElement || document.body;
    return {
      title: document.title,
      scrollHeight: root?.scrollHeight || 0,
      clientHeight: root?.clientHeight || 0,
    };
  });

  const summary = {
    title: finalMeta.title,
    firstExpand,
    secondExpand,
    failedRetryCount,
    scrollRounds: rounds,
    scrollHeight: finalMeta.scrollHeight,
    clientHeight: finalMeta.clientHeight,
  };

  await fs.mkdir(path.dirname(OUT), { recursive: true });
  await fs.writeFile(OUT, JSON.stringify(summary, null, 2), "utf8");
  console.log(JSON.stringify(summary, null, 2));
  await browser.close();
}

await main();
