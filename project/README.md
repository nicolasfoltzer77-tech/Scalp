SCALP — Architecture & Contracts

Ce projet implémente un moteur de scalping distribué, orchestré par une FSM globale
et des bases SQLite cloisonnées (1 writer strict par DB).

Ce document définit les règles NON NEGOCIABLES du système.

==================================================
1. PRINCIPES FONDAMENTAUX
==================================================

SQLITE
- 1 DB = 1 writer strict
- Tous les autres processus accèdent en lecture seule
- Communication inter-process par SELECT read-only ou VIEWS
- Pas de bus
- Pas de ATTACH DATABASE

FSM
- FSM globale et canonique
- Le diagramme FSM fait foi
- Aucun état implicite
- Aucune décision distribuée

==================================================
2. ROLES ET RESPONSABILITES
==================================================

ROLE       DECIDE   ECRIT DANS        LIT DEPUIS
------------------------------------------------
follower   OUI      follower.db      gest.db
gest       NON      gest.db          follower, opener, closer, exec
opener     NON      opener.db        gest, exec
closer     NON      closer.db        gest, exec
exec       NON      exec.db          opener, closer
recorder   NON      recorder.db      exec, gest

Règles clés :
- follower est le SEUL décideur
- gest est un pivot passif
- exec est une machine déterministe
- recorder est une archive finale (jamais purgée)

==================================================
3. FSM — CYCLE GLOBAL (RESUME)
==================================================

armed -> fire -> open_stdby -> open_done -> follow

follow -> pyramide_req -> pyramide_stdby -> pyramide_done -> follow

follow -> partial_req -> partial_stdby -> partial_done -> follow

follow -> close_req -> close_stdby -> close_done -> recorded

==================================================
4. BASES DE DONNEES
==================================================

Emplacement :
project/data/*.db

ATTENTION :
Les bases SQLite ne font PAS partie du repository Git.
Elles existent uniquement en local / prod.

==================================================
5. SCHEMA DE REFERENCE
==================================================

Fichier canonique :
project/schema_ref.sql

Règles :
- Généré localement à partir des DB réelles
- Source de vérité structurelle
- Toute évolution DB implique :
  1. Modification réelle des DB
  2. Exécution du générateur
  3. Commit de schema_ref.sql

Générateur :
project/scripts/gen_schema_ref.sh

- Déterministe
- Jamais exécuté en CI
- Usage local / prod uniquement

==================================================
6. CI (GITHUB ACTIONS)
==================================================

Principes :
- Aucune dépendance aux DB runtime
- Aucune génération en CI
- Vérifications passives uniquement

Checks actifs :

Schema Reference Guard
- Vérifie que schema_ref.sql n’est pas modifié implicitement
- Bloque toute dérive silencieuse du schéma

FSM Passive Audit
- Exécuté en CI
- SKIP automatique si DB absentes
- Actif en local / prod avec DB réelles

==================================================
7. AUDITS DISPONIBLES
==================================================

Audit FSM (passif)
Commande :
python project/tools/fsm_audit.py

- Vérifie les invariants FSM
- Read-only
- CI-safe

Audit SQLite (runtime)
Commande :
python project/tools/sqlite_audit.py project/data/*.db

- Vérifie single-writer, tables, vues
- Hors CI
- Usage OPS / local uniquement

==================================================
8. REGLES DE CONTRIBUTION (OBLIGATOIRES)
==================================================

- Pas de commit direct sur main
- Pull Request obligatoire
- CI verte obligatoire
- Pas de refactor non demandé
- Pas de breaking change
- Modifications ADDITIVES uniquement

==================================================
9. REGLE D’OR
==================================================

Ce qui n’est pas dans la FSM canonique
ou dans schema_ref.sql
N’EXISTE PAS.

