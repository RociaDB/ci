# Secrets et variables d'organisation

Tous les secrets vivent au niveau de l'organisation, avec une **liste blanche de
dépôts** — jamais « tous les dépôts » par défaut.

## Règle de portée

Un secret d'organisation accessible à un dépôt **public** est lisible par tout
workflow de ce dépôt. Les instances SonarQube et Squash TM étant derrière
Tailscale, leurs secrets ne doivent jamais y être exposés — les dépôts publics
n'en ont de toute façon aucun usage, puisque leurs workflows tournent sur des
runners GitHub qui ne sont pas sur le tailnet.

## Inventaire

| Secret | Portée | Utilisé par |
|---|---|---|
| `RELEASE_APP_ID` | Tous les dépôts | release-please |
| `RELEASE_APP_PRIVATE_KEY` | Tous les dépôts | release-please |
| `SONAR_TOKEN` | **Dépôts privés uniquement** | Job `sonar` |
| `SONAR_HOST_URL` | **Dépôts privés uniquement** | Job `sonar` |
| `SQUASH_TM_URL` | **Dépôts privés uniquement** | Job `squash-tm` |
| `SQUASH_TM_TOKEN` | **Dépôts privés uniquement** | Job `squash-tm` |
| `CARGO_REGISTRY_TOKEN` | `rociadb-core-sdk-rust` | Job `publish` |
| `NPM_TOKEN` | `rociadb-core-sdk-ts` | Job `publish` (registre npmjs) |

## Ce qui n'a délibérément pas de secret

| Cible | Mécanisme | Pourquoi |
|---|---|---|
| PyPI | Trusted Publishing (OIDC) | Aucun jeton à stocker ni à faire tourner |
| npm public | Provenance + OIDC | Idem, et l'attestation est vérifiable publiquement |
| GHCR | `GITHUB_TOKEN` + `packages: write` | Portée au dépôt, expiré à la fin du job |
| Registre npm GitHub | `GITHUB_TOKEN` | Idem |

Pour PyPI, déclarer le publisher de confiance côté PyPI : organisation `RociaDB`,
dépôt, workflow `ci.yml`, environment `release`.

## Rotation

`CARGO_REGISTRY_TOKEN` et `NPM_TOKEN` sont les deux seuls secrets à faire
tourner. La clé privée de l'App se régénère depuis ses settings sans interrompre
les installations existantes.
