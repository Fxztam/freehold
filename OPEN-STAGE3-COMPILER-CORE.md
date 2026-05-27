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
  Compiler/Core/Fixtures.fh
  Compiler/Core/Token.fh
  Compiler/Core/Ast.fh
  Compiler/Core/Lexer.fh
  Compiler/Core/Parser.fh
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
- `Compiler.Core.Fixtures`
  - `CompilerFixtureResult`
  - deterministische Mini-Fixture-Auswertung fuer Package-Pfad, Exportname und Diagnostic-Text
- `Compiler.Core.Token`
  - `TokenKind`
  - `SourceSpan`
  - `Token`
  - Helper fuer Token-Erzeugung, Token-Key und Token-Text
- `Compiler.Core.Ast`
  - `AstNodeKind`
  - `IdentifierNode`
  - `LiteralNode`
  - `ModuleNode`
  - Helper fuer Identifier-, Literal- und Module-Key/Text-Ausgaben
- `Compiler.Core.Lexer`
  - `MiniModuleTokens`
  - kontrollierter Fixture-Lexer fuer `module Demo` / `end Demo`
  - Helper fuer Tokenanzahl und deterministische Lexer-Summary
- `Compiler.Core.Parser`
  - kontrollierter Fixture-Parser fuer `module <Identifier>` / `end <Identifier>`
  - baut aus `MiniModuleTokens` einen `ModuleNode`
  - Helper fuer parsed module name und deterministische Parser-Summary
- `App.Main`
  - Smoke-Einstieg, der die Helper zusammen benutzt und Golden-Ergebniszeilen ausgibt

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
- Ausfuehrung des erzeugten Executables gegen den Golden-Stdout in `artifacts/stage3/compiler_core_v1/expected/compiler_core_results.expected.txt`.

## Manifest

```text
artifacts/stage3/compiler_core_v1/manifest.json
```

Das Manifest beschreibt den ersten Contract `compiler_core_v1_go_project`.

## Naechste Schritte

1. Weitere Mini-Fixtures nur bei neuem Compiler-Core-Verhalten ergaenzen.
2. Kleine Diagnostic-/Result-Form fuer Parserfehler modellieren, bevor echte Fehlerfaelle in den Parser kommen.
3. Danach erst den Parser-Slice ueber das Mini-Modul hinaus erweitern.
4. Stage1-Ausfuehrung erst beginnen, wenn die Mini-Fixtures stabil sind.