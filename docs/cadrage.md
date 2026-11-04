# Cadrage CI/CD RociaDB — décisions

Registre des décisions du projet CI. Les questions ouvertes restantes sont en fin
de document. La version initiale (questionnaire vierge) reste dans l'historique git.

**Périmètre outillé :** ce dépôt fournit les workflows réutilisables et les
templates. **Aucun dépôt existant n'est migré automatiquement** — la migration est
une opération manuelle, dépôt par dépôt, décrite dans [`onboarding.md`](onboarding.md).

---

## A — Décisions structurantes

### A1 — Visibilité du dépôt `ci` : **public** *(action manuelle requise)*

Un dépôt public ne peut pas appeler un workflow réutilisable hébergé dans un dépôt
privé. 6 dépôts sur 14 sont publics, donc `ci` doit être public.

⚠️ **`RociaDB/ci` est encore privé aujourd'hui.** Le passage en public est une
action manuelle à faire dans les settings du dépôt, non automatisable sans risque.
Tant qu'elle n'est pas faite, seuls les dépôts privés peuvent consommer ces
workflows.

Conséquence permanente : **aucun secret, aucune URL interne, aucun nom d'hôte en
dur dans ce dépôt.** Tout passe par des variables et secrets d'organisation.

### A2 — SonarQube : **Community, sur `main` uniquement, et opt-in**

Sonar n'est pas encore déployé ; il le sera derrière une **URL Tailscale**.

Deux conséquences qui n'étaient pas dans la synthèse initiale :

1. **L'analyse de PR reste hors de portée** (fonctionnalité Developer Edition).
   Le quality gate n'est donc pas un garde-fou de merge : Sonar est un tableau de
   bord de dette sur `main`. Le vrai gate PR, c'est lint + types + tests + couverture.
2. **Une URL Tailscale n'est joignable que depuis le tailnet.** Les runners
   GitHub (`ubuntu-latest`) ne peuvent pas l'atteindre. Sonar ne peut donc tourner
   que sur `rocia2`, c'est-à-dire **sur les dépôts privés uniquement**.

Implémentation : input `sonar` (booléen, défaut `false`) sur les workflows `main`.
Pour l'activer un jour sur un dépôt public, il faudrait ajouter
`tailscale/github-action` au runner GitHub — possible, mais cela expose un accès
tailnet à la CI d'un dépôt public. Non retenu par défaut.

### A3 — Identité release-please : **GitHub App d'organisation**

Une PR créée avec le `GITHUB_TOKEN` par défaut ne déclenche aucun workflow. Sans
App, la Release PR n'aurait jamais de check et resterait non mergeable.

Secrets d'organisation attendus : `RELEASE_APP_ID`, `RELEASE_APP_PRIVATE_KEY`.
Voir [`secrets.md`](secrets.md).

### A4 — Plan GitHub : **Team**

Décision prise : passage de Free à GitHub Team. C'est ce qui rend le projet
réellement contraignant plutôt qu'informatif.

| Débloqué par Team | Effet |
|---|---|
| Branch protection et rulesets sur les dépôts privés | Les required status checks **bloquent** un merge sur les 14 dépôts, plus seulement sur les 6 publics |
| 3 000 min/mois de runners GitHub | Marge pour la matrice des SDK publics et un éventuel runner ARM64 |
| 2 Go de packages, 10 Go de transfert/mois | Viable pour GHCR avec purge automatique (Q2) |
| Merge queue | Disponible, non activée (C4) |
| Protections d'environnement sur les privés | L'approbation manuelle avant publication (E5) s'applique aussi à `rocia-db-theme` |

---

## B — Architecture du dépôt `ci`

### B1 — Granularité : un workflow réutilisable par (langage × phase)

`_rust-quality.yml`, `_rust-main.yml`, et l'équivalent Node et Python, plus
`_pr-title.yml` partagé. Sept fichiers.

**Correction par rapport à la synthèse initiale :** il n'y a **pas trois
déclencheurs mais deux**. La phase « release » n'est pas un événement distinct :
c'est la même exécution sur `push: main` où release-please rapporte
`release_created == true` après le merge de sa Release PR. Les jobs `publish`,
`docker` et `squash-tm` sont donc des jobs conditionnels de `_<lang>-main.yml`,
pas un troisième workflow.

Chaque dépôt consommateur a donc **deux fichiers** : `pr.yml` et `main.yml`.

### B1bis — Un seul job par phase, pas un job par gate

Conséquence directe du runner unique (C3) : des jobs parallèles se sérialisent de
toute façon, et chacun repaie le checkout et le setup. Les gates (format, lint,
types, tests) sont donc des **étapes** d'un job `quality` unique, chaînées en
`if: ${{ !cancelled() }}` pour obtenir tous les retours en une seule exécution.

### B2 — Épinglage : `@v1` flottant

Les dépôts consommateurs appellent `RociaDB/ci/.github/workflows/_rust-quality.yml@v1`.
Le tag `v1` est déplacé à chaque release de `ci`.

Note de maintenance : les actions composites internes sont référencées en dur en
`@v1` dans les workflows (GitHub n'expose pas de manière fiable la ref de
chargement d'un workflow réutilisable). **Au passage en `v2`, ces références
internes sont à bumper.** Voir [`conventions.md`](conventions.md).

### B3 — Validation : auto-test interne, aucun dépôt existant touché

Aucun dépôt de l'organisation n'est migré par ce projet. La validation se fait sur
des fixtures internes (`tests/fixtures/`) exercées par `selftest.yml`, qui appelle
les workflows réutilisables de ce dépôt sur lui-même.

Limite assumée : les chemins `publish`, `docker` et `squash-tm` ne sont pas
auto-testables sans secrets ni registres réels. Ils seront validés sur le premier
dépôt volontaire.

### B4 — Un dépôt = un langage

Pas de monorepo, pas de fusion back/front. Un dépôt peut contenir back **et**
front, mais alors dans un seul langage avec un framework dédié (Nuxt SSR).
Conséquence : le workflow Node couvre aussi bien un package npm qu'une application
Nuxt — la cible de publication est un input, pas un workflow distinct.

### B5 — release-please : **mode simple** *(révision)*

Je recommandais le mode `manifest`. La réponse B4 retire l'argument : pas de
monorepo, donc pas de multi-package. Le mode simple (`release-type: rust|node|python`)
expose des outputs plats (`release_created`, `tag_name`, `version`) au lieu des
outputs préfixés `.--tag_name` du mode manifest, ce qui rend les templates
nettement plus lisibles pour ceux qui les maintiendront.

Cas non couvert : un **workspace Cargo** multi-crates à versionner indépendamment
nécessiterait le mode manifest. Non implémenté — à traiter le jour où un dépôt le
demande, plutôt qu'à moitié aujourd'hui.

*Révision du 24 septembre 2026.* Le mode simple reste le défaut, mais chaque
workflow `_<lang>-main.yml` prend une entrée `release_type` : vide, l'action lit
la configuration du dépôt. Deux cas l'ont demandé. Un workspace Cargo dont les
membres héritent leur version — la stratégie `rust` ne sait pas l'écrire, voir
l'onboarding. Et l'amorçage sur des tags existants, que l'onboarding confiait à
une entrée `last_release_sha` qu'aucun workflow ne déclarait. Les sorties ne
changent pas : pour le paquet racine `.`, l'action les rend à plat, comme en mode
simple.

---

## C — Runners

### C1 — Répartition

| Dépôts | Runner | Raison |
|---|---|---|
| Publics | `ubuntu-latest` | Minutes gratuites illimitées, et aucun code de fork n'approche la VPS |
| Privés | `rocia2` | Préserve le quota de 2 000 min/mois |

Input `runs_on` sur tous les workflows, défaut `ubuntu-latest`.

### C2 / C3 — Un seul runner, plan Free

Un runner unique signifie **exécution sérialisée**. Trois conséquences appliquées
dans les templates :

- un seul job par phase (B1bis) ;
- `concurrency` avec `cancel-in-progress: true` sur les PR, **jamais** sur `main` ;
- pas de matrice de versions par défaut.

Durcissement recommandé quand un deuxième runner arrivera : runners `--ephemeral`,
jobs en conteneur. Un runner persistant est *stateful* — un job peut polluer le
cache du suivant. Voir [`runner.md`](runner.md).

### C4 — Pas de merge queue

Indisponible sur les dépôts privés en plan Free, et non justifiée au volume actuel.

---

## D — Qualité et tests

### D1 — Gates

Tous exécutés dans le job `quality`, en étapes chaînées :

| Gate | Rust | Node | Python |
|---|---|---|---|
| Format | `cargo fmt --check` | `prettier --check` | `ruff format --check` |
| Lint | `cargo clippy -D warnings` | `eslint` | `ruff check` |
| Types | *(compilateur)* | `tsc --noEmit` | `mypy` |
| Tests | `cargo nextest` | `vitest run` | `pytest` |
| Couverture | `cargo-llvm-cov` | `vitest --coverage` | `pytest-cov` |
| Audit deps | `cargo-deny` | `pnpm audit` | `uv pip audit` |

Audit et couverture non bloquants au démarrage (`continue-on-error`), à resserrer
après un mois de stabilisation.

### D2 — Couverture : pas de seuil global

Seuil sur le new code uniquement, via `diff-cover` (Sonar Community ne le fait pas).
Désactivé au démarrage, activé dépôt par dépôt.

### D3 — Outillage confirmé

- **Rust** — `cargo fmt`, `clippy`, **`cargo nextest`** (voir D4), `cargo-llvm-cov`, `cargo-deny`.
- **Python** — **`uv`** + `astral-sh/setup-uv`, `ruff` (format + lint), `mypy`, `pytest`.
- **Node** — **pnpm** + **vitest uniquement**, `eslint`, `prettier`, `tsc --noEmit`.

### D4 — JUnit XML partout

`cargo test` ne produit pas de JUnit ; **`cargo nextest` si**, via
`[profile.ci.junit]` dans `.config/nextest.toml`. C'est ce qui rend nextest
obligatoire et non optionnel, puisque Squash TM consomme du JUnit.

---

## E — Release et publication

### E1 — Cibles

| Dépôt | Cible |
|---|---|
| `rociadb-core-sdk-rust` | crates.io |
| `rociadb-core-sdk-python` | PyPI |
| `rociadb-core-sdk-ts` | npm public |
| `rocia-db-theme` | **npm privé GitHub Packages** |
| `rocia-db-*` (applicatifs) | image GHCR multi-arch |
| `example-*` | rien |

### E2 — Authentification

- PyPI → **Trusted Publishing (OIDC)**, aucun token.
- npm public → **`--provenance` + OIDC**, aucun token.
- npm privé GitHub Packages → `GITHUB_TOKEN` + `packages: write`.
- crates.io → `CARGO_REGISTRY_TOKEN` en secret d'organisation.
- GHCR → `GITHUB_TOKEN` + `packages: write`, jamais un PAT.

### E3 — Pas d'image sur `main`

Pas de préprod : on ne construit et ne pousse une image que sur release.

### E4 — Multi-arch AMD64 + ARM64 : **cross-compilation, pas QEMU**

Besoin réel (Kubernetes multi-provider, ARM64 moins cher chez certains).
Contrainte : `rocia2` est un runner amd64 unique.

L'émulation QEMU coûte 10 à 20× sur une compilation Rust. La stratégie retenue est
de **ne jamais rien exécuter pour l'architecture étrangère pendant le build
d'image** :

| Langage | Méthode |
|---|---|
| Rust | `cargo-zigbuild` vers `x86_64-` et `aarch64-unknown-linux-musl`, binaires statiques, image `distroless/static` |
| Node | `pnpm build` une fois (sortie Nitro indépendante de l'architecture), image = `COPY` seul |
| Python | `uv --python-platform` pour résoudre les wheels aarch64 |

**Règle qui en découle, à respecter dans les Dockerfiles : aucune instruction
`RUN` ne doit s'exécuter pour l'architecture étrangère.** Uniquement `COPY`,
`ENV`, `ENTRYPOINT`. C'est ce qui permet de se passer de `setup-qemu-action`.

Échappatoire documentée si un dépôt Python a une dépendance sans wheel aarch64 :
runner GitHub `ubuntu-24.04-arm` (désormais disponible sur les dépôts privés et
décompté du quota gratuit) pour la branche arm, puis fusion des manifestes.

### E5 — Approbation manuelle avant publication publique

Environment GitHub `release` avec required reviewers sur les publications
irréversibles (crates.io, npm, PyPI).

⚠️ Limite plan Free : les règles de protection d'environnement ne sont
disponibles **que sur les dépôts publics**. Les trois SDK publics en bénéficient ;
`rocia-db-theme` (privé) non.

---

## F — Squash TM

Rien n'existe encore côté Squash TM : le standard est défini ici.

### F1 — Convention `automated_test_reference`

```
<repo>/<classname>#<test>
```

Dérivable automatiquement du JUnit des trois frameworks, sans configuration par
dépôt :

| Framework | `classname` JUnit | Exemple de référence |
|---|---|---|
| nextest | crate + module | `rocia-db-core/rocia_db_core::index#test_insert` |
| pytest | module pointé | `rocia-db-admin/tests.test_auth.TestLogin#test_expired` |
| vitest | chemin du fichier | `rocia-db-theme/src/button.test.ts#Button > renders` |

Normalisation (espaces, séparateurs) centralisée dans le script de publication —
un seul endroit à corriger.

### F2 — Itération créée par le pipeline

Une itération par version, créée via l'API au moment du release et nommée d'après
le tag. Pas de création manuelle : ce serait une étape humaine au milieu d'un
pipeline automatique.

### F3 — Les résultats viennent du job `quality` de la même exécution *(révision)*

Je prévoyais de rejouer les tests dans le job de release, par crainte qu'un
artefact soit introuvable. C'était mal poser le problème : `quality` et
`squash-tm` tournent dans **la même exécution**, sur le commit que
release-please vient de taguer. L'artefact JUnit est donc disponible et fait
foi — rien à re-prouver, et sur un dépôt qui demande protoc et une base de
données, le rejeu coûterait toute la mise en place une seconde fois.

### F4 — Échec Squash TM non bloquant

`continue-on-error: true`. Une instance Squash TM indisponible ne doit pas faire
échouer une release.

### F5 — Script Python maison

Dans `scripts/squash_tm/`, exposé via l'action composite `squash-tm-publish`.
OpenTestFactory est un orchestrateur complet, disproportionné pour publier des
résultats sur une API REST.

---

## G — Conventions et gouvernance

### G1 — Squash-merge confirmé → c'est le **titre de PR** qui est linté

En squash-merge, le titre de la PR devient le message de commit, donc c'est lui
que release-please lit. `amannn/action-semantic-pull-request` en check, et merge
commit / rebase à désactiver dans les settings de chaque dépôt.

### G2 — Ruleset d'organisation sur les 14 dépôts

Le plan Team (A4) lève la restriction : un ruleset unique au niveau organisation
couvre les dépôts publics **et** privés, au lieu de 14 configurations qui
divergeraient.

Les required checks sont référencés par nom de job, donc les noms sont figés dès
maintenant : `quality`, `release-please`, `publish`, `docker`, `squash-tm`.

### G3 — Renovate

`renovate.json` fourni à la racine de ce dépôt, et un preset partagé pour les
dépôts consommateurs. C'est lui qui maintient les versions d'actions épinglées ici.

### G4 — Dépôt `RociaDB/.github`

Retenu, mais hors périmètre de ce projet : `ci` porte l'exécutable, `.github`
portera les conventions humaines (templates de PR, CODEOWNERS).

### G5 — Secrets au niveau organisation, liste blanche explicite

⚠️ Un secret d'organisation rendu accessible aux dépôts publics est lisible par
tout workflow de ces dépôts. `SONAR_HOST_URL` et `SQUASH_TM_URL` pointent sur des
instances Tailscale : **ne jamais les exposer aux dépôts publics**, qui n'en ont de
toute façon pas l'usage (A2). Détail dans [`secrets.md`](secrets.md).

---

## H — Séquencement

| Phase | Contenu | État |
|---|---|---|
| 0 | Décisions | ✅ ce document |
| 1 | Workflows réutilisables + templates + auto-test | ✅ ce dépôt |
| 2 | `ci` passé en public + GitHub App créée + secrets d'org | ⬜ **actions manuelles, voir `onboarding.md` §0** |
| 3 | Premier dépôt volontaire migré | ⬜ au choix |
| 4 | Squash TM branché (instance + itérations) | ⬜ |
| 5 | Durcissement runner + Renovate généralisé | ⬜ |

---
## Réponses aux questions en suspens

Série tranchée le 2026-09-20. Toutes les questions ouvertes sont closes.

### Bloquantes

| # | Question | Décision |
|---|---|---|
| Q1 | Plan GitHub | **Passage en Team.** Voir A4 — required checks réellement bloquants sur les 14 dépôts |
| Q2 | Registre des images privées | **GHCR + purge automatique.** Job planifié : suppression des versions non taguées, rétention des N dernières |
| Q3 | Langages des dépôts privés | **Les trois** — Rust, Node/TypeScript et Python sont présents |
| Q4 | Périmètre Squash TM | **Tous les tests, unitaires inclus.** Cas de test créés par les testeurs, pas par le pipeline |
| Q5 | Amorçage des versions | **Aucun tag existant** — release-please démarre à `0.1.0`, rien à amorcer |
| Q5b | Semver | **`0.x`** partout. Attention : en `0.x`, un breaking change produit un bump **mineur** |
| Q6 | Services externes pour les tests | **Réponse démentie par les faits** — voir ci-dessous |
| Q7 | Tests ARM64 | **Build ARM64, tests sur amd64 uniquement.** Risque assumé et documenté |
| Q8 | Frontière du pipeline | **S'arrête à la publication de l'image.** Pas de GitOps, pas d'accès cluster depuis la CI |
| Q9 | Tags d'images | **`1.2.3` + `1.2` + `1`, sans `latest`.** Chemin : `ghcr.io/rociadb/<nom-du-dépôt>` |
| Q10 | État de `rocia2` | **amd64**, Docker + buildx, rustup, node + pnpm et uv **déjà installés**. **Disque < 50 Go** |

#### Correction de Q6 — des tests ont bien besoin d'une base

La réponse au cadrage était « tests autonomes ». L'inspection de
`V2-RociaDB-orchestrator` la dément : sa suite monte un PostgreSQL 18 par
binaire de test via `testcontainers`, et il y a 17 binaires de tests
d'intégration.

Deux conséquences portées dans le template :

- `_rust-quality.yml` accepte un input `postgres` qui démarre **un serveur
  unique** pour toute la suite et expose `DATABASE_URL`, avec ramassage en
  `always()`. Sur un runner persistant au disque contraint, c'est la différence
  entre un conteneur et plusieurs centaines.
- Le harnais du dépôt doit honorer `DATABASE_URL` quand il est présent, sinon
  chaque processus nextest démarrerait le sien. C'est une modification côté
  dépôt, pas côté template.

Les autres dépôts privés sont probablement dans le même cas : la réponse Q6 est
à considérer comme fausse par défaut, et à vérifier dépôt par dépôt.

#### Conséquence de Q4 — dette de référentiel à surveiller

Remonter tous les tests unitaires impose qu'un cas de test existe dans Squash TM
pour chaque référence produite. Les résultats sans cas correspondant sont rejetés.
Le script de publication **listera explicitement les références non appariées** en
fin d'exécution, plutôt que de les perdre en silence : c'est ce qui rendra visible
l'écart entre les tests réels et le référentiel.

#### Conséquence de Q10 — entretien du disque

Moins de 50 Go sur `rocia2`, avec des caches cargo et des couches Docker qui
grossissent à chaque exécution. `maintenance-runner.yml` s'en charge chaque
dimanche.

Côté GHCR, la purge n'est **pas** un job planifié central : l'endpoint
d'énumération des packages d'une organisation refuse les jetons d'App
(HTTP 400 sur `package_type=container`). Elle est donc intégrée au job `docker`,
juste après le push, avec le `GITHUB_TOKEN` du dépôt sur son propre package —
ce qui la fait tourner exactement quand le stockage grossit, sans secret
supplémentaire.

Tout l'outillage étant préinstallé, les actions de setup servent uniquement de
garde-fou de version — elles ne réinstallent rien en pratique.

### Confirmées

| # | Question | Décision |
|---|---|---|
| Q11 | Matrice de versions | Sur les **SDK publics uniquement** (runners GitHub gratuits) ; version unique sur les privés |
| Q12 | Version commune aux 3 SDK | Non — versions indépendantes |
| Q13 | Branche principale | `main` partout |
| Q14 | Mises à jour de dépendances | **Renovate**, config partagée hébergée ici, **sans auto-merge** |
| Q15 | CodeQL | Activé sur les **6 dépôts publics** (gratuit ; payant sur les privés via Advanced Security) |
| Q15b | Secret scanning + push protection | Activé sur les **6 dépôts publics** |
| Q16 | Provenance / signature | **Attestation de provenance buildx** oui. Cosign et SBOM reportés en phase 5 |
| Q17 | Images de base | `distroless/static` (Rust, binaire musl statique), `node:22-alpine`, `python:3.13-slim`. Non-root, labels OCI |
| Q18 | Notifications d'échec | Notifications GitHub natives uniquement |
| Q19 | Licences des dépôts publics | À vérifier dépôt par dépôt — exigé par crates.io et npm. Étape de la checklist d'onboarding |
| Q20 | Publication de la documentation | Hors périmètre |
| Q21 | Noms de jobs | Figés : `quality`, `release-please`, `publish`, `docker`, `squash-tm` |
| Q22 | Préfixe des tags git | `v1.2.3` |

---

## Ce qu'il reste à faire hors de ce dépôt

Aucune de ces actions n'est automatisable depuis ici sans risque. Elles sont
détaillées dans [`onboarding.md`](onboarding.md).

1. Passer l'organisation en plan **Team**.
2. Passer **`RociaDB/ci` en public** — sans quoi les 6 dépôts publics ne peuvent
   pas consommer ces workflows.
3. Créer la **GitHub App** de release et installer ses secrets d'organisation.
4. Créer les **secrets et variables d'organisation** (voir `secrets.md`), en
   veillant à ne **pas** exposer les URL Tailscale aux dépôts publics.
5. Déployer l'instance **SonarQube** et l'instance **Squash TM**.
6. Créer le **ruleset d'organisation** une fois le premier dépôt migré et ses
   noms de checks constatés.
