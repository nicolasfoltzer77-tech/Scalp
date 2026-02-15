# ✅ PR CHECKLIST — SCALP (OBLIGATOIRE)

> Toute PR non strictement conforme est rejetée sans discussion.

---

## 1. Nature de la modification
- [ ] Modification **strictement additive**
- [ ] Aucun refactor (même local)
- [ ] Aucune suppression de code
- [ ] Aucune modification de logique existante
- [ ] Aucun changement de signature (fonctions / classes / API)
- [ ] Aucun breaking change
- [ ] Aucun TODO laissé
- [ ] Scope strictement limité à la demande initiale

---

## 2. Conformité SQLite (invariants forts)
- [ ] **Un seul writer** par base SQLite
- [ ] **Une seule table** par base
- [ ] Aucune écriture cross-DB
- [ ] Accès inter-DB **lecture seule**
- [ ] Communication inter-DB **uniquement via vues**
- [ ] Utilisation exclusive de `SELECT ... WHERE ...` sur vues
- [ ] Aucun `ATTACH DATABASE`
- [ ] Aucun bus / queue / IPC externe

---

## 3. FSM / Architecture Scalp
- [ ] FSM globale respectée
- [ ] Aucun contournement FSM
- [ ] Rôles respectés :
  - follower
  - gest
  - opener
  - closer
- [ ] Aucune transition FSM existante modifiée
- [ ] Alertes critiques présentes si applicable
- [ ] Conformité stricte au diagramme FSM de référence

---

## 4. Code Python
- [ ] Compatible avec la version Python existante
- [ ] Aucun changement silencieux de comportement
- [ ] Aucun effet de bord hors scope
- [ ] Ajouts clairement isolés
- [ ] Code existant laissé intact

---

## 5. Livraison
- [ ] Fichiers **complets uniquement**
- [ ] Aucun extrait partiel
- [ ] Aucun code volontairement omis
- [ ] Format respecté

---

## 6. Verdict
- [ ] ✅ Conforme → merge autorisé
- [ ] ❌ Non conforme → PR rejetée

---

### Règle finale
**En cas de doute, la PR est NON conforme.**
