#!/usr/bin/env python3
"""Export an ordered Markdown/Obsidian collection as one print-ready PDF."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
except ImportError as exc:  # pragma: no cover - dependency message
    raise SystemExit("Install required packages: python -m pip install pypdf reportlab") from exc


DEFAULT_STYLE: dict[str, Any] = {
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
    "embed_pixel_reference": 900,
    "page_number_y_pt": 9,
    "grayscale_text": True,
    "toc_entries_per_page": 20,
    "toc_font_pt": 10.4,
}


@dataclass
class Note:
    index: int
    path: Path
    relative: str
    label: str
    level: int
    start_new_page: bool
    toc: bool
    anchor: str
    marker: str
    content: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--keep-work-dir", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Manifest must be a JSON object: {path}")
    return value


def prepare_work_dir(requested: Path | None, output: Path) -> Path:
    """Create an empty, identifiable build directory without deleting existing data."""
    if requested:
        work_dir = requested.expanduser().resolve()
        if work_dir.exists():
            if not work_dir.is_dir() or any(work_dir.iterdir()):
                raise FileExistsError(f"Work directory must be absent or empty: {work_dir}")
        else:
            work_dir.mkdir(parents=True)
    else:
        work_dir = Path(
            tempfile.mkdtemp(prefix=f".{output.stem}.print-", dir=str(output.parent))
        ).resolve()
    (work_dir / ".printable-markdown-notes-work").write_text(
        "Safe to remove after the export finishes.\n", encoding="utf-8"
    )
    return work_dir


def cleanup_work_dir(work_dir: Path) -> None:
    marker = work_dir / ".printable-markdown-notes-work"
    if not marker.is_file():
        raise RuntimeError(f"Refusing to remove unmarked work directory: {work_dir}")
    shutil.rmtree(work_dir)


def first_heading(text: str, fallback: str) -> str:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return re.sub(r"[*_`]+", "", match.group(1)).strip() if match else fallback


def strip_frontmatter(text: str) -> str:
    return re.sub(r"\A---\s*\r?\n.*?\r?\n---\s*\r?\n", "", text, count=1, flags=re.S)


def find_executable(configured: str | None, candidates: list[str], common: list[Path]) -> Path:
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return candidate.resolve()
        located = shutil.which(configured)
        if located:
            return Path(located).resolve()
        raise FileNotFoundError(f"Configured executable not found: {configured}")
    for name in candidates:
        located = shutil.which(name)
        if located:
            return Path(located).resolve()
    for path in common:
        if path.exists():
            return path.resolve()
    raise FileNotFoundError(f"Required executable not found. Tried: {', '.join(candidates)}")


def resolve_tools(manifest: dict[str, Any]) -> tuple[Path, Path]:
    tools = manifest.get("tools", {})
    pandoc = find_executable(
        tools.get("pandoc"),
        ["pandoc"],
        [Path.home() / "AppData/Local/Pandoc/pandoc.exe"],
    )
    browser = find_executable(
        tools.get("browser"),
        ["msedge", "chrome", "chromium", "chromium-browser"],
        [
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        ],
    )
    return pandoc, browser


def build_notes(vault: Path, manifest: dict[str, Any]) -> list[Note]:
    file_specs = manifest.get("files")
    if not isinstance(file_specs, list) or not file_specs:
        raise ValueError("Manifest 'files' must be a non-empty list")
    notes: list[Note] = []
    for index, raw in enumerate(file_specs):
        spec = {"path": raw} if isinstance(raw, str) else dict(raw)
        relative = str(spec["path"]).replace("\\", "/")
        path = (vault / Path(relative)).resolve()
        if not path.is_file() or vault.resolve() not in path.parents:
            raise FileNotFoundError(f"Note is missing or outside the vault: {relative}")
        source = path.read_text(encoding="utf-8-sig")
        label = str(spec.get("label") or first_heading(source, path.stem))
        notes.append(
            Note(
                index=index,
                path=path,
                relative=relative,
                label=label,
                level=max(1, int(spec.get("level", 1))),
                start_new_page=bool(spec.get("start_new_page", True)),
                toc=bool(spec.get("toc", True)),
                anchor=f"note-{index:03d}",
                marker=f"PRINT_NOTE_{index:03d}",
            )
        )
    return notes


def build_link_map(notes: list[Note]) -> dict[str, str]:
    result: dict[str, str] = {}
    for note in notes:
        stem = note.relative[:-3] if note.relative.lower().endswith(".md") else note.relative
        result[stem] = note.anchor
        result[Path(stem).name] = note.anchor
        result[note.path.stem] = note.anchor
    return result


def resolve_embed(vault: Path, note_path: Path, target: str) -> Path | None:
    clean = target.split("#", 1)[0].replace("\\", "/")
    name = Path(clean).name
    candidates = [note_path.parent / clean, vault / clean, vault / "attachments" / name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    matches = list(vault.rglob(name)) if name else []
    return matches[0].resolve() if len(matches) == 1 else None


def width_percent(raw: str | None, style: dict[str, Any]) -> float:
    default = float(style["image_width_percent"])
    if not raw:
        return default
    raw = raw.strip()
    if raw.endswith("%"):
        try:
            return max(5.0, min(100.0, float(raw[:-1])))
        except ValueError:
            return default
    try:
        pixels = float(raw)
    except ValueError:
        return default
    reference = max(1.0, float(style["embed_pixel_reference"]))
    return max(5.0, min(100.0, pixels / reference * 100.0))


def render_mermaid(
    code: str,
    work_dir: Path,
    manifest: dict[str, Any],
    browser: Path,
    warnings: list[str],
) -> str:
    config = manifest.get("mermaid", {})
    mode = str(config.get("mode", "auto")).lower()
    if mode == "code":
        return f"```text\n[Mermaid diagram source]\n{code.rstrip()}\n```"
    command = config.get("command")
    if command is None:
        mmdc = shutil.which("mmdc")
        command = [mmdc] if mmdc else None
    if not command:
        message = "Mermaid CLI unavailable; retained diagram source as code"
        if mode == "render":
            raise RuntimeError(message)
        warnings.append(message)
        return f"```text\n[Mermaid diagram source]\n{code.rstrip()}\n```"
    if isinstance(command, str):
        command = [command]
    command = list(command)
    located = shutil.which(command[0])
    if located:
        command[0] = located
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]
    source = work_dir / "mermaid" / f"{digest}.mmd"
    output = work_dir / "mermaid" / f"{digest}.svg"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(code, encoding="utf-8")
    puppeteer = work_dir / "mermaid" / "puppeteer.json"
    executable = str(config.get("browser_executable") or browser)
    puppeteer.write_text(
        json.dumps({"executablePath": executable, "headless": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    args = command + [
        "-i", str(source), "-o", str(output), "-b", "transparent", "-t", "neutral", "-p", str(puppeteer)
    ]
    env = os.environ.copy()
    env.setdefault("PUPPETEER_SKIP_DOWNLOAD", "true")
    process = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )
    if process.returncode or not output.exists():
        message = f"Mermaid rendering failed for {digest}: {(process.stderr or process.stdout).strip()}"
        if mode == "render":
            raise RuntimeError(message)
        warnings.append(message)
        return f"```text\n[Mermaid diagram source]\n{code.rstrip()}\n```"
    return f"![Flowchart]({output.as_uri()}){{.diagram width=92%}}"


def preprocess_note(
    note: Note,
    vault: Path,
    link_map: dict[str, str],
    style: dict[str, Any],
    manifest: dict[str, Any],
    work_dir: Path,
    browser: Path,
    warnings: list[str],
) -> str:
    text = strip_frontmatter(note.path.read_text(encoding="utf-8-sig"))
    text = re.sub(r"%%.*?%%", "", text, flags=re.S)

    def mermaid_repl(match: re.Match[str]) -> str:
        return render_mermaid(match.group(1), work_dir, manifest, browser, warnings)

    text = re.sub(r"```mermaid\s*\r?\n(.*?)\r?\n```", mermaid_repl, text, flags=re.S | re.I)

    def image_repl(match: re.Match[str]) -> str:
        payload = match.group(1)
        parts = payload.rsplit("|", 1)
        target = parts[0].strip()
        size = parts[1].strip() if len(parts) == 2 else None
        asset = resolve_embed(vault, note.path, target)
        if not asset:
            warnings.append(f"Unresolved embed in {note.relative}: {target}")
            return f"**[Missing image: {html.escape(target)}]**"
        width = width_percent(size, style)
        alt = Path(target.split("#", 1)[0]).stem.replace("-", " ")
        # Surround block images with blank lines so a following Markdown heading
        # cannot be absorbed into the same paragraph (common with consecutive
        # Obsidian embeds).
        return f"\n\n![{alt}]({asset.as_uri()}){{.note-image width={width:.2f}%}}\n\n"

    text = re.sub(r"!\[\[([^\]]+)\]\]", image_repl, text)

    def wikilink_repl(match: re.Match[str]) -> str:
        payload = match.group(1)
        target_part, alias = (payload.split("|", 1) + [None])[:2] if "|" in payload else (payload, None)
        target, heading = (target_part.split("#", 1) + [None])[:2] if "#" in target_part else (target_part, None)
        target = target.strip()
        display = (alias or heading or Path(target).name or target).strip()
        anchor = link_map.get(target) or link_map.get(Path(target).name)
        return f"[{display}](#{anchor})" if anchor else display

    text = re.sub(r"(?<!!)\[\[([^\]]+)\]\]", wikilink_repl, text)
    text = re.sub(
        r"(?m)^>\s*\[!([A-Za-z0-9_-]+)\][+-]?\s*(.*)$",
        lambda m: f"> **{(m.group(2) or m.group(1)).strip()}**",
        text,
    )
    text = re.sub(r"==(.+?)==", r"<mark>\1</mark>", text)
    return text.strip() + "\n"


def make_css(template_path: Path, target: Path, style: dict[str, Any]) -> None:
    mono = bool(style["grayscale_text"])
    tokens = {
        "MARGIN_TOP": style["page_margin_top_mm"],
        "MARGIN_RIGHT": style["page_margin_right_mm"],
        "MARGIN_BOTTOM": style["page_margin_bottom_mm"],
        "MARGIN_LEFT": style["page_margin_left_mm"],
        "INK": "#171717" if mono else "#173b3c",
        "MUTED": "#555555" if mono else "#52646b",
        "LINE": "#aaaaaa" if mono else "#aabfc0",
        "WASH": "#f1f1f1" if mono else "#eef5f4",
        "BODY_SIZE": style["body_font_pt"],
        "LINE_HEIGHT": style["line_height"],
        "MATH_SIZE": style["math_scale_percent"],
        "IMAGE_WIDTH": style["image_width_percent"],
        "H1_SIZE": style["h1_font_pt"],
        "H1_LINE_HEIGHT": style["h1_line_height"],
        "H1_AFTER": style["h1_space_after_mm"],
        "H2_SIZE": style["h2_font_pt"],
        "H3_SIZE": style["h3_font_pt"],
        "TABLE_SIZE": style["table_font_pt"],
        "TABLE_VPAD": style["table_cell_vertical_mm"],
        "TABLE_HPAD": style["table_cell_horizontal_mm"],
        "CODE_SIZE": style["code_font_pt"],
        "TOC_SIZE": style["toc_font_pt"],
    }
    css = template_path.read_text(encoding="utf-8")
    for key, value in tokens.items():
        css = css.replace(f"@@{key}@@", str(value))
    leftovers = re.findall(r"@@[A-Z0-9_]+@@", css)
    if leftovers:
        raise ValueError(f"Unresolved CSS tokens: {leftovers}")
    target.write_text(css, encoding="utf-8")


def cover_markdown(manifest: dict[str, Any]) -> str:
    title = html.escape(str(manifest.get("title", "Printable Notes")))
    subtitle = html.escape(str(manifest.get("subtitle", "Print Edition")))
    cover = manifest.get("cover", {})
    details = [html.escape(str(item)) for item in cover.get("details", [])]
    notice = html.escape(str(cover.get("notice", "")))
    detail_html = "<br>\n".join(details)
    notice_html = f"<p>{notice}</p>" if notice else ""
    return (
        '<section class="cover">\n\n'
        f"# {title}\n\n## {subtitle}\n\n"
        f'<div class="cover-meta">\n{detail_html}\n{notice_html}\n</div>\n\n'
        "</section>\n\n<div class=\"page-break\"></div>\n"
    )


def toc_markdown(notes: list[Note], style: dict[str, Any], page_map: dict[int, int] | None) -> str:
    entries = [note for note in notes if note.toc]
    size = max(1, int(style["toc_entries_per_page"]))
    chunks = [entries[i : i + size] for i in range(0, len(entries), size)]
    sections: list[str] = []
    for chunk_index, chunk in enumerate(chunks):
        title = "Contents（目录）" if chunk_index == 0 else "Contents continued（目录续）"
        rows = []
        for note in chunk:
            page = str(page_map[note.index]) if page_map else f"@@PAGE_{note.index:03d}@@"
            label = html.escape(note.label)
            rows.append(
                f'<tr><td class="toc-level-{note.level}"><a href="#{note.anchor}">{label}</a></td>'
                f"<td>{page}</td></tr>"
            )
        sections.append(
            '<section class="toc-page">\n\n'
            f"# {title}\n\n<table class=\"toc-table\"><tbody>\n"
            + "\n".join(rows)
            + "\n</tbody></table>\n\n</section>\n\n<div class=\"page-break\"></div>\n"
        )
    return "\n".join(sections)


def combined_markdown(manifest: dict[str, Any], notes: list[Note], style: dict[str, Any], page_map: dict[int, int] | None) -> str:
    language = str(manifest.get("language", "en"))
    chunks = [f"---\npagetitle: {json.dumps(str(manifest.get('title', 'Printable Notes')), ensure_ascii=False)}\nlang: {language}\n---\n"]
    chunks.append(cover_markdown(manifest))
    chunks.append(toc_markdown(notes, style, page_map))
    for position, note in enumerate(notes):
        if position and note.start_new_page:
            chunks.append('<div class="note-break"></div>\n')
        chunks.append(f'<div id="{note.anchor}"></div><span class="note-marker">{note.marker}</span>\n\n')
        chunks.append(note.content)
    return "\n".join(chunks)


def run_pandoc(pandoc: Path, markdown: Path, css: Path, html_path: Path) -> None:
    command = [
        str(pandoc), str(markdown),
        "--from", "markdown+tex_math_dollars+raw_html+fenced_divs+link_attributes",
        "--to", "html5", "--standalone", "--embed-resources", "--mathml",
        "--syntax-highlighting=none", "--css", str(css), "--output", str(html_path),
    ]
    subprocess.run(command, check=True, cwd=markdown.parent)


def print_html(browser: Path, html_path: Path, pdf_path: Path, profile: Path, manifest: dict[str, Any]) -> None:
    profile.mkdir(parents=True, exist_ok=True)
    args = [
        str(browser), "--headless", "--disable-gpu", "--no-pdf-header-footer",
        f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ]
    args.extend(str(item) for item in manifest.get("tools", {}).get("browser_args", []))
    process = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if process.returncode or not pdf_path.exists():
        raise RuntimeError(f"Browser PDF print failed: {(process.stderr or process.stdout).strip()}")


def extract_marker_pages(pdf_path: Path, notes: list[Note]) -> dict[int, int]:
    expected = {note.marker: note.index for note in notes}
    found: dict[int, int] = {}
    for page_number, page in enumerate(PdfReader(str(pdf_path)).pages, start=1):
        text = page.extract_text() or ""
        for marker, index in expected.items():
            if marker in text:
                found[index] = page_number
    missing = [notes[index].relative for index in range(len(notes)) if index not in found]
    if missing:
        raise RuntimeError(f"Could not detect note start markers: {missing}")
    return found


def page_has_images(page: Any) -> bool:
    try:
        resources = page.get("/Resources") or {}
        return bool(resources.get("/XObject"))
    except Exception:
        return False


def add_footer_and_bookmarks(
    source: Path,
    target: Path,
    manifest: dict[str, Any],
    notes: list[Note],
    page_map: dict[int, int],
    style: dict[str, Any],
) -> tuple[int, list[int]]:
    reader = PdfReader(str(source))
    writer = PdfWriter()
    total = len(reader.pages)
    footer = manifest.get("footer", {})
    show_total = bool(footer.get("show_total", True))
    start_at = int(footer.get("start_at", 1))
    y = float(style["page_number_y_pt"])
    blank_candidates: list[int] = []
    for index, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if len(text) < 2 and not page_has_images(page):
            blank_candidates.append(index + 1)
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        overlay = BytesIO()
        layer = canvas.Canvas(overlay, pagesize=(width, height))
        layer.setStrokeColorRGB(0.70, 0.70, 0.70)
        layer.setLineWidth(0.45)
        layer.line(width * 0.42, y + 12, width * 0.58, y + 12)
        layer.setFillColorRGB(0.28, 0.28, 0.28)
        layer.setFont("Helvetica", 8)
        number = index + start_at
        label = f"{number} / {total + start_at - 1}" if show_total else str(number)
        layer.drawCentredString(width / 2, y, label)
        layer.save()
        overlay.seek(0)
        page.merge_page(PdfReader(overlay).pages[0])
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": str(manifest.get("title", "Printable Notes")),
            "/Subject": str(manifest.get("subtitle", "Print Edition")),
        }
    )
    writer.add_outline_item("Cover", 0)
    if total > 1:
        writer.add_outline_item("Contents", 1)
    parents: dict[int, Any] = {}
    for note in notes:
        page_index = page_map[note.index] - 1
        parent = parents.get(note.level - 1) if note.level > 1 else None
        item = writer.add_outline_item(note.label, page_index, parent=parent)
        parents[note.level] = item
        for deeper in [key for key in parents if key > note.level]:
            del parents[deeper]
    with target.open("wb") as stream:
        writer.write(stream)
    return total, blank_candidates


def main() -> int:
    args = parse_args()
    vault = args.vault.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not vault.is_dir():
        raise FileNotFoundError(f"Vault not found: {vault}")
    manifest = load_json(manifest_path)
    style = dict(DEFAULT_STYLE)
    style.update(manifest.get("style", {}))
    notes = build_notes(vault, manifest)
    pandoc, browser = resolve_tools(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    work_dir = prepare_work_dir(args.work_dir, output)
    warnings: list[str] = []
    link_map = build_link_map(notes)
    for note in notes:
        note.content = preprocess_note(note, vault, link_map, style, manifest, work_dir, browser, warnings)

    skill_root = Path(__file__).resolve().parents[1]
    css_path = work_dir / "print.css"
    make_css(skill_root / "assets" / "print.css.template", css_path, style)

    pass1_md = work_dir / "pass1.md"
    pass1_html = work_dir / "pass1.html"
    pass1_pdf = work_dir / "pass1.pdf"
    pass1_md.write_text(combined_markdown(manifest, notes, style, None), encoding="utf-8")
    run_pandoc(pandoc, pass1_md, css_path, pass1_html)
    print_html(browser, pass1_html, pass1_pdf, work_dir / "browser-pass1", manifest)
    first_map = extract_marker_pages(pass1_pdf, notes)

    pass2_md = work_dir / "final.md"
    pass2_html = work_dir / "final.html"
    pass2_pdf = work_dir / "final-raw.pdf"
    pass2_md.write_text(combined_markdown(manifest, notes, style, first_map), encoding="utf-8")
    run_pandoc(pandoc, pass2_md, css_path, pass2_html)
    print_html(browser, pass2_html, pass2_pdf, work_dir / "browser-pass2", manifest)
    final_map = extract_marker_pages(pass2_pdf, notes)
    if final_map != first_map:
        raise RuntimeError(f"Pagination changed between passes: first={first_map}, final={final_map}")

    total_pages, blank_candidates = add_footer_and_bookmarks(
        pass2_pdf, output, manifest, notes, final_map, style
    )
    report = {
        "output": str(output),
        "pages": total_pages,
        "notes": len(notes),
        "note_pages": {note.relative: final_map[note.index] for note in notes},
        "blank_page_candidates": blank_candidates,
        "warnings": warnings,
        "work_dir": str(work_dir) if args.keep_work_dir else None,
        "tools": {"pandoc": str(pandoc), "browser": str(browser)},
        "style": style,
    }
    report_path = output.with_suffix(".build-report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    resolved_path = output.with_suffix(".resolved-manifest.json")
    resolved = dict(manifest)
    resolved["style"] = style
    resolved_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.keep_work_dir:
        cleanup_work_dir(work_dir)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
