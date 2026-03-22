from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SCRIPTS = REPO_ROOT / "scripts"
EXPORT_ROOT = REPO_ROOT / "exports" / "cdp-export"
FINAL_HTML = EXPORT_ROOT / "full-live-export-v2" / "document-v2.html"
AUDIT_JSON = EXPORT_ROOT / "full-live-export-v2" / "content-completeness-audit.json"
IMAGE_AUDIT_JSON = EXPORT_ROOT / "full-live-export-v2" / "image-completeness-final.json"
MATERIAL_AUDIT_JSON = EXPORT_ROOT / "full-live-export-v2" / "material-completeness-audit.json"


def run(cmd: list[str], env: dict[str, str]) -> None:
    subprocess.run(cmd, check=True, cwd=REPO_ROOT, env=env)


def build_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env["FEISHU_EXPORT_TARGET_URL"] = args.url
    if args.sections:
        payload = json.dumps(args.sections, ensure_ascii=False)
        env["FEISHU_SECTION_TITLES"] = payload
        env["FEISHU_VERIFY_TARGETS"] = payload
    env["FEISHU_VERIFY_FILE_URL"] = FINAL_HTML.resolve().as_uri()
    return env


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full local Feishu export pipeline against the current live Chrome tab.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Target wrapper or Feishu doc URL that is already open in Chrome with CDP enabled.",
    )
    parser.add_argument(
        "--section",
        action="append",
        dest="sections",
        default=[],
        help="Optional heading text to verify and to export as folded-section supplements.",
    )
    parser.add_argument(
        "--skip-open",
        action="store_true",
        help="Do not open the final HTML after export.",
    )
    args = parser.parse_args()

    env = build_env(args)

    run(["node", str(WORKSPACE_SCRIPTS / "preprocess_feishu_live_page.mjs")], env)
    run(["node", str(WORKSPACE_SCRIPTS / "export_feishu_full_live.mjs")], env)
    run(["node", str(WORKSPACE_SCRIPTS / "export_feishu_live_structured_html.mjs")], env)
    run(["node", str(WORKSPACE_SCRIPTS / "export_full_clientvar_sequence.mjs")], env)
    if args.sections:
        run(["node", str(WORKSPACE_SCRIPTS / "export_missing_intro_sections_from_clientvars.mjs")], env)
    run(["node", str(WORKSPACE_SCRIPTS / "backfill_missing_images_from_live_sections.mjs")], env)
    run(["python3", str(WORKSPACE_SCRIPTS / "build_full_live_v2.py")], env)
    run(["python3", str(WORKSPACE_SCRIPTS / "audit_v2_content_completeness.py")], env)
    run(["python3", str(WORKSPACE_SCRIPTS / "audit_image_completeness.py")], env)
    run(["python3", str(WORKSPACE_SCRIPTS / "audit_material_completeness.py")], env)
    run(["node", str(WORKSPACE_SCRIPTS / "verify_v2_sections_in_chrome_cdp.mjs")], env)
    if not args.skip_open:
        run(["open", str(FINAL_HTML)], env)

    print(
        json.dumps(
            {
                "final_html": str(FINAL_HTML),
                "audit": str(AUDIT_JSON),
                "image_audit": str(IMAGE_AUDIT_JSON),
                "material_audit": str(MATERIAL_AUDIT_JSON),
                "url": args.url,
                "sections": args.sections,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
