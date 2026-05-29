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
| **`Global`- und `Depends`-Aspekte** | **Modularitätsvertrag**: Globale Variablenzugriffe über Modulgrenzen hinweg sind streng über `import`/`exposing` limitiert. | **Geparkt**: Feingranulare Aspekte zur Spezifikation von Informationsfluss-Abhängigkeiten (z. B. *"Ausgabe X hängt nur von Eingabe Y ab"*) sind für V1 nicht vorgesehen. |

---

## 2. Proof (Beweis-Analyse)

| GNATprove Feature | Status in Freehold (V1 Erledigt) | Offen / Geparkt (V2/V3) |
| :--- | :--- | :--- |
| **Verification Conditions (VCs)** | **Implementiert**: Der Freehold-Verifier generiert mathematische VCs aus AST-Knoten für Vorbedingungen, Nachbedingungen und Schleifen. | *Keine offenen V1-Kernsachen.* |
| **SMT-Solver Anbindung** | **Implementiert**: Direkte Anbindung des SMT-Solvers **Z3** über das SMT-LIB v2 Format (`query.smt2`) zur automatischen Beweisführung. | **Geparkt**: Eine Why3-ähnliche Abstraktionsschicht zur Unterstützung alternativer Solver (CVC5, Alt-Ergo) ist geparkt; Z3 ist derzeit der exklusive Solver. |
| **Prä- & Postbedingungen** | **Vollständig gelöst**: `requires` und `ensures` Verträge werden sowohl bei Routine-Deklarationen als auch an allen Aufrufstellen (Call-sites) geprüft. | *Keine offenen V1-Kernsachen.* |
| **Schleifeninvarianten** | **Vollständig gelöst**: `invariant`-Ausdrücke in Schleifen werden genutzt, um Indizes und Wertegrenzen mathematisch zu beweisen (wichtig für den compiler-core). | *Keine offenen V1-Kernsachen.* |
| **Typinvarianten & Subtypen** | **Array-Bounds-Prüfung**: Mathematischer Nachweis der Out-of-Bounds-Sicherheit (`0 <= index < size`) ist vollständig aktiv. | **Geparkt**: Komplexe Subtypen mit Wertebereichen (wie Adas `subtype My_Range is Integer range 1 .. 10`) und deren automatische Invarianten-Prüfung sind geparkt. |
| **Abort / Exception Paths** | **Propagation**: Aborts werden typisiert und als Go-`error` zurückgegeben und geprüft. | **Geparkt**: Pfadsensitive Kontrollfluss-Beweise und logische Abort-Implikationsprüfungen (statische Verifikation, ob ein Abort-Pfad unter bestimmten Vorbedingungen jemals erreicht werden kann) sind geparkt. |
