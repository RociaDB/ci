# ci

Workflows CI/CD partagés par les dépôts de l'organisation RociaDB.

Toute la logique — build, gates de qualité, SonarQube, release-please,
publication, images Docker multi-arch, Squash TM — vit ici en un seul exemplaire.
Un dépôt consommateur n'embarque qu'un stub d'une quinzaine de lignes.

```yaml
# .github/workflows/ci.yml d'un dépôt consommateur
jobs:
  pr:
    if: github.event_name == 'pull_request'
    uses: RociaDB/ci/.github/workflows/_rust-quality.yml@v1
  main:
    if: github.event_name == 'push'
    uses: RociaDB/ci/.github/workflows/_rust-main.yml@v1
    secrets: inherit
```

## Par où commencer

| Document | Contenu |
|---|---|
| [`docs/onboarding.md`](docs/onboarding.md) | **Migrer un dépôt** — prérequis d'organisation et procédure |
| [`docs/cadrage.md`](docs/cadrage.md) | Registre des décisions et leurs raisons |
| [`docs/conventions.md`](docs/conventions.md) | Commits, noms de jobs, tags d'images, références Squash TM |
| [`docs/secrets.md`](docs/secrets.md) | Secrets d'organisation et leurs portées |
| [`docs/runner.md`](docs/runner.md) | Runner `rocia2` et contraintes associées |

## Structure

```
.github/workflows/
  _rust-quality.yml    gate appelé sur PR, et réutilisé par _rust-main.yml
  _rust-main.yml       quality → release-please → publish / docker / squash-tm
  _node-*.yml          idem pour Node et TypeScript (package npm ou Nuxt SSR)
  _python-*.yml        idem pour Python (gestionnaire uv)
  _pr-title.yml        lint du titre de PR — squash-merge oblige
  maintenance-runner.yml  purge hebdomadaire du disque de rocia2
actions/
  squash-tm-publish/   action composite enveloppant le script de publication
scripts/squash_tm/     lecture JUnit, normalisation des références, publication
config/                deny.toml et preset Renovate partagés
templates/             fichiers à copier dans un dépôt consommateur
```

## Modèle de déclenchement

```
PR vers main ─────────► quality (+ titre de PR)          required checks
                            │
                        merge squash
                            ▼
push sur main ────────► quality → sonar
                            └───► release-please ──► Release PR perpétuelle
                                        │
                                  merge de la Release PR
                                        ▼
push sur main ────────► ... release_created = true
                            ├──► publish   crates.io / npm / PyPI
                            ├──► docker    image multi-arch sur GHCR
                            └──► squash-tm résultats de tests
```

Il n'y a que **deux déclencheurs**, pas trois. La phase de release n'est pas un
événement distinct : c'est le même push sur `main`, où release-please rapporte
`release_created` après le merge de sa propre PR.

## Tests

```bash
python3 scripts/squash_tm/tests/test_junit.py   # lecture JUnit et convention
python3 scripts/verifier-workflows.py           # permissions, références, inputs
```

Le second contrôle les invariants qu'un workflow ne révèle qu'à l'exécution :
un appelé ne peut pas demander plus de permissions que son appelant lui
accorde, une référence `@v1` doit exister, un `with:` doit nommer un input
déclaré.
