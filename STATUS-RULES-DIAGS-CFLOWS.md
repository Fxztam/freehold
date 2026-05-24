# Status: Rules, Diagnostics, Control Flow

Stand: 2026-05-24

Dieser Status trennt drei Ebenen, die leicht verwechselt werden koennen:

- Spezifikation in `spec/freehold.diag`, `spec/freehold.rules` und `spec/analyzer.cflow`.
- Direkt im Go-Frontend implementierte Parser-/AST-/Syntaxdiagnostik.
- Python-seitig implementierte Semantik-, Typ- und Control-Flow-Pruefung, die ueber die offiziellen Gates abgeglichen wird.

## Kurzfassung

Direkt im Go-Code sind aktuell 23 Diagnostics/Parser-Regeln umgesetzt. Die komplette Spec ist groesser und wird ueber Python-Verifier, Expected-Manifests, Normalizer und Gates vollstaendig abgeglichen.

Der Go-Parser ist bei Syntax/AST-Paritaet sehr weit: alle 319 Language-Module-Faelle haben denselben Parser-Status wie DHParser; alle 274 parse-ok Faelle haben passende AST-Shape- und Semantic-AST-Artefakte.

## Aktuelle Spec-Zahlen

`spec/freehold.diag`:

- Diagnostic-Specs: `111`

`spec/freehold.rules`:

- Rules: `113`
- Emits: `113`

`spec/analyzer.cflow`:

- Summaries: `3`
- Meanings: `12`
- Facts: `15`
- Rules: `9`
- Limits: `3`
- Non-goals: `7`

## Direkt im Go-Frontend umgesetzt

Go-Datei:

- `go-frontend/internal/diagnostic/catalog.go`

Aktueller Go-Diagnostic-Catalog:

- Catalog-Eintraege: `23`
- davon `FH-SYN-*`: `23`
- davon alle `FH-*`: `23`

Damit sind im Go-Code direkt vor allem Syntax-/Parserdiagnostics umgesetzt. Das entspricht dem Go-Parser/Go-AST-Frontend, nicht dem kompletten Semantiksystem.

Einordnung gegen die Spec:

- `23/111` Diagnostic-Specs direkt im Go-Catalog.
- grob die `parse_syntax`-Schicht aus `freehold.rules`, also `23/113` Rules/Emits direkt im Go-Frontend.
- Semantik-, Typ-, Contract-, Abort-, Concurrency-, Generic-, JSON-, Record- und gRPC-Diagnostics sind aktuell nicht als kompletter Go-Verifier umgesetzt.

## Go-Parser- und AST-Abdeckung

Aktueller Parser-Status-Vergleich:

```text
compare-parser-status.cmd

Total cases:        319
Matching status:    319
Mismatching status: 0
Missing Go:         0
Missing DHParser:   0
Go:                 OK 274 / FAIL 45
DHParser:           OK 274 / FAIL 45
```

Aktuelle AST-Vergleiche:

```text
compare-ast-shape.cmd

Comparable parse-ok cases: 274
Matching shape:            274
Mismatching shape:         0

compare-ast-semantic.cmd

Comparable parse-ok cases:    274
Matching semantic AST:        274
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

Offizieller Spec-Diagnostic-Check:

```text
verify-spec-diagnostics.cmd

Diagnostic specs:        111
Rule emits:              113
Expected syntax codes:   19
Expected semantic codes: 83
CODE_MAP entries:        88
Failures:                0
```

Semantik-Diagnostic-Vergleich:

```text
compare-semantic-diagnostics.cmd

Expected semantic diagnostics:    95
Matching semantic diagnostics:    95
Mismatching semantic diagnostics: 0
```

Das bedeutet: Die volle Diagnostic-/Rule-Spec ist aktuell gruen abgeglichen, aber nicht vollstaendig in Go implementiert. Der vollstaendige Semantikpfad laeuft noch ueber den Python-Verifier plus Normalizer/Manifests.

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

Noch nicht als eigener Go-Analyzer umgesetzt:

- `ResultReturnSummary`
- `ScopeFlowSummary`
- strukturierte Scope-Flow-Regeln als eigener Analyzer
- path-aware Proofs
- breitere Abort-Contract-Implication

## Aktuelle Einschaetzung

- Go Parser / AST / Syntax-Diagnostics: sehr weit, gruen gegen die 319 Language-Module-Faelle.
- Go Diagnostic Catalog: `23/111` Diagnostic-Specs direkt in Go, alle Syntax.
- `freehold.rules` direkt in Go: grob `23/113` Rules/Emits, also die Parser-/Syntax-Schicht.
- Semantik-Regeln: Python-seitig gruen abgeglichen, noch nicht Go-native.
- Control Flow: Python V0 vorhanden, Go-native Control Flow noch offen.

## Praktische Konsequenz

Wenn der Go-Frontend-Pfad Richtung Bootstrap wachsen soll, sind die naechsten grossen Portierungsbloecke:

1. Semantic-Diagnostic/Rule-Engine oder gezielte Go-Verifier-Slices.
2. Go-native Symboltabellen und Typkontext.
3. Go-native Routine-/Call-/Import-Semantik.
4. Go-native Control-Flow-V0 analog `freehold/core/control_flow.py`.
5. Danach Result-/Scope-/Abort-CFlow-Erweiterungen.

Der Parser ist also schon ein starker Anker. Der naechste grosse Abstand liegt nicht mehr in Syntax/AST, sondern in Semantik und Control Flow.