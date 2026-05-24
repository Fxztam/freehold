# OPEN Status

Stand: 2026-05-24

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
| gRPC IDL | `OPEN-GRPC.md` | V1 parser/AST/semantics, diagnostics, proto3 codegen, and artifacts implemented. |
| Transport Scope Architecture | `OPEN-CONRURRENT-GRPC-WEBSOCKET-REST.md` | V1 architecture decision recorded: transport libs reuse common Concurrent.Scope. |
| Generics | `OPEN-GENERICS.md` | V1b record and function generics implemented; codegen/inference/bounds parked. |

## Naechste Phase: Go Compiler Vorbereitung

| Bereich | Dokument | Status |
| --- | --- | --- |
| Before Go Compiler | `OPEN-BEFORE-GO-COMPILER.md` | Abgeschlossen fuer Compiler V1 Start: proto mapping getestet, schema minimal rule, generics codegen policy, Result/Abort policy, runtime builtins boundary, syntax freeze. |
| VS Code Language Support | `OPEN-VSCODE-LANGUAGE-SUPPORT.md` | Completion V1 vor Formatter-Ausbau vorgezogen; Extension nach `tools/vscode/freehold-vscode` ueberfuehrt. |
| Go Compiler | `OPEN-GO-COMPILER.md` | Compiler V1 Start-Slice plus Import-, Result-, Abort- und Multi-File-Slices implementiert: `go-codegen`, `go-codegen-project`, JSON-Spiegel, Golden-Faelle, Artefakt-Gate, import-aware Package-Calls, Result-Wertreturns und Abort-Error-Returns. |

## V2/V3 geparkt

Diese Themen sind absichtlich nicht Teil des aktuellen V1-Abschlusses:

- gRPC Go server/client bindings from generated `.proto` files.
- gRPC error/status-code mapping and schema-evolution rules such as `reserved proto`.
- gRPC streaming, cancellation, deadlines, metadata, and auth annotations.
- Runtime execution for async tasks, executor scheduling, cancellation tokens, and channel runtime behavior.
- Transport libraries for REST, WebSocket, SSE, and their ergonomic request/connection scopes.
- Generics bounds, inference, qualified generic calls, monomorphized codegen artifacts, and generic IDL monomorphization.
- Path-aware control-flow analysis, abort condition implication, handler syntax, reachability, and proof-obligation integration.
- Broad Go compiler feature coverage beyond the modular Compiler V1 start slice.
- AST-based VS Code formatter and semantic editor completion; pragmatic completion V1 comes first.

## Current Gate Baseline

Latest verified baseline after Go compiler verify/artifact start-slice:

```text
verify-spec-diagnostics.cmd
Diagnostic specs: 111
Rule emits:       113
Failures:         0

compare-semantic-diagnostics.cmd
Expected semantic diagnostics: 95
Matching semantic diagnostics: 95
Mismatching semantic diagnostics: 0

verify-parser-conformance.cmd
Total: 319
OK:    274
FAIL:  45
Go codegen artifacts: 31/31 matching
AST shape:     274/274
Semantic AST:  274/274
Parser conformance verify passed.
```
