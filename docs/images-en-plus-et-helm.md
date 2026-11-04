# Images en plus et charts Helm

Deux ajouts **facultatifs**. Un dépôt qui n'active ni l'un ni l'autre ne voit
aucune différence : `extra_images` vaut `'[]'` par défaut, et les workflows Helm
ne sont appelés que par les dépôts qui les câblent.

## Des images en plus dans `_rust-main.yml`

Pour un dépôt dont l'espace de travail Cargo produit plusieurs binaires livrés
chacun dans leur image, par exemple le service (`binary_name`, l'image
principale) et un agent qui a sa propre version.

```yaml
  main:
    with:
      docker: true
      binary_name: orchestrateur
      extra_images: >-
        [{"binary": "rocia-agent",
          "suffix": "agent",
          "version_from": "bin/agent/Cargo.toml",
          "dockerfile": "bin/agent/Dockerfile.ci"}]
```

| Clé | Rôle |
|---|---|
| `binary` | Nom du binaire Cargo, tel que `cargo build` le produit |
| `suffix` | Image `ghcr.io/<organisation>/<dépôt>-<suffix>` |
| `version_from` | `Cargo.toml` dont le `[package]` porte `version = "X.Y.Z"` (pas `version.workspace = true`) |
| `dockerfile` | Dockerfile de l'image, relatif à la racine du dépôt |

Ce qui se passe, quand une version du dépôt est créée par release-please
(`docker: true` requis) :

1. Le job `docker` compile comme avant, une fois, les deux architectures : cargo
   construit déjà tous les binaires de l'espace de travail. Il copie en plus
   chaque `binary` en `dist/amd64/<binary>` et `dist/arm64/<binary>` (à côté de
   `dist/<arch>/app`, sans collision) et les transmet au job suivant.
2. Le job `docker-extra`, une instance par entrée, lit la version dans
   `version_from`, construit l'image pour les deux architectures et la pousse
   étiquetée `X.Y.Z`, `X.Y` et `X` — jamais `latest`.
3. **Si l'étiquette `X.Y.Z` existe déjà sur ghcr.io, rien n'est poussé** : une
   version de l'image qui n'a pas changé ne se republie pas. L'étiquette est
   immuable. L'image est donc étiquetée de sa version à elle, pas de celle du
   dépôt, et un dépôt qui sort la 0.3.0 peut très bien laisser l'agent à 0.9.0.

Le Dockerfile suit le même contrat que `templates/rust/Dockerfile` : **aucun
`RUN`**, il ne fait que copier. Le contexte est la racine du dépôt.

```dockerfile
FROM gcr.io/distroless/static-debian12:nonroot
ARG TARGETARCH
COPY dist/${TARGETARCH}/rocia-agent /usr/local/bin/rocia-agent
USER nonroot:nonroot
ENTRYPOINT ["/usr/local/bin/rocia-agent"]
```

Les mêmes purges que l'image principale s'appliquent à chaque image en plus
(versions non taguées, puis `image_retention`).

## Les charts Helm

Deux workflows réutilisables, au modèle des autres langages, et un gabarit :
`templates/helm/` (`ci.yml`, `pr-title.yml`), plus `templates/helm-manifeste/`
si le dépôt a plusieurs charts à versionner chacun.

| Workflow | Job | Fait |
|---|---|---|
| `_helm-quality.yml` | `quality` | Pour chaque chart : `helm lint` puis `helm template`, avec les valeurs par défaut et avec chaque fichier de `values_files` |
| `_helm-main.yml` | `quality` | Le même gate, rejoué sur `main` |
| | `release-please` | Calcule la version, ouvre la Release PR |
| | `publish` | À la création d'une release : `helm package` et `helm push` de chaque chart vers `oci://ghcr.io/<organisation>/charts` |

Entrées (`_helm-quality.yml` ; `_helm-main.yml` les reprend, plus `release_type`) :

| Entrée | Défaut | Rôle |
|---|---|---|
| `runs_on` | `ubuntu-latest` | Runner |
| `charts` | `'["."]'` | Répertoires des charts : `'["charts/socle","charts/plateforme"]'` |
| `values_files` | `'[]'` | Fichiers de valeurs rendus en plus : `'["ci/banc.yaml"]'`. Chemins **relatifs à chaque chart** : un chart utilise ceux qu'il contient, un fichier qu'aucun chart ne contient est une erreur |
| `helm_version` | `v4.3.1` | Installé par `azure/setup-helm@v4` |
| `release_type` | `helm` | Stratégie de release-please. Vide : le mode manifeste |

Un chart qui déclare des `dependencies:` les reçoit par `helm dependency build`
avant le lint et la publication.

**Versions.** Avec `release_type: helm`, un chart à la racine, une version, un
tag `vX.Y.Z`. Avec plusieurs charts, `release_type: ''` : release-please lit
`release-please-config.json` et `.release-please-manifest.json` (copier
`templates/helm-manifeste/` et adapter les chemins), chaque chart a sa version
et son tag (`socle-v0.2.0`). `publish` s'exécute dès qu'une release existe et
pousse tous les charts de la liste, **sauf ceux dont la version est déjà dans le
registre** : la version d'un chart est immuable.

**Droits.** Le job appelant doit accorder `contents: read` et `packages: write`
(le gabarit le fait). La connexion à ghcr.io utilise le `GITHUB_TOKEN`.

**Rattacher les charts au dépôt.** Helm écrit l'annotation
`org.opencontainers.image.source` à partir du premier élément de `sources:` de
`Chart.yaml` ; sans elle, ghcr.io ne relie pas le paquet au dépôt et le
`GITHUB_TOKEN` ne peut pas le mettre à jour. Mettre
`sources: [https://github.com/RociaDB/<dépôt>]` dans chaque chart.

**Mise en service.** Les workflows s'appellent en `@v1` : tant que l'étiquette
`v1` n'a pas été déplacée sur un commit qui les contient, un dépôt qui les
appelle échoue au chargement (voir « Quand le template évolue » dans
`onboarding.md`).
