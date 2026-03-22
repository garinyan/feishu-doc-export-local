import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const TARGET_URL =
  process.env.FEISHU_EXPORT_TARGET_URL ||
  "";
const OUT = path.resolve(
  "exports",
  "cdp-export",
  "v2-work",
  "missing-intro-sections.json",
);
const SECTION_TITLES = process.env.FEISHU_SECTION_TITLES
  ? JSON.parse(process.env.FEISHU_SECTION_TITLES)
  : [];
const STOP_TITLES = new Set(SECTION_TITLES);

async function findPage(browser) {
  for (const context of browser.contexts()) {
    for (const page of context.pages()) {
      if (page.url().includes(TARGET_URL)) return page;
    }
  }
  throw new Error("Target page not found");
}

const browser = await chromium.connectOverCDP("http://127.0.0.1:9222");
const page = await findPage(browser);
const frame = await (await page.locator("iframe").first().elementHandle())?.contentFrame();
if (!frame) throw new Error("Feishu frame not accessible");

const result = await frame.evaluate(({ sectionTitles, stopTitles }) => {
  const manager = window.docxClientvarFetchManager;

  const readText = (block) => {
    const value = block?.data?.text?.initialAttributedTexts?.text;
    if (!value) return "";
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.join("");
    if (typeof value === "object") return Object.values(value).join("");
    return "";
  };

  const orderedKeys = [manager._token, ...(manager._remainInfo?.cursorL || [])];
  const sequence = [];
  for (const key of orderedKeys) {
    const payload = manager._clientvarMap.get(key);
    const blockSequence = payload?.data?.block_sequence || [];
    const blockMap = payload?.data?.block_map || {};
    for (const id of blockSequence) {
      const block = blockMap[id];
      if (!block) continue;
      sequence.push({
        id,
        type: block?.data?.type || "",
        text: readText(block),
      });
    }
  }

  const sections = {};
  for (const title of sectionTitles) {
    const start = sequence.findIndex((item) => item.type === "heading2" && item.text === title);
    if (start < 0) continue;
    const items = [];
    for (let i = start + 1; i < sequence.length; i += 1) {
      const item = sequence[i];
      if (
        item.type === "heading2" &&
        (stopTitles.includes(item.text) || sectionTitles.includes(item.text))
      ) {
        break;
      }
      items.push(item);
    }
    sections[title] = items;
  }

  return {
    sectionTitles,
    sections,
  };
}, { sectionTitles: SECTION_TITLES, stopTitles: [...STOP_TITLES] });

await fs.mkdir(path.dirname(OUT), { recursive: true });
await fs.writeFile(OUT, JSON.stringify(result, null, 2), "utf8");
console.log(
  JSON.stringify(
    Object.fromEntries(
      Object.entries(result.sections).map(([title, items]) => [title, items.length]),
    ),
    null,
    2,
  ),
);
await browser.close();
