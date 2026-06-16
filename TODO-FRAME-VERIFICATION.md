# TODO: Frame & Aliasing Verification (Post-Bootstrap Milestone)

This todo list outlines the remaining steps to implement complete, mathematically sound Frame and Aliasing checks in Freehold, inspired by SPARK Ada and GNATprove principles.

---

## 1. Roadmap & Implementation Steps

- [x] **Schritt 1: Syntax & Parser-Erweiterung (Syntax)**
  - [x] EBNF in `freehold.lark` adaptiert für optionales `modifies_clause`.
  - [x] Syntax-String in `grammar_inline.py` synchronisiert.
  - [x] AST-Knoten `RoutineDecl` in `ast.py` um `modifies_specs` Feld ergänzt.
  - [x] Parser-Mapping `modifies_clause` in `parser_legacy.py` implementiert.
  - [x] Dateien der Testsuite `10_frame_aliasing_future` von `.pending.fh` nach `.fh` umbenannt.
  - [x] Änderungen sicher im lokalen Git committed.

- [ ] **Schritt 2: Field-Level Dependency Tracking (Semantik)**
  - [ ] Methode `collect_mutated_vars` im `Verifier` (`verifier.py`) erweitern, um alle Ziel-Zuweisungspfade (`AssignStmt`, `FieldAssignStmt`, `IndexAssignStmt`) zu analysieren.
  - [ ] Sicherstellen, dass jede Schreibmodifikation auf Feldebene (z. B. `acc.balance := val`) im `modifies`-Vertrag der Routine deklariert ist.
  - [ ] Erzeugung von statischen Typprüfungsfehlern (`TypeCheckError`), wenn nicht deklarierte Felder modifiziert werden.

- [ ] **Schritt 3: SMT-Frame-Stabilitäts-Axiome (Symbolic & Z3)**
  - [ ] Generierung impliziter Postconditions in `symbolic.py` für alle Felder eines veränderten Records, die *nicht* in `modifies` enthalten sind:
    $$\forall f \notin \text{modifies}.\ S_{new}.f = S_{old}.f$$
  - [ ] Mathematische Absicherung durch Z3, dass der Zustand unbeteiligter Konten oder Datenfelder über Prozedurgrenzen hinweg absolut stabil bleibt.

- [ ] **Schritt 4: Parameter-Aliasing-Prüfung**
  - [ ] Statische Überprüfung an allen Prozedur-Aufrufstellen (`CallStmt`), ob derselbe veränderbare Record fälschlicherweise an mehrere Parameter übergeben wird (Aliasing-Schutz).
  - [ ] Abwehr von Laufzeit-Anomalien durch getrennte Speicherannahmen im Solver.

- [ ] **Schritt 5: Test-Aktivierung & Integration**
  - [ ] Fehlerbehebung der verbleibenden negativen Szenarien in `10_frame_aliasing_future`:
    - `neg_frame_update_undeclared_field.fh`
    - `neg_alias_two_mutable_parameters.fh`
  - [ ] Einbindung des Sprachmoduls `10_frame_aliasing_future` in die automatische Test-Suite und Härten über den Selbst-Hoster.
