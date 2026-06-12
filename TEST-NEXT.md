# Test Next: Freehold Compiler V1 Examples

Stand: 2026-06-03

Ziel dieses Testpfads: echte Freehold-Beispielprojekte als Mini-Projekte anfassen, verifizieren, nach Go kompilieren und als generierte Go-Projekte bauen. Dieser Pfad ergaenzt die Language-Module und Goldens; er ist ein pragmatischer Smoke-Test fuer den Compiler-V1-Alltag.

## Aktueller Stand

Der Beispielprojekt-Spielplatz steht unter:

```text
examples/compiler_v1/
```

Die Compare-IR-Abdeckung der Compiler-V1-Samples ist als Feature/Sample/IR-Knoten-Matrix dokumentiert in:

```text
COMPARE-IR-COVERAGE-MATRIX.md
```

Der Standard-Command ist:

```text
verify-compiler-examples.cmd
```

Der Wrapper prueft pro positivem Beispiel:

1. `python -m freehold verify <entry>`
2. `python -m freehold go-codegen-project <entry> --output-dir .tmp/compiler_examples/<name> --json ...`
3. das generierte `build.cmd` im Output-Projekt
4. fuer alte buildbare Examples einen Runtime-Testlauf mit `<module-name>.log` gegen `examples/expected_logs/<module-name>.expected.log`

Fuer bewusst nicht unterstuetzte Beispiele prueft der Wrapper:

1. Frontend-Verifikation ist erfolgreich.
2. Go-Projekt-Codegen schlaegt erwartbar fehl.
3. Das JSON enthaelt eine Go-Codegen-Diagnostic (`FH-GOCODEGEN-0001`).

## Positive Beispiele

1. `01_minimal_app`
   - `App.Main` ohne Imports
   - primitive Werte
   - `check`

2. `02_records_functions`
   - Record-Typen
   - Record-Literale
   - Feldzugriffe
   - einfache Funktionen

3. `03_cross_module_calls`
   - `App.Main` importiert ein Domain-Modul
   - exposed Call: `is_valid(...)`
   - qualifizierter Call: `Domain.Rules.is_valid(...)`

4. `04_result_abort`
   - importierter Record-Typ
   - `Result<Array<imported Record>, imported Error>`
   - importierter abortender Call mit Go-`err`-Propagation
   - abgedeckte V1-Aborts bleiben same-error-name propagation; breitere abort contract implication und Handler-Syntax sind deferred

5. `05_runtime_builtins`
   - `String.*`
   - `String.template` fuer statische Template-Literale
   - `Math.*`
   - `Json.stringify`
   - `Std.IO.log` / `Std.IO.logf`
   - `Big.*`

6. `06_integer_big_loop`
   - Freehold-`Integer` in `while`-Schleifen
   - lokale Integer-Laufvariablen gegen Integer-Parameter
   - `Big.fromInteger(...)` mit berechneten Integer-Werten

7. `07_complex_contracts`
   - komplexe `requires` mit mehreren kommaseparierten Bedingungen
   - komplexe `ensures` mit mehreren kommaseparierten Bedingungen
   - Runtime-Smoke fuehrt `main()` aus und vergleicht die Ausgabe

8. `08_cross_module_type_composition`
   - importierte Records als Felder in einem Record eines zweiten Domain-Moduls
   - direkte `Array<imported/composed Record>`-Signatur zwischen Domain und App
   - verschachtelte Feldzugriffe und Array-Indexzugriffe in `App.Main`
   - Runtime-Smoke fuehrt `main()` aus und vergleicht die Ausgabe

9. `09_result_record_type_composition`
   - importierte verschachtelte Records als `Result<Order, Error>`-Payload
   - `ensures value...` ueber verschachtelte Record-Felder
   - Runtime-Smoke fuehrt `main()` aus und vergleicht die Ausgabe

10. `10_result_record_contract_demo`
   - sprechendes Demo fuer importierte verschachtelte Records als `Result<Shipment, Error>`-Payload
   - `ensures value...` prueft verschachtelte Record-Felder des erfolgreichen Result-Payloads
   - `App.Main` verwendet `outcome.value` als normalen Record-Wert und schreibt eine Runtime-Ausgabe

11. `11_result_array_record_payload`
   - importierte verschachtelte Records als `Result<Array<Order, 2>, Error>`-Payload
   - `App.Main` bindet `outcome.value` explizit an ein Array und liest `orders[0]` / `orders[1]` als Records
   - Runtime-Smoke prueft verschachtelte Felder und Ausgabe fuer beide Array-Elemente

12. `12_qualified_name_conflicts`
   - zwei importierte Module definieren gleichnamige Records, Errors und Routinen (`Order`, `Address`, `NotFound`, `load_order`)
   - `App.Main` verwendet qualifizierte Calls, damit beide Namensraeume im gleichen Go-Projekt kollisionsfrei bleiben
   - Runtime-Smoke prueft, dass beide Modulpfade getrennte Werte und Ausgaben liefern

13. `13_control_flow_runtime_log`
   - `while` mit Invarianten und Variante
   - `if`/`else`-Zweig mit Runtime-Ausgabe
   - `case` ueber berechnetem Wert

14. `14_big_loop_runtime_log`
   - BigInteger-Akkumulation in einer Schleife
   - lokale Integer-Laufvariablen als Big-Konversionsquelle
   - Runtime-Smoke prueft berechnete Big-Ausgabe

15. `15_result_abort_array_runtime_builtins`
   - `Result<Array<StockItem, 3>, StockMissing>` mit Record-Payloads
   - abortender importierter Domain-Call plus Runtime-Builtins in einem Drei-Modul-Projekt
   - Runtime-Smoke prueft Result/Abort/Array sowie Math/String/Json/Big-Ausgabe

16. `16_abort_propagation_runtime_log`
   - sprechendes Demo fuer erfolgreiche Abort-Propagation ueber mehrere Routinen
   - `main` deklariert den propagierten `NotFound`-Abort explizit
   - Runtime-Smoke prueft den normalen Erfolgszweig mit sichtbarer Ausgabe

17. `17_record_mutation_runtime_log`
   - Record-Feldmutation (`record.field := ...`) im Runtime-Pfad
   - String-Runtime-Funktion in einer Feldzuweisung
   - Runtime-Smoke prueft mutierten Record-Zustand

17b. `17_mutation_record_update_runtime_log`
   - rekonstruiertes Demo im leeren 17er-Kontext
   - Record-Update ueber Prozedurargument plus mehrere Field Assignments
   - Runtime-Smoke prueft aktualisierte SKU, Menge, Reservierung, Boolean-Feld und String-Marker

18. `18_result_error_branch_runtime_log`
   - normaler `Result`-Fehlerzweig ohne Abort-Propagation
   - `outcome.error` wird im App-Code ausgewertet und ausgegeben
   - Runtime-Smoke prueft Fehlerzweig und Error-Payload

19. `19_async_scope_runtime`
   - async/scope/JoinHandle-Oberflaeche im Compiler-V1-Projektpfad
   - aktueller Smoke sichert Verifikation, IR-/Projektoberflaeche und Go-Codegen-Grenzen ab

20. `20_grpc_binding`
   - gRPC IDL / Binding-Oberflaeche im Compiler-V1-Projektpfad
   - unary Server-Bindings bleiben ueber den separaten `grpc-go-bindings`-Pfad abgedeckt

21. `21_concurrent_grpc_channel_demo`
   - Concurrency/gRPC/Channel-Demo als integrierter Compiler-V1-Smoke
   - vollstaendige scheduler-backed Runtime-Ausfuehrung bleibt spaeterer Runtime-Slice

23. `23_generic_type_inference_and_constraints`
   - Generics-Inferenz und Constraints im Compiler-V1-Beispielpfad
   - Go-Projekt-Codegen baut fuer die monomorphisierten konkreten Instanzen

25. `25_quantified_arrays`
   - Array-Quantifier im Compiler-V1-Beispielpfad
   - Verifikation und Go-Projekt-Codegen sichern den positiven Pfad ab

26. `26_generic_function`
   - vormals unsupported Generic-Function-Smoke, jetzt positiver Compiler-V1-Smoke
   - generische Function-/Procedure-Instanzen werden fuer Go monomorphisiert

27. `27_websocket_demo`
   - einfacher WebSocket-Transport-Smoke ueber `Std.Connect.WebSocket`
   - Go-native WebSocket-Runtime und Runtime-Log werden im Example-Gate geprueft

28. `28_websocket_multi_client_demo`
   - Multi-Client-WebSocket-Smoke ueber `Std.Connect.WebSocket`
   - prueft mehrere Verbindungen und Runtime-Log-Ausgabe

29. `29_websocket_go_backend_demo`
   - WebSocket-Client gegen externen Go-Backend-Smoke
   - prueft `Std.Connect.WebSocket.connect` und Backend-Integration

30. `30_websocket_json_broadcast_demo`
   - typed JSON Broadcast ueber `Std.Connect.WebSocket`
   - nutzt `ConnectionScope`, `MessageScope`, Keepalive, Backpressure und Close-Status

32. `32_websocket_json_broadcast_schema_neg`
   - WebSocket-naher JSON-Negativslice ohne eigene Transportverbindung
   - prueft runtime-invalid JSON-/Schema-Faelle als `Result`-Fehler

33. `33_websocket_room_broadcast_demo`
   - WebSocket-naher Room-/Topic-Broadcast-Slice ueber Channels
   - prueft, dass nur Clients im Ziel-Room queued werden

34. `34_http_rest_contract_demo`
   - erster HTTP/REST-Stdlib-Smoke ueber `Std.Connect.Common`, `Std.Connect.Http` und `Std.Connect.Rest`
   - prueft Endpoint, RequestScope, typed JSON GET/POST und `ProblemDetails` ohne native Netzwerk-Runtime

35. `35_http_client_go_backend_demo`
   - Go-native HTTP-Client-Smoke ueber `Std.Connect.Http.send`, `get` und `post_json`
   - prueft echte GET-/POST-/404-Roundtrips gegen ein kleines Go-Backend auf Port 8104
   - verifiziert Statuscodes, Response-Body-JSON, `Json.parse<Record>` und Expected-Log im Example-Gate

36. `36_http_server_demo`
   - Go-native HTTP-Server-Smoke ueber `Std.Connect.Http.serve`, `accept_request`, `respond` und `stop_server`
   - ein Freehold-Server bedient GET-/POST-Requests des nativen HTTP-Clients im selben Prozess auf Port 8106
   - verifiziert Routing nach Methode/Pfad, Response-JSON und Expected-Log im Example-Gate

37. `37_http_middleware_demo`
   - datengetriebene Middleware-Onion (Logging + Auth) ueber `Std.Connect.Http.MiddlewareContext`, `context_with_trace`, `context_short_circuit` und `with_trace_header`
   - autorisierter Request durchlaeuft alle Schichten inkl. Handler, anonymer Request wird von der Auth-Schicht mit 401 kurzgeschlossen (Port 8107)
   - der Onion-Trace wird ueber den Response-Header zurueckgespiegelt und im Expected-Log verifiziert

38. `38_http_streaming_demo`
   - Go-native HTTP-Streaming-Smoke ueber `Std.Connect.Http.respond_stream` und `open_stream` (HTTP/1.1 `Transfer-Encoding: chunked`)
   - der Server sendet drei Chunks ueber einen `Channel<String>`/`Receiver<String>`; der native Client liest sie via `StreamResponse.chunks` wieder ein (Port 8108)
   - verifiziert Chunk-Reihenfolge, Reassembly und Expected-Log im Example-Gate

39. `39_http_sse_demo`
   - Go-native SSE-Smoke ueber `Std.Connect.Http.respond_sse` und `open_sse` (`text/event-stream`, `event:`/`data:`-Frames)
   - der Server sendet drei `SseEvent`-Werte ueber einen `Channel<SseEvent>`/`Receiver<SseEvent>`; der native Client liest sie via `SseStream.events` wieder ein (Port 8109)
   - verifiziert Event-Reihenfolge, Event-Typ/Daten und Expected-Log im Example-Gate

## Unsupported-Smokes

Bewusst nicht unterstuetzte Go-Codegen-V1-Faelle bleiben als Smoke-Test wichtig. Aktuell abgedeckt:

- gRPC Service-Deklarationen im allgemeinen Go-Codegen; unary Server-Bindings laufen ueber den separaten `grpc-go-bindings`-Pfad.
- Async/Scope Runtime im Go-Codegen.
- Alte Concurrency/gRPC-Demo mit async/channel/runtime gaps.

Weiterhin geparkt fuer spaetere Unsupported- oder Positiv-Smokes:

- Async/Channels/Scope Runtime als Positiv-Slice.
- gRPC client/server bindings, custom status mapping und streaming sind inzwischen vollständig implementiert.

## Akzeptanzkriterien

- Es gibt einen Beispielordner mit echten Freehold-Modulen.
- Mindestens ein Multi-Modul-Beispiel kompiliert nach Go.
- Das generierte Go-Projekt baut mit `go test ./...`.
- Ein einziger Smoke-Test-Command prueft alle Beispiele.
- Unsupported-Beispiele liefern nachvollziehbare Diagnostics.
- Der Testpfad ist dokumentiert und reproduzierbar.

## Additive Testlinie

Bestehende `.fh`-Faelle und vorhandene Dateien unter `artifacts/` sind eingefrorene Verifikationsbaselines. Neue Compiler-Erkenntnisse werden als neue `.fh`-Faelle plus neue Goldens/Artefakte ergaenzt; vorhandene Artefakte werden nicht aktualisiert.

Der Compiler-V1-Compare-IR-Gate bleibt im normalen Check-Modus non-mutating:

```text
compare-ir-compiler-v1.cmd
```

Der Command generiert Python- und Go-IR in ein temporaeres Verzeichnis, prueft zuerst die frisch generierte Python/Go-Paritaet und vergleicht danach beide generierten Seiten gegen die eingefrorenen Baselines unter `artifacts/compare-ir/compiler_v1/`. Baseline-Updates sind nur ueber den expliziten Update-Command erlaubt:

```text
compare-ir-compiler-v1-update.cmd
```

Die drei bewussten Stage-1-Skips (`unsupported_generic_function`, `unsupported_async_scope_runtime`, `unsupported_grpc_binding`) werden nicht in Stage 1 nachgezogen. Stage 2 ist als eigener Pfad in `OPEN-COMPARE-IR-STAGE2.md` geplant, mit separatem Manifest/Gate und demselben non-mutating Default. Der aktuelle Stage-2-Gate ist:

```text
compare-ir-compiler-v1-stage2.cmd
```

Baseline-Updates fuer Stage 2 laufen nur explizit ueber:

```text
compare-ir-compiler-v1-stage2-update.cmd
```

Der Standardablauf nutzt additive Artifact-Generatoren und prueft die Regel mit:

```text
verify-additive-test-line.cmd
```

`verify-parser-conformance.cmd` fuehrt dieses Gate vor den Go-Tests aus. Erlaubt sind neue Dateien; verboten sind Modifikationen, Loeschungen oder Renames bestehender `.fh`-Faelle und bestehender Artefakte. Der Guard refreshed den Git-Index vor der Statusauswertung, damit content-identische EOL/Stat-Aenderungen nicht als Frozen-Verletzungen zaehlen.

## Naechste sinnvolle Erweiterungen

- Policy-only/rejected V1-Pfade sind vor echten deferred Features abgesichert: `12_type_conflicts` hat Go-Codegen-Rejection-Cases fuer alle negativen Konflikt-Fixtures; `13_contract_blocks` ist fuer gueltige V1-Contracts positiv supported und fuer ungueltige Contract-Fixtures mit Go-Codegen-Rejection-Cases abgesichert; `22_generics` hat Unsupported-Cases fuer frontend-gueltige Generics und Rejection-Cases fuer ungueltige Generics.
- Generics-Inferenz, Constraints und Function/Procedure-Monomorphisierung sind inzwischen positiv abgedeckt: `23_generic_type_inference_and_constraints` und `26_generic_function` laufen als Compiler-V1-Go-Codegen-Smokes; das V2/V3-Modul `03_generic_type_inference_and_constraints` deckt inklusive nested conflict und monomorphized Go codegen `8/8` Faelle ab.
- Kleine deferred Codegen-Slices sind fuer V1 abgedeckt: `11_errors_results` Result-value-field-access, `13_contract_blocks` Result-Array-`value[index].field`-Contracts, `18_string_templates` dynamische Formatargumente und `04_types` breitere User-Type-Alias-Kombinationen.
- Grosse deferred Slices spaeter: `23_concurrency` Runtime/Channels/Scope (inzwischen in Go supported), `24_grpc_idl` client bindings/custom status mapping/streaming (inzwischen supported), `21_abort_handling` breitere implication/Handler.
- Aktueller Go-native Project-Semantic-Stand: `verify-go-semantic-projects.cmd` deckt 18 OK-/Loader-Projektfaelle ab; `verify-go-project-semantic-diagnostics.cmd` deckt 13 negative project-aware Semantikgoldens ab. Die negativen Goldens umfassen Result-`value.field`, Result-Array-`value[index].field`, importierte abortende Routine-Calls, `requires`-Ausdruecke mit importierten Routine-Calls, hidden/non-exposed Symbolnutzung, falsche qualifizierte Modulnutzung und mehrere Diagnostics in einem Projekt. Der normale single-module Gate bleibt bei 18 Diagnostics.
- Naechster empfohlener Project-Semantic-Slice: die Gate-Trennung beibehalten; neue Loader-/OK-Faelle gehen in `verify-go-semantic-projects.cmd`, neue negative semantische Goldens in `verify-go-project-semantic-diagnostics.cmd`.
- Testmodus fuer Ausgabe-Regression weiter nutzen: Der Compiler-Example-Smoke schreibt fuer alte buildbare Examples sowie `05_runtime_builtins`, `07_complex_contracts`, `08_cross_module_type_composition`, `09_result_record_type_composition`, `10_result_record_contract_demo`, `11_result_array_record_payload`, `12_qualified_name_conflicts`, `13_control_flow_runtime_log`, `14_big_loop_runtime_log` und `15_result_abort_array_runtime_builtins` bereits `<module-name>.log` und vergleicht gegen `examples/expected_logs/<module-name>.expected.log`. Durch einfache Go-Runtime-Checks fuer `requires`/`ensures` sind nun auch die alten Contract-Beispiele Teil dieser Runtime-Flotte. `15_result_abort_array_runtime_builtins` ist der aktuelle Anker fuer Result/Abort/Array plus Math/String/Json/Big-Builtins in einem Drei-Modul-Projekt und deckt nun Result-Array-`value[index]`-Contracts ab; offen bleiben gezielte Positiv-Smokes fuer abortende Calls im Runtime-Ausdruckspfad.
- Weitere Cross-Module-Typkompositionen: Namenskonflikte und negative Result-/Import-Kontraktfaelle. Negative Result-`value.field`-Faelle sind in `13_contract_blocks` und `03_import_resolution` als additive Artefakte verankert; `Result<Array<Order, 2>, Error>` ist positiv als Compiler-V1-Smoke und negativ als project-aware Semantic-Golden abgedeckt; qualifizierte gleichnamige Module sind als Compiler-V1-Smoke abgedeckt; doppelt exponierte Routinen, Records und Errors werden in `03_import_resolution` negativ abgesichert. Transitive gleichnamige Records/Errors in getrennten Importgraph-Aesten sind positiv in `import_transitive_name_conflicts` abgedeckt. Offen bleiben weitere komplexe Alias-Konflikte.
- Async/Channels/Scope Runtime als spaeterer Positiv-Slice; ein Unsupported-Smoke dokumentiert die aktuelle Go-Codegen-Grenze.
- gRPC server und client bindings, custom status mapping und streaming sind inzwischen vollständig unterstützt.
- Dynamische `String.template`-Formatargumente sind in `18_string_templates` fuer positionale, benannte und `Std.IO.logf`-Codegen-Pfade abgedeckt.
- Abort breiter machen als spaeterer CFlow-/Proof-Slice: `21_abort_handling` deckt V1/V2-Propagation ab, breitere abort contract implication und Handler-Syntax bleiben geparkt.
- Kleinere Goldens/Policies fuer `01_core`, `02_import`, `14_comments_whitespace` und `16_control_flow_edges` sind fuer V1 abgedeckt; bei `16_control_flow_edges` bleibt nur path-aware proof integration als spaeterer CFlow-Slice.
- Go-native Semantik-/CFlow-Slices Richtung Bootstrap.

## V2/V3 Language-Module Baseline

Der aktuelle V2/V3-Gate steht bei:

```text
verify-language-modules-v2_3.cmd
54/54 language module tests passed
```

Neu beziehungsweise jetzt dokumentiert:

- `03_generic_type_inference_and_constraints`: Inferenz, Constraints, Procedure Generics, nested inference conflict und monomorphized Go codegen.
- `07_concurrency_verification`: channel invariant send substitution und alias violation als gezielte Pos/Neg-Abdeckung.
- `08_runtime_assertions`: VM Runtime Assertions und Hardening fuer Subtype-Ranges, Array-Bounds und Check-Verifikation.
