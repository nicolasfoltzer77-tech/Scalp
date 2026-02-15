# SCALP — Règles de développement et de contribution

Ce document est **contractuel**.
Toute Pull Request non conforme est rejetée sans discussion.

---

## 1. Règles générales de modification
- Modifications **strictement additives**
- Aucun refactor (même local)
- Aucune suppression de code
- Aucune modification de logique existante
- Aucun changement de signature
- Aucun breaking change
- Aucun TODO laissé
- Scope strictement limité à la demande

---

## 2. Invariants SQLite (non négociables)
- **Un seul writer par base SQLite**
- **Une seule table par base**
- Accès inter-processus **lecture seule**
- Communication inter-DB **uniquement via vues**
- Les vues :
  - matérialisent les données
  - sont read-only
  - utilisées uniquement via `SELECT ... WHERE ...`
- Interdictions absolues :
  - `ATTACH DATABASE`
  - bus / queue / IPC externe
  - écriture cross-DB

Objectif : stabilité, absence de lock, comportement déterministe.

---

## 3. Architecture FSM Scalp
- FSM **globale** et canonique
- Le diagramme FSM fait foi
- Le code doit se conformer au diagramme, jamais l’inverse

### Rôles stricts
- follower
- gest
- opener
- closer

### Règles
- Aucune transition existante ne doit être modifiée
- Aucun contournement de la FSM
- Alertes critiques obligatoires si violation potentielle

---

## 4. Workflow Git / Pull Requests
- Aucun commit direct sur `main`
- Toute modification passe par une PR
- 1 PR = 1 intention claire
- PR petites, lisibles, auditables

### Checklist obligatoire
Voir le template PR fourni dans :
`.github/pull_request_template.md`

---

## 5. Règle finale
> **En cas de doute, la PR est NON conforme.**
