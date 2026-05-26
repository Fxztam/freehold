# Test Next: Freehold Compiler V1 Examples

Stand: 2026-05-25

Ziel dieses Testpfads: echte Freehold-Beispielprojekte als Mini-Projekte anfassen, verifizieren, nach Go kompilieren und als generierte Go-Projekte bauen. Dieser Pfad ergaenzt die Language-Module und Goldens; er ist ein pragmatischer Smoke-Test fuer den Compiler-V1-Alltag.

## Aktueller Stand

Der Beispielprojekt-Spielplatz steht unter:

```text
examples/compiler_v1/
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

## Unsupported-Smokes

Bewusst nicht unterstuetzte Go-Codegen-V1-Faelle bleiben als Smoke-Test wichtig. Aktuell abgedeckt:

- User-Generics im Go-Codegen.
- gRPC Service-Deklarationen im allgemeinen Go-Codegen; unary Server-Bindings laufen ueber den separaten `grpc-go-bindings`-Pfad.
- Async/Scope Runtime im Go-Codegen.
- Alte Concurrency/gRPC-Demo mit async/channel/runtime gaps.

Weiterhin geparkt fuer spaetere Unsupported- oder Positiv-Smokes:

- Async/Channels/Scope Runtime als Positiv-Slice.
- Generics-Monomorphisierung, falls sie in V2/V3 angegangen wird.
- gRPC client bindings, explizite Implementierungsbindung, custom status mapping und streaming als V2/V3-Codegen-Pfade.

## Akzeptanzkriterien

- Es gibt einen Beispielordner mit echten Freehold-Modulen.
- Mindestens ein Multi-Modul-Beispiel kompiliert nach Go.
- Das generierte Go-Projekt baut mit `go test ./...`.
- Ein einziger Smoke-Test-Command prueft alle Beispiele.
- Unsupported-Beispiele liefern nachvollziehbare Diagnostics.
- Der Testpfad ist dokumentiert und reproduzierbar.

## Additive Testlinie

Bestehende `.fh`-Faelle und vorhandene Dateien unter `artifacts/` sind eingefrorene Verifikationsbaselines. Neue Compiler-Erkenntnisse werden als neue `.fh`-Faelle plus neue Goldens/Artefakte ergaenzt; vorhandene Artefakte werden nicht aktualisiert.

Der Standardablauf nutzt additive Artifact-Generatoren und prueft die Regel mit:

```text
verify-additive-test-line.cmd
```

`verify-parser-conformance.cmd` fuehrt dieses Gate vor den Go-Tests aus. Erlaubt sind neue Dateien; verboten sind Modifikationen, Loeschungen oder Renames bestehender `.fh`-Faelle und bestehender Artefakte. Der Guard refreshed den Git-Index vor der Statusauswertung, damit content-identische EOL/Stat-Aenderungen nicht als Frozen-Verletzungen zaehlen.

## Naechste sinnvolle Erweiterungen

- Policy-only/rejected V1-Pfade sind vor echten deferred Features abgesichert: `12_type_conflicts` hat Go-Codegen-Rejection-Cases fuer alle negativen Konflikt-Fixtures; `13_contract_blocks` ist fuer gueltige V1-Contracts positiv supported und fuer ungueltige Contract-Fixtures mit Go-Codegen-Rejection-Cases abgesichert; `22_generics` hat Unsupported-Cases fuer frontend-gueltige Generics und Rejection-Cases fuer ungueltige Generics.
- Kleine deferred Codegen-Slices sind fuer V1 abgedeckt: `11_errors_results` Result-value-field-access, `18_string_templates` dynamische Formatargumente und `04_types` breitere User-Type-Alias-Kombinationen.
- Grosse deferred Slices spaeter: `23_concurrency` Runtime/Channels/Scope, `24_grpc_idl` client bindings/implements/custom status mapping/streaming, `21_abort_handling` breitere implication/Handler.
- Aktueller Go-native Project-Semantic-Stand: `verify-go-semantic-projects.cmd` deckt 31 Faelle ab. Die letzten Slices ergaenzen negative Mehr-Package-Faelle fuer Result-`value.field`, Result-Array-`value[index].field`, importierte abortende Routine-Calls, `requires`-Ausdruecke mit importierten Routine-Calls, einen strukturierten importierten Parse-Fehler sowie hidden/non-exposed Symbolnutzung, falsche qualifizierte Modulnutzung, transitive Dependency-Fehler und mehrere Diagnostics in einem Projekt. Der normale single-module Gate bleibt bei 18 Diagnostics.
- Naechster empfohlener Project-Semantic-Slice: bei weiterem Wachstum optional einen separaten `project_semantic_diagnostics`-Gate einfuehren; der bestehende Sammelgate ist fuer die aktuellen project-aware Negativgoldens noch stabil.
- Testmodus fuer Ausgabe-Regression ausweiten: Der Compiler-Example-Smoke schreibt fuer alte buildbare Examples sowie `05_runtime_builtins`, `07_complex_contracts`, `08_cross_module_type_composition`, `09_result_record_type_composition`, `10_result_record_contract_demo`, `11_result_array_record_payload`, `12_qualified_name_conflicts`, `13_control_flow_runtime_log` und `14_big_loop_runtime_log` bereits `<module-name>.log` und vergleicht gegen `examples/expected_logs/<module-name>.expected.log`. Durch einfache Go-Runtime-Checks fuer `requires`/`ensures` sind nun auch die alten Contract-Beispiele Teil dieser Runtime-Flotte. Naechster Schritt ist, weitere neue `compiler_v1`-Examples mit bewusster Ausgabe in diesen Mechanismus aufzunehmen.
- Weitere Cross-Module-Typkompositionen: Namenskonflikte und negative Result-/Import-Kontraktfaelle. Negative Result-`value.field`-Faelle sind in `13_contract_blocks` und `03_import_resolution` als additive Artefakte verankert; `Result<Array<Order, 2>, Error>` ist positiv als Compiler-V1-Smoke und negativ als project-aware Semantic-Golden abgedeckt; qualifizierte gleichnamige Module sind als Compiler-V1-Smoke abgedeckt; doppelt exponierte Routinen, Records und Errors werden in `03_import_resolution` negativ abgesichert. Transitive gleichnamige Records/Errors in getrennten Importgraph-Aesten sind positiv in `import_transitive_name_conflicts` abgedeckt. Offen bleiben weitere komplexe Alias-Konflikte.
- Async/Channels/Scope Runtime als spaeterer Positiv-Slice; ein Unsupported-Smoke dokumentiert die aktuelle Go-Codegen-Grenze.
- gRPC server bindings haben einen ersten separaten unary `grpc-go-bindings`-Pfad; client bindings, explizite Implementierungsbindung, custom status mapping und streaming bleiben V2/V3.
- Dynamische `String.template`-Formatargumente sind in `18_string_templates` fuer positionale, benannte und `Std.IO.logf`-Codegen-Pfade abgedeckt.
- Abort breiter machen als spaeterer CFlow-/Proof-Slice: `21_abort_handling` deckt V1/V2-Propagation ab, breitere abort contract implication und Handler-Syntax bleiben geparkt.
- Kleinere Goldens/Policies fuer `01_core`, `02_import`, `14_comments_whitespace` und `16_control_flow_edges` sind fuer V1 abgedeckt; bei `16_control_flow_edges` bleibt nur path-aware proof integration als spaeterer CFlow-Slice.
- Go-native Semantik-/CFlow-Slices Richtung Bootstrap.
