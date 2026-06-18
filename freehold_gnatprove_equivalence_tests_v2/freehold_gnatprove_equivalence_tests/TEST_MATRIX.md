# Test Matrix: GNATprove → Freehold Proof Equivalence

| Gruppe | Zweck | Positiv | Negativ | Status |
|---|---|---:|---:|---|
| 01_contract_overflow | Integer.Last Overflow durch fehlende Precondition | 1 | 1 | aktiv |
| 02_array_bounds | Array-Indexbereich allgemein | 1 | 1 | aktiv |
| 03_loop_invariant | Postcondition über Schleife nur mit Invariante beweisbar | 1 | 1 | aktiv |
| 04_runtime_checks | Division by zero, Index, Overflow, Natural/Range-Konversion | 1 | 1 | aktiv |
| 05_assertions | `check` / Assertion nur mit Precondition beweisbar | 1 | 1 | aktiv |
| 06_callsite_precondition | Verletzung einer requires-Bedingung am Aufrufort | 1 | 1 | aktiv |
| 07_integer_underflow | Integer.First Underflow | 1 | 2 | aktiv |
| 08_array_lower_upper_bounds | Lower- und Upper-Bound getrennt | 1 | 2 | aktiv |
| 09_record_updates | Feldupdate, `old(...)`, unbeabsichtigte Feldänderung | 1 | 2 | aktiv |
| 10_frame_aliasing_future | Frame Conditions und mutable Aliasing | 1 | 2 | aktiv |

Aktive Dateien enden auf `.fh`.
Pending-Dateien enden auf `.pending.fh` und werden vom Runner standardmäßig übersprungen.
