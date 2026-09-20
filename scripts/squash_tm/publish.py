"""Publication des résultats de tests dans Squash TM.

Le périmètre retenu (décision Q4) est « tous les tests, unitaires inclus », et
les cas de test sont créés par les testeurs, pas par le pipeline. Un résultat
dont la référence n'a pas de cas correspondant est donc rejeté côté Squash TM.

Pour que cet écart reste visible plutôt que silencieux, le script imprime
systématiquement un rapport des références publiées et de celles que l'instance
n'a pas reconnues, et l'écrit dans le résumé de job GitHub.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from junit import SUCCESS, TestResult, parse_reports

#: Chemin de l'API d'import documenté par Squash TM. Configurable : il varie
#: selon la version de l'instance, et celle de RociaDB n'existe pas encore.
DEFAULT_IMPORT_PATH = "api/rest/latest/import/results"


def build_payload(results: list[TestResult], version: str) -> dict:
    """Construit le corps de la requête d'import.

    L'itération porte le nom de la version : une itération par release, créée à
    la volée plutôt qu'à la main (décision F2).
    """
    return {
        "iteration": version,
        "results": [
            {
                "automated_test_reference": result.reference,
                "status": result.status,
                "duration": result.duration_ms,
                "message": result.message,
            }
            for result in results
        ],
    }


def post(url: str, token: str, payload: dict, timeout: int = 60) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode() or "{}"
    return json.loads(body)


def report(results: list[TestResult], unmatched: list[str]) -> str:
    """Rend le compte rendu affiché dans les logs et le résumé de job."""
    passed = sum(1 for result in results if result.status == SUCCESS)
    lines = [
        "## Publication Squash TM",
        "",
        f"- {len(results)} résultats lus ({passed} en succès)",
        f"- {len(results) - len(unmatched)} appariés à un cas de test",
        f"- **{len(unmatched)} sans cas de test correspondant**",
    ]
    if unmatched:
        lines += [
            "",
            "Ces références n'existent pas dans le référentiel Squash TM et leurs",
            "résultats ont été ignorés. Créer les cas correspondants, ou retirer",
            "ces tests du périmètre remonté :",
            "",
            *(f"- `{reference}`" for reference in sorted(unmatched)[:50]),
        ]
        if len(unmatched) > 50:
            lines.append(f"- … et {len(unmatched) - 50} autres")
    return "\n".join(lines)


def write_summary(text: str) -> None:
    """Ajoute le compte rendu au résumé de job GitHub, s'il y en a un."""
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path, help="rapports JUnit à publier")
    parser.add_argument("--repo", required=True, help="nom du dépôt, préfixe des références")
    parser.add_argument("--version", required=True, help="version publiée, nom de l'itération")
    parser.add_argument("--url", default="", help="URL de base de l'instance Squash TM")
    parser.add_argument("--token", default="", help="jeton d'API Squash TM")
    parser.add_argument("--import-path", default=DEFAULT_IMPORT_PATH)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="analyser et rapporter sans appeler l'instance",
    )
    args = parser.parse_args(argv)

    missing = [path for path in args.reports if not path.exists()]
    if missing:
        print(f"rapport introuvable : {', '.join(map(str, missing))}", file=sys.stderr)
        return 1

    results = parse_reports(args.reports, args.repo)
    if not results:
        print("aucun résultat de test dans les rapports fournis", file=sys.stderr)
        return 1

    payload = build_payload(results, args.version)

    if args.dry_run or not args.url:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        write_summary(report(results, unmatched=[]))
        return 0

    url = f"{args.url.rstrip('/')}/{args.import_path.lstrip('/')}"
    try:
        response = post(url, args.token, payload)
    except urllib.error.HTTPError as error:
        print(f"Squash TM a répondu {error.code} : {error.read().decode()[:500]}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"instance Squash TM injoignable : {error.reason}", file=sys.stderr)
        return 1

    unmatched = response.get("unmatched") or response.get("unknownReferences") or []
    text = report(results, unmatched)
    print(text)
    write_summary(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
