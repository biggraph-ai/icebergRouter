import json
import os
from pathlib import Path
import unittest


BASE = Path(__file__).resolve().parents[2]
LAYOUT = BASE / "provenance" / "reference-layout.json"


class OptionalReferenceLayoutTests(unittest.TestCase):
    def test_layout_matches_core_study_manifest(self):
        layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
        manifest = json.loads((BASE / "repo_manifest.json").read_text(encoding="utf-8"))
        expected = {
            item["id"] for item in manifest["repositories"] if "core" in item["groups"]
        }
        actual = {item["id"] for item in layout["repositories"]}
        self.assertEqual(expected, actual)
        self.assertTrue(layout["optional"])
        self.assertEqual(layout["canonicalRoot"], "references/repos")

    def test_configured_reference_checkout_when_present(self):
        layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
        configured = os.environ.get("ICEBERG_REFERENCE_ROOT")
        if configured:
            roots = (Path(configured).resolve(),)
        else:
            roots = ((BASE / layout["canonicalRoot"]).resolve(), BASE.resolve())

        located = {}
        for item in layout["repositories"]:
            candidates = [roots[0] / item["canonicalPath"]]
            candidates.extend(BASE / path for path in item["legacyPaths"])
            match = next((path for path in candidates if path.is_dir()), None)
            if match is not None:
                located[item["id"]] = match.resolve()

        if not located:
            self.skipTest("optional reference checkout is not present")
        missing = sorted(
            item["id"] for item in layout["repositories"] if item["id"] not in located
        )
        self.assertEqual(missing, [], "configured study checkout is incomplete")
        product = (BASE / "src" / "iceberg_router").resolve()
        self.assertTrue(
            all(product not in path.parents and path != product for path in located.values())
        )


if __name__ == "__main__":
    unittest.main()
