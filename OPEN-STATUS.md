# OPEN Status

Stand: 2026-06-11

Diese Uebersicht trennt abgeschlossene V1-Arbeitsbloecke von bewusst geparkten V2/V3-Themen. Die ehemals offenen `OPEN-*.md`-Dateien, die vollständig für V1 gelöst sind, wurden mit `=== CLOSED ===` versehen und in den neuen Ordner `CLOSED-OPENS/` verschoben. 

## CLOSED-OPENS (V1 abgeschlossen)

Die folgenden Dokumente wurden erfolgreich gelöst, geschlossen und nach `CLOSED-OPENS/` verschoben:

| Bereich | Dokument (in `CLOSED-OPENS/`) | Status |
| --- | --- | --- |
| Return Results | `CLOSED-OPENS/OPEN-RETURN_RESULTS.md` | V1 accepted and conformance-checked. |
| Requires/Ensures | `CLOSED-OPENS/OPEN-REQIRE_ENSURE.md` | V1 notation and diagnostic behavior documented. |
| String Templates | `CLOSED-OPENS/OPEN-STRING_TEMPLATES.md` | V1 implemented and covered by language-module tests. |
| JSON Handling | `CLOSED-OPENS/OPEN-JSON_HANDLINGS.md` | `Json.stringify(record)`, typed `Json.parse<Record>(text)`, `@json` field names, compile-time literal schema checks and runtime Result failures are implemented for the current slice. |
| Record Initialisierung | `CLOSED-OPENS/OPEN-RECORD_INITIAL.md` | V1 record literals/field initialization implemented. |
| Semantic Rules | `CLOSED-OPENS/OPEN-SEAMNTIC_RULES.md` | spec/freehold.diag, spec/freehold.rules, and verify-spec-diagnostics.cmd are active. |
| Abort Handling | `CLOSED-OPENS/OPEN-ABORT_HANDLING.md` | V1/V2/V3 implemented for declared aborts, propagation, and main rules. |
| Control Flow Analyzer | `CLOSED-OPENS/OPEN-CONTROL-FLOW-ANALISE.md` | V0 routine summaries plus abort/main formalization implemented; path-aware analysis parked. |
| Structured Concurrency | `CLOSED-OPENS/OPEN-CONCURRENT.md` | V1 async/await core, runtime types, channels, structured scope, and formal concurrency verification implemented. |
| gRPC IDL | `CLOSED-OPENS/OPEN-GRPC.md` | V1 parser/AST/semantics, diagnostics, proto3 codegen, and unary Go server binding generation implemented. |
| Transport Scope Architecture | `CLOSED-OPENS/OPEN-CONRURRENT-GRPC-WEBSOCKET-REST.md` | V1 architecture decision recorded; WebSocket runtime and typed JSON broadcast examples 27/28/29/30/32/33 are covered by compiler/example gates. |
| Generics | `CLOSED-OPENS/OPEN-GENERICS.md` | V1b record and function generics implemented; V2/V3 inference, constraints, procedure generics and Go codegen monomorphization are now covered by language-module and compiler-example tests. |
| Stage 3 Compiler Core | `CLOSED-OPENS/OPEN-STAGE3-COMPILER-CORE.md` | Mini-Compilerkern in Freehold implementiert, Go-transpiliert und verifiziert. |
| Stage 1 Bootstrapping | `CLOSED-OPENS/OPEN-STAGE1-BOOTSTRAPPING.md` | Alle Meilensteine 1-5 (Lexer, Parser, Resolver, Lowering und Selbstübersetzung) erfolgreich abgeschlossen und per bytegleichem IR-Vergleich verifiziert. Post-Self-Hosting Roadmap gestartet. |
| Before Go Compiler | `CLOSED-OPENS/OPEN-BEFORE-GO-COMPILER.md` | Abgeschlossen fuer Compiler V1 Start: proto mapping getestet, schema minimal rule, generics codegen policy, Result/Abort policy, runtime builtins boundary, syntax freeze. |
| VS Code Language Support | `CLOSED-OPENS/OPEN-VSCODE-LANGUAGE-SUPPORT.md` | Completion V1 vor Formatter-Ausbau vorgezogen; Extension nach tools/vscode/freehold-vscode ueberfuehrt. |
| Go Compiler | `CLOSED-OPENS/OPEN-GO-COMPILER.md` | Compiler V1 Start-Slice plus Import-, Cross-Module-Call-, Cross-Module-Record-Type-, Cross-Module-Result-Error-Abort-, Cross-Module-Typkompositions-, Result-, Abort-, Multi-File-, Runtime-Builtin-, BigNumber-, Array-, Go-Projekt-Build- und Feature-Matrix-Slices implementiert. |
| Compare IR Stage 2 | `CLOSED-OPENS/OPEN-COMPARE-IR-STAGE2.md` | Stage 2 compiler V1 semantic comparison and Go project contracts implemented. |

## OPEN (V2/V3 verbleibend oder Design-Phase)

Die folgenden Dokumente verbleiben im Hauptverzeichnis für zukünftige Phasen:

| Bereich | Dokument | Status |
| --- | --- | --- |
| gRPC Streaming V3 | `OPEN-GRPC-STREAM-V3.md` | gRPC streaming integration design & roadmap for Freehold V3. |

## V2/V3 geparkt

Diese Themen sind absichtlich nicht Teil des aktuellen V1-Abschlusses:

### 3. Geparkte V2/V3-Themen (Nicht Teil des V1-Scopes)
Die folgenden komplexen Sprach- und Runtime-Features sind bewusst geparkt und blockieren das V1-Self-Hosting nicht:
- **gRPC-Client-Bindings, Streaming, Deadlines und Metadaten-Annotationen.**
- **Async-Runtime-Executor (Scheduling, Cancellation Tokens).**
- **REST/SSE-Verbindungsbibliotheken und weitere ergonomische Transport-APIs.** WebSocket V1 Runtime plus typed JSON Broadcast-Smokes sind umgesetzt; eine standardisierte langlebige WebSocket-Stdlib-API bleibt V2/V3-Design.
- **Pfadsensitive Kontrollfluss-Analyse (Path-aware analysis) und Abort-Implikationsprüfung.**

Weitere Details:
- gRPC client bindings and explicit service implementation binding from generated `.proto` files.
- gRPC custom error/status-code mapping and schema-evolution rules such as `reserved proto`.
- gRPC streaming, cancellation, deadlines, metadata, and auth annotations.
- Runtime execution for async tasks, executor scheduling, cancellation tokens, and channel runtime behavior.
- Transport libraries for REST and SSE, plus broader ergonomic request/connection scopes. The current WebSocket V1 binding and compiler examples cover runtime communication, typed JSON broadcast, rooms/topics, backpressure policy, keepalive status, and frame-policy modeling.
- Remaining generics expansion beyond the current V2/V3 slice, especially qualified generic calls in broader module contexts and generic IDL monomorphization.
- Path-aware control-flow analysis, abort condition implication, handler syntax, reachability, and proof-obligation integration.
- Broad Go compiler feature coverage beyond the modular Compiler V1 start slice.
- AST-based VS Code formatter and semantic editor completion; pragmatic completion V1 comes first.

## Current Gate Baseline

Recent WebSocket/JSON compiler-example slice:

```text
30_websocket_json_broadcast_demo
   typed JSON envelope broadcast, @json("clientId"), keepalive, registry, room broadcast, timeout, backpressure, frame policy, typed error status

32_websocket_json_broadcast_schema_neg
   dynamic invalid JSON/schema cases return Result failures; compile-time invalid literals remain covered by VF-J009 language-module invalid tests

33_websocket_room_broadcast_demo
   broadcast is queued only for the target room/topic
```

Latest verified baseline after the compiler runtime breadth, V2/V3 generics, channel-verification, and runtime-assertion updates:

```text
verify-go-semantic-projects.cmd
Expected semantic projects: 18
Mismatches:                 0

verify-go-project-semantic-diagnostics.cmd
Expected semantic projects: 13
Mismatches:                 0

verify-go-semantic-diagnostics.cmd
Expected semantic diagnostics: 18
Mismatches:                    0

go test ./... in go-frontend
ok freehold-go-frontend/internal/semantic

verify-grammar-consistency.cmd
Report warnings: 71
Mismatches:      0

verify-compiler-examples.cmd
Compiler example smoke passed; includes compiler_v1_result_abort_array_runtime_builtins.expected.log and the positive generics examples `23_generic_type_inference_and_constraints` / `26_generic_function`

verify-additive-test-line.cmd
Allowed additions:       0
Frozen-line violations: 0

verify-stage3-compiler-core-v1.cmd
Total contracts:    1
Matching contracts: 1
Failing contracts:  0

verify-stage3-loader-v1.cmd
Total contracts:    1
Matching contracts: 1
Failing contracts:  0

compare-source-map-compiler-v1.cmd
Total samples:       18
Matching samples:    18
Mismatching samples: 0
Skipped samples:     0

compare-source-map-compiler-v1-stage2.cmd
Total samples:       6
Matching samples:    6
Mismatching samples: 0
Skipped samples:     0

verify-language-modules-v2_3.cmd
Passed language module tests: 60/60

Included V2/V3 slices:
- `03_generic_type_inference_and_constraints` covers inference, constraints, procedure generics, nested inference conflicts, and monomorphized Go codegen.
- `07_concurrency_verification` covers channel invariant send substitution and alias violation diagnostics.
- `08_runtime_assertions` covers VM runtime assertion hardening cases for subtype ranges, array bounds, and check verification.

git diff --check
No whitespace errors.
```

The normal single-module Go semantic gate remains intentionally narrow and unchanged at 18 expected diagnostics. The project-aware gates are now split: `verify-go-semantic-projects.cmd` covers OK and loader/project-loader behavior, while `verify-go-project-semantic-diagnostics.cmd` covers negative cross-module semantic failures.

## Festgelegte naechste Schritte

1. Project-aware diagnostics weiter haerten, aber den single-module Gate stabil lassen.
   - Erledigt: strukturierte Diagnostics fuer Syntaxfehler in importierten Modulen, damit `imported_module_syntax_error` manifestfaehig ist statt als roher Loader-Fehler zu enden.
   - Erledigt: negative Mini-Projekte fuer hidden/non-exposed Symbolnutzung, falsche qualifizierte Modulnutzung, transitive Dependency-Fehler und mehrere Diagnostics in einem Projekt.

2. Separaten Project-Semantic-Diagnostics-Gate pflegen.
   - Erledigt: `verify-go-project-semantic-diagnostics.cmd` trennt project-aware Goldens und Reports klar von Loader-/OK-Projektfaellen, ohne `verify-go-semantic-diagnostics.cmd` umzubauen.
   - Der bestehende `verify-go-semantic-projects.cmd` bleibt fuer Loader-/OK-Projekte fokussiert.

3. Go Codegen V1 Runtime-Breite weiter ausbauen.
   - Erledigt: `15_result_abort_array_runtime_builtins` prueft `Result<Array<imported Record, 3>, imported Error>`, eine abortende importierte Domain-Routine, komplexere `requires`/`ensures` und Math/String/Json/Big-Builtins in einem echten Mehr-Package-Beispiel mit `verify-compiler-examples.cmd`-Ausgabevergleich.
   - Erledigt: Result-Array-Contracts koennen im Python-Frontend und Go-Codegen `value[index].field` nutzen; Beispiel 15 prueft diese Form im Mehr-Package-Runtime-Smoke.
   - Erledigt: Generics-Inferenz, Constraints und Function/Procedure-Monomorphisierung sind in V2/V3 und in den Compiler-V1-Beispielen als positive Go-Codegen-Smokes abgedeckt.
   - Naechste Runtime-Smokes koennen gezielt die noch offenen Grenzen wie abortende Calls im Runtime-Ausdruckspfad adressieren.

4. Spaeter groessere Bootstrap-Bloecke angehen.
   - Erledigt: FH-Native Loader V1-Scope festgezogen als begrenzter JSON-ProjectGraph-Reader (`Compiler.Core.Loader`) mit eigenem Stage3-Gate `verify-stage3-loader-v1.cmd`.
   - Go-native Control-Flow-V0 analog Python-CFlow.
   - Breitere Abort-Contract-Implication und Handler-Syntax bleiben bewusst nachgelagert.
