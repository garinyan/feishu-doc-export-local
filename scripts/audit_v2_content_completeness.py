from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1] / "exports" / "cdp-export"
SRC_PATH = ROOT / "v2-work" / "full-clientvar-sequence.json"
HTML_PATH = ROOT / "full-live-export-v2" / "document-v2.html"
OUT_PATH = ROOT / "full-live-export-v2" / "content-completeness-audit.json"


def norm(text: str) -> str:
    return " ".join((text or "").split())


src_items = json.loads(SRC_PATH.read_text())["items"]
html = HTML_PATH.read_text("utf-8")
soup = BeautifulSoup(html, "lxml")
body = norm(soup.get_text("\n"))

missing = []
for item in src_items:
    text = norm(item.get("text") or "")
    if not text:
        continue
    if item.get("type") == "page":
        continue
    if text not in body:
        missing.append(
            {
                "id": item["id"],
                "type": item["type"],
                "text": text,
            }
        )

images = soup.find_all("img")

report = {
    "source_nonempty_text_blocks": sum(1 for item in src_items if norm(item.get("text") or "")),
    "missing_exact_text_blocks": len(missing),
    "missing_by_type": dict(Counter(item["type"] for item in missing)),
    "source_total_blocks": len(src_items),
    "local_image_refs": len(images),
}

OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(OUT_PATH)
