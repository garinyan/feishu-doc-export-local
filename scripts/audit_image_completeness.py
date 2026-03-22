from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "exports" / "cdp-export"
SRC_PATH = ROOT / "v2-work" / "full-clientvar-sequence.json"
HTML_PATH = ROOT / "full-live-export-v2" / "document-v2.html"
IMAGES_DIR = ROOT / "full-live-export-v2" / "images"
OUT_PATH = ROOT / "full-live-export-v2" / "image-completeness-final.json"


src_items = json.loads(SRC_PATH.read_text())["items"]
source_image_ids = [item["id"] for item in src_items if item.get("type") == "image"]

existing_stems = {path.stem for path in IMAGES_DIR.iterdir() if path.is_file()}
missing = [image_id for image_id in source_image_ids if image_id not in existing_stems]

html = HTML_PATH.read_text("utf-8", errors="ignore")

report = {
    "source_image_blocks": len(source_image_ids),
    "local_image_files_present": len(source_image_ids) - len(missing),
    "missing_source_image_ids": missing,
    "missing_count": len(missing),
    "html_image_refs_total": html.count("./images/"),
}

OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(OUT_PATH)
