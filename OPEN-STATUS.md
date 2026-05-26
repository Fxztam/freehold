# OPEN Status

Stand: 2026-05-26

Diese Uebersicht trennt abgeschlossene V1-Arbeitsbloecke von bewusst geparkten V2/V3-Themen. Die `OPEN-*.md`-Dateien bleiben als Design- und Roadmap-Dokumente erhalten; `OPEN` bedeutet hier nicht automatisch, dass der aktuelle V1-Slice unvollstaendig ist.

## V1 abgeschlossen

| Bereich | Dokument | Status |
| --- | --- | --- |
| Return Results | `OPEN-RETURN_RESULTS.md` | V1 accepted and conformance-checked. |
| Requires/Ensures | `OPEN-REQIRE_ENSURE.md` | V1 notation and diagnostic behavior documented. |
| String Templates | `OPEN-STRING_TEMPLATES.md` | V1 implemented and covered by language-module tests. |
| JSON Stringify | `OPEN-JSON_HANDLINGS.md` | V1 stringify semantics implemented for supported record shapes. |
| Record Initialisierung | `OPEN-RECORD_INITIAL.md` | V1 record literals/field initialization implemented. |
| Semantic Rules | `OPEN-SEAMNTIC_RULES.md` | `spec/freehold.diag`, `spec/freehold.rules`, and `verify-spec-diagnostics.cmd` are active. |
| Abort Handling | `OPEN-ABORT_HANDLING.md` | V1/V2/V3 implemented for declared aborts, propagation, and main rules. |
| Control Flow Analyzer | `OPEN-CONTROL-FLOW-ANALISE.md` | V0 routine summaries plus abort/main formalization implemented; path-aware analysis parked. |
| Structured Concurrency | `OPEN-CONCURRENT.md` | V1 async/await core, runtime types, channels, and structured scope lifetime rules implemented. |
| gRPC IDL | `OPEN-GRPC.md` | V1 parser/AST/semantics, diagnostics, proto3 codegen, artifacts, and unary Go server binding generation implemented. |
| Transport Scope Architecture | `OPEN-CONRURRENT-GRPC-WEBSOCKET-REST.md` | V1 architecture decision recorded: transport libs reuse common Concurrent.Scope. |
| Generics | `OPEN-GENERICS.md` | V1b record and function generics implemented; codegen/inference/bounds parked. |

## Naechste Phase: Go Compiler Vorbereitung

| Bereich | Dokument | Status |
| --- | --- | --- |
| Before Go Compiler | `OPEN-BEFORE-GO-COMPILER.md` | Abgeschlossen fuer Compiler V1 Start: proto mapping getestet, schema minimal rule, generics codegen policy, Result/Abort policy, runtime builtins boundary, syntax freeze. |
| VS Code Language Support | `OPEN-VSCODE-LANGUAGE-SUPPORT.md` | Completion V1 vor Formatter-Ausbau vorgezogen; Extension nach `tools/vscode/freehold-vscode` ueberfuehrt. |
| Go Compiler | `OPEN-GO-COMPILER.md` | Compiler V1 Start-Slice plus Import-, Cross-Module-Call-, Cross-Module-Record-Type-, Cross-Module-Result-Error-Abort-, Cross-Module-Typkompositions-, Result-, Abort-, Multi-File-, Runtime-Builtin-, BigNumber-, Array-, Go-Projekt-Build- und Feature-Matrix-Slices implementiert: `go-codegen`, `go-codegen-project`, JSON-Spiegel, Golden-Faelle, Artefakt-Gate, import-aware Package-Calls, importierte Freehold-Routinen via `exposing` und qualifizierte Modulnamen, exposed importierte Record-Typen in Signaturen, importierte Result-/Error-/Abort-Paketgrenzen, `Result<Array<imported Record>, imported Error>` plus importierter Abort-Call, Result-Wertreturns, Abort-Error-Returns, Math/Std.IO/String/Json.stringify/Big Runtime-Imports, fixed-size Array-Go-Goldens, `go.mod`/`build.cmd` fuer generierte Projekte, Zwei-Package- und Drei-Package-Projektgoldens, 24/24 Go-Codegen-Feature-Matrix-Abdeckung sowie Go-native Semantic-V0-Diagnostics fuer Project-Loader, Routine-Calls, Record-Felder/Literals, Array-Index-Ausdruecke, Result-Contract-Bindings, Variablen-/Typnamen, Duplicate Params/Locals und einfache Assignments; der Go-Semantic-Project-Gate deckt 27 importierte Mini-Projekte, transitive Importfaelle und negative cross-module Semantik-/Loader-Faelle inklusive importierter Syntaxfehler und Result-/Array-/Abort-/Contract-Kombinationen ab. `verify-grammar-consistency.cmd` ist in den Parser-Conformance-Gate eingebunden und berichtet Lark-vs.-Spec-Regeldeltas sowie reservierte Keyword-Fixture-Kandidaten report-only; der Compiler-Example-Smoke umfasst nun einen BigInteger-Loop mit Runtime-Log. |

## V2/V3 geparkt

Diese Themen sind absichtlich nicht Teil des aktuellen V1-Abschlusses:

- gRPC client bindings and explicit service implementation binding from generated `.proto` files.
- gRPC custom error/status-code mapping and schema-evolution rules such as `reserved proto`.
- gRPC streaming, cancellation, deadlines, metadata, and auth annotations.
- Runtime execution for async tasks, executor scheduling, cancellation tokens, and channel runtime behavior.
- Transport libraries for REST, WebSocket, SSE, and their ergonomic request/connection scopes.
- Generics bounds, inference, qualified generic calls, monomorphized codegen artifacts, and generic IDL monomorphization.
- Path-aware control-flow analysis, abort condition implication, handler syntax, reachability, and proof-obligation integration.
- Broad Go compiler feature coverage beyond the modular Compiler V1 start slice.
- AST-based VS Code formatter and semantic editor completion; pragmatic completion V1 comes first.

## Current Gate Baseline

Latest verified baseline after the project-aware negative mini-project expansion:

```text
verify-go-semantic-projects.cmd
Expected semantic projects: 31
Mismatches:                 0

verify-go-semantic-diagnostics.cmd
Expected semantic diagnostics: 18
Mismatches:                    0

go test ./... in go-frontend
ok freehold-go-frontend/internal/semantic

verify-grammar-consistency.cmd
Report warnings: 71
Mismatches:      0

verify-additive-test-line.cmd
Allowed additions:       9
Frozen-line violations: 0

git diff --check
No whitespace errors; only LF/CRLF warnings for touched Go files.
```

The normal single-module Go semantic gate remains intentionally narrow and unchanged at 18 expected diagnostics. The project-aware gate is the current expansion point for imported mini-projects, transitive import graphs, loader diagnostics, and cross-module semantic failures.

## Festgelegte naechste Schritte

1. Project-aware diagnostics weiter haerten, aber den single-module Gate stabil lassen.
   - Erledigt: strukturierte Diagnostics fuer Syntaxfehler in importierten Modulen, damit `imported_module_syntax_error` manifestfaehig ist statt als roher Loader-Fehler zu enden.
   - Erledigt: negative Mini-Projekte fuer hidden/non-exposed Symbolnutzung, falsche qualifizierte Modulnutzung, transitive Dependency-Fehler und mehrere Diagnostics in einem Projekt.

2. Optional separaten `project_semantic_diagnostics`-Gate einfuehren.
   - Ziel: project-aware Goldens und Reports klar von Loader-/OK-Projektfaellen trennen, ohne `verify-go-semantic-diagnostics.cmd` umzubauen.
   - Der bestehende `verify-go-semantic-projects.cmd` bleibt bis dahin stabiler Sammelgate.

3. Go Codegen V1 Runtime-Breite wieder aufnehmen.
   - Naechste Runtime-Smokes: weitere `Result`/`Abort`/`Array`-Kombinationen, komplexere `requires`/`ensures`, und Runtime-Builtins in echten Mehr-Package-Beispielen.
   - Bestehender Anker: `14_big_loop_runtime_log` fuer BigInteger-Loop plus `Std.IO.logf`.

4. Spaeter groessere Bootstrap-Bloecke angehen.
   - Go-native Control-Flow-V0 analog Python-CFlow.
   - Breitere Abort-Contract-Implication und Handler-Syntax bleiben bewusst nachgelagert.
