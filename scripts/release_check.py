#!/usr/bin/env python3
"""Release consistency check for membrane-brain (stdlib only, read-only).

Asserts, before anyone tags a release, that the version, licence, author,
ORCID and title agree across brain.py, pyproject.toml, CITATION.cff,
.zenodo.json and CHANGELOG.md, that the Zenodo metadata follows Zenodo's
rules, that no DOI has been invented, and (optionally) that a git tag
matches the version.

    python scripts/release_check.py                 # pre-release state
    python scripts/release_check.py --tag v0.1.0    # also check a tag name
    python scripts/release_check.py --post-release  # DOI fields now allowed
    python scripts/release_check.py --json          # machine-readable

The script never talks to the network, never reads a token, never tags and
never touches a webhook. Exit status 0 = every check passed, 1 = a check failed.

Copyright (C) 2026 Jean-François Brisson. SPDX-License-Identifier: AGPL-3.0-only
"""

import argparse
import json
import os
import re
import sys

REPO_URL = "https://github.com/sparkainlp-x/membrane-brain"
LICENSE_ID = "AGPL-3.0-only"
AUTHOR_FAMILY, AUTHOR_GIVEN = "Brisson", "Jean-François"
AUTHOR_ORCID = "0009-0000-9778-5374"
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>)]+", re.I)
ZENODO_DOI_RE = re.compile(r"^10\.5281/zenodo\.\d+$")
# Keys Zenodo's GitHub integration accepts in .zenodo.json (legacy deposit metadata).
ZENODO_KEYS = {
    "title", "version", "upload_type", "publication_type", "image_type", "description",
    "creators", "contributors", "license", "access_right", "embargo_date", "access_conditions",
    "language", "keywords", "subjects", "related_identifiers", "references", "notes",
    "publication_date", "communities", "grants", "locations", "dates", "method",
    "journal_title", "journal_volume", "journal_issue", "journal_pages", "conference_title",
    "conference_acronym", "conference_dates", "conference_place", "conference_url",
    "conference_session", "conference_session_part", "imprint_publisher", "imprint_isbn",
    "imprint_place", "partof_title", "partof_pages", "thesis_supervisors", "thesis_university",
    "prereserve_doi", "doi",
}


def orcid_checksum_ok(orcid):
    """ISO 7064 mod 11-2 check digit used by ORCID iDs."""
    digits = orcid.replace("-", "")
    if not re.fullmatch(r"\d{15}[\dX]", digits):
        return False
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    return digits[-1] == ("X" if check == 10 else str(check))


class Checker:
    def __init__(self, root):
        self.root = root
        self.rows = []

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def exists(self, rel):
        return os.path.exists(os.path.join(self.root, rel))

    def add(self, name, ok, detail=""):
        self.rows.append({"check": name, "ok": bool(ok), "detail": detail})


def cff_scalar(text, key):
    m = re.search(r"^%s:\s*(.+?)\s*$" % re.escape(key), text, re.M)
    if not m:
        return None
    v = m.group(1)
    if v[:1] in "\"'" and v[-1:] == v[:1]:
        v = v[1:-1]
    return v


def cff_block_text(text, key):
    """Text of a folded (>-) or plain top-level block, joined with spaces."""
    m = re.search(r"^%s:\s*>-?\s*\n((?:[ \t]+.*\n?)+)" % re.escape(key), text, re.M)
    if not m:
        return None
    return " ".join(line.strip() for line in m.group(1).splitlines()).strip()


def run(root, tag=None, post_release=False):
    c = Checker(root)
    # ---- files exist
    need = ["brain.py", "pyproject.toml", "CITATION.cff", ".zenodo.json", "CHANGELOG.md",
            "LICENSE", "README.md", "RESULTS.md"]
    missing = [f for f in need if not c.exists(f)]
    c.add("required files exist", not missing, "missing: %s" % missing if missing else "")
    if missing:
        return c.rows
    brain_src, pyproj = c.read("brain.py"), c.read("pyproject.toml")
    cff, changelog = c.read("CITATION.cff"), c.read("CHANGELOG.md")
    readme, results = c.read("README.md"), c.read("RESULTS.md")
    try:
        zen = json.loads(c.read(".zenodo.json"))
        c.add(".zenodo.json is valid JSON", True)
    except ValueError as exc:
        c.add(".zenodo.json is valid JSON", False, str(exc))
        return c.rows

    # ---- version agreement
    v_brain = (re.search(r'^__version__\s*=\s*"([^"]+)"', brain_src, re.M) or [None, None])[1]
    v_py = (re.search(r'^version\s*=\s*"([^"]+)"', pyproj, re.M) or [None, None])[1]
    v_cff = cff_scalar(cff, "version")
    v_zen = zen.get("version")
    m = re.search(r"^## \[?v?(\d+\.\d+\.\d+)", changelog, re.M)
    v_log = m.group(1) if m else None
    versions = {"brain.py": v_brain, "pyproject.toml": v_py, "CITATION.cff": v_cff,
                ".zenodo.json": v_zen, "CHANGELOG.md (newest entry)": v_log}
    c.add("one version everywhere", len(set(versions.values())) == 1 and None not in versions.values(),
          ", ".join("%s=%s" % kv for kv in versions.items()))
    version = v_brain
    c.add("version is semantic (X.Y.Z)", bool(version and re.fullmatch(r"\d+\.\d+\.\d+", version)), str(version))
    if tag is not None:
        c.add("git tag equals v<version>", tag == "v%s" % version, "tag=%s version=%s" % (tag, version))

    # ---- licence
    lic = {"pyproject.toml": ('"%s"' % LICENSE_ID) in pyproj, "CITATION.cff": cff_scalar(cff, "license") == LICENSE_ID,
           ".zenodo.json": zen.get("license") == LICENSE_ID}
    c.add("licence is %s in pyproject, CFF and Zenodo" % LICENSE_ID, all(lic.values()), str(lic))
    c.add("LICENSE file is the GNU Affero GPL v3", "GNU AFFERO GENERAL PUBLIC LICENSE" in c.read("LICENSE").upper()
          and "Version 3" in c.read("LICENSE"))

    # ---- author / ORCID
    creators = zen.get("creators") or []
    want_name = "%s, %s" % (AUTHOR_FAMILY, AUTHOR_GIVEN)
    c.add("Zenodo creator is 'Family, Given' with the right name",
          len(creators) == 1 and creators[0].get("name") == want_name, str(creators[:1]))
    z_orcid = creators[0].get("orcid") if creators else None
    c.add("Zenodo ORCID is bare, well formed and passes the ORCID check digit",
          bool(z_orcid) and re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", z_orcid) is not None
          and orcid_checksum_ok(z_orcid) and z_orcid == AUTHOR_ORCID, str(z_orcid))
    c.add("Zenodo creator has an affiliation", bool(creators and creators[0].get("affiliation")),
          str(creators[0].get("affiliation") if creators else None))
    cff_orcid = (re.search(r"orcid:\s*[\"']?(\S+?)[\"']?\s*$", cff, re.M) or [None, None])[1]
    c.add("CFF ORCID is the https://orcid.org/ URL of the same iD", cff_orcid == "https://orcid.org/" + AUTHOR_ORCID,
          str(cff_orcid))
    c.add("CFF author name matches", ('family-names: "%s"' % AUTHOR_FAMILY) in cff and ('given-names: "%s"' % AUTHOR_GIVEN) in cff)
    cff_aff = (re.search(r"affiliation:\s*[\"'](.+?)[\"']\s*$", cff, re.M) or [None, None])[1]
    c.add("CFF and Zenodo affiliations agree", bool(cff_aff) and creators and cff_aff == creators[0].get("affiliation"),
          "%s | %s" % (cff_aff, creators[0].get("affiliation") if creators else None))

    # ---- Zenodo metadata rules
    unknown = sorted(set(zen) - ZENODO_KEYS)
    c.add(".zenodo.json uses only keys Zenodo accepts", not unknown, "unknown: %s" % unknown if unknown else "")
    c.add("upload_type is software", zen.get("upload_type") == "software", str(zen.get("upload_type")))
    c.add("access_right is open", zen.get("access_right") == "open", str(zen.get("access_right")))
    c.add("title present, equal in CFF and Zenodo, at most 250 characters",
          bool(zen.get("title")) and zen.get("title") == cff_scalar(cff, "title") and len(zen["title"]) <= 250,
          str(len(zen.get("title", ""))) + " characters")
    desc = zen.get("description", "")
    c.add("Zenodo description is HTML-wrapped and honest (says it is not a brain)",
          desc.startswith("<p>") and desc.endswith("</p>") and "not a brain" in desc.lower())
    cff_abs = cff_block_text(cff, "abstract") or ""
    plain = re.sub(r"<[^>]+>", "", desc).strip()
    c.add("CFF abstract equals the Zenodo description text", cff_abs == plain, "")
    kws = zen.get("keywords") or []
    c.add("keywords: 3 or more, unique, none empty", len(kws) >= 3 and len(set(k.lower() for k in kws)) == len(kws)
          and all(k.strip() for k in kws), str(kws))
    c.add("language is a 3-letter ISO 639-3 code", bool(re.fullmatch(r"[a-z]{3}", zen.get("language", ""))),
          str(zen.get("language")))
    rel = zen.get("related_identifiers") or []
    c.add("related identifier: the repository URL (isSupplementTo)",
          any(r.get("identifier") == REPO_URL and r.get("relation") == "isSupplementTo" and r.get("scheme") == "url"
              for r in rel), str(rel))
    ok_rel = all(r.get("identifier") and r.get("relation") and r.get("scheme") in ("url", "doi") for r in rel)
    c.add("every related identifier has identifier, relation and scheme", ok_rel)
    c.add("no publication_date pinned (Zenodo uses the release date)", "publication_date" not in zen)

    # ---- no invented DOI
    scan = {"CITATION.cff": cff, ".zenodo.json": c.read(".zenodo.json"), "README.md": readme,
            "RESULTS.md": results, "CHANGELOG.md": changelog}
    found = {k: DOI_RE.findall(v) for k, v in scan.items() if DOI_RE.search(v)}
    if post_release:
        bad = {k: [d for d in v if not ZENODO_DOI_RE.match(d.rstrip(".,;"))] for k, v in found.items()}
        bad = {k: v for k, v in bad.items() if v}
        c.add("any DOI present is a well-formed Zenodo DOI (post-release mode)", not bad, str(bad) if bad else str(found))
    else:
        c.add("no DOI anywhere (none exists before the release)", not found, str(found) if found else "")
        c.add("CFF has no doi / identifiers field", not re.search(r"^(doi|identifiers):", cff, re.M))

    # ---- docs and honesty
    c.add("README links RESULTS.md and states it is a toy / not a brain",
          "RESULTS.md" in readme and "not a brain" in readme.lower())
    c.add("RESULTS.md says 'This is a toy, not a brain.'", "This is a toy, not a brain." in results)
    c.add("CHANGELOG has an entry for the version", ("## " in changelog) and bool(version) and version in changelog)

    # ---- game copies in sync (only if the game exists)
    if c.exists("docs/game/py/bridge.py"):
        def raw(path):
            with open(path, "rb") as fh:
                return fh.read()
        diff = [f for f in ("brain.py", "rigor.py", "tests.py")
                if raw(os.path.join(root, f)) != raw(os.path.join(root, "docs/game/py", f))]
        c.add("docs/game/py copies of brain.py, rigor.py, tests.py are byte-identical to the root files",
              not diff, "differs: %s" % diff if diff else "")
    return c.rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--tag", default=None, help="git tag name to compare with v<version>")
    ap.add_argument("--post-release", action="store_true", help="allow well-formed Zenodo DOIs")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rows = run(args.root, args.tag, args.post_release)
    failed = [r for r in rows if not r["ok"]]
    if args.json:
        print(json.dumps({"ok": not failed, "checks": rows}, indent=2, ensure_ascii=False))
    else:
        for r in rows:
            print("%-4s %s%s" % ("PASS" if r["ok"] else "FAIL", r["check"], ("  [%s]" % r["detail"]) if (r["detail"] and not r["ok"]) else ""))
        print("\n%d/%d checks pass" % (len(rows) - len(failed), len(rows)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
