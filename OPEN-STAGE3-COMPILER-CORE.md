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
  Compiler/Core/ParseResult.fh
  Compiler/Core/Resolve.fh
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
  - `FH-REF-1001`-Helper fuer unbekannte exposed Symbole in importierten Modulen
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
  - `RecordTypeNode`
  - `ModuleWithRecordNode`
  - `FunctionNode`
  - `ModuleWithFunctionNode`
  - `ProcedureNode`
  - `ModuleWithProcedureNode`
  - `ImportNode`
  - `ModuleWithImportNode`
  - `ImportReferenceNode`
  - `FunctionImportReferenceNode`
  - `ModuleWithImportReferenceNode`
  - Helper fuer Identifier-, Literal- und Module-Key/Text-Ausgaben
- `Compiler.Core.Lexer`
  - `MiniModuleTokens`
  - `MiniRecordModuleTokens`
  - `MiniFunctionModuleTokens`
  - `MiniProcedureModuleTokens`
  - `MiniImportModuleTokens`
  - `MiniImportReferenceModuleTokens`
  - kontrollierter Fixture-Lexer fuer `module Demo` / `end Demo` und `module Demo` / `end Other`
  - kontrollierter Fixture-Lexer fuer `module Demo type X is record end record end Demo`
  - kontrollierter Fixture-Lexer fuer `module Demo function answer() returns Integer is return 42 end answer end Demo`
  - kontrollierter Fixture-Lexer fuer `module Demo procedure run() is end run end Demo`
  - kontrollierter Fixture-Lexer fuer `import Demo.Support exposing answer` vor `module Demo end Demo`
  - kontrollierter Fixture-Lexer fuer eine Function, die `answer` aus `import Demo.Support exposing answer` referenziert
  - kontrollierter Fixture-Lexer fuer negative Import-/Exposing-Referenzen mit unterschiedlichem exposed Symbol und Return-Symbol
  - Helper fuer Tokenanzahl und deterministische Lexer-Summary
- `Compiler.Core.Parser`
  - kontrollierter Fixture-Parser fuer `module <Identifier>` / `end <Identifier>`
  - kontrollierter Fixture-Parser fuer ein Modul mit einer leeren Record-Typdeklaration
  - kontrollierter Fixture-Parser fuer ein Modul mit einer einfachen Function-Deklaration
  - kontrollierter Fixture-Parser fuer ein Modul mit einer einfachen Procedure-Deklaration
  - kontrollierter Fixture-Parser fuer ein Modul mit einer Import-Praeambel
  - kontrollierter Fixture-Parser fuer eine Function-Return-Referenz auf ein exposed Import-Symbol
  - negativer Import-/Exposing-Result-Pfad fuer `exposing answer` mit `return missing` (`FH-PARSE-0002`)
  - baut aus `MiniModuleTokens` einen `ModuleNode`, aus `MiniRecordModuleTokens` einen `ModuleWithRecordNode`, aus `MiniFunctionModuleTokens` einen `ModuleWithFunctionNode`, aus `MiniProcedureModuleTokens` einen `ModuleWithProcedureNode`, aus `MiniImportModuleTokens` einen `ModuleWithImportNode` und aus `MiniImportReferenceModuleTokens` einen `ModuleWithImportReferenceNode`
  - Helper fuer parsed module name, deterministische Parser-Summary und OK-/Fehler-`ParseResult`-Rueckgabe
- `Compiler.Core.ParseResult`
  - `ParseStatus`
  - `ParseError`
  - `ParseResult`
  - Helper fuer OK-/Fehler-Ergebnisse und deterministische Result-Summary
- `Compiler.Core.Resolve`
  - `ResolveStatus`
  - `ResolveResult`
  - Mini-Resolver fuer kontrollierte Import-Reference-Tokens
  - stabile Resolver-Summary-Zeilen fuer `resolver.import_ref.result` und `resolver.import_ref.unknown`
  - OK-Ausgang fuer `import Demo.Support exposing answer` / `return answer`
  - Diagnostic-Ausgang mit `FH-REF-1001` fuer `return missing`
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

1. Den Mini-Resolver ueber Tokens hinaus auf das positive Import-Reference-AST-Modell ausweiten.
2. Danach Import-/Exposing-Diagnostik und Parser-Result-Pfad konsolidieren, sobald Resolver und Parser die Phasengrenze sauber teilen.
3. Stage1-Ausfuehrung erst beginnen, wenn die Mini-Fixtures stabil sind.