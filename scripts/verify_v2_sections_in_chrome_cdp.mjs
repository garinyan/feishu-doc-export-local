import { chromium } from 'playwright';
import path from 'node:path';

const FILE_URL =
  process.env.FEISHU_VERIFY_FILE_URL ||
  new URL(
    path.resolve('exports', 'cdp-export', 'full-live-export-v2', 'document-v2.html'),
    'file:',
  ).href;
const TARGETS = process.env.FEISHU_VERIFY_TARGETS
  ? JSON.parse(process.env.FEISHU_VERIFY_TARGETS)
  : [];

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const context = browser.contexts()[0] || (await browser.newContext());
const page = await context.newPage();
await page.goto(FILE_URL, { waitUntil: 'load' });
await page.waitForTimeout(1500);

const result = await page.evaluate((targets) => {
  const images = Array.from(document.images);
  const loadedImages = images.filter((img) => img.naturalWidth > 0).length;
  const sections = targets.map((title) => {
    const heading = Array.from(document.querySelectorAll('h2')).find((el) => el.textContent.trim() === title);
    const siblings = [];
    let node = heading?.nextElementSibling || null;
    while (node && siblings.length < 6) {
      if (node.tagName === 'H2') break;
      const text = (node.textContent || '').replace(/\s+/g, ' ').trim();
      siblings.push({ tag: node.tagName, text: text.slice(0, 180) });
      node = node.nextElementSibling;
    }
    return { title, found: Boolean(heading), siblings };
  });
  return {
    totalImages: images.length,
    loadedImages,
    navItems: document.querySelectorAll('.nav-item').length,
    sections,
  };
}, TARGETS);

console.log(JSON.stringify(result, null, 2));
await page.close();
await browser.close();
