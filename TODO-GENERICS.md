# Spezifikations- und Anforderungsanalyse: Generische Routinen in Go-Codegen (Phase 2)
**Erstellungsdatum:** 14. Juni 2026

Dieses Dokument analysiert den aktuellen Implementierungsstand von generischen Routinen und Datentypen im Freehold-Compiler und definiert den detaillierten Umsetzungsplan für das Go-Backend.

---

## 1. Status Quo Analyse

Die Syntax und Semantik von Generics (Zusammenwirken von Typvariablen `$T`, `$U`, etc.) ist im Parser (`freehold.lark`) und im semantischen Verifier (`verifier.py`) bereits vollständig etabliert. Beide Phasen verifizieren Verwendungen generischer Funktionen und Strukturen einwandfrei.

Die Hürde liegt exklusiv im Go-Codegen-Backend (`go_codegen.py`). Dort löst die Erkennung von Generics im Haupt-Routine-Deklarationspfad folgende Fehlermeldung aus:
```python
if routine.type_params:
    self.unsupported(routine, "generic routines are not supported by Go codegen V1")
```

### Vorhandene Infrastruktur
Der Go-Codegen besitzt bereits eine wertvolle Grundlage für Generics in Form eines **Monomorphisierungs-Durchlaufs**:
* `monomorphize()` scannt den AST auf generische Strukturen und spezialisiert sie.
* `specialize_record()` und `specialize_routine()` erzeugen konkrete AST-Knoten (`RecordTypeDecl` und `RoutineDecl`) für jede gemutete Typkombination.
* Generierte Namen werden über `go_specialized_name_fragment` gebildet (z. B. `Value_Integer` oder `SomeRoutine_Integer`).

---

## 2. Architektonische Defizite & Konfliktpunkte

Trotz der starken Vorarbeit verbleiben einige architektonische Lücken, die gelöst werden müssen:

### a) Das Verteilungs- / Rekursionsproblem (Scan Phase)
* **Problem:** `monomorphize()` durchläuft bei den Scans der Statements (`visit_stmt`) und Ausdrücke (`visit_expr`) nicht transitiv alle importierten/referenzierten Module. 
* Wenn eine spezialisierte Routine `Routine_Integer` wiederum eine andere generische Routine `Helper<$T>` aufruft, muss diese transponierte Instanziierung sauber erfasst und der Scan-Warteschlange `pending_scans` hinzugefügt werden.

### b) Typsubstitution in Kontrakten
* **Problem:** In `specialize_routine` ([go_codegen.py](freehold/core/go_codegen.py#L800)) werden die Typübertragungen in den Contracts (`requires`, `ensures`, `aborts`) teilweise flach gehalten.
* Wenn Bedingungen wie `requires x is T` oder komplexe SMT-Ausdrücke verarbeitet werden, muss die vollständige AST-Substitution von `$T` zu konkreten Typen gewährleistet sein.

### c) Typ-Inferenz (`infer_type_args`) für Aufrufe
* **Problem:** Die Methode `infer_type_args` ([go_codegen.py](freehold/core/go_codegen.py#L661)) leitet Typen anhand von Calling-Argumenten ab. Dies ist fehleranfällig, wenn ungetypte numerische Literale (wie `42` oder `3.14`) übergeben werden.
* **Lösung:** Unterstützung der Inferenz durch engmaschigeres Matching mit den Typreferenzen des Verifiers oder den Go-Standardfallbackregeln (z.B. Fallback auf `Integer` bei leeren Inferenzgruppen).

---

## 3. Detaillierter Implementierungsfahrplan (Todo-Liste)

### Phase 1: Transitiven Monomorphisierungs-Scan absichern
- [ ] **Scan-Queue stabilisieren:** Sicherstellen, dass jeder Aufruf von `process_call` innerhalb einer spezialisierten Routine die generierten Instanzen sicher in `pending_scans` einreiht.
- [ ] **Importierte Generics:** Support für das Erfassen generischer Signaturen aus fremden Modulen (Cross-Module Inferenz) sicherstellen.
- [ ] **Erweiterte Typsubstitution:** Vervollständigen der Typsubstitution für komplexe Typkombinationen (z. B. verschachtelte `Result<Array<T, 5>, Error>`).

### Phase 2: Anpassung der Codegen pipeline
- [ ] **Monomorphisierte Routinen emittieren:** Den fehlerhaften Block entfernen und monomorphisierte Routinen als eigenständige, spezialisierte Go-Funktionen deklarieren:
  ```go
  // Original Freehold: function identity<T>(x: T) returns T is return x end identity
  // Generierter Go-Konstruktor:
  func Identity_Integer(x int64) int64 {
      return x
  }
  func Identity_String(x string) string {
      return x
  }
  ```
- [ ] **Call-Seiten umschreiben:** Bei jedem physischen Aufruf im Go-Code (`is_async`, `spawn`, `call_stmt`) den Funktionsnamen zu der spezialisierten Namensvariante umschreiben (z. B. `Identity_Integer(...)` statt `Identity(...)`).

### Phase 3: Validierung & Qualitätskontrolle
- [ ] Integrationstests für generische Funktionen (scalar, Record- und Array-Typen) in `tests/language_modules/` verankern.
- [ ] Testabdeckung für Edge Cases (z. B. redundante generische Parameter, unbeabsichtigte Name-Conflicts mit generischen Typen).
