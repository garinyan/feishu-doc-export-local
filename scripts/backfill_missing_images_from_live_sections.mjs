import fs from "node:fs/promises";
import path from "node:path";

const TARGET_URL = process.env.FEISHU_EXPORT_TARGET_URL || "";
const ROOT = path.resolve("exports", "cdp-export");
const FULL_DIR = path.join(ROOT, "full-live-export");
const FULL_IMAGES_DIR = path.join(FULL_DIR, "images");
const V2_DIR = path.join(ROOT, "full-live-export-v2");
const V2_IMAGES_DIR = path.join(V2_DIR, "images");
const SEQUENCE_PATH = path.join(ROOT, "v2-work", "full-clientvar-sequence.json");
const REPORT_PATH = path.join(V2_DIR, "image-backfill-report.json");

if (!TARGET_URL) throw new Error("FEISHU_EXPORT_TARGET_URL is required");

function extForMime(mime) {
  if (mime === "image/png") return "png";
  if (mime === "image/jpeg") return "jpg";
  if (mime === "image/webp") return "webp";
  if (mime === "image/gif") return "gif";
  return "bin";
}

function headingLevel(blockType) {
  const match = /^heading([1-6])$/.exec(blockType || "");
  return match ? Number(match[1]) : null;
}

async function fetchTargets() {
  const res = await fetch("http://127.0.0.1:9222/json/list");
  if (!res.ok) throw new Error(`Failed to query CDP targets: ${res.status}`);
  return res.json();
}

function chooseTargets(targets) {
  const pageCandidates = targets.filter(
    (target) =>
      target.type === "page" &&
      typeof target.url === "string" &&
      target.url.includes(TARGET_URL) &&
      target.webSocketDebuggerUrl,
  );
  if (!pageCandidates.length) throw new Error("Target page not found in CDP target list");

  const scored = pageCandidates
    .map((page) => {
      const iframeCandidates = targets.filter(
        (target) =>
          target.parentId === page.id &&
          target.type === "iframe" &&
          typeof target.url === "string" &&
          target.url.includes("feishu.cn/docx/") &&
          target.webSocketDebuggerUrl,
      );
      return { page, iframeCandidates };
    })
    .filter((item) => item.iframeCandidates.length);

  if (!scored.length) throw new Error("No Feishu iframe target found under the target page");

  const chosen = scored[scored.length - 1];
  return { page: chosen.page, iframe: chosen.iframeCandidates[0] };
}

function evaluateInTarget(wsUrl, expression) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const timer = setTimeout(() => {
      try {
        ws.close();
      } catch {}
      reject(new Error("Timed out waiting for CDP Runtime.evaluate"));
    }, 60000);

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          id: 1,
          method: "Runtime.evaluate",
          params: {
            expression,
            awaitPromise: true,
            returnByValue: true,
          },
        }),
      );
    };

    ws.onerror = (event) => {
      clearTimeout(timer);
      reject(new Error(`WebSocket error: ${String(event?.message || event)}`));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.id !== 1) return;
      clearTimeout(timer);
      ws.close();
      if (data.result?.exceptionDetails) {
        const desc =
          data.result.exceptionDetails.exception?.description ||
          data.result.exceptionDetails.text ||
          "Runtime.evaluate failed";
        reject(new Error(desc));
        return;
      }
      resolve(data.result?.result?.value);
    };
  });
}

async function readSequence() {
  const raw = JSON.parse(await fs.readFile(SEQUENCE_PATH, "utf8"));
  return raw.items || [];
}

async function listImageStems(dir) {
  try {
    const entries = await fs.readdir(dir);
    return new Set(entries.map((name) => path.parse(name).name));
  } catch {
    return new Set();
  }
}

function buildMissingTasks(blocks, existingImageStems) {
  const stack = [];
  const tasks = [];

  for (const block of blocks) {
    const level = headingLevel(block.type);
    if (level) {
      while (stack.length && stack[stack.length - 1].level >= level) stack.pop();
      stack.push({ id: block.id, text: block.text || "", level });
      continue;
    }
    if (block.type !== "image") continue;
    if (existingImageStems.has(block.id)) continue;
    tasks.push({
      id: block.id,
      anchors: [...stack].reverse().map((item) => item.id),
      headings: [...stack].map((item) => item.text || ""),
    });
  }

  return tasks;
}

function makeExpression(tasks) {
  return `(async () => {
    const tasks = ${JSON.stringify(tasks)};
    function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
    function getRoot() {
      return document.querySelector('.bear-web-x-container') || document.scrollingElement || document.body;
    }
    function findImageNode(id) {
      return document.querySelector('.block[data-record-id="' + id + '"] img');
    }
    async function jumpToAnchor(anchorId) {
      const toc = document.querySelector('.catalogue__list-item[data-id="' + anchorId + '"] a, a[href$="#' + anchorId + '"]');
      if (toc) {
        toc.click();
        await sleep(1000);
        return;
      }
      const block = document.querySelector('.block[data-record-id="' + anchorId + '"]');
      if (block) {
        block.scrollIntoView({ block: 'start' });
        await sleep(1000);
      }
    }
    async function scanVirtualContainer(anchorId, imageId) {
      const root = getRoot();
      const block = document.querySelector('.block[data-record-id="' + anchorId + '"]');
      if (!block) return null;
      const placeholder = block.nextElementSibling && block.nextElementSibling.classList.contains('bear-virtual-renderUnit-placeholder')
        ? block.nextElementSibling
        : null;
      const base = placeholder || block;
      const baseRect = base.getBoundingClientRect();
      const rootIsWindow =
        root === document.body || root === document.documentElement || root === document.scrollingElement;
      const height = Math.max(baseRect.height, root.clientHeight || window.innerHeight || 900);
      for (let i = 0; i < 100; i++) {
        const img = findImageNode(imageId);
        if (img && img.currentSrc && img.complete && img.naturalWidth > 0) return img;
        const offset = Math.min(Math.max(0, height - 200), i * 180);
        const y = Math.max(0, (root.scrollTop || window.scrollY || 0) + baseRect.top + offset);
        if (rootIsWindow) window.scrollTo(0, y);
        else root.scrollTop = y;
        await sleep(350);
      }
      return findImageNode(imageId);
    }
    async function readImageData(img) {
      const res = await fetch(img.currentSrc || img.src);
      const blob = await res.blob();
      const bytes = new Uint8Array(await blob.arrayBuffer());
      let binary = '';
      const chunkSize = 0x8000;
      for (let i = 0; i < bytes.length; i += chunkSize) {
        binary += String.fromCharCode.apply(null, Array.from(bytes.slice(i, i + chunkSize)));
      }
      return {
        ok: true,
        mime: blob.type || 'application/octet-stream',
        width: img.naturalWidth,
        height: img.naturalHeight,
        base64: btoa(binary),
      };
    }
    const out = [];
    for (const task of tasks) {
      let result = null;
      for (const anchorId of task.anchors) {
        await jumpToAnchor(anchorId);
        let img = findImageNode(task.id);
        if (!img || !(img.currentSrc || img.src) || img.naturalWidth <= 0) {
          img = await scanVirtualContainer(anchorId, task.id);
        }
        if (img && (img.currentSrc || img.src) && img.naturalWidth > 0) {
          result = { id: task.id, anchorId, ...(await readImageData(img)) };
          break;
        }
      }
      if (!result) {
        out.push({
          id: task.id,
          ok: false,
          headings: task.headings,
          anchorsTried: task.anchors,
          error: 'image not rendered in live iframe after section-targeted retry',
        });
      } else {
        out.push({ ...result, headings: task.headings, anchorsTried: task.anchors });
      }
    }
    return out;
  })()`;
}

async function main() {
  await fs.mkdir(FULL_IMAGES_DIR, { recursive: true });
  await fs.mkdir(V2_IMAGES_DIR, { recursive: true });

  const blocks = await readSequence();
  const existing = await listImageStems(FULL_IMAGES_DIR);
  const tasks = buildMissingTasks(blocks, existing);

  if (!tasks.length) {
    const report = {
      sourceImageBlocks: blocks.filter((block) => block.type === "image").length,
      missingBeforeBackfill: 0,
      recovered: [],
      unrecovered: [],
    };
    await fs.writeFile(REPORT_PATH, JSON.stringify(report, null, 2), "utf8");
    console.log(JSON.stringify(report, null, 2));
    return;
  }

  const targets = await fetchTargets();
  const { page, iframe } = chooseTargets(targets);
  const payload = await evaluateInTarget(iframe.webSocketDebuggerUrl, makeExpression(tasks));

  const recovered = [];
  const unrecovered = [];
  for (const item of payload || []) {
    if (item.ok && item.base64) {
      const ext = extForMime(item.mime);
      const fileName = `${item.id}.${ext}`;
      const buffer = Buffer.from(item.base64, "base64");
      await fs.writeFile(path.join(FULL_IMAGES_DIR, fileName), buffer);
      await fs.writeFile(path.join(V2_IMAGES_DIR, fileName), buffer);
      recovered.push({
        id: item.id,
        fileName,
        width: item.width,
        height: item.height,
        anchorId: item.anchorId || null,
        headings: item.headings || [],
      });
    } else {
      unrecovered.push(item);
    }
  }

  const report = {
    pageUrl: page.url,
    iframeUrl: iframe.url,
    sourceImageBlocks: blocks.filter((block) => block.type === "image").length,
    missingBeforeBackfill: tasks.length,
    recovered,
    unrecovered,
  };

  await fs.writeFile(REPORT_PATH, JSON.stringify(report, null, 2), "utf8");
  console.log(JSON.stringify(report, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
