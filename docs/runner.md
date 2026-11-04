# Runner self-hosted `rocia2`

## État

amd64, Docker et buildx installés, rustup, Node, pnpm et uv présents. **Moins de
50 Go de disque.** Un seul runner, donc **exécution sérialisée**.

L'outillage étant déjà en place, les actions de setup des workflows ne servent
que de garde-fou de version : elles ne réinstallent rien en pratique.

## Ce qui en découle dans les workflows

- **Un seul job par phase**, avec les gates en étapes chaînées. Des jobs
  parallèles se sérialiseraient de toute façon, en repayant chacun le checkout
  et le setup.
- **`concurrency` avec annulation sur les PR**, jamais sur `main` : chaque push
  sur le trunk doit être vu par release-please.
- **Pas de matrice sur les dépôts privés.** Les matrices sont réservées aux SDK
  publics, qui tournent sur des runners GitHub gratuits et illimités.
- **Cross-compilation plutôt que QEMU** pour le multi-arch. Émuler de l'aarch64
  pour compiler du Rust coûte 10 à 20×, intenable ici.

## Label, pas nom

`runs-on` n'apparie que des **labels**. Le nom d'un runner — celui qui s'affiche
dans `Settings` → `Actions` → `Runners` — n'entre dans aucun appariement.

Un runner ne porte par défaut que `self-hosted`, `Linux` et `X64`. Le label
attendu par les workflows doit donc être ajouté explicitement, à
l'enregistrement (`--labels rocia`) ou depuis sa fiche dans l'interface.

Le label retenu décrit un **pool**, pas une machine : un second runner qui
rejoint le pool reçoit le même label et prend sa part du travail sans qu'aucun
des dépôts consommateurs ne bouge. Un label nommé d'après la machine obligerait
à modifier les 14 dépôts le jour où elle change.

## Partage public / privé

| Dépôts | Runner |
|---|---|
| Publics | `ubuntu-latest` |
| Privés | `rocia2` |

Les dépôts publics ne touchent jamais `rocia2` : une PR issue d'un fork y
exécuterait du code arbitraire. Les minutes GitHub étant gratuites et illimitées
sur les dépôts publics, la règle ne coûte rien.

## Entretien

`maintenance-runner.yml` s'exécute le dimanche. Par défaut il fait un ménage
**sélectif** (voir la section suivante) ; avec `CI_MENAGE_COMPLET=true`, il
ajoute le ménage d'une machine dédiée : `docker system prune`, volumes anonymes
abandonnés, purge du registre cargo. Dans les deux cas il supprime les
répertoires `target` de plus de 14 jours dans le travail du runner et affiche
l'espace disque avant et après — c'est le signal à surveiller.

Si le disque sature malgré tout, la piste suivante est de réduire la rétention
des artefacts (actuellement 7 jours) avant de toucher aux caches.

## Un runner sur un poste de travail

Quand le runner tourne sur la machine de quelqu'un (sous son compte, avec son
Docker et son `HOME`), le ménage ne doit retirer que ce que la CI a créé. C'est
le comportement par défaut de `maintenance-runner.yml`.

**Ce que le ménage sélectif fait.** Les conteneurs que la CI lance portent
l'étiquette `rociadb.ci=true` (aujourd'hui, le `ci-postgres` de
`_rust-quality.yml`). Chaque dimanche, il retire ceux qui sont arrêtés, avec
leurs volumes anonymes, puis les volumes étiquetés `rociadb.ci=true` que plus
aucun conteneur n'utilise, et enfin les répertoires `target` de plus de 14 jours
dans le travail du runner (le parent de `$RUNNER_WORKSPACE`, rien d'autre).

**Ce qu'il ne fait pas.** Aucun `docker system prune`, aucun `docker volume
prune` sans filtre, aucun `docker builder prune`, rien sous `~/.cargo`. Il ne
touche pas aux conteneurs en marche, ni à ceux que les suites de test créent
(testcontainers) ou que des actions tierces démarrent : ils n'ont pas
l'étiquette. Le cache de construction de buildx n'est pas visé non plus : le
constructeur vient de `docker/setup-buildx-action`, qui le démonte lui-même en
fin de job, et le cache de couches est celui de GitHub (`type=gha`).

**Une machine dédiée.** Pour retrouver le ménage complet (toutes les images
inutilisées de plus d'une semaine, tous les volumes anonymes abandonnés, les
sources et archives du registre cargo non lues depuis 30 jours), poser la
variable `CI_MENAGE_COMPLET` à `true` dans les variables du dépôt `ci` ou de
l'organisation (`Settings` → `Secrets and variables` → `Actions` → `Variables`).
À ne faire que si plus rien d'autre n'utilise ce Docker ni ce `~/.cargo`.

**Ce qui reste partagé avec le poste**, à titre d'information : le `~/.cargo`
de l'utilisateur (les jobs y alimentent le registre, et `taiki-e/install-action` y
dépose cargo-nextest, cargo-llvm-cov et cargo-deny) ; son `~/.rustup`, que
`dtolnay/rust-toolchain` met à jour et auquel il ajoute des toolchains ; les
images que les jobs tirent (`postgres`, les images de base des `Dockerfile`),
qui s'ajoutent à celles de ses autres projets ; et son Docker rootless, donc
le port `127.0.0.1:5432` que le `ci-postgres` occupe le temps d'une
exécution. Rien de cela n'est nettoyé par défaut.

## Durcissement à prévoir

Un runner persistant est *stateful* : un job peut polluer le cache du suivant.
Quand un deuxième runner arrivera, passer en `--ephemeral` avec des jobs en
conteneur. En attendant, la règle « les dépôts publics ne touchent pas `rocia2` »
est la protection principale.

Ne jamais utiliser `pull_request_target` combiné à un checkout du head de la PR :
c'est le moyen le plus direct d'exécuter du code de fork avec les secrets.

## Un job reste en `queued`

Un job qui ne trouve aucun runner correspondant n'échoue pas : il attend, et
GitHub ne l'abandonne qu'au bout de 24 heures, sur « no runner matching the
labels ». Inutile de patienter — c'est toujours l'une de ces quatre causes.

| Constat dans `Settings` → `Actions` → `Runners` | Cause | Correction |
|---|---|---|
| Le runner y figure et est `Idle` | Le label demandé n'est pas porté par le runner — souvent son **nom** confondu avec un label | Ajouter le label sur sa fiche |
| Le runner y figure et est `Idle`, et le label est bon | Le dépôt n'est pas dans le périmètre du runner group | `Runner groups` → **Repository access** |
| Le runner est `Offline` | Le service ne tourne plus sur la VPS | `sudo systemctl status 'actions.runner.*'` |
| Le runner est absent de la liste de l'organisation | Il a été enregistré au niveau d'un dépôt, et ne sert que celui-là | Le réenregistrer au niveau organisation |

Pour séparer « la CI est-elle correcte ? » de « le runner est-il joignable ? »,
basculer temporairement le `runs_on` du dépôt sur `ubuntu-latest` : les runners
GitHub ont Docker, donc protoc, le PostgreSQL de test et testcontainers s'y
comportent de la même manière.
