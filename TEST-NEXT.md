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

5. `05_runtime_builtins`
   - `String.*`
   - `String.template`
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

## Unsupported-Smokes

Bewusst nicht unterstuetzte Go-Codegen-V1-Faelle bleiben als Smoke-Test wichtig. Aktuell abgedeckt:

- User-Generics im Go-Codegen.
- gRPC Go-Bindings.
- Alte Concurrency/gRPC-Demo mit async/channel/runtime gaps.

Weiterhin geparkt fuer spaetere Unsupported- oder Positiv-Smokes:

- Async/Channels/Scope Runtime.
- Generics-Monomorphisierung, falls sie in V2/V3 angegangen wird.
- gRPC server/client bindings, sobald `.proto`-Codegen nicht mehr das Ende der V1-Linie ist.

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

- Testmodus fuer Ausgabe-Regression ausweiten: Der Compiler-Example-Smoke schreibt fuer alte buildbare Examples und das neue `07_complex_contracts`-Beispiel bereits `<module-name>.log` und vergleicht gegen `examples/expected_logs/<module-name>.expected.log`. Durch einfache Go-Runtime-Checks fuer `requires`/`ensures` sind nun auch die alten Contract-Beispiele Teil dieser Runtime-Flotte. Naechster Schritt ist, weitere neue `compiler_v1`-Examples mit bewusster Ausgabe in diesen Mechanismus aufzunehmen.
- Weitere Cross-Module-Typkompositionen: direkte `Array<imported Record>`-Signaturen, verschachtelte importierte Records/Results und Namenskonflikte.
- Async/Channels/Scope Runtime als Unsupported-Smoke oder spaeterer Positiv-Slice.
- gRPC server/client bindings als eigener V2/V3-Codegen-Pfad.
- Go-native Semantik-/CFlow-Slices Richtung Bootstrap.