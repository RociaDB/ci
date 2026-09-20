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

### A4 — Plan GitHub : **Free** — limites à assumer *(question ouverte)*

Le plan Free contraint le projet plus que l'outillage. Trois limites à connaître :

| Limite | Effet |
|---|---|
| **Pas de branch protection ni de rulesets sur les dépôts privés** | Les required status checks sont **impossibles** sur les 8 dépôts privés. La CI tourne et signale, mais rien n'empêche de merger une PR rouge. |
| 2 000 minutes/mois de runners GitHub sur les dépôts privés | C'est la raison d'être de `rocia2`. Les dépôts publics restent illimités et gratuits. |
| GitHub Packages privés : 500 Mo de stockage, 1 Go de transfert/mois | Très serré pour 6 dépôts × images multi-arch × plusieurs versions. Saturation en quelques semaines. |

Le « garde-fou avant merge » de la synthèse initiale ne s'applique donc **qu'aux
dépôts publics** en l'état. Voir la question ouverte **Q1**.

---

## B — Architecture du dépôt `ci`

### B1 — Granularité : un workflow réutilisable par (langage × phase)

`_rust-pr.yml`, `_rust-main.yml`, et l'équivalent Node et Python, plus
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

Les dépôts consommateurs appellent `RociaDB/ci/.github/workflows/_rust-pr.yml@v1`.
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

### F3 — Les tests sont rejoués dans le job de release

Plutôt que de récupérer l'artifact JUnit du run de `main` : rétention limitée,
et run introuvable si le workflow a été relancé.

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

### G2 — Rulesets : **dépôts publics uniquement** *(révision)*

Je recommandais un ruleset d'organisation pour les 14 dépôts. Le plan Free ne le
permet pas sur les dépôts privés (voir A4). La protection est donc en place sur les
6 dépôts publics et **inexistante sur les 8 privés** tant que le plan ne change pas.

Les noms de jobs sont malgré tout figés dès maintenant (`quality`, `release-please`,
`publish`, `docker`, `squash-tm`) pour que les required checks soient activables
sans retouche le jour où le plan change.

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
## Questions ouvertes

Deux niveaux : **bloquantes** (un mauvais choix ici se paie en reprise sur tous les
dépôts) et **à confirmer** (j'ai un défaut raisonnable, il suffit de le valider ou
de le corriger).

---

### Bloquantes

#### Q1 — Plan GitHub : rester en Free ou passer en Team ?

Décision à plus fort levier du projet, et elle n'est pas technique. Le plan Team
débloque d'un coup : branch protection et rulesets sur les dépôts privés (donc des
required checks qui **bloquent** réellement un merge), 3 000 min/mois, 2 Go de
packages, merge queue, protections d'environnement sur les privés.

Sans ce changement, la CI des 8 dépôts privés est **informative, pas bloquante** :
elle signale, elle n'empêche rien. Tout le discours « garde-fou avant merge » de la
synthèse initiale ne vaut que pour les 6 dépôts publics.

**Réponse :**

#### Q2 — Où stocker les images privées ?

500 Mo de GitHub Packages privés ne tiendront pas avec 6 dépôts × 2 architectures ×
n versions. Options : registre auto-hébergé sur la VPS (cohérent avec Sonar et
Squash TM déjà sur le tailnet — mais les clusters Kubernetes multi-provider
doivent l'atteindre), plan Team (2 Go, repousse sans résoudre), ou purge
automatique agressive.

**Réponse :**

#### Q3 — Quel langage pour chaque dépôt privé ?

Le template couvre Rust, Node et Python. Connaître la répartition permet de
préparer les fichiers de configuration à l'avance et de valider le bon workflow
en premier.

**Réponse :**

#### Q4 — Quel périmètre de tests remonte dans Squash TM ?

C'est la question qui conditionne tout le design de la partie F, et elle n'était
posée nulle part.

Squash TM est un outil de **gestion de tests** : chaque résultat importé doit
correspondre à un **cas de test existant** portant une `automated_test_reference`.
Or une base Rust produit vite des centaines ou des milliers de tests unitaires.
Créer un cas de test Squash par test unitaire est ingérable, et sans correspondance
les résultats sont rejetés silencieusement.

Trois sous-questions :
- **Périmètre** : seulement les tests fonctionnels / e2e (usage classique), ou
  vraiment tous les tests unitaires ?
- **Création des cas de test** : à la main par les testeurs, ou le pipeline
  crée-t-il le cas s'il n'existe pas ?
- **Découpage** : un projet Squash TM par dépôt, ou un projet global ?

Si la réponse est « fonctionnels seulement », il faut un marqueur dans les tests
(feature nextest, marker pytest, tag vitest) pour filtrer ce qui remonte — à
définir dans la convention.

**Réponse :**

#### Q5 — Amorçage des versions existantes

Piège classique de l'adoption de release-please : sur un dépôt qui a déjà des tags
ou une version dans son manifeste, release-please repart de zéro s'il n'est pas
amorcé (`bootstrap-sha`, `last-release-sha`, version initiale).

- Les dépôts ont-ils déjà des tags de version et des releases GitHub ?
- Les SDK sont-ils en `0.x` ou déjà `≥ 1.0` ? En `0.x`, release-please traite un
  breaking change en bump **mineur**, pas majeur — comportement souvent inattendu.

**Réponse :**

#### Q6 — Des tests ont-ils besoin de services externes ?

Base de données, broker, `docker-compose`, instance RociaDB de test… Sur un runner
unique et sérialisé, cela change l'architecture des jobs (services GitHub Actions,
conteneurs annexes, temps d'exécution) et c'est structurant.

**Réponse :**

#### Q7 — Teste-t-on sur ARM64, ou seulement build ?

En l'état, on publierait des images ARM64 déployées en production sans jamais y
exécuter un seul test. Pour du Rust c'est un risque réel (dépendances natives,
alignement, comportements flottants). Options : exécuter aussi les tests sur
`ubuntu-24.04-arm` (runner GitHub, décompté du quota), ou assumer le risque
explicitement.

**Réponse :**

#### Q8 — Le pipeline s'arrête-t-il à l'image, ou déploie-t-il ?

La synthèse s'arrête à la publication. Mais il y a des clusters Kubernetes
multi-provider. Si le déploiement est en GitOps (ArgoCD, Flux), il faut
probablement bumper un manifeste dans un dépôt d'infrastructure — ce qui **ajoute
un dépôt au périmètre** et un secret d'écriture croisée. À cadrer maintenant :
c'est la frontière du projet.

**Réponse :**

#### Q9 — Nommage et tags des images

Une fois dans les manifestes Kubernetes, c'est figé.
- Chemin : `ghcr.io/rociadb/<repo>` ou `ghcr.io/rociadb/<produit>/<composant>` ?
- Tags produits : `1.2.3` seul, ou aussi `1.2`, `1`, `latest` ?
- `latest` est-il souhaitable, ou interdit (bonne pratique en Kubernetes) ?

**Réponse :**

#### Q10 — État réel de `rocia2`

Déterminant pour savoir si les workflows peuvent réutiliser les actions standard :
- OS et architecture (amd64 présumé) ?
- Docker installé, et le user du runner est-il dans le groupe `docker` ?
- `rustup`, `node`, `uv`, `zig` préinstallés, ou installés à chaque exécution ?
- Espace disque disponible, et politique de purge des caches Rust et des images ?

**Réponse :**

---

### À confirmer (un défaut existe)

| # | Question | Mon défaut |
|---|---|---|
| Q11 | Matrice de versions de langage ? | Une seule version sur les dépôts privés (runner unique) ; matrice sur les SDK publics (runners GitHub gratuits et illimités) |
| Q12 | Les 3 SDK partagent-ils un même numéro de version ? | Non — versions indépendantes. release-please ne synchronise pas entre dépôts |
| Q13 | Branche principale `main` partout ? | Oui |
| Q14 | Renovate : auto-merge des patches ? | Titres conventional oui ; auto-merge non tant que la CI n'est pas éprouvée |
| Q15 | CodeQL + secret scanning + push protection sur les dépôts publics ? | Oui — gratuit, et à activer dès maintenant |
| Q16 | Signature d'images (cosign), SBOM, attestation de provenance ? | Provenance buildx oui (gratuite) ; cosign et SBOM en phase 5 |
| Q17 | Politique d'images de base ? | `distroless/static` (Rust), `node:22-alpine` (Node), `python:3.13-slim` (Python), non-root, labels OCI |
| Q18 | Où notifier les échecs de CI ? | Rien de plus que les notifications GitHub natives |
| Q19 | Les dépôts publics ont-ils une licence ? | Requis par crates.io et npm — à vérifier dépôt par dépôt |
| Q20 | Publier la documentation (rustdoc / typedoc / mkdocs) ? | Hors périmètre pour l'instant |
| Q21 | Noms de jobs figés : `quality`, `release-please`, `publish`, `docker`, `squash-tm` ? | Oui — ils deviennent les noms des required checks, donc difficiles à renommer ensuite |
| Q22 | Préfixe des tags git ? | `v1.2.3` |

**Réponses :**
