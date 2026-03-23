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
    parser.add_argument(
        "--export-md",
        action="store_true",
        help="Also convert the final HTML package into a Markdown package.",
    )
    parser.add_argument(
        "--import-obsidian",
        action="store_true",
        help="After Markdown export, copy the Markdown package into an Obsidian vault.",
    )
    parser.add_argument(
        "--obsidian-vault",
        help="Explicit Obsidian vault path. Defaults to the currently open vault from obsidian.json.",
    )
    parser.add_argument(
        "--obsidian-subdir",
        default="Imports/Feishu",
        help="Relative folder inside the Obsidian vault when using --import-obsidian.",
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
    markdown_path = None
    obsidian_note = None
    obsidian_uri = None
    if args.export_md or args.import_obsidian:
        markdown_cmd = [
            "python3",
            str(WORKSPACE_SCRIPTS / "export_html_package_to_markdown.py"),
            "--html",
            str(FINAL_HTML),
        ]
        if args.import_obsidian:
            markdown_cmd.append("--import-obsidian")
            if args.obsidian_vault:
                markdown_cmd.extend(["--obsidian-vault", args.obsidian_vault])
            if args.obsidian_subdir:
                markdown_cmd.extend(["--obsidian-subdir", args.obsidian_subdir])
        output = subprocess.run(
            markdown_cmd,
            check=True,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        payload = json.loads(output.stdout)
        markdown_path = payload.get("markdown")
        obsidian_note = payload.get("obsidian_note")
        obsidian_uri = payload.get("obsidian_uri")
    if not args.skip_open:
        run(["open", obsidian_uri or obsidian_note or markdown_path or str(FINAL_HTML)], env)

    print(
        json.dumps(
            {
                "final_html": str(FINAL_HTML),
                "final_markdown": markdown_path,
                "audit": str(AUDIT_JSON),
                "image_audit": str(IMAGE_AUDIT_JSON),
                "material_audit": str(MATERIAL_AUDIT_JSON),
                "obsidian_note": obsidian_note,
                "obsidian_uri": obsidian_uri,
                "url": args.url,
                "sections": args.sections,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
