"""Tests for scripts/release_check.py. Run: python -m unittest tests_release -v"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scripts"))
import release_check as rc  # noqa: E402

FILES = ["brain.py", "rigor.py", "tests.py", "pyproject.toml", "CITATION.cff", ".zenodo.json",
         "CHANGELOG.md", "LICENSE", "README.md", "RESULTS.md"]


def failed(rows):
    return {r["check"] for r in rows if not r["ok"]}


class TestReleaseCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for f in FILES:
            shutil.copy(os.path.join(HERE, f), os.path.join(self.tmp, f))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def edit(self, name, fn):
        p = os.path.join(self.tmp, name)
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(fn(text))

    def test_the_repository_passes(self):
        rows = rc.run(HERE)
        self.assertEqual(failed(rows), set(), [r for r in rows if not r["ok"]])
        self.assertGreaterEqual(len(rows), 25)

    def test_cli_exit_codes_and_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(rc.main(["--root", HERE, "--json"]), 0)
        self.assertTrue(json.loads(buf.getvalue())["ok"])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rc.main(["--root", HERE, "--tag", "v9.9.9"]), 1)
            self.assertEqual(rc.main(["--root", HERE, "--tag", "v0.1.0"]), 0)

    def test_tag_must_equal_v_version(self):
        self.assertEqual(failed(rc.run(self.tmp, tag="v0.1.0")), set())
        self.assertIn("git tag equals v<version>", failed(rc.run(self.tmp, tag="0.1.0")))
        self.assertIn("git tag equals v<version>", failed(rc.run(self.tmp, tag="v0.1.1")))

    def test_version_drift_is_caught_in_each_file(self):
        for name, old, new in [("CITATION.cff", "version: 0.1.0", "version: 0.1.1"),
                               ("pyproject.toml", 'version = "0.1.0"', 'version = "0.1.2"'),
                               (".zenodo.json", '"version": "0.1.0"', '"version": "0.2.0"'),
                               ("brain.py", '__version__ = "0.1.0"', '__version__ = "0.1.3"')]:
            with self.subTest(name):
                self.setUp()
                self.edit(name, lambda t: t.replace(old, new, 1))
                self.assertIn("one version everywhere", failed(rc.run(self.tmp)))

    def test_changelog_without_the_version_is_caught(self):
        self.edit("CHANGELOG.md", lambda t: t.replace("0.1.0", "0.0.9"))
        self.assertTrue(failed(rc.run(self.tmp)))

    def test_invented_doi_is_caught_before_release_and_allowed_after(self):
        self.edit("README.md", lambda t: t + "\nDOI: 10.5281/zenodo.1234567\n")
        self.assertIn("no DOI anywhere (none exists before the release)", failed(rc.run(self.tmp)))
        self.assertEqual(failed(rc.run(self.tmp, post_release=True)), set())
        self.edit("README.md", lambda t: t + "\nDOI: 10.9999/not-zenodo\n")
        self.assertTrue(failed(rc.run(self.tmp, post_release=True)))

    def test_cff_doi_field_is_caught(self):
        self.edit("CITATION.cff", lambda t: t + 'doi: "10.5281/zenodo.1"\n')
        self.assertTrue(failed(rc.run(self.tmp)))

    def test_zenodo_rules(self):
        def mutate(fn):
            self.setUp()
            p = os.path.join(self.tmp, ".zenodo.json")
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            fn(d)
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False)
            return failed(rc.run(self.tmp))
        self.assertIn("upload_type is software", mutate(lambda d: d.update(upload_type="dataset")))
        self.assertIn("access_right is open", mutate(lambda d: d.update(access_right="closed")))
        self.assertIn(".zenodo.json uses only keys Zenodo accepts", mutate(lambda d: d.update(bogus=1)))
        self.assertTrue(mutate(lambda d: d.update(license="MIT")))
        self.assertTrue(mutate(lambda d: d["creators"][0].update(orcid="0009-0000-9778-5375")))   # bad check digit
        self.assertTrue(mutate(lambda d: d["creators"][0].update(name="Jean-François Brisson")))  # not 'Family, Given'
        self.assertTrue(mutate(lambda d: d["creators"][0].pop("affiliation")))
        self.assertTrue(mutate(lambda d: d.update(related_identifiers=[])))
        self.assertTrue(mutate(lambda d: d.update(description="<p>A real brain model.</p>")))
        self.assertTrue(mutate(lambda d: d.update(publication_date="2026-01-01")))
        self.assertTrue(mutate(lambda d: d.update(keywords=["a", "A", "b"])))

    def test_cff_orcid_and_author_drift(self):
        self.edit("CITATION.cff", lambda t: t.replace("0009-0000-9778-5374", "0009-0000-9778-5375"))
        self.assertTrue(failed(rc.run(self.tmp)))

    def test_missing_file_is_reported(self):
        os.remove(os.path.join(self.tmp, "CHANGELOG.md"))
        self.assertEqual(failed(rc.run(self.tmp)), {"required files exist"})

    def test_orcid_check_digit(self):
        self.assertTrue(rc.orcid_checksum_ok("0009-0000-9778-5374"))
        self.assertTrue(rc.orcid_checksum_ok("0000-0002-1825-0097"))    # ORCID's documentation example
        self.assertFalse(rc.orcid_checksum_ok("0000-0002-1825-0098"))
        self.assertFalse(rc.orcid_checksum_ok("not-an-orcid"))

    def test_game_copy_drift_is_caught(self):
        os.makedirs(os.path.join(self.tmp, "docs/game/py"))
        for f in ("brain.py", "rigor.py", "tests.py", "bridge.py"):
            shutil.copy(os.path.join(HERE, "docs/game/py", f), os.path.join(self.tmp, "docs/game/py", f))
        self.assertEqual(failed(rc.run(self.tmp)), set())
        with open(os.path.join(self.tmp, "docs/game/py/brain.py"), "a") as fh:
            fh.write("\n# drift\n")
        self.assertTrue(any("byte-identical" in c for c in failed(rc.run(self.tmp))))


if __name__ == "__main__":
    unittest.main()
