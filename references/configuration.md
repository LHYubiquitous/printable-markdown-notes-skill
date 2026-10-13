# Configuration Reference

The manifest is JSON so the exporter has no YAML dependency. Relative note paths are resolved from `--vault`.

## Minimal manifest

```json
{
  "title": "Course Notes",
  "subtitle": "Printable Study Edition",
  "files": [
    {"path": "00 Index.md", "level": 1},
    {"path": "Topics/01 Topic.md", "level": 2}
  ]
}
```

Each file may specify:

- `path`: required relative Markdown path.
- `label`: optional printed contents/bookmark label; otherwise the first level-one heading or filename is used.
- `level`: bookmark and contents hierarchy, normally `1` or `2`.
- `start_new_page`: defaults to `true`.
- `toc`: defaults to `true`.

## Layout settings

Place overrides under `style`. Omitted values use the exporter defaults.

```json
{
  "style": {
    "page_margin_top_mm": 13,
    "page_margin_right_mm": 13.5,
    "page_margin_bottom_mm": 15,
    "page_margin_left_mm": 13.5,
    "body_font_pt": 10.4,
    "line_height": 1.34,
    "h1_font_pt": 16.5,
    "h1_line_height": 1.08,
    "h1_space_after_mm": 2.8,
    "h2_font_pt": 12.8,
    "h3_font_pt": 11.4,
    "code_font_pt": 9.25,
    "math_scale_percent": 100,
    "table_font_pt": 9.15,
    "table_cell_vertical_mm": 0.9,
    "table_cell_horizontal_mm": 1.2,
    "image_width_percent": 72,
    "page_number_y_pt": 9,
    "grayscale_text": true,
    "toc_entries_per_page": 20
  }
}
```

Useful independent adjustments:

- Set `image_width_percent` to `80` for larger figures. This never changes the natural aspect ratio.
- Set `body_font_pt` without changing `code_font_pt` or `math_scale_percent`.
- Increase `math_scale_percent` when equations need emphasis without enlarging prose.
- Reduce `table_cell_vertical_mm` to make long reference tables denser.
- Move footer numbers with `page_number_y_pt`; keep sufficient bottom margin to avoid collisions.
- Set `grayscale_text` to `false` to use the optional accent colour. Images remain in colour either way.

## Per-image overrides

Obsidian embeds retain their width intent:

```markdown
![[figure.png|80%]]
![[figure.png|650]]
```

- A percentage is used directly.
- A numeric pixel width is converted relative to `embed_pixel_reference` (default `900`), so `650` is approximately `72%`.
- An embed without a width uses `image_width_percent`.

Standard Markdown image attributes such as `{width=80%}` also remain available.

## Cover, contents, and footer

Optional manifest fields:

```json
{
  "cover": {
    "details": ["Semester 2", "Open-book revision edition"],
    "notice": "Prepared for duplex printing"
  },
  "footer": {
    "show_total": true,
    "start_at": 1
  }
}
```

The contents is generated in fixed-size chunks, then the document is printed twice. The first pass discovers the actual start page of every note. The second pass writes those values into the contents. Footer page numbers and bookmarks are added after pagination is stable.

## Mermaid

The exporter checks for `mmdc`. To use another command, provide a command array:

```json
{
  "mermaid": {
    "mode": "render",
    "command": ["npx.cmd", "-y", "@mermaid-js/mermaid-cli"],
    "browser_executable": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
  }
}
```

Modes:

- `render`: diagram failure stops the build.
- `auto`: render when a command is available; otherwise retain a labelled code fallback and record a warning.
- `code`: deliberately retain Mermaid source as a printable code block.

For `npx`, network access may be required on the first run. Do not download packages without the user's authorization.
