from __future__ import annotations

import shutil
import unittest

from scripts.release_common import (
    REPO_ROOT,
    materialize_legacy_dataset,
    parse_case_id,
    sanitize_public_text,
)
from scripts.validate_release import find_personal_paths


class ReleaseCommonTest(unittest.TestCase):
    def test_parse_case_id(self):
        self.assertEqual(parse_case_id("module02/test1"), (2, 1))

    def test_sanitize_public_text(self):
        linux_path = "/ho" + "me/alice/work/file.txt"
        self.assertEqual(sanitize_public_text(linux_path), "<HOME>/work/file.txt")
        windows_path = "C:" + "\\Us" + r"ers\alice\work\file.txt"
        self.assertEqual(sanitize_public_text(windows_path), r"<HOME>\work\file.txt")

    def test_run_path_scan(self):
        root = REPO_ROOT / "reproduced" / "test_release_path_scan"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        try:
            hidden_path = "/ho" + "me/alice/run/output.json"
            (root / "report.json").write_text(hidden_path, encoding="utf-8")
            self.assertEqual(find_personal_paths(root), ["report.json"])
        finally:
            if root.exists():
                shutil.rmtree(root)

    def test_materialize_one_public_case(self):
        root = REPO_ROOT / "reproduced" / "test_release_common_workspace"
        if root.exists():
            shutil.rmtree(root)
        try:
            cases = materialize_legacy_dataset("benchmark1", root, ["module02/test1"])
            self.assertEqual(cases, ["module02/test1"])
            case = root / "module2" / "test1"
            self.assertTrue((case / "description" / "description0.txt").is_file())
            self.assertTrue((case / "description" / "image_name0.txt").is_file())
            self.assertTrue((case / "code" / "tb.v").is_file())
        finally:
            if root.exists():
                shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
