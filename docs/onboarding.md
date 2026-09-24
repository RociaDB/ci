# Migrer un dépôt vers la CI partagée

Deux parties : les **prérequis d'organisation** (§0), à faire une seule fois, et
la **procédure par dépôt** (§1 à §4), à répéter pour chaque dépôt que tu décides
de migrer.

Aucun dépôt n'est migré automatiquement. C'est une opération délibérée, dépôt par
dépôt.

---

## §0 — Prérequis d'organisation (une seule fois)

### 0.1 Passer l'organisation en plan Team

`Settings` → `Billing and plans` → `Upgrade`.

Sans cela, les required status checks ne sont pas applicables aux dépôts privés :
la CI signalerait sans jamais bloquer un merge.

### 0.2 Rendre `RociaDB/ci` public

`Settings` → `General` → `Danger Zone` → `Change repository visibility`.

**Un dépôt public ne peut pas appeler un workflow réutilisable hébergé dans un
dépôt privé.** Tant que `ci` est privé, les 6 dépôts publics ne peuvent pas être
migrés. C'est aussi ce qui permet à `_rust-quality.yml` de récupérer
`config/deny.toml` par une simple requête HTTP.

Règle permanente qui en découle : aucun secret, aucune URL interne et aucun nom
d'hôte en dur dans ce dépôt.

### 0.3 Créer la GitHub App de release

> **Pourquoi une App et pas le `GITHUB_TOKEN`.** Une PR ouverte avec le
> `GITHUB_TOKEN` par défaut ne déclenche aucun workflow — GitHub l'empêche pour
> éviter les boucles. La Release PR n'aurait donc jamais de check, et resterait
> non mergeable pour toujours dès que les required checks sont actifs.

#### a. Créer l'App

`https://github.com/organizations/RociaDB/settings/apps` → **New GitHub App**

| Champ | Valeur |
|---|---|
| **GitHub App name** | `RociaDB Release Bot` — le nom est unique sur tout GitHub, ajouter un suffixe s'il est pris |
| **Homepage URL** | `https://github.com/RociaDB/ci` — obligatoire, le contenu n'importe pas |
| **Callback URL** | vide |
| **Setup URL** | vide |
| **Webhook → Active** | ⚠️ **décocher.** Coché par défaut, il exige alors une URL de webhook dont on n'a aucun usage |
| **Where can this GitHub App be installed?** | *Only on this account* |

**Repository permissions** — tout le reste sur *No access* :

| Permission | Niveau | Pourquoi |
|---|---|---|
| Contents | Read and write | Créer les tags et les commits de release |
| Issues | Read and write | release-please gère ses propres labels |
| Metadata | Read-only | Imposé, se coche automatiquement |
| Pull requests | Read and write | Maintenir la Release PR perpétuelle |

Aucune *Organization permission* n'est nécessaire.

> La permission **Packages** n'est plus requise. Elle l'était pour une purge
> GHCR centralisée, abandonnée : l'endpoint d'énumération des packages d'une
> organisation refuse les jetons d'App (HTTP 400 sur `package_type=container`).
> La purge se fait désormais dans le job `docker`, avec le `GITHUB_TOKEN` du
> dépôt. Si elle a déjà été accordée, elle peut rester sans inconvénient.

→ **Create GitHub App**

#### b. Récupérer les identifiants

1. **App ID**, en haut de la page de l'App — un nombre court, par exemple
   `1234567`. ⚠️ Ce n'est **pas** le Client ID, qui ressemble à `Iv23li...`.
2. Section **Private keys** → **Generate a private key**. Un fichier `.pem` se
   télécharge, et il n'est affiché qu'une seule fois.

#### c. Installer l'App

Créer une App ne suffit pas : il faut l'**installer**. C'est l'oubli le plus
fréquent, et il ne produit aucun message d'erreur explicite.

Menu latéral → **Install App** → ligne `RociaDB` → **Install** →
**All repositories**.

#### d. Vérifier

Une fois les secrets créés (§0.4), dans `RociaDB/ci` : onglet **Actions** →
workflow **selftest · jeton d'App** → **Run workflow**.

Il obtient un jeton d'App et liste les dépôts couverts par l'installation. Vert,
les trois éléments sont bons ; rouge, le message dit lequel manque. Trente
secondes, au lieu de le découvrir à l'étape §4.

### 0.4 Créer les secrets et variables d'organisation

Voir [`secrets.md`](secrets.md) pour la liste complète et les périmètres.

⚠️ `SONAR_HOST_URL` et `SQUASH_TM_URL` pointent sur des instances Tailscale.
**Ne jamais les rendre accessibles aux dépôts publics** : un secret d'organisation
exposé à un dépôt public est lisible par tout workflow de ce dépôt.

### 0.5 Créer le ruleset d'organisation

À faire **après** la migration du premier dépôt, pour que les noms de checks
soient constatés plutôt que devinés.

`Settings` de l'organisation → `Repository` → `Rulesets` → `New ruleset` :

- cible : tous les dépôts, branche `main` ;
- interdire les pushes directs ;
- exiger une pull request avant merge ;
- required status checks : `pr / quality` et `title / pr-title` ;
- exiger que la branche soit à jour avant merge.

---

## §1 — Vérifier l'état du dépôt à migrer

```bash
git ls-remote --tags origin          # doit être vide : sinon, voir §1.1
git branch --show-current            # doit être main
ls LICENSE                           # obligatoire pour un dépôt publié
```

### 1.1 Si le dépôt a déjà des tags de version

Le cadrage indique qu'aucun dépôt n'en a. Si ce n'est pas le cas pour celui-ci,
release-please repartirait de `0.1.0` et écraserait l'historique de versions.
Amorcer d'abord en ajoutant à `.github/workflows/ci.yml`, sous `with:` du job
`main` :

```yaml
      # À retirer après la première Release PR correctement numérotée.
      last_release_sha: <sha du commit de la dernière release>
```

---

## §2 — Copier les fichiers du template

Depuis la racine du dépôt à migrer, avec `<lang>` valant `rust`, `node` ou
`python` :

```bash
CI=/chemin/vers/RociaDB-ci
cp -r "$CI/templates/<lang>/." .
cp "$CI/templates/common/renovate.json" .
```

Ce que cela dépose :

| Fichier | Rôle | Négociable ? |
|---|---|---|
| `.github/workflows/ci.yml` | Câblage des deux phases | Non — GitHub ne découvre les workflows que dans le dépôt |
| `.github/workflows/pr-title.yml` | Lint du titre de PR | Non — déclencheur `edited` distinct |
| `renovate.json` | Étend le preset partagé | Non |
| `.config/nextest.toml` *(Rust)* | Profil `ci` produisant le JUnit | Non — nextest le lit dans l'arbre de travail |
| `Dockerfile` | Assemblage de l'image | Oui, à adapter — mais **sans jamais ajouter de `RUN`** |

⚠️ Les deux fichiers de workflow portent un bloc `permissions` **par job**, en
plus du `permissions: {}` en tête de fichier. Ce n'est pas décoratif : un
workflow appelé ne peut jamais demander plus que ce que son appelant lui
accorde, et un stub écrit à la main sans ces blocs est **refusé au chargement**,
avec un message qui ne dit pas quel appelant corriger.

Puis ouvrir `ci.yml` et régler les interrupteurs :

```yaml
      runs_on: rocia2        # ubuntu-latest si le dépôt est public
      sonar: true            # dépôts privés uniquement (instance sur le tailnet)
      publish_crate: true    # ou publish_npm / publish_pypi
      docker: true           # si le dépôt est livré en image
      squash_tm: true        # une fois l'instance Squash TM en place
```

### 2.1 Rust — interrupteurs et prérequis

| Input | Quand l'activer |
|---|---|
| `protoc: true` | Un `build.rs` compile des `.proto` (tonic). C'est la seule dépendance de la chaîne Rust que cargo n'installe pas : sans elle, le crate ne compile pas |
| `postgres: postgres:18-alpine` | La suite a besoin d'une base. Démarre **un** serveur pour tout le job et expose `DATABASE_URL`, `CI_POSTGRES_HOTE`, `CI_POSTGRES_PORT` et `CI_POSTGRES_CONTENEUR` |
| `postgres_initdb_args` | Locale et encodage de la base de test, si le tri compte |
| `gates_script` | Défaut `scripts/ci-gates.sh`, exécuté s'il existe et est exécutable. C'est là que vont les critères d'arrêt propres au dépôt |
| `binary_name` | Si le binaire ne porte pas le nom du dépôt |

Le dépôt doit fournir `.config/nextest.toml` — `cargo test` ne produit pas de
JUnit, `cargo nextest` si, et c'est ce que Squash TM consomme.

#### Un harnais qui monte ses propres conteneurs

Piège rencontré sur le premier dépôt migré, et qui se reposera sur tout projet
utilisant `testcontainers`.

**nextest exécute chaque test dans son propre processus.** Un harnais qui
démarre un conteneur par binaire de test via un `OnceCell` statique en démarre
alors **un par test** — des centaines, sur un runner persistant au disque
contraint.

Le harnais doit donc accepter un serveur fourni de l'extérieur, et ne démarrer
le sien que si aucun ne l'est — **et tomber** quand la CI n'en fournit qu'une
partie, ou n'en fournit pas du tout :

```rust
fn externe() -> Option<Self> {
    let lire = |nom| std::env::var(nom).ok();
    match (lire("CI_POSTGRES_HOTE"), lire("CI_POSTGRES_PORT"), lire("CI_POSTGRES_CONTENEUR")) {
        (Some(hote), Some(port), Some(docker)) => {
            let port = port.parse().expect("CI_POSTGRES_PORT n'est pas un port");
            Some(Self { _conteneur: None, docker, hote, port })
        }
        // En local : rien de fourni, le harnais démarre le sien.
        (None, None, None) if std::env::var_os("GITHUB_ACTIONS").is_none() => None,
        (None, None, None) => panic!("en CI sans serveur : posez `postgres:` dans le stub"),
        _ => panic!("CI à moitié configurée : les trois CI_POSTGRES_* vont ensemble"),
    }
}
```

La première version de cet extrait se rabattait en silence sur testcontainers
dès qu'une variable manquait ou qu'un port était illisible — et en CI, sans
`postgres:` dans le stub, chaque processus nextest montait alors un
PostgreSQL gardé dans un `static`, jamais retiré : des centaines de
conteneurs, et une suite verte. Trouvé sur les dépôts V2 le 24 septembre 2026.

Trois points s'ensuivent, et chacun a coûté une exécution rouge :

- toute méthode faisant `docker exec` doit viser un **identifiant stocké**, plus
  le handle testcontainers, qui n'existe pas en mode externe ;
- un compteur de bases `AtomicU32` est propre au processus : sur un serveur
  partagé, il faut y mêler `std::process::id()`, sinon deux tests concurrents
  réclament la même base ;
- la vérification du point Docker doit être sautée en mode externe.

Les identifiants de la base de CI sont ceux du module `postgres` de
testcontainers (`postgres`/`postgres`), précisément pour qu'un tel harnais
n'ait qu'une adresse à changer.

### 2.2 Scripts attendus (Node)

Le workflow appelle des scripts `package.json` plutôt que des outils en dur,
pour que chaque dépôt garde la main sur sa configuration :

```json
{
  "scripts": {
    "format:check": "prettier --check .",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test:ci": "vitest run --reporter=default --reporter=junit --outputFile.junit=junit.xml --coverage"
  }
}
```

`--reporter=default` d'abord : `--reporter=junit` seul **remplace** le rapport
de la console, et un test rouge ne s'y lit plus — il faut télécharger
l'artefact. Et la couverture doit produire `coverage/lcov.info`, que le
workflow téléverse et que Sonar lit : les rapports par défaut de Vitest n'en
font pas. Dans `vite.config.ts` (ou `vitest.config.ts`) :

```ts
test: { coverage: { reporter: ['text', 'lcov'] } }
```

### 2.3 Configuration attendue (Python)

Dans `pyproject.toml` : sections `[tool.ruff]`, `[tool.mypy]` et
`[tool.coverage.run]`. Ruff ne sait pas étendre une configuration distante, un
minimum de configuration locale est donc inévitable.

---

## §3 — Régler les paramètres du dépôt

Ces réglages ne sont pas des fichiers et ne peuvent pas être factorisés.

`Settings` → `General` → `Pull Requests` :
- cocher **Allow squash merging** uniquement ;
- décocher merge commits et rebase merging — c'est ce qui garantit que le titre
  de la PR devient le message de commit, donc que release-please le lit ;
- cocher **Automatically delete head branches**.

`Settings` → `Environments` → créer `release` :
- pour les dépôts publiant sur crates.io, npm ou PyPI, ajouter un
  **required reviewer**. Ces publications sont irréversibles.

Pour un dépôt **public**, activer aussi `Settings` → `Code security` :
- CodeQL (default setup) ;
- Secret scanning et Push protection.

Enfin, vérifier que le dépôt est bien dans la portée des secrets d'organisation
dont il a besoin (§0.4).

Pour un dépôt sur `rocia2`, vérifier aussi que le runner **porte bien le label**
attendu par `runs_on`. `runs-on` n'apparie que des labels : le nom du runner
n'entre dans aucun appariement, et un job qui ne trouve personne reste en
`queued` vingt-quatre heures avant de dire quoi que ce soit. Voir
[`runner.md`](runner.md).

---

## §4 — Valider

1. Ouvrir une PR de test avec un titre conventionnel, par exemple
   `chore: câblage de la CI partagée`.
2. Vérifier que deux checks apparaissent : `pr / quality` et `title / pr-title`.
3. Les laisser passer au vert, puis merger en squash.
4. Sur `main`, vérifier que `release-please` ouvre une Release PR.
5. Merger la Release PR : le tag `v0.1.0` est créé, et les jobs `publish`,
   `docker` et `squash-tm` activés se déclenchent.

Si `release-please` n'ouvre pas de PR : le titre du commit de merge n'est
probablement pas conventionnel, ou l'App n'a pas accès au dépôt.

Si la Release PR n'a aucun check : l'App n'est pas utilisée — vérifier
`RELEASE_APP_ID` et `RELEASE_APP_PRIVATE_KEY`.

---

## Revenir en arrière

Supprimer `.github/workflows/ci.yml` et `pr-title.yml` du dépôt, et retirer ses
checks du ruleset d'organisation. Rien d'autre n'a été modifié dans le dépôt : les
tags et releases déjà produits restent valides.

---

## Quand le template évolue

Les dépôts consommateurs épinglent `@v1`, un tag **flottant**. Une correction
poussée sur `main` de `ci` ne les atteint pas tant que le tag n'a pas bougé :

```bash
git fetch origin && git tag -f v1 origin/main && git push -f origin v1
```

Symptôme quand on l'oublie : la correction semble sans effet, et l'exécution
rejoue exactement le même échec. La page d'une exécution indique sous
`referenced_workflows` le SHA réellement chargé — c'est le moyen le plus rapide
de le vérifier.

## Cas particuliers connus

**Une dépendance Python sans wheel aarch64.** Le job `docker` échoue à l'étape de
résolution par architecture. Deux issues : épingler une version disposant du
wheel, ou construire la branche arm64 sur un runner `ubuntu-24.04-arm` et
fusionner les manifestes. Le second cas n'est pas couvert par le template.

**Un workspace Cargo multi-crates à versionner indépendamment.** Le template
utilise le mode simple de release-please (une version par dépôt). Un versionnage
par crate demanderait le mode manifest, non implémenté — à traiter le jour où un
dépôt le demande.

**Des tests nécessitant un service externe.** Le cadrage indique qu'il n'y en a
pas. Si cela change, ajouter un bloc `services:` demandera une évolution du
workflow réutilisable, pas du dépôt.

**Un workspace Cargo dont la version vit dans `[workspace.package]`.** Le
`Cargo.toml` racine n'a alors pas de `[package]`, et rien ne garantit que la
stratégie `rust` de release-please sache y trouver la version à incrémenter.
Non vérifié à ce jour. Le repli est le mode manifest avec `extra-files`.

**Un premier run rouge n'est pas un échec de la migration.** Les étapes sont
chaînées en `!cancelled()` pour montrer tous les défauts d'un coup plutôt qu'un
par exécution. Sur un dépôt jamais passé par cette chaîne, attendre du rouge
sur `cargo fmt --all --check` et sur `clippy --all-targets --all-features
-D warnings`, plus sévères que ce qui se lance d'ordinaire en local. L'audit des
dépendances, lui, est en `continue-on-error` : il ne fait jamais échouer le job.
