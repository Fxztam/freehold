# Freehold VS Code Language Support

Local VS Code extension for Freehold `.fh` and `.freehold` files.

Current priority: completion support is available before deeper formatter work. Formatting remains pragmatic text formatting.

## V1 support

- Completion provider for keywords, core types, built-ins, gRPC IDL, Result/Abort, and structured concurrency snippets.
- Syntax highlighting for modules, imports, records, routines, contracts, gRPC IDL, concurrency, comments, strings, numbers, operators and built-ins.
- Pragmatic document formatter for common Freehold shapes.
- `:=` mutation formatting.
- `import ... exposing ...`.
- Qualified `end` markers: `end main`, `end Module.Name`, `end record`, `end if`, `end while`, `end case`.
- `case / when / default / end case` indentation.
- Line comments `--`, block comments `/* */`, AI/doc comments `/** */`.
- Native `String` highlighting and `String.concat/substr/replace/instr`.
- `Array<T>`, `Result<T,E>`, concurrency runtime types, and gRPC keywords.

## Install / test locally

Open this folder in VS Code and press `F5` to launch an Extension Development Host.

Smoke test:

```bash
node tests/formatter.test.js
```

The test writes:

```text
examples/retail_analytics_one_page_formatted.fh
```

## Package later

```bash
npm install -g @vscode/vsce
vsce package
code --install-extension freehold-language-support-0.1.0.vsix
```

This formatter is still pragmatic text formatting, not yet a grammar/AST-based formatter.

Completion is likewise pragmatic: it offers language-level keywords, snippets, and built-ins without semantic module resolution yet.
