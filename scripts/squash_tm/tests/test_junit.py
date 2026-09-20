"""Tests de la normalisation des références — le cœur de la convention.

Les trois fragments de JUnit ci-dessous sont ceux réellement produits par
nextest, pytest et vitest : si la convention casse, c'est ici qu'on le voit.
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from junit import (  # noqa: E402
    FAILURE,
    SKIPPED,
    SUCCESS,
    build_reference,
    parse_report,
    parse_reports,
)

NEXTEST = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="rocia-db-core">
    <testcase classname="rocia_db_core::index" name="test_insert" time="0.012"/>
    <testcase classname="rocia_db_core::index" name="test_delete" time="0.004">
      <failure message="assertion failed: left == right">details</failure>
    </testcase>
  </testsuite>
</testsuites>
"""

PYTEST = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="pytest" tests="2">
    <testcase classname="tests.test_auth.TestLogin" name="test_expired" time="0.5"/>
    <testcase classname="tests.test_auth.TestLogin" name="test_locked" time="0">
      <skipped message="pas encore implémenté"/>
    </testcase>
  </testsuite>
</testsuites>
"""

# vitest émet un <testsuite> racine, sans <testsuites> englobant.
VITEST = """<?xml version="1.0"?>
<testsuite name="src/button.test.ts" tests="1">
  <testcase classname="src/button.test.ts" name="Button &gt; renders
        a label" time="0.031"/>
</testsuite>
"""


def write(directory: str, name: str, content: str) -> Path:
    path = Path(directory) / name
    path.write_text(content, encoding="utf-8")
    return path


class BuildReference(unittest.TestCase):
    def test_follows_the_convention(self):
        self.assertEqual(
            build_reference("rocia-db-core", "rocia_db_core::index", "test_insert"),
            "rocia-db-core/rocia_db_core::index#test_insert",
        )

    def test_collapses_whitespace(self):
        # Un nom vitest replié sur plusieurs lignes doit produire la même
        # référence qu'un nom tenant sur une ligne.
        self.assertEqual(
            build_reference("theme", "src/b.test.ts", "Button >\n   renders"),
            "theme/src/b.test.ts#Button > renders",
        )

    def test_falls_back_when_classname_is_missing(self):
        self.assertEqual(build_reference("repo", "", "test"), "repo/unknown#test")


class ParseReport(unittest.TestCase):
    def test_reads_nextest(self):
        with TemporaryDirectory() as tmp:
            results = parse_report(write(tmp, "junit.xml", NEXTEST), "rocia-db-core")
        self.assertEqual(
            [result.reference for result in results],
            [
                "rocia-db-core/rocia_db_core::index#test_insert",
                "rocia-db-core/rocia_db_core::index#test_delete",
            ],
        )
        self.assertEqual([r.status for r in results], [SUCCESS, FAILURE])
        self.assertEqual(results[0].duration_ms, 12)
        self.assertIn("assertion failed", results[1].message)

    def test_reads_pytest_and_maps_skipped(self):
        with TemporaryDirectory() as tmp:
            results = parse_report(write(tmp, "junit.xml", PYTEST), "rocia-db-admin")
        self.assertEqual(
            results[0].reference,
            "rocia-db-admin/tests.test_auth.TestLogin#test_expired",
        )
        self.assertEqual(results[0].duration_ms, 500)
        self.assertEqual(results[1].status, SKIPPED)

    def test_reads_a_bare_testsuite_root(self):
        with TemporaryDirectory() as tmp:
            results = parse_report(write(tmp, "junit.xml", VITEST), "rocia-db-theme")
        self.assertEqual(
            results[0].reference,
            "rocia-db-theme/src/button.test.ts#Button > renders a label",
        )

    def test_aggregates_several_reports(self):
        with TemporaryDirectory() as tmp:
            paths = [
                write(tmp, "a.xml", NEXTEST),
                write(tmp, "b.xml", VITEST),
            ]
            self.assertEqual(len(parse_reports(paths, "repo")), 3)


if __name__ == "__main__":
    unittest.main()
