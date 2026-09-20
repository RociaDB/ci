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

Puis ouvrir `ci.yml` et régler les interrupteurs :

```yaml
      runs_on: rocia2        # ubuntu-latest si le dépôt est public
      sonar: true            # dépôts privés uniquement (instance sur le tailnet)
      publish_crate: true    # ou publish_npm / publish_pypi
      docker: true           # si le dépôt est livré en image
      squash_tm: true        # une fois l'instance Squash TM en place
```

### 2.1 Scripts attendus (Node)

Le workflow appelle des scripts `package.json` plutôt que des outils en dur,
pour que chaque dépôt garde la main sur sa configuration :

```json
{
  "scripts": {
    "format:check": "prettier --check .",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test:ci": "vitest run --reporter=junit --outputFile=junit.xml --coverage"
  }
}
```

### 2.2 Configuration attendue (Python)

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
