from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1] / "exports" / "cdp-export"
WORK_DIR = ROOT / "v2-work"
OUT_DIR = ROOT / "full-live-export-v2"
FULL_SEQUENCE = WORK_DIR / "full-clientvar-sequence.json"
MANIFEST = OUT_DIR / "material-manifest.json"
HTML_PATH = OUT_DIR / "document-v2.html"
OUT_PATH = OUT_DIR / "material-completeness-audit.json"


def load_json(path: Path):
    return json.loads(path.read_text())


def compute_heading_paths(items: list[dict]) -> dict[str, str]:
    paths: dict[str, str] = {}
    stack: list[str] = []
    for item in items:
        block_id = item.get("id") or ""
        block_type = item.get("type") or ""
        text = (item.get("text") or "").strip()
        if block_type.startswith("heading") and text:
            try:
                level = int(block_type[-1])
            except ValueError:
                level = 1
            stack = stack[: max(level - 1, 0)]
            stack.append(text)
        if block_id:
            paths[block_id] = " > ".join(stack)
    return paths


def build_source_units(items: list[dict]) -> list[dict]:
    by_id = {item.get("id"): item for item in items if item.get("id")}
    heading_paths = compute_heading_paths(items)
    units: list[dict] = []
    seen_file_children: set[str] = set()

    for item in items:
        block_id = item.get("id") or ""
        block_type = item.get("type") or ""
        if block_type == "view":
            child_id = next((cid for cid in item.get("children") or [] if cid in by_id), "")
            child = by_id.get(child_id, {})
            seen_file_children.add(child_id)
            units.append(
                {
                    "id": block_id,
                    "type": "view",
                    "heading_path": heading_paths.get(block_id, ""),
                    "child_file_id": child_id,
                    "file_name": child.get("file_name") or "",
                    "mimeType": child.get("mimeType") or "",
                    "token": child.get("token") or "",
                }
            )
        elif block_type in {"isv", "whiteboard"}:
            units.append(
                {
                    "id": block_id,
                    "type": block_type,
                    "heading_path": heading_paths.get(block_id, ""),
                    "token": item.get("token") or "",
                }
            )

    for item in items:
        block_id = item.get("id") or ""
        if (item.get("type") or "") == "file" and block_id not in seen_file_children:
            units.append(
                {
                    "id": block_id,
                    "type": "file",
                    "heading_path": heading_paths.get(block_id, ""),
                    "file_name": item.get("file_name") or "",
                    "mimeType": item.get("mimeType") or "",
                    "token": item.get("token") or "",
                }
            )

    return units


items = load_json(FULL_SEQUENCE).get("items", [])
manifest = {entry.get("id"): entry for entry in load_json(MANIFEST)} if MANIFEST.exists() else {}
soup = BeautifulSoup(HTML_PATH.read_text(), "lxml")

units = build_source_units(items)
html_ids = {tag.get("data-material-id") for tag in soup.select("[data-material-id]")}
asset_links = {tag.get("href") for tag in soup.select('a[href^="./assets/"]')}

missing_from_html = []
missing_asset_link = []
missing_local_asset = []

for unit in units:
    unit_id = unit["id"]
    entry = manifest.get(unit_id, {})
    asset_name = entry.get("asset_name") or ""
    if unit_id not in html_ids:
        missing_from_html.append(unit)
    if asset_name and f"./assets/{asset_name}" not in asset_links:
        missing_asset_link.append({**unit, "asset_name": asset_name})
    if asset_name and not (OUT_DIR / "assets" / asset_name).exists():
        missing_local_asset.append({**unit, "asset_name": asset_name})

report = {
    "source_material_units": len(units),
    "html_material_cards": len(html_ids),
    "manifest_entries": len(manifest),
    "missing_from_html_count": len(missing_from_html),
    "missing_asset_link_count": len(missing_asset_link),
    "missing_local_asset_count": len(missing_local_asset),
    "missing_from_html": missing_from_html,
    "missing_asset_link": missing_asset_link,
    "missing_local_asset": missing_local_asset,
}

OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))
