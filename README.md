# feishu-doc-export-local

Export a Feishu/Lark doc, or a Feishu doc wrapped by another site, into a local HTML package with localized images and a completeness audit.

中文说明：

这个项目用于把飞书文档，或者被第三方页面包裹的飞书文档，尽最大努力导出为本地可读 HTML，并补齐本地图片资源，同时给出一份“内容完整性审计”结果。它优先解决“内容不要丢”，其次解决“离线可读”，不把 `MHTML`、打印 PDF、原始 DOM 快照这种看起来省事但实际不稳定的路线当主方案。

This repository contains a reusable agent workflow package plus the scripts that proved most reliable in practice:

- use the user's already-loaded Chrome tab via CDP
- read Feishu runtime chunk data from `docxClientvarFetchManager`
- rebuild a readable offline HTML package
- localize images into a sibling `images/` directory
- audit text completeness against the live runtime sequence

核心思路：

- 复用用户已经登录、已经加载好的 Chrome 标签页
- 通过 Chrome CDP 接管当前标签页，而不是新开浏览器会话
- 从飞书运行时的 `docxClientvarFetchManager` 读取完整 chunk 序列
- 用 live 结构化 HTML 补表格、图片、引用、多列等特殊块
- 用本地化图片和完整性审计保证结果可交付

## What This Is Good At

- maximizing content completeness
- recovering folded sections
- preserving text and image assets offline
- producing a readable local export instead of a blank DOM snapshot

典型适用场景：

- 文档开在飞书官网里
- 文档开在第三方嵌入页里
- 页面里有折叠段落、表格、引用块、图片
- 用户要求“尽量 1:1、尽量不丢信息、尽量完整”

## What This Does Not Guarantee

- exact Feishu runtime styling
- exact interactive behavior for embeds and widgets
- reliable wrapper-page `MHTML` or print-to-PDF output

This project optimizes for content completeness first, then offline readability.

需要明确的边界：

- 对交互式卡片、第三方组件、运行时行为，通常只能做静态化保留
- 本地版不保证和飞书编辑器视觉逐像素一致
- 但会尽量保证文本、图片、章节顺序和主要语义结构不丢

## Repository Layout

- `AGENTS.md`: generic agent workflow instructions
- `AGENTS-zh.md`: 中文版通用 agent 工作流说明
- `CLAUDE.md`: Claude Code oriented entry notes
- `SKILL.md`: Codex/OpenAI skill entry instructions
- `agents/openai.yaml`: OpenAI skill metadata
- `references/`: checklist and retrospective
- `scripts/`: export, build, audit, and verification scripts
- `exports/`: generated outputs, ignored by git

建议阅读顺序：

1. 先看 `README.md`
2. 再看 `AGENTS.md`
3. 如果更习惯中文，再看 `AGENTS-zh.md`
4. 如果在 Codex/OpenAI 环境下使用，再看 `SKILL.md`
5. 需要复盘时看 `references/retrospective.md`
6. 需要执行交付前检查时看 `references/checklist.md`

## Use In Any Agent Tool

This repository is no longer tied to Codex only.

If your tool supports repository-scoped instruction files, start from:

- `AGENTS.md` for generic agent tools
- `AGENTS-zh.md` for generic agent tools in Chinese
- `CLAUDE.md` for Claude Code
- `SKILL.md` for Codex/OpenAI skill environments

If your tool does not support automatic instruction loading, point it at `AGENTS.md` or `AGENTS-zh.md` and ask it to follow the workflow there.

## Use As A Codex Skill

Copy or symlink this repository into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
ln -s "$PWD" ~/.codex/skills/feishu-doc-export-local
```

Then invoke it in Codex with:

```text
Use $feishu-doc-export-local to export this Feishu doc.
```

如果你已经在本机用了这个 skill，推荐直接把 `~/.codex/skills/feishu-doc-export-local` 指到这个仓库，这样仓库更新和 skill 更新会保持一致。

## Use In Claude Code

Open this repository in Claude Code and ask it to follow [AGENTS.md](AGENTS.md) or [CLAUDE.md](CLAUDE.md).

Example prompt:

```text
Use the workflow in AGENTS.md to export this Feishu document into a local HTML package with localized images and a completeness audit.
```

中文提示词也可以直接写成：

```text
请按照 AGENTS-zh.md 里的流程，把这个飞书文档导出为本地 HTML 包，并输出完整性审计结果。
```

## Use In Other Agent Tools

For Cursor agents, Goose, Aider-style wrappers, or custom internal agents:

1. Open this repository as the working directory.
2. Provide `AGENTS.md` or `AGENTS-zh.md` as the workflow instruction file.
3. Ask the agent to run `python3 scripts/run_feishu_local_export.py --url '...'`.
4. If completeness matters, ask it to report the audit result and image-load verification explicitly.

## CI

This repository includes a GitHub Actions workflow at `.github/workflows/ci.yml`.

It currently checks:

- Python script compilation
- Node script syntax
- CLI help output

## Requirements

- macOS or Linux
- Google Chrome started with remote debugging enabled
- Node.js 20+
- Python 3.10+
- the target Feishu page already open in the CDP-enabled Chrome instance

Install dependencies:

```bash
npm install
python3 -m pip install -r requirements.txt
```

说明：

- Node 端主要用于 Playwright + CDP 接管浏览器
- Python 端主要用于重建 HTML 和完整性审计
- 当前依赖保持在最小集，便于后续维护

## Start Chrome For CDP

Close all Chrome windows, then start a dedicated instance:

```bash
open -na "Google Chrome" --args \
  --remote-debugging-port=9222 \
  --user-data-dir="$PWD/.chrome-cdp"
```

Open your Feishu document, or the third-party page that embeds it, in that Chrome instance and wait until the page is fully loaded.

如果页面是第三方嵌入页，确保内部飞书 iframe 也已经加载完全，尤其是图片和折叠内容相关区块。

## Run The Full Export

Basic:

```bash
python3 scripts/run_feishu_local_export.py \
  --url 'https://example.invalid/embedded-feishu-link'
```

With known folded headings to verify:

```bash
python3 scripts/run_feishu_local_export.py \
  --url 'https://example.invalid/embedded-feishu-link' \
  --section 'Heading One' \
  --section 'Heading Two'
```

运行后会依次做这些事：

1. 导出 live 图片和第一版本地 HTML
2. 导出结构化 live HTML
3. 导出完整 clientvar 顺序块
4. 可选补抓指定折叠标题下的内容
5. 重建 `document-v2.html`
6. 生成内容完整性审计
7. 在 Chrome 里打开并验证结果

## Output

The main result is written under:

- `exports/cdp-export/full-live-export-v2/document-v2.html`
- `exports/cdp-export/full-live-export-v2/images/`
- `exports/cdp-export/full-live-export-v2/content-completeness-audit.json`

辅助产物通常还包括：

- `exports/cdp-export/full-live-export/document.json`
- `exports/cdp-export/structured-live-export/document-structured.html`
- `exports/cdp-export/v2-work/full-clientvar-sequence.json`

## Core Workflow

1. Export live images and a first-pass HTML package from the loaded Feishu frame.
2. Export structured live block HTML for tables, grids, quotes, callouts, and image wrappers.
3. Export the full ordered clientvar chunk sequence from `docxClientvarFetchManager`.
4. Optionally extract specific folded sections by heading.
5. Build the offline HTML package from clientvar content plus structured block helpers.
6. Audit completeness against the live clientvar sequence.
7. Open the local result in Chrome and verify images and sections.

为什么这套流程比直接保存网页更稳：

- 第三方嵌入页的 HTML 经常只是一层壳
- live DOM 离线后经常大片空白
- 真正完整的正文顺序通常在飞书运行时 chunk 数据里
- 所以必须把“抓 live 资源”和“重建最终 HTML”拆成两步

## Why This Exists

Raw host-page HTML, `MHTML`, and browser print output often fail on embedded Feishu docs because the real content lives in a cross-origin iframe and depends on runtime data. The more reliable source of truth is the live Feishu runtime chunk manager inside the loaded frame.

这个仓库基于多次导出实验总结而来：前面试过 raw HTML、MHTML、PDF、直接复制到 Notion 等多条路线，最后证明最稳的是 live CDP + clientvar chunk 数据。

## Limitations

- Some interactive embeds are replaced by static cards or placeholders.
- Offline output is not intended to be pixel-identical to the live Feishu editor.
- The scripts assume the target page is already open in the CDP-enabled Chrome instance.

常见失败原因：

- Chrome 不是以 `--remote-debugging-port=9222` 启动
- 目标标签页没有真正加载完成
- 嵌入页里有多个 iframe，但脚本只接到了错误页面
- 只拿到了可见 DOM，没有拿到完整 clientvar chunk
- 导出后没有跑完整性审计就过早交付

## Future Work

- 自动发现当前活动标签页，减少 `--url` 参数依赖
- 进一步提升特殊块还原质量
- 为更多飞书嵌入页模式做兼容
- 增加更细粒度的差异报告

## License

MIT
