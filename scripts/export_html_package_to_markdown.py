from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import shutil
from pathlib import Path
from urllib.parse import quote
from urllib.parse import unquote

from bs4 import BeautifulSoup
from markdownify import markdownify as md


ZERO_WIDTH_RE = re.compile(r"[\u200b\ufeff]")


def slugify_filename(name: str) -> str:
    cleaned = ZERO_WIDTH_RE.sub("", name).strip()
    cleaned = cleaned.replace("/", "／").replace(":", "：")
    return cleaned or "document"


def normalize_line(line: str) -> str:
    return ZERO_WIDTH_RE.sub("", line).replace("\xa0", " ").rstrip()


def cleanup_markdown(text: str) -> str:
    lines = [normalize_line(line) for line in text.splitlines()]
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        next1 = lines[i + 1] if i + 1 < len(lines) else None
        next2 = lines[i + 2] if i + 2 < len(lines) else None
        if next1 == "" and next2 is not None and line.strip() and line.strip() == next2.strip():
            out.append(line)
            i += 3
            continue
        out.append(line)
        i += 1

    text = "\n".join(out)
    text = text.replace("](", "](")
    text = re.sub(r"(?<=\))(?=\[)", "\n", text)
    text = re.sub(r"(?<=\]\])(?=!\[\[)", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?m)^\|(?:\s*\|\s*)+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def detect_title(soup: BeautifulSoup, fallback: str) -> str:
    heading = soup.select_one("main.content h1")
    if heading and heading.get_text(strip=True):
        return slugify_filename(heading.get_text(" ", strip=True))
    if soup.title and soup.title.get_text(strip=True):
        return slugify_filename(soup.title.get_text(" ", strip=True))
    return slugify_filename(fallback)


def resolve_obsidian_vault(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    cfg = Path.home() / "Library/Application Support/obsidian/obsidian.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    vaults = data.get("vaults", {})
    for vault in vaults.values():
        if vault.get("open") and vault.get("path"):
            return Path(vault["path"]).expanduser().resolve()
    for vault in vaults.values():
        if vault.get("path"):
            return Path(vault["path"]).expanduser().resolve()
    raise SystemExit("Could not resolve an Obsidian vault. Pass --obsidian-vault explicitly.")


def convert_html_package(
    html_path: Path,
    output_md: Path | None = None,
) -> tuple[Path, Path, str]:
    html_path = html_path.resolve()
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")
    title = detect_title(soup, html_path.stem)
    main = soup.select_one("main.content") or soup.body or soup

    for selector in ("aside.sidebar", "script", "style"):
        for node in main.select(selector):
            node.decompose()

    md_path = output_md.resolve() if output_md else html_path.with_name(f"{title}.md")
    assets_dir = md_path.with_suffix(".assets")
    assets_dir.mkdir(parents=True, exist_ok=True)

    token_map: dict[str, str] = {}
    image_index = 1
    for img in main.select("img"):
        token = f"OBSIDIAN_IMAGE_TOKEN_{image_index:04d}"
        src = img.get("src", "").strip()
        if not src:
            img.replace_with(f"\n\n{token}\n\n")
            image_index += 1
            continue

        if src.startswith("data:image/"):
            header, encoded = src.split(",", 1)
            media_type = header.split(";")[0].split(":", 1)[1]
            ext = mimetypes.guess_extension(media_type) or ".png"
            asset_name = f"image-{image_index:03d}{ext}"
            asset_path = assets_dir / asset_name
            asset_path.write_bytes(base64.b64decode(encoded))
        else:
            source_path = (html_path.parent / unquote(src)).resolve()
            ext = source_path.suffix or ".png"
            asset_name = f"image-{image_index:03d}{ext}"
            asset_path = assets_dir / asset_name
            if source_path.exists():
                shutil.copy2(source_path, asset_path)
            else:
                asset_path.write_text("", encoding="utf-8")

        token_map[token] = f"![[{assets_dir.name}/{asset_name}]]"
        img.replace_with(f"\n\n{token}\n\n")
        image_index += 1

    markdown = md(
        str(main),
        heading_style="ATX",
        bullets="-",
        autolinks=True,
        escape_asterisks=False,
        escape_underscores=False,
    )
    for token, repl in token_map.items():
        markdown = markdown.replace(token, repl)
    markdown = cleanup_markdown(markdown)

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")
    return md_path, assets_dir, title


def import_into_obsidian(
    md_path: Path,
    assets_dir: Path,
    vault_path: Path,
    subdir: str,
) -> tuple[Path, Path]:
    subpath = Path(subdir)
    note_dest = (vault_path / subpath / md_path.name).resolve()
    assets_dest = note_dest.with_suffix(".assets")
    note_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(md_path, note_dest)
    if assets_dest.exists():
        shutil.rmtree(assets_dest)
    shutil.copytree(assets_dir, assets_dest)
    return note_dest, assets_dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert exported Feishu HTML package to Markdown and optionally import it into Obsidian.")
    parser.add_argument("--html", required=True, help="Path to the exported HTML package entry file.")
    parser.add_argument("--output-md", help="Optional output Markdown path. Defaults to title-based filename next to the HTML file.")
    parser.add_argument("--import-obsidian", action="store_true", help="Copy the generated Markdown package into an Obsidian vault.")
    parser.add_argument("--obsidian-vault", help="Explicit Obsidian vault path. Defaults to the currently open vault from obsidian.json.")
    parser.add_argument("--obsidian-subdir", default="Imports/Feishu", help="Relative folder inside the Obsidian vault.")
    args = parser.parse_args()

    html_path = Path(args.html)
    output_md = Path(args.output_md) if args.output_md else None
    md_path, assets_dir, title = convert_html_package(html_path, output_md)

    result: dict[str, str] = {
        "html": str(html_path.resolve()),
        "markdown": str(md_path),
        "assets_dir": str(assets_dir),
        "title": title,
    }

    if args.import_obsidian:
        vault_path = resolve_obsidian_vault(args.obsidian_vault)
        note_dest, assets_dest = import_into_obsidian(md_path, assets_dir, vault_path, args.obsidian_subdir)
        rel_note = note_dest.relative_to(vault_path).as_posix()
        obsidian_uri = f"obsidian://open?vault={quote(vault_path.name)}&file={quote(rel_note)}"
        result["obsidian_vault"] = str(vault_path)
        result["obsidian_note"] = str(note_dest)
        result["obsidian_assets_dir"] = str(assets_dest)
        result["obsidian_uri"] = obsidian_uri

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
