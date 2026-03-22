import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const TARGET_URL =
  process.env.FEISHU_EXPORT_TARGET_URL ||
  '';
const OUT = path.resolve('exports','cdp-export','v2-work','full-clientvar-sequence.json');

async function findPage(browser) {
  for (const context of browser.contexts()) {
    for (const page of context.pages()) {
      if (page.url().includes(TARGET_URL)) return page;
    }
  }
  throw new Error('Target page not found');
}

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const page = await findPage(browser);
const frame = await (await page.locator('iframe').first().elementHandle())?.contentFrame();
if (!frame) throw new Error('Feishu frame not accessible');

const result = await frame.evaluate(() => {
  const manager = window.docxClientvarFetchManager;
  const orderedKeys = [manager._token, ...(manager._remainInfo?.cursorL || [])];
  const seen = new Set();
  const readText = (block) => {
    const value = block?.data?.text?.initialAttributedTexts?.text;
    if (!value) return '';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.join('');
    if (typeof value === 'object') return Object.values(value).join('');
    return '';
  };
  const items = [];
  for (const key of orderedKeys) {
    const payload = manager._clientvarMap.get(key);
    const seq = payload?.data?.block_sequence || [];
    const bm = payload?.data?.block_map || {};
    for (const id of seq) {
      if (seen.has(id)) continue;
      seen.add(id);
      const block = bm[id];
      if (!block) continue;
      items.push({
        id,
        type: block?.data?.type || '',
        text: readText(block),
        parent_id: block?.data?.parent_id || '',
        children: block?.data?.children || [],
        folded: Boolean(block?.data?.folded),
        sourceKey: key,
      });
    }
  }
  return { orderedKeys, count: items.length, items };
});

await fs.mkdir(path.dirname(OUT), { recursive: true });
await fs.writeFile(OUT, JSON.stringify(result, null, 2), 'utf8');
console.log(JSON.stringify({orderedKeys: result.orderedKeys.length, count: result.count}, null, 2));
await browser.close();
