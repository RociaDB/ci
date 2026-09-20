# Cadrage CI/CD RociaDB — questionnaire de décision

> À compléter. Chaque question a une **réponse par défaut** (ma recommandation).
> Tu peux répondre globalement : « défaut partout sauf A2, D3, F1 », puis détailler
> uniquement celles-là.
>
> Une fois complété, ce document devient le registre de décisions du projet CI.

**Périmètre :** 14 repos de l'organisation RociaDB — 6 publics
(`rociadb-core-sdk-rust`, `rociadb-core-sdk-python`, `rociadb-core-sdk-ts`,
`example-rust-project`, `example-python-project`, `example-ts-project`)
et 8 privés (`ci`, `rocia-db-core`, `rocia-db-core-backend`, `rocia-db-core-ui`,
`rocia-db-admin`, `rocia-db-orchestrator`, `rocia-db-ticket`, `rocia-db-theme`).

---

## A — Décisions bloquantes

À trancher avant d'écrire la première ligne de YAML : chacune change la forme du pipeline.

### A1 — Visibilité du repo `ci`

**Ce que ça bloque :** un repo public ne peut pas appeler un reusable workflow
hébergé dans un repo privé. 6 repos sur 14 sont publics. `ci` est privé aujourd'hui.

- **(a) `ci` devient public** — tout le monde peut l'appeler. Contrainte : zéro secret,
  zéro URL interne, zéro nom de runner en dur ; tout passe par variables/secrets d'org.
- (b) `ci` reste privé — les 6 repos publics dupliquent leurs workflows à la main.
- (c) GitHub Enterprise → visibilité `internal`, qui lève la restriction.

**Ma reco : (a).** Un reusable workflow ne contient aucun secret par construction
(ils arrivent via `secrets: inherit` à l'appel). (b) reconstruit le problème qu'on
cherche à supprimer.

**Réponse :**

### A2 — Édition SonarQube

**Ce que ça bloque :** l'analyse de PR et de branches est une fonctionnalité
Developer Edition. En Community, seule la branche principale est analysable — donc
pas de quality gate bloquant sur PR, quoi qu'en dise le document de synthèse.

- (a) **Developer Edition** — analyse PR native, décoration GitHub, gate sur new code. Payant, tarifé aux lignes de code.
- (b) Community + `mc1arke/sonarqube-community-branch-plugin` — non supporté par SonarSource, **aucun chemin de migration** vers les éditions commerciales, casse à chaque upgrade.
- (c) **Community tel quel** — Sonar sur `main` uniquement, en tableau de bord de dette ; le vrai gate PR = lint + tests + couverture.
- (d) Abandonner Sonar — CodeQL (gratuit sur les repos publics) + clippy/ruff/eslint + couverture.

**Ma reco :** si Sonar est déjà en production et consulté → **(a)**, seul chemin
supporté. Sinon **(c)** pour démarrer, et on réévalue quand le besoin de gate PR
devient concret. J'écarte (b) : la dette de maintenance dépasse le gain.

**Réponse :**

### A3 — Identité utilisée par release-please

**Ce que ça bloque :** une PR créée avec le `GITHUB_TOKEN` par défaut ne déclenche
aucun workflow (anti-récursion GitHub). Si `Build + Tests` est en required check,
la Release PR reste sans check et **impossible à merger, définitivement**.

- (a) **GitHub App d'organisation** + `actions/create-github-app-token`.
- (b) PAT fine-grained sur un compte machine — secret à faire tourner, compte à ne jamais supprimer.
- (c) `GITHUB_TOKEN` + on retire les required checks sur la Release PR — trou dans le garde-fou.

**Ma reco : (a).** Une App, installée une fois sur l'org, sert aussi aux autres
automatisations à venir. C'est ~20 minutes de setup.

**Réponse :**

---

## B — Architecture du repo `ci`

### B1 — Granularité des reusable workflows

- (a) **Un workflow par (langage × phase)** : `rust-pr`, `rust-main`, `rust-release`, idem node/python → 9 fichiers.
- (b) Un workflow par phase avec un input `language` → 3 fichiers, mais un sapin de `if:`.
- (c) Uniquement des composite actions, chaque repo assemble son workflow.

**Ma reco : (a) pour les workflows + (c) pour les briques communes** (setup +
cache, normalisation de couverture, publication Squash TM). (b) devient illisible
dès le troisième cas particulier.

**Réponse :**

### B2 — Épinglage côté repos appelants

- (a) **Tag majeur flottant `@v1`**, déplacé à chaque release de `ci`.
- (b) `@main` — propagation immédiate, casse immédiate aussi.
- (c) SHA épinglé — le plus sûr, mais 14 repos à mettre à jour à chaque correctif.

**Ma reco : (a) partout**, sauf les 3 repos `example-*` qui pointent sur `@main`
et servent de canaris : ils cassent avant les vrais repos.

**Réponse :**

### B3 — Ordre de déploiement / repos pilotes

**Ma reco :** `example-rust-project`, `example-python-project`, `example-ts-project`
d'abord — publics, sans enjeu, et ils valident le chemin public → public. Puis un
repo privé pour valider public → privé avec secrets et runner self-hosted.

**Question : quel repo privé en premier ?** (`rocia-db-ticket` semble le moins
critique, mais tu connais mieux.)

**Réponse :**

### B4 — Un repo = un langage ?

**Ce que ça change :** tout. Matrices, `paths-filter`, et surtout le mode de
release-please (mono-package vs manifest multi-package).

**Question :** y a-t-il des repos polyglottes ou monorepo ? `rocia-db-core-ui` +
`rocia-db-core-backend` sont-ils deux repos ou un futur monorepo ? `rocia-db-core`
contient quoi ?

**Réponse :**

### B5 — Mode release-please

- (a) **Mode `manifest`** (`release-please-config.json` + `.release-please-manifest.json`) même pour les repos mono-package.
- (b) Mode simple avec `release-type` en input.

**Ma reco : (a).** C'est le mode maintenu, et ça évite une migration le jour où un
repo devient multi-package. Config générée depuis un template commun dans `ci`.

**Réponse :**

---

## C — Runners et sécurité

### C1 — Répartition `rocia2` / `ubuntu-latest`

**Ma reco :** repos **publics → `ubuntu-latest`** (minutes gratuites et illimitées
sur les repos publics, et surtout aucun code de fork n'approche la VPS) ;
repos **privés → `rocia2`**. Techniquement : un input `runs-on` dans chaque
reusable workflow, défaut `ubuntu-latest`.

**Réponse :**

### C2 — Durcissement de `rocia2`

Un runner persistant est *stateful* : un job peut empoisonner le cache, le
`~/.cargo` ou le `target/` du job suivant. Un runner group ne protège pas de ça.

**Ma reco :** runners `--ephemeral` + jobs en conteneur. Si c'est trop lourd à
court terme, au minimum : un runner group dédié, `pull_request` depuis les forks
désactivé, et jamais de `pull_request_target` avec checkout du head de PR.

**Questions :** `rocia2` est-il un runner unique ou plusieurs ? Combien de jobs en
parallèle ? Docker est-il disponible dessus pour des jobs conteneurisés ?

**Réponse :**

### C3 — Plan GitHub de l'organisation

**Question :** Free, Team ou Enterprise ? Ça détermine les minutes disponibles sur
les repos privés (donc l'intérêt réel de `rocia2`), la disponibilité de la merge
queue, et celle des rulesets d'org sur les repos privés.

**Réponse :**

### C4 — Merge queue ?

Le document rejoue `Build + Tests` sur `main` après le merge. C'est un doublon si
on exige les branches à jour, et la vraie réponse trunk-based aux conflits
sémantiques, c'est la merge queue (`merge_group`).

**Ma reco : pas tout de suite.** Le double run est un coût acceptable et une
sécurité réelle. On introduit la merge queue quand le volume de PR concurrentes la
justifie.

**Réponse :**

---

## D — Qualité et tests

### D1 — Quels gates sont bloquants sur PR ?

| Gate | Ma reco |
|---|---|
| Build / compile | bloquant J1 |
| Tests unitaires | bloquant J1 |
| Format (`fmt --check`, prettier, ruff format) | bloquant J1 |
| Lint (clippy `-D warnings`, ruff, eslint) | bloquant J1 |
| Types (`tsc --noEmit`, mypy) | bloquant J1 |
| Titre de PR conventional | bloquant J1 |
| Couverture (seuil new code) | informatif 1 mois, puis bloquant |
| Audit dépendances (`cargo-deny`, `pip-audit`, `pnpm audit`) | informatif 1 mois, puis bloquant |
| Quality gate Sonar | selon A2 |

Le document assimile « qualité de code » à SonarQube. Les linters sont plus
rapides, tournent sur PR, et attrapent autre chose — c'est le gate le moins cher
du lot et il était absent.

**Réponse :**

### D2 — Seuil de couverture

**Ma reco :** aucun seuil global au démarrage (le code existant va le faire
échouer partout). Seuil sur le **new code uniquement** : 80 % via Sonar si
Developer Edition, sinon `diff-cover` sur le diff de la PR.

**Réponse :**

### D3 — Outillage par écosystème — à confirmer / corriger

**Rust** — `cargo fmt --check`, `cargo clippy -D warnings`, `cargo nextest`,
couverture `cargo-llvm-cov`, audit `cargo-deny`, cache `Swatinem/rust-cache`.

**Python** — **quel gestionnaire : `uv`, `poetry` ou `pip` ?** C'est la question qui
a le plus d'impact sur le workflow. Ma reco : `uv` + `astral-sh/setup-uv`
(le cache de `actions/setup-python` est médiocre en comparaison). Lint `ruff`
(remplace black + flake8 + isort), types `mypy` ou `pyright`, tests `pytest`.

**Node** — pnpm confirmé (`pnpm/action-setup` **avant** `actions/setup-node`, comme
le note le document). Lint eslint + prettier, ou `biome` si vous démarrez propre.
Types `tsc --noEmit`. Tests : **vitest ou jest ?**

**Réponse :**

### D4 — Format des rapports de tests

**Ma reco : JUnit XML partout**, c'est ce que Squash TM consomme.
Conséquence importante côté Rust : `cargo test` ne produit pas de JUnit,
**`cargo nextest` si** (via `[profile.ci.junit]`). C'est l'argument décisif pour
nextest, au-delà de sa vitesse.

**Réponse :**

---

## E — Release et publication

### E1 — Qui publie quoi ?

À compléter (mon hypothèse préremplie, à corriger) :

| Repo | Cible de publication |
|---|---|
| `rociadb-core-sdk-rust` | crates.io |
| `rociadb-core-sdk-python` | PyPI |
| `rociadb-core-sdk-ts` | npm |
| `rocia-db-core`, `-backend`, `-ui`, `-admin`, `-orchestrator`, `-ticket` | image GHCR |
| `rocia-db-theme` | ? (package npm privé ?) |
| `example-*` | rien — CI uniquement |

Note : le document de synthèse mentionne `cargo publish` et `pnpm publish`, mais
oublie PyPI alors que le SDK Python existe.

**Réponse :**

### E2 — Authentification aux registries

**Ma reco :**
- **PyPI → Trusted Publishing (OIDC)** via `pypa/gh-action-pypi-publish` : aucun token stocké.
- **npm → `--provenance` + OIDC** : aucun token stocké, et attestation de provenance vérifiable.
- **crates.io → token** en secret d'org (le Trusted Publishing y est plus récent ; à vérifier sur le flux actuel avant de miser dessus).
- **GHCR → `GITHUB_TOKEN` + `permissions: packages: write`**, jamais un PAT.

**Réponse :**

### E3 — Image Docker aussi sur `main` ?

Le document ne build que sur release. Tu ne peux donc jamais tester un déploiement
avant de publier la version.

**Question :** y a-t-il une préprod ? Si oui, ma reco est un tag `:edge` /
`:main-<sha>` poussé sur push `main`, en plus des tags de version au release.

**Réponse :**

### E4 — Multi-arch ?

**Question :** arm64 est-il un besoin réel ?

**Ma reco :** si non → amd64 seul, et on supprime la complexité. Si oui et que
c'est du Rust → **cross-compilation**, pas QEMU : l'émulation coûte 10 à 20× sur
une compilation Rust, sur une VPS ça devient ingérable.

**Réponse :**

### E5 — Approbation manuelle avant publication publique ?

**Ma reco : oui** — un GitHub *environment* `release` avec required reviewers pour
crates.io / npm / PyPI. Ces publications sont **irréversibles** : on ne dépublie
pas une version, on en publie une autre.

**Réponse :**

---

## F — Squash TM

### F1 — Convention `automated_test_reference`

Il faut une convention **dérivable automatiquement** des trois frameworks, qui ne
nomment pas les tests de la même façon (`crate::module::test_name` côté Rust,
`tests/test_x.py::TestClass::test_y` côté pytest, `describe > it` côté vitest).

**Ma reco :** `<repo>/<chemin-normalisé>#<nom-du-test>`, avec la normalisation
faite dans le script de publication — un seul endroit à corriger. À figer **une
fois pour l'org**, pas repo par repo.

**Question :** as-tu déjà des cas de test dans Squash TM avec une convention
existante à respecter ?

**Réponse :**

### F2 — Itération cible

**Question :** une itération Squash TM par release ? Créée à la main ou via l'API ?

**Ma reco :** créée par le pipeline via API au moment du release, nommée d'après le
tag. Si c'est manuel, tu introduis une étape humaine qui bloquera le pipeline un
vendredi soir.

**Réponse :**

### F3 — D'où viennent les résultats au moment du release ?

Le point que le document laisse ouvert : au merge de la Release PR, les tests ne
tournent pas — ils ont tourné au push sur `main`.

- (a) **Rejouer les tests dans le job de release.** Plus cher, mais autonome et fiable.
- (b) Récupérer l'artifact JUnit du run de `main` correspondant au SHA. Fragile : rétention limitée, run introuvable si le workflow a été relancé.

**Ma reco : (a).**

**Réponse :**

### F4 — Un échec de publication Squash TM fait-il échouer le pipeline ?

**Ma reco : non** (`continue-on-error: true`) au démarrage. Une instance Squash TM
indisponible ne doit pas bloquer une release. On resserre plus tard si besoin.

**Réponse :**

### F5 — OpenTestFactory Orchestrator ou script maison ?

**Ma reco : script Python maison.** ~150 lignes, versionné dans `ci`, testé,
maîtrisé. OTF est un orchestrateur complet — disproportionné pour publier des
résultats sur une API REST.

**Réponse :**

---

## G — Conventions et gouvernance

### G1 — Respect des conventional commits

Toute la chaîne release-please en dépend, et **rien ne l'impose** dans le document.

Point important : en squash-merge, c'est le **titre de la PR** qui devient le
message de commit. C'est donc le titre qu'il faut linter, pas les commits de la
branche.

**Ma reco :** `amannn/action-semantic-pull-request` en check bloquant, + désactiver
merge commit et rebase dans les settings des repos pour que titre = message.

**Question : squash-merge partout, confirmé ?**

**Réponse :**

### G2 — Branch protection par repo ou ruleset d'org ?

**Ma reco : ruleset au niveau organisation** — un seul endroit pour 14 repos,
au lieu de 14 configurations qui divergeront.

Contrainte à anticiper : les required checks sont référencés **par nom de job**,
donc les noms de jobs doivent être identiques partout → à figer dans les reusable
workflows dès le départ.

**Réponse :**

### G3 — Renovate ou Dependabot ?

**Ma reco : Renovate**, avec une config partagée hébergée dans `ci` (`extends`
depuis les 14 repos), groupement des mises à jour et auto-merge des patches une
fois la CI fiable. Dependabot n'a pas d'équivalent propre pour la config partagée.

**Réponse :**

### G4 — Repo `RociaDB/.github` ?

Templates de PR et d'issues, CODEOWNERS par défaut, profil public de l'org.

**Ma reco : oui**, il complète `ci` naturellement — `ci` porte l'exécutable,
`.github` porte les conventions humaines.

**Réponse :**

### G5 — Secrets : niveau org ou repo ?

**Ma reco : org-level avec liste explicite de repos autorisés** pour `SONAR_TOKEN`,
`SONAR_HOST_URL`, `SQUASH_TM_URL` / `SQUASH_TM_TOKEN`, `CARGO_REGISTRY_TOKEN`.

⚠️ Point de vigilance : un secret d'org rendu accessible aux repos **publics** est
lisible par tout workflow de ces repos. `SONAR_HOST_URL` et `SQUASH_TM_URL`
pointent sur des instances self-hosted — ne les expose pas aux repos publics,
qui n'en ont de toute façon pas besoin si Sonar ne tourne que sur les privés.

**Réponse :**

---

## H — Séquencement

**Ma reco :**

| Phase | Contenu | Sortie |
|---|---|---|
| 0 | Réponses à ce document + GitHub App + visibilité `ci` | Décisions figées |
| 1 | Reusable workflows Rust/Python/Node (PR + main) + les 3 `example-*` | Chemin public→public validé |
| 2 | Les 3 SDK publics : release-please + publication registries | Premières releases automatisées |
| 3 | Repos privés + `rocia2` + rulesets d'org | Couverture complète |
| 4 | Squash TM (script + itérations + convention) | Traçabilité des tests |
| 5 | Durcissement runner (éphémère, conteneurs) + Renovate | Régime de croisière |

**Réponse :**

---

## Questions ouvertes restantes

À remplir au fil des réponses — tout ce qui émerge et n'entre dans aucune section.

-
