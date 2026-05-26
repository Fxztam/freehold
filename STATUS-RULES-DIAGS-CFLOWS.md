# Status: Rules, Diagnostics, Control Flow

Stand: 2026-05-25

Dieser Status trennt drei Ebenen, die leicht verwechselt werden koennen:

- Spezifikation in `spec/freehold.diag`, `spec/freehold.rules` und `spec/analyzer.cflow`.
- Direkt im Go-Frontend implementierte Parser-/AST-/Syntaxdiagnostik.
- Python-seitig implementierte Semantik-, Typ- und Control-Flow-Pruefung, die ueber die offiziellen Gates abgeglichen wird.

## Kurzfassung

Direkt im Go-Code sind aktuell 44 Diagnostics umgesetzt: 23 Syntax-/Parserdiagnostics, 6 Typdiagnostics und 15 semantische Diagnostics. Die Go-native Semantik deckt inzwischen Record-FieldAccess, Record-Literals, Array-Index-Ausdruecke, lokale/exposed Routine-Calls, Variablen-/Typnamen, Duplicate Params/Locals, einfache Assignments sowie strukturierte Project-Loader-Importdiagnostics ab. Die komplette Spec ist groesser und wird ueber Python-Verifier, Expected-Manifests, Normalizer und Gates vollstaendig abgeglichen.

Der Go-Parser ist bei Syntax/AST-Paritaet sehr weit: alle 322 Parser/AST-Vergleichsfaelle haben denselben Parser-Status wie DHParser; alle 277 parse-ok Faelle haben passende AST-Shape- und Semantic-AST-Artefakte. Der vollstaendige Language-Module-Gate steht aktuell bei 461/461.

## Aktuelle Spec-Zahlen

`spec/freehold.diag`:

- Diagnostic-Specs: `114`

`spec/freehold.rules`:

- Rules: `114`
- Emits: `115`

`spec/analyzer.cflow`:

- Summaries: `3`
- Meanings: `12`
- Facts: `15`
- Flows: `1`
- Rules: `11`
- Limits: `5`
- Non-goals: `6`

## Direkt im Go-Frontend umgesetzt

Go-Datei:

- `go-frontend/internal/diagnostic/catalog.go`

Aktueller Go-Diagnostic-Catalog:

- Catalog-Eintraege: `44`
- davon `FH-SYN-*`: `23`
- davon `FH-TYP-*`: `6`
- davon `FH-SEM-*`: `15`
- davon alle `FH-*`: `44`

Damit sind im Go-Code direkt vor allem Syntax-/Parserdiagnostics umgesetzt. Neu ist ein Go-native Semantikanker fuer Record-FieldAccess, Record-Literals, Array-Index-Ausdruecke, Routine-Calls, Variablen-/Typnamen, Duplicate Params/Locals, einfache Assignments und `go-semantic-project`-Loaderfehler; das ist noch kein komplettes Semantiksystem.

Einordnung gegen die Spec:

- `44/114` Diagnostic-Specs direkt im Go-Catalog.
- grob die `parse_syntax`-Schicht aus `freehold.rules` plus Go-native Record-/Array-/Routine-/Name-/Assignment- und Project-Loader-Semantikdiagnostics, also `44/115` Rules/Emits direkt im Go-Frontend.
- Semantik-, Typ-, Contract-, Abort-, Concurrency-, Generic-, JSON-, Record- und gRPC-Diagnostics sind aktuell nicht als kompletter Go-Verifier umgesetzt.

## Go-Parser- und AST-Abdeckung

Aktueller Parser-Status-Vergleich:

```text
compare-parser-status.cmd

Total cases:        322
Matching status:    322
Mismatching status: 0
Missing Go:         0
Missing DHParser:   0
Go:                 OK 277 / FAIL 45
DHParser:           OK 277 / FAIL 45
```

Aktuelle AST-Vergleiche:

```text
compare-ast-shape.cmd

Comparable parse-ok cases: 277
Matching shape:            277
Mismatching shape:         0

compare-ast-semantic.cmd

Comparable parse-ok cases:    277
Matching semantic AST:        277
Mismatching semantic AST:     0
```

Go-Frontend-Testlauf:

```text
go test ./...

freehold-go-frontend/cmd/go-parse-tests-language-modules        [no test files]
freehold-go-frontend/internal/ast                               [no test files]
freehold-go-frontend/internal/diagnostic                        [no test files]
freehold-go-frontend/internal/lexer                             [no test files]
freehold-go-frontend/internal/parser                            [no test files]
freehold-go-frontend/internal/token                             [no test files]
```

## Spec- und Semantic-Diagnostic-Gates

Import-/Record-Semantik:

- `spec/freehold.rules` enthaelt eine nicht-emittierende `meaning imported_record_type_context` fuer exposed/importierte Records: transitive Type-/Record-Abhaengigkeiten von Record-Feldern gehoeren in den Typkontext des importierenden Moduls. Das ist eine positive Aufloesungsregel; Fehlerfaelle laufen weiter ueber `FH-TYP-2101 field_access_requires_record` bzw. `FH-SEM-1105 unknown_record_field`.

Async-/Scope-Semantik:

- `spec/freehold.rules` enthaelt die `concurrency`-Regeln fuer `await`, Channel-Builtins und strukturierte Scope-Blocks.
- `spec/freehold.diag` enthaelt die stabilen Concurrency-Diagnostics `FH-CON-3101`, `FH-CON-3102`, `FH-CON-3111`, `FH-CON-3112`, `FH-CON-3121` und `FH-CON-3122`.
- `spec/analyzer.cflow` enthaelt `ScopeFlowSummary` sowie die Scope-Ownership-Regeln fuer `spawn`, `join`, Escape und unjoined Handles.
- Der Compiler-V1-Smoke `examples/compiler_v1/unsupported/async_scope_runtime/App/Main.fh` dokumentiert die aktuelle Grenze: Python-Frontend/Semantik/CFlow verifizieren den strukturierten Scope, Go-Codegen V1 meldet fuer async Runtime weiterhin `FH-GOCODEGEN-0001`.

Offizieller Spec-Diagnostic-Check:

```text
verify-spec-diagnostics.cmd

Diagnostic specs:        114
Rule emits:              115
Expected syntax codes:   19
Expected semantic codes: 85
CODE_MAP entries:        91
Failures:                0
```

Semantik-Diagnostic-Vergleich:

```text
compare-semantic-diagnostics.cmd

Expected semantic diagnostics:    99
Matching semantic diagnostics:    99
Mismatching semantic diagnostics: 0
```

Das bedeutet: Die volle Diagnostic-/Rule-Spec ist aktuell gruen abgeglichen, aber nicht vollstaendig in Go implementiert. Der vollstaendige Semantikpfad laeuft noch ueber den Python-Verifier plus Normalizer/Manifests.

Go-Codegen-Rejection-Beweise:

- `12_type_conflicts` ist als policy-only/rejected V1-Pfad abgesichert: alle negativen Konflikt-Fixtures laufen zusaetzlich durch den Go-Codegen-Einstieg und muessen mit derselben Verifier-Diagnostic abbrechen, bevor Go-Output akzeptiert wird.
- `13_contract_blocks` ist nicht mehr pauschal policy-only/rejected: gueltige V1-Contract-Formen werden als Go-Runtime-Checks emittiert, ungueltige Contract-Fixtures laufen zusaetzlich durch den Go-Codegen-Einstieg und muessen mit derselben Syntax-/Semantik-Diagnostic abbrechen, bevor Go-Output akzeptiert wird.
- `22_generics` ist als policy-only/rejected V1-Pfad abgesichert: frontend-gueltige Generic-Fixtures muessen mit `FH-GOCODEGEN-0001` unsupported bleiben, ungueltige Generic-Fixtures muessen mit derselben Semantik-Diagnostic abbrechen, bevor Go-Output akzeptiert wird.
- `04_types`, `11_errors_results` und `18_string_templates` sind fuer die kleinen deferred Go-Codegen-Slices positiv abgedeckt: breitere Alias-Kombinationen, Result-`value.field` und dynamische String-Template-Formate laufen ohne neue Spec-Diagnostics.
- `21_abort_handling` hat mit V4a eine Python-Semantik-/CFlow-Regel: Statements nach garantiertem Exit werden ueber `VF-ABT010` / `FH-ABT-3010` abgelehnt. V4b ergaenzt einfache syntaktische Abort-Condition-Implication ueber `requires` und `if`/`else`-Pfadbedingungen; ungedeckte Sites werden ueber `VF-ABT006` / `FH-ABT-3006` abgelehnt.
- `24_grpc_idl` hat einen separaten `grpc-go-bindings`-Codegen fuer unary Go-Server-Adapter und konservatives Status-Mapping. Der allgemeine `go-codegen-project`-Pfad lehnt Service-Deklarationen weiterhin als `FH-GOCODEGEN-0001` ab.
- Fuer die Go-Codegen-Slices waren keine neuen `spec/freehold.diag`-, `spec/freehold.rules`- oder `spec/analyzer.cflow`-Eintraege noetig; die bestehenden Diagnostics wie `VF-N001`, `VF-ST002`, `VF-U008`, `VF-U009`, `VF-CT001`, `VF-CT002`, `VF-E001`, `VF-E002` und die `VF-GEN*`-Diagnostics bleiben die Quelle.
- Aktueller Language-Module-Gate nach dieser Erweiterung: `461/461`.

## Go-Native Semantik V0

Erster Go-native Semantikanker:

- Paket: `go-frontend/internal/semantic`
- SymbolTable V0 sammelt Record-Typen, deren Felder sowie Function-/Procedure-Signaturen aus dem Go-AST; `BuildSymbolTableWithImports` ergaenzt exposed importierte Records/Routinen inklusive transitiver Record-Feldtyp-Abhaengigkeiten.
- `ValidateModule` prueft lokale Routine-Parameter, `let`-Bindings, verschachtelte FieldAccess-Ausdruecke und lokale/exposed Routine-Calls; `ValidateModuleWithImports` nutzt dieselben Regeln mit import-aware SymbolLookup. Die schmale Typinferenz deckt Literal-Basistypen, Routine-Return-Typen, einfache Operatoren und Array-Index-Elementtypen ab.
- Abgedeckte Diagnostics: `FH-TYP-2101 field_access_requires_record`, `FH-SEM-1105 unknown_record_field`, `FH-SEM-1204 unknown_routine`, `FH-SEM-1205 routine_argument_count_mismatch` und `FH-TYP-2201 routine_argument_type_mismatch`.
- Relevante Go-AST-Decl-/Stmt-/Expr-Knoten tragen interne Source-Positionen (`json:"-"`), sodass Go-native Semantic-Diagnostics positionsgenau sein koennen, ohne AST-JSON-Goldens zu veraendern.
- Der Parser-CLI `go-parse-tests-language-modules` kann den Analyzer optional mit `--semantic` nach erfolgreichem Parse ausfuehren. `verify-go-semantic-diagnostics.cmd` schreibt temporaere Artefakte nach `.tmp/go-semantic` und vergleicht die V0-Diagnostics gegen `tests/language_modules/expected_go_semantic_diagnostics.json`.
- `go-semantic-project` laedt ein Entry-Modul samt Imports nach derselben Modulpfad-Konvention (`App.Main -> App/Main.fh`). `verify-go-semantic-projects.cmd` schreibt temporaere Artefakte nach `.tmp/go-semantic-project` und verankert den importierten Nested-Record-FieldAccess-Projektfall.
- Bewusste Grenze: keine vollstaendige Typinferenz.

## Control Flow

Direkter Go-Control-Flow-Analyzer:

- aktuell `0`
- es gibt noch keinen dedizierten Go-native Control-Flow-Analyzer.

Python-Control-Flow-Analyzer:

- Datei: `freehold/core/control_flow.py`
- Kernklasse: `ControlFlowAnalyzer`
- Summary-Typ: `RoutineFlowSummary`

Der Python-V0-Kern implementiert aktuell:

- `normal_return_possible`
- `guaranteed_exit`
- `declared_aborts`
- `emitted_aborts`
- `called_routines`
- `propagated_aborts`
- Block-Flow fuer `return`, `abort`, `call`, `let`, assignment, field assignment, `check`, `if`, `while` und `case`
- V4a-Reachability im Python-Verifier: ein Statement nach einem garantiert beendenden Statement im selben Block ist unzulaessig.
- V4b-Abort-Condition-Implication im Python-Verifier: ein `abort X` mit `aborts X when condition` muss unter einer syntaktisch passenden `requires`- oder `if`/`else`-Pfadbedingung stehen.

Noch nicht als eigener Go-Analyzer umgesetzt:

- `ResultReturnSummary`
- `ScopeFlowSummary`
- strukturierte Scope-Flow-Regeln als eigener Analyzer
- path-aware Proofs
- breitere Abort-Contract-Implication ueber direkte syntaktische Path-Matches hinaus

Der neue Unsupported-Smoke fuer Async/Scope aendert diese Einordnung nicht: Er bestaetigt die bestehende Python-Semantik- und CFlow-Grenze und haelt die Go-native Runtime-/Analyzer-Arbeit weiter als offenen Positiv-Slice fest.

## Aktuelle Einschaetzung

- Go Parser / AST / Syntax-Diagnostics: sehr weit, gruen gegen die 322 Parser/AST-Vergleichsfaelle.
- Go Diagnostic Catalog: `25/114` Diagnostic-Specs direkt in Go, davon 23 Syntax und 2 Record-FieldAccess-Semantik.
- `freehold.rules` direkt in Go: grob `25/115` Rules/Emits, also die Parser-/Syntax-Schicht plus erster Record-FieldAccess-Semantikanker.
- Semantik-Regeln: Python-seitig gruen abgeglichen; Go-native V0 existiert fuer single-module Record-FieldAccess, der Rest ist noch nicht Go-native.
- Control Flow: Python V0 vorhanden, Go-native Control Flow noch offen.

## Praktische Konsequenz

Wenn der Go-Frontend-Pfad Richtung Bootstrap wachsen soll, sind die naechsten grossen Portierungsbloecke:

1. Semantic-Diagnostic/Rule-Engine oder gezielte Go-Verifier-Slices.
2. Go-native Symboltabellen und Typkontext ueber Record-FieldAccess V0 hinaus.
3. Go-native Routine-/Call-/Import-Semantik.
4. Go-native Control-Flow-V0 analog `freehold/core/control_flow.py`.
5. Danach Result-/Scope-/Abort-CFlow-Erweiterungen.

Der Parser ist also schon ein starker Anker. Der naechste grosse Abstand liegt nicht mehr in Syntax/AST, sondern in Semantik und Control Flow.