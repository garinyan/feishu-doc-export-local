# 飞书文档导出工作流

当任务是把飞书文档，或嵌入在第三方页面中的飞书文档，导出为本地 HTML 包时，优先使用本仓库。

## 目标

- 尽量完整保留文本内容
- 将图片资源本地化
- 重建可离线阅读的 HTML
- 对照 live 运行时数据做完整性校验

## 推荐流程

1. 复用用户已经登录并加载完成的 Chrome 标签页。
2. 通过 Chrome CDP 连接 `9222` 端口。
3. 如果目标在第三方页面中，进入其中的飞书 iframe。
4. 从 `docxClientvarFetchManager` 导出完整且有序的运行时 chunk 序列。
5. 导出 live 图片和结构化块 HTML。
6. 重建最终离线 HTML 包。
7. 运行完整性审计。
8. 在 Chrome 中验证图片加载和关键章节存在性。

## 不要走这些捷径

- 不要把 raw DOM 快照当最终结果。
- 不要把 `MHTML` 或 print-to-PDF 当主导出链路。
- 不要在存在运行时 chunk 数据时只依赖 `document.json`。
- 不要假设当前可见 DOM 已经包含所有折叠内容。

## 主入口

```bash
python3 scripts/run_feishu_local_export.py \
  --url 'https://example.invalid/embedded-feishu-link'
```

如需验证指定折叠标题：

```bash
python3 scripts/run_feishu_local_export.py \
  --url 'https://example.invalid/embedded-feishu-link' \
  --section 'Heading One' \
  --section 'Heading Two'
```

## 关键文件

- `scripts/run_feishu_local_export.py`
- `scripts/export_feishu_full_live.mjs`
- `scripts/export_feishu_live_structured_html.mjs`
- `scripts/export_full_clientvar_sequence.mjs`
- `scripts/export_missing_intro_sections_from_clientvars.mjs`
- `scripts/build_full_live_v2.py`
- `scripts/audit_v2_content_completeness.py`
- `scripts/verify_v2_sections_in_chrome_cdp.mjs`

## 预期输出

- `exports/cdp-export/full-live-export-v2/document-v2.html`
- `exports/cdp-export/full-live-export-v2/images/`
- `exports/cdp-export/full-live-export-v2/content-completeness-audit.json`

## 成功标准

- `missing_exact_text_blocks = 0`
- 本地化图片能正常加载
- 用户关心的折叠章节已经恢复
- 剩余差异只属于视觉或运行时行为，不是内容缺失
