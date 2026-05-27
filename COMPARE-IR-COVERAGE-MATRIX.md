# Compare-IR Coverage Matrix

Stand: 2026-05-27

Diese Matrix beschreibt die aktuelle Compare-IR-Compiler-V1-Abdeckung nach Feature, Sample und zentralen IR-Knoten. Stage 1 bleibt die eingefrorene Basis; Stage 2 ist der gezielte Erweiterungspfad fuer neue Compiler-Demos.

## Sample-Stages

| Stage | Samples | Gate | Status |
| --- | --- | --- | --- |
| Stage 1 | `01` bis `15` | `compare-ir-compiler-v1.cmd` | 18 total, 15 matching, 0 mismatching, 3 bewusst skipped |
| Stage 2 | `16` bis `21` | `compare-ir-compiler-v1-stage2.cmd` | 6 bewusst gewaehlt enrichment samples, 6 semantic/full matching, 0 mismatching, 0 skipped; 3/3 Go project contracts |

## Stage-2-Enrichment-Auswahl

| Sample | Warum bewusst aufgenommen? | Neue IR-Oberflaeche |
| --- | --- | --- |
| `16_abort_propagation_runtime_log` | Abort-Propagation im Runtime-Pfad pruefen | Aborting call propagation, `Main() error`, `AbortContractClause`, `ErrorRef` |
| `17_record_mutation_runtime_log` | Mutation explizit in Compare-IR sichtbar machen | `AssignStmt`, `FieldAssignStmt`, `FieldAccessExpr` |
| `18_result_error_branch_runtime_log` | Normalen Result-Fehlerzweig und importierte Error-Konstante abdecken | `ResultTypeName`, `FieldAccessExpr(path: outcome.error)`, `VarExpr(PaymentDeclined)`, `IfStmt` |
| `19_async_scope_runtime` | Async/Scope-Oberflaeche in Compare-IR und Go-Projektcodegen absichern | `is_async`, `GenericTypeName(JoinHandle<T>)`, Scope spawn/join Calls, Go project contract |
| `20_grpc_binding` | gRPC IDL-Oberflaeche und Proto-Feld-IDs in IR/Projektstruktur absichern | `ServiceDecl`, `RpcDecl`, `proto_id`, `request_type_repr`, `response_type_repr`, gRPC extra files |
| `21_concurrent_grpc_channel_demo` | Kombinierte gRPC/async/channel-Oberflaeche als Stage-2-Stresssample pruefen | `ServiceDecl`, `GenericTypeName(Channel/Sender/Receiver/JoinHandle)`, async routines, Go channel/gRPC contracts |

## Stage-2-Semantikprojektion

Stage 2 vergleicht nicht jedes AST-nahe JSON-Detail gleich hart. Der Gate nutzt eine semantische Compiler-Contract-Projektion mit diesen Prioritaeten:

| Prioritaet | Sichtbare IR-Felder |
| --- | --- |
| Import closure | `module.imports`, exposed symbols, `analysis.types`, `analysis.records`, `analysis.errors`, `analysis.routines` |
| Routine signatures | `routine_kind`, `name`, `type_params`, `is_async`, `params`, `return_type` |
| Contracts + bindings | `contracts.requires`, `contracts.ensures`, `contracts.aborts`, `contract_bindings`, Result value/error bindings |
| Abort effects | `AbortContractClause`, `ErrorRef`, abortrelevante `CallExpr`/`CallStmt`-Pfade |
| Result payload/error shape | `ResultTypeName.ok_type`, `ResultTypeName.error_type`, `ResultTypeName.error_ref`, `outcome.value`, `outcome.error` |
| Control-flow skeleton | `IfStmt`, `WhileStmt`, `CaseStmt`, Branch-Struktur, Bedingungen, Invarianten, Variante |
| Mutation targets | `AssignStmt` target/name, `FieldAssignStmt.path`, semantische RHS-Form |

Reine Source-/AST-Metadaten wie Spans bleiben aus der Projektion draussen. Der Stage-2-Gate fuehrt den Full-JSON-Vergleich parallel ueber `--comparison full` aus, damit der strenge Hash-Waechter erhalten bleibt.

## Feature-Matrix

| Feature | Samples | Zentrale IR-Knoten / Felder | Hinweise |
| --- | --- | --- | --- |
| Minimal module / primitive checks | `01_minimal_app` | `Module`, `RoutineDecl`, `LetStmt`, `CheckStmt`, `BinaryExpr`, `NumberExpr`, `BoolExpr`, `VarExpr` | Basis fuer Modulstruktur, lokale Bindings und einfache Pruefungen. |
| Records | `02_records_functions`, `08_cross_module_type_composition`, `09_result_record_type_composition`, `10_result_record_contract_demo`, `11_result_array_record_payload`, `12_qualified_name_conflicts`, `15_result_abort_array_runtime_builtins`, `16_abort_propagation_runtime_log`, `17_record_mutation_runtime_log`, `20_grpc_binding`, `21_concurrent_grpc_channel_demo` | `RecordTypeDecl`, `RecordDef`, `RecordFieldDef`, `RecordLiteralExpr`, `FieldAccessExpr`, `TypeName`, `proto_id` | Deckt lokale Records, importierte Records, verschachtelte Records, gleichnamige Records aus getrennten Modulen und Proto-Record-Felder ab. |
| Arrays | `04_result_abort`, `08_cross_module_type_composition`, `11_result_array_record_payload`, `15_result_abort_array_runtime_builtins` | `ArrayTypeName`, `ArrayLiteralExpr`, `IndexExpr`, `IndexedFieldAccessExpr`, `ResultTypeName.ok_type.element_type_repr` | Deckt Array-Payloads, Indexzugriffe und Result-Array-Contracts ab. |
| Result success payload | `04_result_abort`, `09_result_record_type_composition`, `10_result_record_contract_demo`, `11_result_array_record_payload`, `15_result_abort_array_runtime_builtins` | `ResultTypeName`, `ReturnOk`, `FieldAccessExpr`, `ContractBindings`, `result_value_binding`, `VarExpr(value)` | Erfolgreiche Result-Pfade mit Record- und Array-Payloads. |
| Result error branch | `18_result_error_branch_runtime_log` | `ResultTypeName`, `FieldAccessExpr(path: outcome.error)`, `BinaryExpr`, `VarExpr(PaymentDeclined)`, `IfStmt` | Stage-2-Anker fuer normalen Result-Fehlerzweig ohne Abort-Propagation. |
| Error constants | `12_qualified_name_conflicts`, `18_result_error_branch_runtime_log` | `ErrorDecl`, `ErrorRef`, `VarExpr(<ErrorName>)`, `BinaryExpr` | Deckt gleichnamige Error-Symbole und direkte importierte Error-Konstanten im Ausdruckspfad ab. |
| Abort contracts | `04_result_abort`, `15_result_abort_array_runtime_builtins`, `16_abort_propagation_runtime_log` | `AbortContractClause`, `ErrorRef`, `aborts`, `contracts.aborts`, `CallExpr`, `LetStmt` | Deckt deklarierte Aborts, importierte abortende Calls und Stage-2 Abort-Propagation ab. |
| Requires / ensures | `07_complex_contracts`, `09_result_record_type_composition`, `10_result_record_contract_demo`, `11_result_array_record_payload`, `15_result_abort_array_runtime_builtins`, `17_record_mutation_runtime_log` | `ContractClause`, `contracts.requires`, `contracts.ensures`, `ContractBindings`, `BinaryExpr`, `FieldAccessExpr`, `IndexedFieldAccessExpr` | Umfasst einfache und mehrteilige Contracts sowie Result-`value`-Bindings. |
| Imports / exposed symbols | `03_cross_module_calls`, `04_result_abort`, `08_cross_module_type_composition`, `09_result_record_type_composition`, `10_result_record_contract_demo`, `11_result_array_record_payload`, `12_qualified_name_conflicts`, `15_result_abort_array_runtime_builtins`, `16_abort_propagation_runtime_log`, `18_result_error_branch_runtime_log` | `ImportDecl`, `analysis.types`, `analysis.records`, `analysis.errors`, `analysis.routines`, `TypeName`, `ErrorRef` | Deckt exposed Routinen, Records, Errors und importierte Typ-Closure ab. |
| Qualified calls | `03_cross_module_calls`, `12_qualified_name_conflicts`, `15_result_abort_array_runtime_builtins` | `CallExpr(name: Module.Routine)`, `CallStmt`, `ImportDecl` | Deckt qualifizierte Domain-Calls und Namenskonflikte zwischen Modulen ab. |
| Runtime calls | `05_runtime_builtins`, `07_complex_contracts`, `08_cross_module_type_composition`, `09_result_record_type_composition`, `10_result_record_contract_demo`, `11_result_array_record_payload`, `12_qualified_name_conflicts`, `13_control_flow_runtime_log`, `14_big_loop_runtime_log`, `15_result_abort_array_runtime_builtins`, `16_abort_propagation_runtime_log`, `17_record_mutation_runtime_log`, `18_result_error_branch_runtime_log` | `CallStmt`, `CallExpr`, `PositionalArg`, `NamedArg`, `StringExpr` | Deckt `Std.IO`, `String`, `Math`, `Json` und `Big` Runtime-Oberflaechen im IR ab. |
| Control flow: if | `13_control_flow_runtime_log`, `18_result_error_branch_runtime_log` | `IfStmt`, `then_body`, `else_body`, `BinaryExpr` | Stage 2 ergaenzt den If-Zweig ueber Result-Error-Auswertung. |
| Control flow: while | `06_integer_big_loop`, `13_control_flow_runtime_log`, `14_big_loop_runtime_log` | `WhileStmt`, `invariants`, `variant`, `AssignStmt`, `BinaryExpr` | Deckt Integer- und BigInteger-Schleifen inklusive Invarianten/Variante ab. |
| Control flow: case | `13_control_flow_runtime_log` | `CaseStmt`, `branches`, `default_body` | Ein aktueller Anker fuer `case` im Compare-IR. |
| Mutation / assignment | `13_control_flow_runtime_log`, `14_big_loop_runtime_log`, `17_record_mutation_runtime_log` | `AssignStmt`, `FieldAssignStmt`, `FieldAccessExpr`, `CallExpr` | Stage 2 deckt explizit Record-Feldmutation und String-Runtime in Field Assignment ab. |
| Async / Scope | `19_async_scope_runtime`, `21_concurrent_grpc_channel_demo` | `RoutineDecl.is_async`, `GenericTypeName(JoinHandle<T>)`, `CallExpr(scope.spawn/join)`, `AwaitExpr` | Stage 2 sichert die IR- und Go-Projektoberflaeche ab; vollstaendige parallele Runtime-Ausfuehrung bleibt deferred. |
| Channels | `21_concurrent_grpc_channel_demo` | `GenericTypeName(Channel<T>/Sender<T>/Receiver<T>)`, Runtime helper calls | Stage 2 prueft TypeRefs und Go-Projektwrapper fuer Channel/Sender/Receiver. |
| gRPC IDL / project bindings | `20_grpc_binding`, `21_concurrent_grpc_channel_demo` | `ServiceDecl`, `RpcDecl`, `request_type_repr`, `response_type_repr`, `proto_id` | Stage 2 prueft IR-Paritaet und Go-Projektstrukturcontracts fuer gRPC-Stubs/Bindings. |
| Cross-module type composition | `08_cross_module_type_composition`, `09_result_record_type_composition`, `10_result_record_contract_demo`, `11_result_array_record_payload`, `15_result_abort_array_runtime_builtins`, `16_abort_propagation_runtime_log` | `ImportDecl`, `RecordDef`, `RecordFieldDef`, `TypeName`, `ArrayTypeName`, `ResultTypeName` | Deckt verschachtelte importierte Typen, Result-Payloads und Array-Payloads ab. |
| Name conflicts | `12_qualified_name_conflicts` | `ImportDecl`, `RecordDef`, `ErrorRef`, `CallExpr`, `TypeName` | Anker fuer gleichnamige Records, Errors und Routinen in getrennten Imports. |

## Sample-Matrix

| Sample | Stage | Feature-Schwerpunkt | Wichtige IR-Knoten |
| --- | --- | --- | --- |
| `01_minimal_app` | Stage 1 | Minimal module, primitive checks | `Module`, `RoutineDecl`, `LetStmt`, `CheckStmt`, `BinaryExpr` |
| `02_records_functions` | Stage 1 | Records, functions | `RecordTypeDecl`, `RecordDef`, `RecordLiteralExpr`, `FieldAccessExpr`, `ReturnPlain` |
| `03_cross_module_calls` | Stage 1 | Imports, exposed calls, qualified calls | `ImportDecl`, `CallExpr`, `CallStmt`, `analysis.routines` |
| `04_result_abort` | Stage 1 | Result + Array payload, aborting imported call | `ResultTypeName`, `ArrayTypeName`, `AbortContractClause`, `LetStmt`, `CallExpr` |
| `05_runtime_builtins` | Stage 1 | Runtime calls | `CallExpr`, `CallStmt`, `StringExpr`, `PositionalArg`, `NamedArg` |
| `06_integer_big_loop` | Stage 1 | Integer loop | `WhileStmt`, `AssignStmt`, `BinaryExpr`, `CallExpr` |
| `07_complex_contracts` | Stage 1 | Requires/ensures | `ContractClause`, `ContractBindings`, `BinaryExpr`, `CallStmt` |
| `08_cross_module_type_composition` | Stage 1 | Imported nested records, arrays | `ImportDecl`, `RecordDef`, `ArrayTypeName`, `FieldAccessExpr`, `IndexExpr` |
| `09_result_record_type_composition` | Stage 1 | Result<Record, Error>, nested ensures | `ResultTypeName`, `ContractClause`, `FieldAccessExpr`, `ReturnOk` |
| `10_result_record_contract_demo` | Stage 1 | Result record contracts, runtime output | `ResultTypeName`, `ContractBindings`, `FieldAccessExpr`, `CallStmt` |
| `11_result_array_record_payload` | Stage 1 | Result<Array<Record>>, index access | `ResultTypeName`, `ArrayTypeName`, `IndexExpr`, `IndexedFieldAccessExpr` |
| `12_qualified_name_conflicts` | Stage 1 | Qualified calls, import name conflicts | `ImportDecl`, `CallExpr`, `RecordDef`, `ErrorRef` |
| `13_control_flow_runtime_log` | Stage 1 | if/while/case | `IfStmt`, `WhileStmt`, `CaseStmt`, `AssignStmt` |
| `14_big_loop_runtime_log` | Stage 1 | Big loop runtime | `WhileStmt`, `AssignStmt`, `CallExpr`, `BinaryExpr` |
| `15_result_abort_array_runtime_builtins` | Stage 1 | Result/Abort/Array + runtime builtins | `ResultTypeName`, `ArrayTypeName`, `AbortContractClause`, `CallExpr`, `IndexedFieldAccessExpr` |
| `16_abort_propagation_runtime_log` | Stage 2 | Abort propagation runtime path | `AbortContractClause`, `ErrorRef`, `LetStmt`, `CallExpr`, `FieldAccessExpr` |
| `17_record_mutation_runtime_log` | Stage 2 | Record mutation / field assignment | `RecordTypeDecl`, `FieldAssignStmt`, `FieldAccessExpr`, `CallExpr` |
| `18_result_error_branch_runtime_log` | Stage 2 | Result error branch, error constant | `ResultTypeName`, `FieldAccessExpr`, `VarExpr`, `IfStmt`, `CallStmt` |
| `19_async_scope_runtime` | Stage 2 | Async Scope / JoinHandle | `RoutineDecl.is_async`, `GenericTypeName`, `CallExpr`, `AwaitExpr` |
| `20_grpc_binding` | Stage 2 | gRPC IDL and proto records | `ServiceDecl`, `RpcDecl`, `RecordFieldDef.proto_id`, `TypeName` |
| `21_concurrent_grpc_channel_demo` | Stage 2 | gRPC + async + channel type refs | `ServiceDecl`, `GenericTypeName`, `RoutineDecl.is_async`, `CallExpr` |

## Gaps / Deferred

| Gap | Current anchor | Next path |
| --- | --- | --- |
| User-defined generics in Go codegen | Unsupported `unsupported_generic_function` | Future strategy slice after monomorphization-vs-rejection decision. |
| Full async/channel runtime execution | Stage-2 samples `19`/`21` cover IR and sequential Go lowering | Keep deferred for first Stage-3 slice; do not block compiler-core bootstrap. |
| Full gRPC server/client runtime | Stage-2 samples `20`/`21` cover IDL and project binding shape | Keep binding/runtime expansion separate from Stage-3 compiler-core start. |
| Broader abort handling | `04`, `15`, `16` cover V1 propagation | Handler syntax and broader implication remain deferred. |
