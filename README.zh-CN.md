# Printable Markdown Notes Skill

[English](README.md)

`printable-markdown-notes` 是一个 Codex Skill 与确定性导出工具，用于将有序的 Markdown 文档集或 Obsidian vault 导出为一份可直接打印的 PDF。

## 功能概览

- 生成封面、带页码的目录、PDF 书签以及页脚页码；
- 支持 Obsidian wikilink、图片嵌入、callout 和 frontmatter；
- 支持 MathML 公式、代码块、密集表格及可选 Mermaid 渲染；
- 分别控制正文、标题、代码、表格和数学公式的字号；
- 可配置 A4 页边距、行高、表格内边距、图片宽度和页码位置；
- 提供紧凑的单页目录、标题间距控制和稀疏尾页报告；
- 可仅在打印输出中排除指定文件、章节或行，同时保留章节首页分页；
- 可选横向 Mermaid 流程图，并为图表单独配置尺寸边界；
- 可逐图覆盖宽度设置，始终保持原始宽高比；
- 使用两次分页，并输出机器可读的构建报告。

## 安装为 Codex Skill

将本仓库复制到 Codex Skills 目录，并保持 `SKILL.md` 位于仓库根目录。

## 导出 PDF

```powershell
python scripts/export_notes.py `
  --vault "D:\notes\vault" `
  --manifest "D:\notes\print-manifest.json" `
  --output "D:\notes\printable-notes.pdf"
```

配置项请参见 [configuration.md](references/configuration.md)，完整清单示例请参见 [manifest.example.json](examples/manifest.example.json)。

## 运行环境

- Python 3.10 或更高版本
- Pandoc
- Microsoft Edge、Chrome 或 Chromium
- Python 包：`pypdf`、`reportlab`
- 可选：用于渲染图表的 Mermaid CLI（`mmdc`）

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

运行轻量级测试：

```powershell
python -m unittest discover -s tests -v
```

## 许可证

MIT
