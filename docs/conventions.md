# Conventions

## Commits et titres de PR

Les dépôts fusionnent en **squash** : le titre de la PR devient le message de
commit, et c'est lui que release-please lit pour calculer la version. C'est donc
le **titre de la PR** qui est linté, pas les commits de la branche.

Types acceptés : `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`,
`ci`, `chore`, `revert`. Le sujet commence par une minuscule.

⚠️ Tous les dépôts sont en `0.x`. En `0.x`, release-please traite un breaking
change (`feat!` ou `BREAKING CHANGE:`) en bump **mineur** (`0.4.1` → `0.5.0`),
pas majeur. C'est conforme à semver, et cela surprend systématiquement.

## Noms de jobs

Figés, parce qu'ils deviennent les noms des required status checks du ruleset
d'organisation et que les renommer imposerait de reprendre le ruleset :

`quality` · `release-please` · `publish` · `docker` · `squash-tm`

Vus depuis une PR, ils apparaissent préfixés par le nom du job appelant :
`pr / quality`, et `title / pr-title` pour le lint de titre.

## Versionnage de ce dépôt

Les dépôts consommateurs épinglent `@v1`, un tag majeur flottant déplacé à chaque
release de `ci`. Les 3 dépôts `example-*` peuvent pointer sur `@main` pour servir
de canaris : ils cassent avant les dépôts réels.

⚠️ **Maintenance au passage en `v2`.** GitHub n'expose pas de manière fiable la
ref avec laquelle un workflow réutilisable a été chargé. Les références internes
sont donc écrites en dur :

```
.github/workflows/_rust-main.yml    uses: RociaDB/ci/.github/workflows/_rust-quality.yml@v1
.github/workflows/_node-main.yml    uses: RociaDB/ci/.github/workflows/_node-quality.yml@v1
.github/workflows/_python-main.yml  uses: RociaDB/ci/.github/workflows/_python-quality.yml@v1
.github/workflows/_*-main.yml       uses: RociaDB/ci/actions/squash-tm-publish@v1
.github/workflows/_rust-quality.yml curl .../RociaDB/ci/v1/config/deny.toml
```

Toutes sont à bumper en même temps que le tag majeur.

## Images Docker

- Chemin : `ghcr.io/rociadb/<nom-du-dépôt>`
- Tags : `1.2.3`, `1.2`, `1` — **jamais `latest`**, qui rend un déploiement
  Kubernetes non reproductible.
- Utilisateur non-root, labels OCI générés par `docker/metadata-action`.
- **Aucune instruction `RUN` dans les Dockerfiles.** Toute la construction a lieu
  en amont dans la CI, l'image ne fait que copier. C'est ce qui permet de
  produire du multi-arch sans QEMU.

> À vérifier au premier release : `docker/metadata-action` est censé ne pas
> émettre le tag majeur seul quand la version est en `0.x`. Si un tag `:0`
> apparaît, retirer la ligne `pattern={{major}}` des workflows `main`.

## Références de test Squash TM

```
<repo>/<classname>#<test>
```

Dérivée automatiquement du JUnit des trois frameworks. La normalisation est
centralisée dans `scripts/squash_tm/junit.py` — un seul endroit à corriger.

| Framework | Exemple |
|---|---|
| nextest | `rocia-db-core/rocia_db_core::index#test_insert` |
| pytest | `rocia-db-admin/tests.test_auth.TestLogin#test_expired` |
| vitest | `rocia-db-theme/src/button.test.ts#Button > renders` |

Le périmètre retenu est **tous les tests, unitaires inclus**, et les cas de test
sont créés par les testeurs. Un résultat sans cas correspondant est rejeté par
Squash TM : le script liste ces références en fin d'exécution et dans le résumé
de job, pour que l'écart avec le référentiel reste visible.
