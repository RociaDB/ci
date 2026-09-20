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

## Partage public / privé

| Dépôts | Runner |
|---|---|
| Publics | `ubuntu-latest` |
| Privés | `rocia2` |

Les dépôts publics ne touchent jamais `rocia2` : une PR issue d'un fork y
exécuterait du code arbitraire. Les minutes GitHub étant gratuites et illimitées
sur les dépôts publics, la règle ne coûte rien.

## Entretien

`maintenance-runner.yml` s'exécute le dimanche : `docker system prune`, purge du
registre cargo et suppression des répertoires `target` de plus de 14 jours. Il
affiche l'espace disque avant et après — c'est le signal à surveiller.

Si le disque sature malgré tout, la piste suivante est de réduire la rétention
des artefacts (actuellement 7 jours) avant de toucher aux caches.

## Durcissement à prévoir

Un runner persistant est *stateful* : un job peut polluer le cache du suivant.
Quand un deuxième runner arrivera, passer en `--ephemeral` avec des jobs en
conteneur. En attendant, la règle « les dépôts publics ne touchent pas `rocia2` »
est la protection principale.

Ne jamais utiliser `pull_request_target` combiné à un checkout du head de la PR :
c'est le moyen le plus direct d'exécuter du code de fork avec les secrets.
