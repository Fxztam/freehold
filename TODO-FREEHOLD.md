# TODO Freehold: Verification & Roadmap (GNATprove / SPARK Ada Parity)

> [!IMPORTANT]
> **Grammar & Parser Source of Truth:**
> - `freehold/grammar/freehold.lark` is the executable Lark parser grammar and is the primary source of truth for the parser.
> - `freehold/core/grammar_inline.py` (which defines `FREEHOLD_GRAMMAR`) contains the inline version of the Lark grammar and must always be kept in absolute synchronization.
> - The various EBNF files under `freehold/grammar/freehold*.ebnf` are design specifications, documentation, or visualization aids, and must **not** be confused with the active Lark/inline grammar definition.

This document outlines the strategic alignment of Freehold's formal verification capabilities with GNATprove (SPARK Ada), highlighting what has been successfully completed in V1 and what is parked for V2/V3.

---

## 1. Flow Analysis (Datenfluss-Analyse)

| GNATprove Feature | Status in Freehold (V1 Erledigt) | Offen / Geparkt (V2/V3) |
| :--- | :--- | :--- |
| **Variablen-Initialisierung** | **Vollständig gelöst**: Der Verifier/Semantic-Analyzer prüft streng die Zuweisungsreihenfolge (`let` / `:=`). Die Nutzung nicht-initialisierter Variablen führt zu Compilerfehlern. | *Keine offenen V1-Punkte.* |
| **Seiteneffekte erkennen** | **Vollständig gelöst**: Strikte Trennung zwischen reinen Funktionen (`function`, seiteneffektfrei, keine Zustandsänderungen) und Prozeduren (`procedure`). | *Keine offenen V1-Punkte.* |
| **`Global`- und `Depends`-Aspekte** | **Vollständig gelöst**: Unterstützt `global` und `depends` Kontrakte, transitive Globals-Propagation, Alias-Prüfungen auf Parametern und Feldebene (Record Fields). | *Keine offenen V1-Punkte.* |

---

## 2. Proof (Beweis-Analyse)

| GNATprove Feature | Status in Freehold (V1 Erledigt) | Offen / Geparkt (V2/V3) |
| :--- | :--- | :--- |
| **Verification Conditions (VCs)** | **Implementiert**: Der Freehold-Verifier generiert mathematische VCs aus AST-Knoten für Vorbedingungen, Nachbedingungen und Schleifen. | *Keine offenen V1-Kernsachen.* |
| **SMT-Solver Anbindung** | **Vollständig gelöst**: Direkte Anbindung des SMT-Solvers **Z3** sowie alternative Solver (CVC5) über multi-solver Sequenzen und konfigurierbare Timeouts via Umgebungsvariablen. Warum3-style Übersetzung in `whyml_codegen.py` implementiert. | *Keine offenen V1-Kernsachen.* |
| **Prä- & Postbedingungen** | **Vollständig gelöst**: `requires` und `ensures` Verträge werden sowohl bei Routine-Deklarationen als auch an allen Aufrufstellen (Call-sites) und bei `ReturnStmt` (mit Substitution) geprüft. | *Keine offenen V1-Kernsachen.* |
| **Schleifeninvarianten** | **Vollständig gelöst**: `invariant`-Ausdrücke in Schleifen werden genutzt, um Indizes und Wertegrenzen mathematisch zu beweisen (wichtig für den compiler-core). | *Keine offenen V1-Kernsachen.* |
| **Typinvarianten & Subtypen** | **Array-Bounds & Subtypes**: Mathematischer Nachweis der Out-of-Bounds-Sicherheit (`0 <= index < size`) und statische Subtyp-Wertebereiche (`Integer range A .. B`) sind vollständig aktiv. | *Keine offenen V1-Kernsachen.* |
| **Abort / Exception Paths** | **Abort-Implikationsprüfung**: Aborts werden typisiert, als Go-`error` zurückgegeben und formal im SMT-Solver verifiziert, dass deklarierte Aborts unter den Vorbedingungen nicht verletzt werden. | *Keine offenen V1-Kernsachen.* |
