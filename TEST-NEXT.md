# Test Next: Freehold Compiler Test Modules

Stand: 2026-05-24

Ziel fuer den naechsten Arbeitsschritt: einen kleinen Freehold-Testmodul-Spielplatz schaffen, mit dem echte Freehold-Beispielmodule verifiziert, nach Go kompiliert und als Go-Projekt gebaut werden koennen.

## Zielbild

Wir wollen nicht nur Language-Module testen, sondern echte Beispielmodule als Mini-Projekte anfassen koennen:

- Freehold-Quellmodule schreiben.
- Importierte Freehold-Module verwenden.
- Verifier laufen lassen.
- `go-codegen-project` laufen lassen.
- generiertes Go-Projekt mit `build.cmd` bauen.
- Unsupported-Features sauber als Diagnostics sehen.

## Vorgeschlagene Struktur

Ein neuer Beispielbereich, z.B.:

```text
examples/compiler_v1/
    App/Main.fh
    Domain/Rules.fh
    Domain/Types.fh
    Runtime/Demo.fh
```

Moegliche Alternative:

```text
samples/compiler_v1/
```

Entscheidung morgen: `examples/` oder `samples/`, je nachdem was besser zum Repo passt.

## Standard-Command

Ein einzelner Wrapper soll alle Beispielmodule pruefen, z.B.:

```text
verify-compiler-examples.cmd
```

Der Wrapper soll pro Beispielprojekt ausfuehren:

1. Freehold-Verifikation.
2. `python -m freehold go-codegen-project <entry> --output-dir <out>`.
3. optional JSON-Artefakt-Ausgabe.
4. generiertes `build.cmd` im Output-Projekt.
5. klare Fehlerausgabe bei unsupported Go-Codegen-Features.

## Erste Testmodule

Start mit 3 bis 5 kleinen Freehold-Projekten:

1. Minimal-App
   - ein `App.Main` ohne Imports
   - primitive Werte
   - `check`

2. Records + Functions
   - Record-Typen
   - Record-Literale
   - Feldzugriffe
   - einfache Funktionen

3. Cross-Module Calls
   - `App.Main` importiert ein Domain-Modul
   - exposed Call, z.B. `is_valid()`
   - qualifizierter Call, z.B. `Domain.Rules.is_valid()`

4. Result/Abort
   - `Result<T,E>` ok/error Returns
   - deklarierter Abort
   - propagierender abortender Call, soweit V1-Codegen abgedeckt ist

5. Runtime-Builtins
   - `String.*`
   - `String.template`
   - `Math.*`
   - `Json.stringify`
   - `Std.IO.log` / `Std.IO.logf`

## Unsupported-Feature-Smoke-Tests

Zusaetzlich zu gruenen Beispielen sollten ein paar bewusst nicht unterstuetzte Beispiele sauber diagnostiziert werden:

- `Big.*`, solange BigNumber-Codegen noch deferred ist.
- User-Generics im Go-Codegen.
- Async/Channels/Scope Runtime.
- gRPC Go-Bindings.

Ziel: Der Compiler soll nicht kryptisch scheitern, sondern klar sagen, dass das Feature fuer Go-Codegen V1 noch nicht unterstuetzt ist.

## Akzeptanzkriterien fuer morgen

- Es gibt einen Beispielordner mit echten Freehold-Modulen.
- Mindestens ein Multi-Modul-Beispiel kompiliert nach Go.
- Das generierte Go-Projekt baut mit `go test ./...`.
- Ein einziger Smoke-Test-Command prueft alle Beispiele.
- Unsupported-Beispiele liefern nachvollziehbare Diagnostics.
- Der neue Testpfad ist dokumentiert und reproduzierbar.

## Danach

Wenn dieser Testmodul-Spielplatz steht, koennen wir neue Compiler-Slices sehr viel greifbarer pruefen:

- BigNumber-/Runtime-Builtins
- Arrays
- Cross-Module Records/Results/Aborts
- Go-native Semantik-/CFlow-Slices Richtung Bootstrap