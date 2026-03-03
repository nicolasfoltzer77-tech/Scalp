# FSM req_step / done_step — flux gest ↔ follower ↔ opener/closer ↔ exec

## TL;DR

- Oui: **`exec.py` est le seul composant qui incrémente le `step` canonique** (`step = step + 1`).
- Les autres services **propagent / ACK** ce step via leurs transitions de statut.
- Côté `follower`, le verrou d'autorisation d'action est: **`req_step == done_step`**.
- Ton intuition `f.step = g.step - 1` est **souvent vraie pendant un `*_req` en vol**, mais ce n'est pas l'invariant principal (et ce n'est pas vrai en régime stable `follow`).

## Source canonique du step

Dans `exec.py`, lorsqu'un ordre est exécuté, la ligne `exec` passe en `done` avec:

- `step = step + 1`
- `done_step = step + 1`

Donc le nouveau step canonique est produit ici. Les autres modules ne font pas `+1` sur `step`; ils recopient/ACK. 

## Descente d'une décision follower (REQ)

### 1) follower décide une action

Depuis `follow`, `follower_decide.py` fait:

- `status -> pyramide_req | partial_req | close_req`
- `req_step = req_step + 1`
- **ne modifie pas `step` follower** (invariant explicite dans le code)

### 2) gest ingère la requête follower

`gest.py` lit `follower` en `*_req` et pousse la demande en `gest`.
Le flux miroir peut porter `gest.step = follower.req_step` (voir `gest_from_follower.py`), ce qui matérialise le step demandé côté orchestration.

### 3) opener/closer ingèrent depuis gest

- `opener` pour `open/pyramide`
- `closer` pour `partial/close`

Ils créent des lignes `*_stdby`/`open` pour `exec` en **copiant le step reçu**, sans incrément canonique.

## Exécution et remontée ACK (DONE)

### 4) exec exécute

`exec.py` exécute au marché puis:

- `status='done'`
- `step = step + 1`
- `done_step = step + 1`

C'est le **seul endroit canonique** où le step avance.

### 5) opener/closer ACK depuis exec

Exemple `opener_from_exec.py`:

- lit `step_new = done_step (ou step)`
- calcule `step_done = step_new - 1`
- ACK la ligne opener du step précédent vers `*_done` et la repositionne en `step_new`

=> c'est bien une remontée ACK, pas une nouvelle incrémentation métier locale.

### 6) gest ACK depuis opener/closer

`gest_from_opener.py` et `gest_from_closer.py` font passer:

- `*_req -> *_done`
- en recopiant le step/infos d'exécution

### 7) follower se resynchronise

Deux mécanismes:

- `follower_fsm_sync.py`:
  - lit `gest.status` pour revenir en `follow` quand `*_done` est observé
  - recopie `step = g.step`
- `follower_sync_steps.py`:
  - lit `MAX(done_step)` depuis `exec`
  - met à jour `follower.done_step`

Le garde FSM (`follower_fsm_guard.py`) autorise une nouvelle décision seulement si `req_step == done_step`.

## Invariants pratiques à vérifier

### Invariant A (canonique, recommandé)

- `req_step >= done_step`
- en `follow`: `req_step == done_step`
- en `*_req`: `req_step == done_step + 1` (cas nominal mono-action)

### Invariant B (step local follower)

- en `follow` stable: `f.step == g.step`
- pendant un `*_req` en vol: `f.step` peut rester à l'ancien ACK alors que `g.step` reflète déjà la demande
  - donc souvent `f.step == g.step - 1`
  - mais ce n'est **pas** l'unique vérité (retries, rattrapages, flux legacy)

## Réponse à ta phrase finale

> « s’il y a une vérification à faire lors de la remontée ce serait : f.step = g.step-1 »

- **Partiellement vrai**, mais seulement comme heuristique en phase `*_req` in-flight.
- La vérification robuste pour éviter les blocages est:
  - `f.req_step == f.done_step` avant de lancer une nouvelle décision,
  - et monotonicité `done_step` (source de vérité: `exec`).

C'est exactement la logique implémentée aujourd'hui dans `follower_fsm_guard.py`, `follower_decide.py`, `follower_fsm_sync.py`, `follower_sync_steps.py`.
