# Stage 3 Compiler Core V1

Stand: 2026-05-27

Stage 3 beginnt bewusst klein. Der erste Slice ist kein Self-Hosting-Compiler, sondern ein Freehold-geschriebener Mini-Compilerkern, den Stage0 als Go-Projekt bauen kann.

## Ziel

- Erste echte Compilerlogik liegt als Freehold-Quellcode vor.
- Stage0 baut daraus ein reproduzierbares Go-Projekt.
- Der Slice bleibt klein genug, um nicht von Parser-Self-Hosting, voller Async-Runtime oder gRPC-Runtime blockiert zu werden.

## Quelle

```text
bootstrap/compiler_core_v1/
  App/Main.fh
  Compiler/Core/Names.fh
  Compiler/Core/Diagnostics.fh
  Std/IO.fh
```

## Aktueller Inhalt

- `Compiler.Core.Names`
  - `ModuleName`
  - `SymbolName`
  - `GoPackagePath`
  - Helper fuer Modulnamen, Symbolnamen, Go-Package-Pfade und exportierte Go-Namen
- `Compiler.Core.Diagnostics`
  - `Diagnostic`
  - Diagnostic-Key/Text-Helfer
- `App.Main`
  - Smoke-Einstieg, der die Helper zusammen benutzt

## Gate

```text
verify-stage3-compiler-core-v1.cmd
```

Das Gate prueft:

- Manifest-Policy und Contract-Anzahl.
- Stage0-Go-Codegen-Projektstruktur.
- Erwartete Go-Dateien fuer App, Names, Diagnostics und Std.IO.
- Erwartete Build-Dateien inklusive Executable-Entry.
- `go test ./...` und Go-Build ueber das generierte `build.cmd`.

## Manifest

```text
artifacts/stage3/compiler_core_v1/manifest.json
```

Das Manifest beschreibt den ersten Contract `compiler_core_v1_go_project`.

## Naechste Schritte

1. Mini-Fixtures fuer Namensbildung und Diagnostics als Golden-Vergleich ergaenzen.
2. Optional Runtime-Log-Smoke fuer `App.Main` ergaenzen.
3. Danach erst kleine IR-/Go-Codegen-Helfer in Freehold modellieren.
4. Stage1-Ausfuehrung erst beginnen, wenn die Mini-Fixtures stabil sind.