#!/usr/bin/env python3
"""Contrôles statiques des workflows, avant qu'une exécution ne les trouve.

Trois invariants, chacun correspondant à une panne déjà rencontrée :

1. **Permissions.** Un workflow appelé ne peut pas demander plus que ce que son
   appelant lui accorde. GitHub le refuse au chargement, et le message ne dit
   pas quel appelant corriger.
2. **Références.** Tout `RociaDB/ci/<chemin>@v1` doit désigner un fichier qui
   existe, sinon l'appel échoue sur un « workflow not found ».
3. **Inputs.** Un `with:` qui nomme un input inconnu de l'appelé est refusé.
"""

from __future__ import annotations

import glob
import pathlib
import re
import sys

import yaml

#: L'ordre des niveaux : accorder « write » couvre une demande de « read ».
NIVEAUX = {"none": 0, "read": 1, "write": 2}

#: Clé du bloc de déclencheurs. PyYAML lit le `on:` nu comme le booléen True.
ON = True

APPEL = re.compile(r"RociaDB/ci/(\.github/workflows/[^@]+)@v1")


def charger(chemin: str) -> dict:
    return yaml.safe_load(pathlib.Path(chemin).read_text(encoding="utf-8")) or {}


def accorde(workflow: dict, job: dict) -> dict | None:
    """Ce dont un job dispose : son propre bloc, sinon celui du fichier."""
    for source in (job, workflow):
        if "permissions" in source:
            valeur = source["permissions"]
            # `permissions: read-all` et consorts : rien à vérifier finement.
            return valeur if isinstance(valeur, dict) else None
    return None


def exige(chemin: str, vus: set[str] | None = None) -> dict:
    """Ce qu'un workflow réclame, en remontant ses appels imbriqués."""
    vus = vus or set()
    if chemin in vus or not pathlib.Path(chemin).exists():
        return {}
    vus.add(chemin)

    workflow = charger(chemin)
    besoin: dict[str, str] = {}

    def retenir(perms: dict) -> None:
        for nom, niveau in perms.items():
            if NIVEAUX.get(niveau, 0) > NIVEAUX.get(besoin.get(nom, "none"), 0):
                besoin[nom] = niveau

    for job in (workflow.get("jobs") or {}).values():
        perms = job.get("permissions", workflow.get("permissions"))
        if isinstance(perms, dict):
            retenir(perms)
        if appel := APPEL.match(str(job.get("uses", ""))):
            retenir(exige(appel.group(1), vus))
    return besoin


def controler(chemin: str) -> list[str]:
    workflow = charger(chemin)
    defauts = []

    for nom, job in (workflow.get("jobs") or {}).items():
        appel = APPEL.match(str(job.get("uses", "")))
        if not appel:
            continue
        cible = appel.group(1)

        if not pathlib.Path(cible).exists():
            defauts.append(f"{chemin}:{nom} appelle {cible}, qui n'existe pas")
            continue

        besoin = exige(cible)
        donne = accorde(workflow, job)
        if donne is None:
            if besoin:
                defauts.append(
                    f"{chemin}:{nom} n'accorde aucune permission explicite alors que "
                    f"{cible} demande {besoin}"
                )
        else:
            for perm, niveau in besoin.items():
                if NIVEAUX.get(donne.get(perm, "none"), 0) < NIVEAUX.get(niveau, 0):
                    defauts.append(
                        f"{chemin}:{nom} accorde {perm}: "
                        f"{donne.get(perm, 'none')}, mais {cible} demande {niveau}"
                    )

        declares = set((charger(cible).get(ON) or {}).get("workflow_call", {}).get("inputs") or {})
        for passe in job.get("with") or {}:
            if passe not in declares:
                defauts.append(f"{chemin}:{nom} passe '{passe}', inconnu de {cible}")

    return defauts


def main() -> int:
    fichiers = sorted(
        glob.glob(".github/workflows/*.yml")
        + glob.glob("templates/*/.github/workflows/*.yml")
    )
    defauts = [d for f in fichiers for d in controler(f)]
    if defauts:
        print("\n".join(defauts), file=sys.stderr)
        return 1
    print(f"{len(fichiers)} workflows : permissions, références et inputs cohérents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
