# Printable Markdown Notes Skill

[中文文档](README.zh-CN.md)

A Codex skill and deterministic exporter for turning an ordered Markdown or Obsidian vault into one print-ready PDF.

Features:

- cover, page-numbered contents, PDF bookmarks and footer page numbers;
- Obsidian wikilinks, image embeds, callouts and frontmatter handling;
- MathML equations, code blocks, dense tables and optional Mermaid rendering;
- independent controls for body, heading, code, table and mathematics sizes;
- configurable A4 margins, line height, table padding, image width and page-number position;
- compact single-page contents controls, heading-spacing controls and sparse-tail-page reporting;
- print-only file, section and line exclusions while preserving chapter-start page breaks;
- optional horizontal Mermaid flowcharts with independent diagram bounds;
- per-image width overrides with aspect ratio preserved;
- two-pass pagination and a machine-readable build report.

## Install as a Codex skill

Copy this repository to your Codex skills directory, keeping `SKILL.md` at the repository root.

## Export

```powershell
python scripts/export_notes.py `
  --vault "D:\notes\vault" `
  --manifest "D:\notes\print-manifest.json" `
  --output "D:\notes\printable-notes.pdf"
```

See [configuration.md](references/configuration.md) and [manifest.example.json](examples/manifest.example.json).

## Requirements

- Python 3.10+
- Pandoc
- Microsoft Edge, Chrome or Chromium
- Python packages: `pypdf`, `reportlab`
- Optional: Mermaid CLI (`mmdc`) for diagrams

Install the Python dependencies with:

```powershell
python -m pip install -r requirements.txt
```

Run the lightweight tests with:

```powershell
python -m unittest discover -s tests -v
```

## License

MIT
