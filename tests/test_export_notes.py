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
