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

Stage 2 enthaelt inzwischen die gezielt aufgenommenen Compiler-Demos 16 bis 21. Diese Samples sind bewusst als Enrichment-Samples markiert, nicht als automatisches Demo-Wachstum:

- `16_abort_propagation_runtime_log`: aborting call propagation und `Main() error`.
- `17_record_mutation_runtime_log`: Assignment und Field Assignment.
- `18_result_error_branch_runtime_log`: Result error branch und imported error constant.
- `19_async_scope_runtime`: async Routinen, Scope spawn/join und `JoinHandle<T>`-TypeRefs.
- `20_grpc_binding`: gRPC Service Declaration, Proto Field IDs und RPC Request/Response TypeRefs.
- `21_concurrent_grpc_channel_demo`: kombinierte gRPC/async/channel-Oberflaeche mit generischen Runtime-TypeRefs.

Manifest und Gate:

```text
artifacts/fhir-samples/compiler_v1_stage2/manifest.json
compare-ir-compiler-v1-stage2.cmd
compare-ir-compiler-v1-stage2-update.cmd
```

Der normale Stage-2-Command ist non-mutating und prueft die frisch generierte Python/Go-IR-Paritaet zweigleisig: semantische Projektion und Full-JSON-Hash. Zusaetzlich prueft er drei Go-Projektstruktur-Contracts fuer die neueren Runtime-/IDL-Oberflaechen 19/20/21. Baseline-Schreibzugriff bleibt auf den expliziten Update-Command begrenzt.

## Stage-2-Restarbeiten vor Stage 3

1. Dokumente und Matrix mit dem echten Stage-2-Stand synchron halten.
   - `OPEN-COMPARE-IR-STAGE2.md` und `COMPARE-IR-COVERAGE-MATRIX.md` muessen 16-21, Full-JSON-Paritaet und Go-Projektcontracts korrekt ausweisen.
   - `DONE.md` bleibt Ergebnislog fuer ausgefuehrte Checks.

2. Stage-2-Gate als Exit-Kriterium stabilisieren.
   - `compare-ir-compiler-v1-stage2.cmd` muss dauerhaft 6/6 semantic, 6/6 full und 3/3 Go project contracts liefern.
   - Nach neu aufgenommenen Compiler-Demos bleibt Stage-2-Wachstum opt-in; neue Beispiele werden nicht automatisch in das Manifest gezogen.

3. Stage-3-Minimum festlegen.
   - Stage 3 sollte nicht versuchen, den ganzen Compiler zu portieren.
   - Der erste sinnvolle Slice ist ein kleiner Freehold-Compilerkern fuer Namen/Package-Pfade, Diagnosemodelle und minimale IR-/Go-Codegen-Helfer.
   - Akzeptanzkriterium: Stage0 kann diesen Kern bauen, und der Kern verarbeitet Mini-Fixtures deterministisch.

4. Noch bewusst deferred halten.
   - User-Generics im Go-Codegen bleiben ein eigener Strategie-Slice.
   - Vollstaendige Async/Channel-Runtime-Ausfuehrung bleibt groesser als der erste Stage-3-Slice.
   - gRPC Server/Client-Bindings bleiben ausserhalb des ersten Stage-3-Kerns.

## Stage-3-Startvorschlag

Der naechste echte Arbeitsschritt ist ein `compiler_core_v1`-Mini-Projekt in Freehold:

- kleine Datentypen fuer Modulnamen, Symbolnamen und Diagnostics;
- reine Helper-Funktionen fuer Go-Package-Pfade und exportierte Go-Namen;
- Mini-Fixtures mit erwarteten JSON-/Text-Goldens;
- Stage0-Go-Codegen-Projektcontract, der den Freehold-Kern baut;
- optional spaeter ein FH-IR-Exportcontract fuer denselben Kern.

Dieser Slice nutzt Stage 2 als Sicherheitsnetz: Stage 2 beweist, dass die benoetigten Sprach-/Runtime-Oberflaechen fuer einen kleinen Compilerkern stabil genug sind, waehrend Stage 3 erstmals Freehold-Code als Compilerlogik-Artefakt baut.

## Gate-Regel

- Stage-2-Gates muessen wie Stage 1 non-mutating sein.
- Baseline-Updates brauchen einen expliziten Update-Command.
- Stage 1 darf durch Stage-2-Arbeit weder Sample-Anzahl noch skipped Set veraendern.
- Stage 2 vergleicht standardmaessig die semantische Compiler-Contract-Projektion und fuehrt den Full-JSON-Hash parallel aus.