from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parents[1] / "exports" / "cdp-export"
FULL_DIR = ROOT / "full-live-export"
STRUCTURED_DIR = ROOT / "structured-live-export"
WORK_DIR = ROOT / "v2-work"
OUT_DIR = ROOT / "full-live-export-v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path):
    return json.loads(path.read_text())


def esc(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


full_sequence_path = WORK_DIR / "full-clientvar-sequence.json"
if full_sequence_path.exists():
    blocks = load_json(full_sequence_path).get("items", [])
    use_full_sequence = True
else:
    blocks = load_json(FULL_DIR / "document.json")
    use_full_sequence = False
structured_html = (STRUCTURED_DIR / "document-structured.html").read_text()
structured = BeautifulSoup(structured_html, "lxml")
images_dir = FULL_DIR / "images"
image_files = {p.stem: p.name for p in images_dir.iterdir() if p.is_file()}
missing_sections_path = WORK_DIR / "missing-intro-sections.json"
missing_sections = (
    {}
    if use_full_sequence
    else load_json(missing_sections_path).get("sections", {})
    if missing_sections_path.exists()
    else {}
)


def is_block(tag: Tag) -> bool:
    return isinstance(tag, Tag) and tag.name and "block" in (tag.get("class") or []) and tag.get("data-record-id")


special_types = {"table", "grid", "callout", "quote_container"}
special_blocks: dict[str, dict] = {}
image_blocks: dict[str, str] = {}
grid_insertions: dict[str, dict] = {}
embed_blocks: dict[str, str] = {}
embed_skip_children: dict[str, list[str]] = {}

for tag in structured.find_all(attrs={"data-record-id": True, "data-block-type": True}):
    if not is_block(tag):
        continue
    block_id = tag.get("data-record-id")
    block_type = tag.get("data-block-type")
    if block_type in special_types:
        cloned = BeautifulSoup(str(tag), "lxml")
        node = cloned.find(attrs={"data-record-id": block_id})
        if not node:
            continue
        for bad in node.select(".gpf-biz-action-manager-forbidden-placeholder, .docx-block-zero-space, .grid-column-percent"):
            bad.decompose()
        for img in node.select("img"):
            img.attrs.pop("crossorigin", None)
            img.attrs.pop("srcset", None)
        for nested in node.select('.block[data-block-type="image"][data-record-id]'):
            nested_id = nested.get("data-record-id")
            img = nested.find("img")
            if nested_id in image_files and img:
                img["src"] = f"./images/{image_files[nested_id]}"
        html = str(node)
        special_blocks[block_id] = {"type": block_type, "html": html}
        if block_type == "grid":
            child_nodes = [
                (child.get("data-record-id"), child.get("data-block-type"))
                for child in node.select('.block[data-record-id]')
                if child.get("data-record-id") != block_id
            ]
            child_ids = [rid for rid, _ in child_nodes]
            content_ids = [rid for rid, typ in child_nodes if typ != "grid_column"]
            anchor_id = content_ids[0] if content_ids else (child_ids[0] if child_ids else None)
            if anchor_id:
                grid_insertions[anchor_id] = {"grid_id": block_id, "child_ids": child_ids}
    elif block_type in {"view", "file", "isv"}:
        texts = [
            t.strip()
            for t in tag.stripped_strings
            if t.strip() and t.strip() not in {"\u200b", "Unable to print"}
        ]
        if block_type in {"view", "file"}:
            filename = next((t for t in reversed(texts) if "." in t and len(t) < 120), "")
            if not filename:
                filename = next((t for t in reversed(texts) if len(t) < 120 and not any(ch in t for ch in "/:")), "")
            duration = next((t for t in reversed(texts) if ":" in t and len(t) <= 8), "")
            label = "视频附件" if filename.endswith(".mp4") else "文件附件"
            parts = [f"<strong>{label}</strong>"]
            if filename:
                parts.append(f"<div class=\"embed-file-name\">{esc(filename)}</div>")
            if duration:
                parts.append(f"<div class=\"embed-file-meta\">时长 {esc(duration)}</div>")
            embed_blocks[block_id] = f"<section class=\"embed-card embed-{block_type}\">{''.join(parts)}</section>"
            if block_type == "view" and tag.get("data-record-id"):
                child_file = tag.find(attrs={"data-block-type": "file", "data-record-id": True})
                if child_file:
                    embed_skip_children[block_id] = [child_file.get("data-record-id")]
        else:
            embed_blocks[block_id] = "<section class=\"embed-card embed-isv\"><strong>嵌入式互动卡片</strong><div class=\"embed-file-meta\">原网页为第三方交互组件，本地版保留占位。</div></section>"
    elif block_type == "image":
        cloned = BeautifulSoup(str(tag), "lxml")
        node = cloned.find(attrs={"data-record-id": block_id})
        if not node:
            continue
        for bad in node.select(".gpf-biz-action-manager-forbidden-placeholder, .docx-block-zero-space"):
            bad.decompose()
        img = node.find("img")
        if img and block_id in image_files:
            img.attrs.pop("crossorigin", None)
            img.attrs.pop("srcset", None)
            img["src"] = f"./images/{image_files[block_id]}"
        image_blocks[block_id] = str(node)


html_parts = []
skipped_ids: set[str] = set()
diffs = []
nav_items = []

def render_inline_item(block: dict) -> str:
    text = block.get("text", "")
    block_type = block.get("type")
    if block_type == "bullet":
        return f"<li>{esc(text)}</li>"
    if block_type == "ordered":
        return f"<li>{esc(text)}</li>"
    if block_type == "code":
        return f'<pre class="code-block"><code>{esc(text)}</code></pre>'
    return f"<p>{esc(text)}</p>"


def collect_container_items(start_idx: int, source_blocks: list[dict]) -> list[dict]:
    collected: list[dict] = []
    saw_content = False
    for probe in source_blocks[start_idx + 1 :]:
        probe_type = probe.get("type")
        probe_text = (probe.get("text") or "").strip()
        if probe_type not in {"text", "bullet", "ordered", "code"}:
            break
        if not probe_text:
            if saw_content:
                break
            skipped_ids.add(probe["id"])
            continue
        saw_content = True
        collected.append(probe)
        skipped_ids.add(probe["id"])
    return collected


def render_block(block: dict, idx: int, source_blocks: list[dict], allow_supplement: bool = False) -> None:
    block_id = block["id"]
    block_type = block["type"]
    text = block.get("text", "")

    if block_id in skipped_ids:
        return

    if block_id in grid_insertions:
        grid = grid_insertions[block_id]
        html_parts.append(grid["grid_id"])
        html_parts[-1] = special_blocks[grid["grid_id"]]["html"]
        skipped_ids.update(grid["child_ids"])
        return

    if block_id in embed_blocks:
        html_parts.append(embed_blocks[block_id])
        skipped_ids.update(embed_skip_children.get(block_id, []))
        return

    if block_type in {"callout", "quote_container"} and not text and block_id not in special_blocks:
        container_items = collect_container_items(idx, source_blocks)
        if container_items:
            rendered = "".join(render_inline_item(item) for item in container_items)
            if block_type == "callout":
                html_parts.append(f'<section class="callout generated-callout">{rendered}</section>')
            else:
                html_parts.append(f'<blockquote class="generated-quote">{rendered}</blockquote>')
            return

    if block_id in special_blocks:
        html_parts.append(special_blocks[block_id]["html"])
        return

    if block_type == "image":
        caption = ""
        next_block = source_blocks[idx + 1] if idx + 1 < len(source_blocks) else None
        if next_block and next_block["type"] == "text":
            next_text = (next_block.get("text") or "").strip()
            if next_text and len(next_text) <= 120:
                caption = next_text
                skipped_ids.add(next_block["id"])

        if block_id in image_blocks:
            img_html = image_blocks[block_id]
            if caption:
                wrapped = f'<figure class="image-figure">{img_html}<figcaption>{esc(caption)}</figcaption></figure>'
                html_parts.append(wrapped)
            else:
                html_parts.append(img_html)
        elif block_id in image_files:
            alt = esc(caption or "Feishu image")
            html_parts.append(
                f'<figure class="image-figure"><img class="fallback-image" src="./images/{image_files[block_id]}" alt="{alt}"/>'
                + (f"<figcaption>{esc(caption)}</figcaption>" if caption else "")
                + "</figure>"
            )
        else:
            diffs.append({"id": block_id, "reason": "missing_image_asset"})
        return

    if block_type == "heading1":
        html_parts.append(f'<h1 id="{block_id}">{esc(text)}</h1>')
        nav_items.append((1, block_id, text))
    elif block_type == "heading2":
        html_parts.append(f'<h2 id="{block_id}">{esc(text)}</h2>')
        nav_items.append((2, block_id, text))
        if allow_supplement:
            for extra_idx, extra_block in enumerate(missing_sections.get(text, [])):
                render_block(extra_block, extra_idx, missing_sections[text], allow_supplement=False)
    elif block_type == "heading3":
        html_parts.append(f'<h3 id="{block_id}">{esc(text)}</h3>')
        nav_items.append((3, block_id, text))
    elif block_type == "heading4":
        html_parts.append(f'<h4 id="{block_id}">{esc(text)}</h4>')
        nav_items.append((4, block_id, text))
    elif block_type == "heading5":
        html_parts.append(f'<h5 id="{block_id}">{esc(text)}</h5>')
        nav_items.append((5, block_id, text))
    elif block_type == "bullet":
        html_parts.append(f"<p class=\"bullet\">{esc(text)}</p>")
    elif block_type == "ordered":
        html_parts.append(f"<p class=\"ordered\">{esc(text)}</p>")
    elif block_type == "code":
        html_parts.append(f"<pre class=\"code-block\"><code>{esc(text)}</code></pre>")
    elif block_type == "callout":
        html_parts.append(f'<section class="callout"><p>{esc(text)}</p></section>')
        diffs.append({"id": block_id, "reason": "fallback_callout"})
    elif block_type == "quote_container":
        html_parts.append(f"<blockquote>{esc(text)}</blockquote>")
        diffs.append({"id": block_id, "reason": "fallback_quote"})
    elif block_type == "table":
        html_parts.append(f"<pre>{esc(text)}</pre>")
        diffs.append({"id": block_id, "reason": "fallback_table"})
    elif block_type != "page" and text:
        html_parts.append(f"<p>{esc(text)}</p>")


for idx, block in enumerate(blocks):
    render_block(block, idx, blocks, allow_supplement=True)


nav_html = "".join(
    f'<a class="nav-item level-{level}" href="#{block_id}">{esc(text)}</a>'
    for level, block_id, text in nav_items
    if text
)

html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>AI编程产品出海（含OpenClaw）实战手册 - Feishu Docs</title>
  <style>
    :root{{--bg:#f7f3ea;--panel:#fffdf9;--line:#e7dfd1;--muted:#6e675b;--text:#23201b;--accent:#a16207}}
    *{{box-sizing:border-box}}
    html{{scroll-behavior:smooth}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.72;color:var(--text);background:linear-gradient(180deg,#faf8f4 0%,#f3eee3 100%);margin:0}}
    .page{{display:flex;align-items:flex-start;gap:28px;max-width:1460px;margin:0 auto;padding:24px}}
    .sidebar{{position:sticky;top:0;max-height:100vh;overflow:auto;width:300px;padding:16px 0 24px;border-right:1px solid var(--line)}}
    .sidebar h2{{font-size:13px;margin:0 0 12px;padding:0 18px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}
    .nav-item{{display:block;padding:6px 18px;color:#494236;text-decoration:none;font-size:13px;line-height:1.45;border-left:2px solid transparent}}
    .nav-item:hover{{background:#f2ede3;border-left-color:#d9c4a0}}
    .nav-item.level-2{{padding-left:28px}}
    .nav-item.level-3{{padding-left:40px}}
    .nav-item.level-4{{padding-left:52px}}
    .nav-item.level-5{{padding-left:64px}}
    .content{{max-width:940px;min-width:0;flex:1;background:var(--panel);border:1px solid var(--line);border-radius:22px;padding:28px 38px;box-shadow:0 10px 30px rgba(54,42,18,.05)}}
    h1,h2,h3,h4,h5{{margin-top:30px;line-height:1.3;scroll-margin-top:24px}}
    h1{{font-size:34px;letter-spacing:-.02em}}
    h2{{font-size:24px;padding-top:12px;border-top:1px solid #f1eadf}}
    h3{{font-size:20px}}
    h4{{font-size:17px;color:#3e382f}}
    h5{{font-size:15px;color:#595246}}
    p{{margin:12px 0;word-break:break-word}}
    .bullet,.ordered{{padding-left:4px}}
    ul.doc-list,ol.doc-list{{margin:12px 0 12px 22px;padding-left:18px}}
    ul.doc-list li,ol.doc-list li{{margin:6px 0}}
    .code-block{{white-space:pre-wrap;background:#171717;color:#f7f7f7;border:1px solid #2f2f2f;padding:14px 16px;overflow:auto;border-radius:14px;font-size:13px;line-height:1.65}}
    .code-block code{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}}
    .callout{{background:#fff4e5;border-left:4px solid #f59e0b;padding:12px 16px;margin:18px 0;border-radius:12px}}
    blockquote{{border-left:4px solid #c7c7c7;padding:10px 16px;background:#f7f7f7;margin:18px 0;border-radius:0 12px 12px 0}}
    .embed-card{{margin:18px 0;padding:14px 16px;border:1px solid #d8d0c2;border-radius:14px;background:#f8f5ee}}
    .embed-file-name{{margin-top:6px;font-weight:600}}
    .embed-file-meta{{margin-top:4px;color:var(--muted);font-size:13px}}
    .image-figure,.block.docx-image-block{{margin:24px 0}}
    .fallback-image,.docx-image{{display:block;max-width:100%;height:auto;border:1px solid #ddd;background:#fafafa;border-radius:14px}}
    .block.docx-image-block .image-block-width-wrapper,
    .block.docx-image-block .image-block-container,
    .block.docx-image-block .resizable-wrapper{{max-width:100% !important;width:100% !important}}
    .block.docx-image-block .img,
    .block.docx-image-block .img.crop-container{{display:flex;justify-content:center;overflow:hidden;border-radius:14px}}
    figcaption{{font-size:14px;color:var(--muted);margin-top:10px;padding:0 2px}}
    pre{{white-space:pre-wrap;background:#fafafa;border:1px solid #ddd;padding:12px;overflow:auto;border-radius:12px}}
    table{{border-collapse:collapse;max-width:100%;width:max-content;min-width:100%}}
    td,th{{border:1px solid #d9d9d9;padding:10px 12px;vertical-align:top;background:#fff}}
    tr:first-child td, tr:first-child th{{font-weight:600;background:#f7efe0}}
    .docx-table-block,.block[data-block-type="table"]{{overflow:auto;margin:22px 0;padding-bottom:4px}}
    .scrollable-wrapper,.scrollable-container,.scrollable-item,.content-scroller,.table-scrollable-content{{width:auto !important;left:auto !important;max-width:100% !important;overflow:visible !important}}
    .docx-grid-block,.block[data-block-type="grid"]{{display:flex;flex-wrap:wrap;gap:18px;align-items:flex-start;margin:22px 0}}
    .docx-grid_column-block,.block[data-block-type="grid_column"]{{min-width:280px;flex:1 1 320px;width:auto !important}}
    .docx-callout-block,.docx-quote_container-block{{margin:20px 0}}
    .docx-callout-block .callout-block{{border-radius:14px;padding:14px 16px !important}}
    .docx-quote_container-block .quote-container-block{{background:#f7f7f7;border-left:4px solid #c8c8c8;border-radius:0 14px 14px 0;padding:10px 14px}}
    .gpf-biz-action-manager-forbidden-placeholder,.docx-block-zero-space,.grid-column-percent{{display:none !important}}
    @media (max-width: 1100px) {{
      .page{{display:block;padding:16px}}
      .sidebar{{position:relative;width:auto;max-height:none;border-right:0;border-bottom:1px solid var(--line);margin-bottom:16px;padding-bottom:16px}}
      .content{{padding:22px 18px}}
    }}
  </style>
</head>
<body>
  <div class="page">
    <aside class="sidebar">
      <h2>目录</h2>
      {nav_html}
    </aside>
    <main class="content">
      <h1>AI编程产品出海（含OpenClaw）实战手册</h1>
      {''.join(html_parts)}
    </main>
  </div>
</body>
</html>
"""

soup = BeautifulSoup(html, "lxml")

for p in soup.select("p.bullet"):
    text = p.get_text(" ", strip=True)
    while text.startswith("• "):
        text = text[2:]
    p.string = text

for p in soup.select("p.ordered"):
    text = p.get_text(" ", strip=True)
    text = text.removeprefix("1. ").strip()
    p.string = text

for selector, list_tag in [("p.bullet", "ul"), ("p.ordered", "ol")]:
    while True:
        first = soup.select_one(selector)
        if not first:
            break
        new_list = soup.new_tag(list_tag, attrs={"class": "doc-list"})
        first.insert_before(new_list)
        cursor = first
        while cursor and cursor.name == "p" and selector.split(".")[1] in (cursor.get("class") or []):
            next_cursor = cursor.find_next_sibling()
            li = soup.new_tag("li")
            li.string = cursor.get_text(" ", strip=True)
            new_list.append(li)
            cursor.extract()
            cursor = next_cursor

for special in soup.select(".docx-callout-block, .docx-quote_container-block"):
    nxt = special.find_next_sibling()
    if nxt and nxt.name == "p":
        special_text = special.get_text(" ", strip=True)
        next_text = nxt.get_text(" ", strip=True)
        if special_text and next_text and next_text in special_text:
            nxt.decompose()

for img_block in soup.select(".block.docx-image-block"):
    wrapper = img_block.find(class_="image-block")
    img = img_block.find("img")
    if not img:
        continue
    align = "center"
    if wrapper:
        classes = wrapper.get("class") or []
        for c in classes:
            if c.startswith("align-"):
                align = c.replace("align-", "")
                break
    figure = soup.new_tag("figure", attrs={"class": f"image-figure align-{align}"})
    img.extract()
    img["class"] = ["docx-image"]
    for attr in ["width", "height", "style", "crossorigin"]:
        img.attrs.pop(attr, None)
    figure.append(img)
    caption = img_block.find_next_sibling("figcaption")
    if caption:
        caption.extract()
        figure.append(caption)
    img_block.replace_with(figure)

html = str(soup)

(OUT_DIR / "document-v2.html").write_text(html)
(OUT_DIR / "diffs.json").write_text(json.dumps(diffs, ensure_ascii=False, indent=2))
(OUT_DIR / "summary.json").write_text(
    json.dumps(
        {
            "sourceBlocks": len(blocks),
            "specialBlocks": len(special_blocks),
            "gridInsertions": len(grid_insertions),
            "imageBlocks": len(image_blocks),
            "diffCount": len(diffs),
        },
        ensure_ascii=False,
        indent=2,
    )
)

link_path = OUT_DIR / "images"
if link_path.exists() or link_path.is_symlink():
    if link_path.is_symlink() or link_path.is_file():
        link_path.unlink()
    else:
        shutil.rmtree(link_path)
shutil.copytree(images_dir, link_path)

print(OUT_DIR / "document-v2.html")
