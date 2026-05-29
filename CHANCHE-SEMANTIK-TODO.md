# Chanche Semantik Todo

> [!IMPORTANT]
> **Grammatik & Parser Source of Truth:**
> - `freehold/grammar/freehold.lark` ist die exakt auszuführende Parser-Grammatik (Lark) und die primäre Source of Truth für den Parser.
> - `freehold/core/grammar_inline.py` (enthält `FREEHOLD_GRAMMAR`) enthält die exakt gespiegelte Inline-Variante der Lark-Grammatik und muss bei jeder Grammatikänderung absolut synchron gehalten werden.
> - Die verschiedenen EBNF-Dateien in `freehold/grammar/freehold*.ebnf` dienen primär der Spezifikation, Dokumentation oder Visualisierung (z. B. Syntax-Highlighting, Railroad-Diagramme) und dürfen **nicht** mit der aktiven Lark-Grammatik verwechselt werden.

Dieses Dokument beschreibt den Prozess, mit dem der String-Templates-Change umgesetzt wurde. Es dient als schneller Einstieg fuer spaetere semantische Sprach-Changes, besonders wenn Grammatik, Parser, Diagnostics, Tests und Conformance gemeinsam bewegt werden muessen.

## Zielbild

Ein Change soll nicht nur syntaktisch funktionieren, sondern durch alle Schichten stabil sein:

```text
EBNF/Lark -> Parser/AST -> Verifier/Runtime -> Diagnostics -> Spec/Rules -> Tests -> Go/DHParser Conformance
```

Der String-Template-Change hat als Muster gedient:

```fh
String.template("id=${id}", id: id)
```

V1-Regeln:

```text
Positional templates mit ${} bleiben gueltig.
Named templates nutzen ${name} und name: expr.
Alle named placeholders muessen gebunden sein.
Alle named bindings muessen benutzt werden.
Duplicate bindings werden abgelehnt.
Positional und named modes werden nicht gemischt.
Template values bleiben scalar display values: String, Integer, Boolean, Double.
```

## Prozess

### 1. Iststand klaeren

Vor dem Editieren immer erst die vorhandenen Schichten suchen:

```text
freehold/grammar/freehold.lark
freehold/grammar/freehold.dhparser.ebnf
freehold/core/grammar_inline.py
freehold/core/parser_legacy.py
freehold/core/ast.py
freehold/core/verifier.py
freehold/core/interpreter.py
freehold/core/string_templates.py
freehold/core/diagnostics.py
go-frontend/internal/parser/parser.go
go-frontend/internal/ast/ast.go
tests/language_modules/<module>
spec/freehold.diag
spec/freehold.rules
tools/compare_semantic_diagnostics.py
```

Beim String-Template-Change war der Befund:

```text
named_arg existierte bereits fuer Record-Literals.
Funktionsaufrufe akzeptierten nur positionale arg_list.
String.template konnte nur ${} positional placeholders.
Named templates waren als TODO diagnostic modelliert.
```

### 2. Grammatik zuerst aendern

Wenn ein Sprach-Feature neue Syntax braucht, zuerst die Grammatik in beiden Parser-Welten anpassen:

```text
Lark:      freehold/grammar/freehold.lark
Inline:    freehold/core/grammar_inline.py
DHParser:  freehold/grammar/freehold.dhparser.ebnf
Go:        go-frontend/internal/parser/parser.go
```

Muster fuer named call arguments:

```text
arg_list: call_arg ("," call_arg)*
call_arg: NAME ":" expr -> named_call_arg | expr -> positional_call_arg
```

DHParser-Variante:

```text
arg_list = call_arg { "," call_arg }
call_arg = named_arg | expr
```

Wichtig: Grammatik allein reicht nicht. Go-AST, Python-AST-Builder und AST-Normalizer muessen dieselbe semantische Form sehen.

### 3. AST und Parser rueckwaertskompatibel erweitern

Bestehende positionale Calls duerfen nicht brechen.

Python-seitig wurde `NamedArg` fuer Call-Argumente wiederverwendet. Go-seitig wurde ein eigener Knoten ergaenzt:

```go
type NamedArgumentExpr struct {
    Kind  string `json:"kind"`
    Name  string `json:"name"`
    Value Expr   `json:"value"`
}
```

Regel:

```text
Normale Routinen und Built-ins bleiben positional-only, solange sie named args nicht explizit unterstuetzen.
String.template und Std.IO.logf duerfen named template bindings nutzen.
```

### 4. Semantik im Verifier modellieren

Semantik gehoert in den Verifier, nicht in die Grammatik.

Pruefpunkte fuer named templates:

```text
erstes Argument muss positional String sein
binding values muessen scalar display values sein
keine positional values nach named bindings
keine Mischung aus positional und named mode
validate_template(template, positional_count, binding_names)
```

Fehler sollen als klare TypeCheckError-Texte formuliert werden, damit `diagnostics.py` sie stabil klassifizieren kann.

### 5. Runtime passend machen

Wenn ein Feature auch interpretierbar ist, Runtime nachziehen:

```text
String.template(template, values..., name: value)
Std.IO.logf(template, values..., name: value)
```

Rendering-Regel:

```text
${} wird positional ersetzt.
${name} wird aus binding dict ersetzt.
bool wird als true/false gerendert.
```

### 6. Diagnostics stabilisieren

Keine neuen losen Fehlermeldungen ohne Diagnostic-Verankerung.

Bei Template-Changes wurden legacy Codes auf stabile Freehold-Codes gemappt:

```text
VF-TPL001 -> FH-TPL-4001 template_placeholder_count_mismatch
VF-TPL002 -> FH-TPL-4002 template_old_placeholder_rejected
VF-TPL003 -> FH-TPL-4003 template_invalid_named_placeholder
VF-TPL004 -> FH-TPL-4004 template_invalid_brace
VF-TPL005 -> FH-TPL-4005 template_value_type_mismatch
VF-TPL006 -> FH-TPL-4006 template_duplicate_binding
VF-TPL007 -> FH-TPL-4007 template_missing_binding
VF-TPL008 -> FH-TPL-4008 template_unused_binding
VF-TPL009 -> FH-TPL-4009 template_mixed_modes
```

Dabei immer alle drei Stellen synchron halten:

```text
freehold/core/diagnostics.py
tools/compare_semantic_diagnostics.py
spec/freehold.diag
spec/freehold.rules
```

### 7. Tests erweitern

Neue Syntax braucht positive und negative Tests.

String-Template-Muster:

```text
valid/string_template_named_values.fh
invalid_semantics/string_template_missing_binding.fh
invalid_semantics/string_template_unused_binding.fh
invalid_semantics/string_template_duplicate_binding.fh
```

Zusaetzlich pflegen:

```text
tests/language_modules/18_string_templates/manifest.json
tests/language_modules/expected_semantic_diagnostics.json
tests/language_modules/positive_feature_matrix.json
tests/language_modules/18_string_templates/expected_errors/*.err
freehold_features.json
```

Alte TODO-Tests entfernen oder in echte v1-Regeln umwandeln. Keine stale artifacts fuer geloeschte Testfaelle liegen lassen.

### 8. Go/DHParser AST-Normalizer aktualisieren

Wenn neue AST-Knoten entstehen, muessen Vergleichstools sie kennen:

```text
tools/compare_ast_shape.py
tools/compare_ast_semantic.py
```

Beim String-Template-Change war der erste Full-Gate-Fehler korrekt und hilfreich:

```text
Go zeigte NamedArgumentExpr.
DHParser normalisierte zu id:id.
AST shape mismatch.
```

Fix:

```text
NamedArgumentExpr in Go-Text normalisieren.
DHParser call_arg/named_arg in NamedArgumentExpr normalisieren.
```

### 9. Gates in sinnvoller Reihenfolge laufen lassen

Schnell zuerst:

```powershell
.\compare-semantic-diagnostics.cmd
.\verify-spec-diagnostics.cmd
```

Dann AST-Vergleiche, falls Parser-Artefakte schon aktuell sind:

```powershell
.\compare-ast-shape.cmd
.\compare-ast-semantic.cmd
```

Zum Schluss die volle Kette:

```powershell
.\verify-parser-conformance.cmd
```

Akzeptierter Endzustand aus dem Template-Change:

```text
Compare semantic diagnostics: 57/57, 0 mismatches
Verify spec diagnostics:      84 specs, 84 emits, 0 failures
Parser conformance:           passed
Total:                        262
OK:                           219
FAIL:                         43
AST shape:                    219/219
Semantic AST:                 219/219
Go tests:                     passed
```

### 10. Dokumentation und Baselines aktualisieren

Nach gruenen Gates die Dokumentation nachziehen:

```text
OPEN-<FEATURE>.md
README_FREEHOLD_CLI.md
go-frontend/PARSER_STATUS.md
```

Baselines muessen aus dem letzten erfolgreichen Full-Gate stammen, nicht aus einem Zwischenlauf. Beim Template-Change war wichtig, ein altes `string_template_named_todo` Artifact zu entfernen, damit die Zahlen wieder sauber waren.

## Checkliste fuer den naechsten Semantik-Change

```text
[ ] Iststand in Grammar/Core/Go/Tests/Spec suchen
[ ] Syntaxentscheidung in Lark, inline grammar und DHParser spiegeln
[ ] Go-Parser und Go-AST nachziehen
[ ] Python AST-Builder nachziehen
[ ] Verifier-Regeln implementieren
[ ] Runtime implementieren, falls ausfuehrbar
[ ] diagnostics.py klassifiziert alle neuen Fehler
[ ] CODE_MAP ergaenzt
[ ] spec/freehold.diag ergaenzt
[ ] spec/freehold.rules ergaenzt
[ ] Positive Tests angelegt
[ ] Negative Tests angelegt
[ ] expected_semantic_diagnostics.json aktualisiert
[ ] manifest.json und expected_errors aktualisiert
[ ] positive_feature_matrix.json aktualisiert
[ ] AST-Normalizer aktualisiert
[ ] compare-semantic-diagnostics.cmd gruen
[ ] verify-spec-diagnostics.cmd gruen
[ ] verify-parser-conformance.cmd gruen
[ ] stale artifacts geloeschter Tests entfernt
[ ] README/PARSER_STATUS/Open-Doc Baselines aktualisiert
```

## Typische Stolperstellen

```text
PowerShell unterstuetzt keine Bash here-docs wie python - <<'PY'.
Dollarzeichen in Inline-Kommandos koennen von PowerShell angefasst werden.
Generated artifacts koennen alte geloeschte Testfaelle weiter sichtbar halten.
Go/DHParser koennen parse-ok sein und trotzdem im AST-Normalizer auseinanderlaufen.
Spec-Checker muss mit erwarteten Diagnostics und CODE_MAP synchron bleiben.
```

## Naechste gute Kandidaten

Nach dem String-Template-Change sind diese Features besser vorbereitet:

```text
Record Initializers, weil named arguments jetzt fuer Calls/Bindings etabliert sind.
JSON templates, weil named bindings und placeholder completeness stabil diagnostiziert sind.
Requires/Ensures comma notation, weil der Spec-Checker-Prozess fuer neue Regeln steht.
```

## Geparkte V2/V3-Themen (Nicht Teil des V1-Scopes)

Die folgenden komplexen Sprach- und Runtime-Features sind bewusst geparkt und blockieren das V1-Self-Hosting nicht:
- **gRPC-Client-Bindings, Streaming, Deadlines und Metadaten-Annotationen.**
- **Async-Runtime-Executor (Scheduling, Cancellation Tokens).**
- **REST/WebSocket-Verbindungsbibliotheken.**
- **Generics-Inferenz und Monomorphisierung des generierten Go-Codes.**
- **Pfadsensitive Kontrollfluss-Analyse (Path-aware analysis) und Abort-Implikationsprüfung.**