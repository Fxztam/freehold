# Open: VS Code Language Support

Stand: 2026-05-24

Status: Completion vor Formatter-Ausbau vorgezogen; pragmatische V1-Completion ins Freehold-Repo ueberfuehrt

Dieses Dokument legt die Prioritaet fuer den VS-Code-Sprachsupport fest. Fuer die naechste Tooling-Phase wird Completion vor weiterer Formatter-Vertiefung behandelt. Der Formatter bleibt wichtig, aber Completion bringt beim Arbeiten an Freehold-Programmen frueher Nutzen: Keywords, Typen, Builtins, gRPC-IDL, Result/Abort und Concurrency-Blöcke sollen beim Schreiben direkt verfuegbar sein.

## Prioritaet

```text
1. VS Code Completion V1
2. Syntax Highlighting auf aktuellen Sprachstand nachziehen
3. Formatter stabilisieren
4. Spaeter: semantische Completion ueber Parser/Verifier/Module Resolver
```

## Completion V1 Scope

Completion V1 ist bewusst pragmatisch und editorlokal:

- Keywords: `module`, `import`, `type`, `record`, `function`, `procedure`, `service`, `rpc`, `proto`, `scope`, `spawn`, `join`, `result`.
- Typen: `Integer`, `Boolean`, `Double`, `String`, `BigInteger`, `BigFloat`, `Array`, `Result`, `Executor`, `Scope`, `JoinHandle`, `Channel`, `Sender`, `Receiver`.
- Builtins: `String.*`, `Math.*`, `Json.stringify`, `Std.IO.*`, einfache concurrency runtime helpers.
- Snippets: module block, record type, function, procedure, service rpc, if, case, scope block, `return ok`, `return error`.

V1 ist keine semantische Completion. Sie liest noch keine Imports, keine Exposing-Listen, keine Record-Felder und keine Routinen aus dem aktuellen Projekt.

## Formatter Policy

Der bestehende VS-Code-Formatter bleibt erhalten, wird aber nicht vor Completion ausgebaut. Er bleibt zunaechst pragmatisches Textformatting und kein AST-basierter Formatter.

Formatter-Ausbau wird erst danach priorisiert:

- aktuelle Syntax vollstaendig formatieren
- gRPC/service/rpc/record proto stabil einruecken
- Scope-Blöcke stabil einruecken
- spaeter AST-basierter Formatter oder Parser-gestuetzter Formatter

## Aktueller Implementierungsort

Pragmatische Completion V1 ist jetzt im Freehold-Repo versionierbar:

```text
tools/vscode/freehold-vscode
```

Geaenderte Extension-Bereiche:

- `extension.js`: Completion-Metadaten und VS-Code Completion Provider.
- `package.json`: Completion-Einstellung und Kategorie.
- `tests/formatter.test.js`: Smoke-Test fuer Completion-Labels.
- `README.md`: Completion-vor-Formatter-Prioritaet dokumentiert.
- `syntaxes/freehold.tmLanguage.json`: Highlighting fuer aktuellen Freehold-Sprachstand.
- `examples/`: Formatter-Smoke-Beispiele.

Der zuvor lose Workspace-Ordner `veraflow_vscode_formatter_v11g/veraflow_vscode_formatter_v11g` bleibt nur noch Herkunft/Referenz. Der versionierte Freehold-Stand liegt unter `tools/vscode/freehold-vscode`.

## Tests

Aktueller Smoke-Test:

```text
node tests/formatter.test.js
```

Er prueft weiterhin Formatter-Basisverhalten und zusaetzlich zentrale Completion-Labels wie `service`, `rpc`, `proto`, `Array`, `Result`, `String.concat`, `Json.stringify`, `service rpc` und `scope block`.

## Naechste Schritte

1. Completion-Snippets fuer weitere haeufige Formen ergaenzen.
2. Danach semantische Completion planen: Module, Imports, Exposing, Record-Felder, Routine-Namen.
3. Erst danach Formatter V2/AST-Formatter starten.

=== CLOSED ===
