# Compare-IR Compiler V1 Stage 2

Stand: 2026-05-27

Stage 1 bleibt eingefroren: 15 aktive Samples, 3 bewusst skipped Samples, non-mutating Check-Default. Die drei skipped Samples werden nicht nachtraeglich in Stage 1 hineingezogen, sondern in einem eigenen Stage-2-Slice bearbeitet.

## Ziel

- Stage 1 bleibt ein stabiler Waechter fuer die aktuelle Python/Go-IR-Paritaet.
- Stage 2 bekommt ein eigenes Manifest und ein eigenes Gate, sobald ein deferred Feature gezielt angegangen wird.
- Neue Compiler-Demos bleiben opt-in und wachsen nicht automatisch in Stage 1 oder Stage 2 hinein.
- Stage 2 priorisiert semantikrelevante IR-Felder statt jedes AST-nahe Detail gleich hart zu vergleichen.

## Semantikrelevante IR-Felder

Der Stage-2-Gate nutzt `tools/compare_ir_hashes.py --comparison semantic` als semantische Hauptsicht und fuehrt parallel den Full-JSON-Hash mit `--comparison full` aus. Die semantische Projektion haelt Compiler-Vertraege sichtbar und blendet reine Source-/AST-Metadaten wie Spans aus; der Full-Hash bleibt als strenger Regression-Waechter erhalten.

Priorisierte Felder:

- Import closure: Modulimports, exposed Symbole und `analysis`-Closure fuer Typen, Records, Errors und Routinen.
- Routine signatures: Routine-Art, Name, Type-Parameter, Async-Flag, Parameter und Return-Type.
- Contracts + bindings: `requires`, `ensures`, `aborts`, `ContractBindings`, Result-Value/Error-Bindings.
- Abort effects: Abort-Contract-Clauses, ErrorRefs und abortrelevante Call-Pfade im Body-Skelett.
- Result payload/error shape: `ResultTypeName`, OK-Payload, Error-Typ und ErrorRef.
- Control-flow skeleton: `if`, `while`, `case` mit Bedingungen, Branch-Struktur, Invarianten und Variante.
- Mutation targets: `AssignStmt`-Targets und `FieldAssignStmt`-Pfade inklusive semantischer RHS-Form.

## Aktueller Stage-2-Stand

Stage 2 startet mit den gezielt aufgenommenen Compiler-Demos 16, 17 und 18. Diese Samples sind bewusst als Enrichment-Samples markiert, nicht als automatisches Demo-Wachstum:

- `16_abort_propagation_runtime_log`: aborting call propagation und `Main() error`.
- `17_record_mutation_runtime_log`: Assignment und Field Assignment.
- `18_result_error_branch_runtime_log`: Result error branch und imported error constant.

Manifest und Gate:

```text
artifacts/fhir-samples/compiler_v1_stage2/manifest.json
compare-ir-compiler-v1-stage2.cmd
compare-ir-compiler-v1-stage2-update.cmd
```

Der normale Stage-2-Command ist non-mutating und prueft die frisch generierte Python/Go-IR-Paritaet zweigleisig: semantische Projektion und Full-JSON-Hash. Baseline-Schreibzugriff bleibt auf den expliziten Update-Command begrenzt.

## Stage-2-Kandidaten

1. `unsupported_generic_function`
   - Vermutlich kleinster und klarster deferred Block.
   - Vor Aufnahme entscheiden, ob Generics als echter Support-Slice kommen oder bewusst weiter Unsupported bleiben.
   - Wenn Support geplant wird: zuerst IR-Form und Go-Codegen-Strategie klaeren, insbesondere Monomorphisierung vs. Rejection.

2. `unsupported_async_scope_runtime`
   - Groesserer Runtime-Slice fuer Async, Scope und JoinHandle.
   - Nicht nur IR-Export, sondern auch Go-Runtime-Verhalten und Compiler-Codegen muessen gemeinsam passen.
   - Erst angehen, wenn die Runtime-Semantik fuer Scope/Join stabil beschrieben ist.

3. `unsupported_grpc_binding`
   - Zuletzt angehen.
   - gRPC hat bereits einen separaten Binding-Pfad; Compare-IR sollte erst folgen, wenn IDL-, Binding- und Runtime-Semantik klarer sind.

## Gate-Regel

- Stage-2-Gates muessen wie Stage 1 non-mutating sein.
- Baseline-Updates brauchen einen expliziten Update-Command.
- Stage 1 darf durch Stage-2-Arbeit weder Sample-Anzahl noch skipped Set veraendern.
- Stage 2 vergleicht standardmaessig die semantische Compiler-Contract-Projektion und fuehrt den Full-JSON-Hash parallel aus.