"""Lecture des rapports JUnit et normalisation des références de test.

Les trois écosystèmes produisent du JUnit, mais ne nomment pas les tests de la
même manière :

    nextest   classname = crate::module        name = test_insert
    pytest    classname = tests.test_auth.Foo  name = test_expired
    vitest    classname = src/button.test.ts   name = "Button > renders"

La convention RociaDB les ramène toutes à la même forme :

    <repo>/<classname>#<name>

C'est la seule chose que Squash TM voit, donc la normalisation est centralisée
ici — un seul endroit à corriger si la convention évolue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

_WHITESPACE = re.compile(r"\s+")

#: Statuts Squash TM. Les rapports JUnit distinguent échec (assertion) et erreur
#: (exception non rattrapée) ; Squash TM ne connaît que FAILURE.
SUCCESS, FAILURE, SKIPPED = "SUCCESS", "FAILURE", "BLOCKED"


@dataclass(frozen=True)
class TestResult:
    """Un résultat de test, prêt à être publié."""

    reference: str
    status: str
    duration_ms: int
    message: str = ""


def normalise(text: str) -> str:
    """Réduit les blancs d'un fragment de référence.

    Les noms vitest contiennent des espaces (``Button > renders``) et les
    rapports peuvent porter des retours à la ligne. Sans cette normalisation, la
    même référence peut différer entre deux exécutions.
    """
    return _WHITESPACE.sub(" ", text).strip()


def build_reference(repo: str, classname: str, name: str) -> str:
    """Compose la référence d'un cas de test selon la convention RociaDB."""
    classname = normalise(classname) or "unknown"
    return f"{normalise(repo)}/{classname}#{normalise(name)}"


def _status_of(case: ElementTree.Element) -> tuple[str, str]:
    for tag, status in (("failure", FAILURE), ("error", FAILURE), ("skipped", SKIPPED)):
        node = case.find(tag)
        if node is not None:
            detail = node.get("message") or (node.text or "")
            return status, normalise(detail)[:2000]
    return SUCCESS, ""


def parse_report(path: Path, repo: str) -> list[TestResult]:
    """Extrait les résultats d'un rapport JUnit.

    Accepte les deux formes rencontrées : une racine ``<testsuites>`` ou un
    ``<testsuite>`` isolé, selon le framework.
    """
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.iter("testsuite")

    results = []
    for suite in suites:
        for case in suite.iter("testcase"):
            status, message = _status_of(case)
            results.append(
                TestResult(
                    reference=build_reference(
                        repo,
                        case.get("classname") or suite.get("name") or "",
                        case.get("name") or "",
                    ),
                    status=status,
                    duration_ms=round(float(case.get("time") or 0) * 1000),
                    message=message,
                )
            )
    return results


def parse_reports(paths: list[Path], repo: str) -> list[TestResult]:
    """Agrège plusieurs rapports — un dépôt peut produire plusieurs suites."""
    return [result for path in paths for result in parse_report(path, repo)]
