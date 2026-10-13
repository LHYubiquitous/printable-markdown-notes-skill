import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "export_notes", ROOT / "scripts" / "export_notes.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ExportNotesTests(unittest.TestCase):
    def test_width_percent_supports_defaults_percentages_and_pixels(self):
        style = {"image_width_percent": 72, "embed_pixel_reference": 900}
        self.assertEqual(MODULE.width_percent(None, style), 72)
        self.assertEqual(MODULE.width_percent("80%", style), 80)
        self.assertAlmostEqual(MODULE.width_percent("650", style), 650 / 9)

    def test_mermaid_direction_can_be_preserved_or_overridden(self):
        source = "flowchart TD\nA --> B\n"
        self.assertEqual(MODULE.orient_mermaid(source, "preserve"), source)
        self.assertTrue(MODULE.orient_mermaid(source, "LR").startswith("flowchart LR"))
        with self.assertRaises(ValueError):
            MODULE.orient_mermaid(source, "diagonal")

    def test_print_only_exclusions_are_stored_on_note(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as parent:
            vault = Path(parent)
            (vault / "Index.md").write_text("# Index\n", encoding="utf-8")
            notes = MODULE.build_notes(
                vault,
                {
                    "files": [
                        {
                            "path": "Index.md",
                            "exclude_sections": ["2. Audit"],
                            "exclude_lines_matching": ["Internal only"],
                        }
                    ]
                },
            )
            self.assertEqual(notes[0].exclude_sections, ["2. Audit"])
            self.assertEqual(notes[0].exclude_lines_matching, ["Internal only"])

            warnings = []
            filtered = MODULE.apply_print_exclusions(
                "# Index\nKeep\n## 2. Audit\nRemove\n### Detail\nRemove too\n## 3. Study\nKeep too\nInternal only\n",
                notes[0],
                warnings,
            )
            self.assertNotIn("Audit", filtered)
            self.assertNotIn("Remove", filtered)
            self.assertNotIn("Internal only", filtered)
            self.assertIn("## 3. Study", filtered)
            self.assertEqual(warnings, [])

    def test_work_directory_must_be_empty(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as parent:
            output = Path(parent) / "notes.pdf"
            occupied = Path(parent) / "occupied"
            occupied.mkdir()
            (occupied / "keep.txt").write_text("user data", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                MODULE.prepare_work_dir(occupied, output)
            self.assertTrue((occupied / "keep.txt").is_file())

    def test_cleanup_requires_marker(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as parent:
            unmarked = Path(parent) / "unmarked"
            unmarked.mkdir()
            with self.assertRaises(RuntimeError):
                MODULE.cleanup_work_dir(unmarked)


if __name__ == "__main__":
    unittest.main()
