# Freehold Strategie

Stand: 2026-05-23

Dieses Dokument haelt die besprochene strategische Reihenfolge fuer Freehold, den Go-Compiler, den Interpreter, das Bootstrap-Verfahren und den finalen Image Builder fest.

## Grundsatz

Freehold braucht zuerst eine stabile Referenzsemantik. Erst wenn diese Referenz stabil ist, wird der Go-Compiler als robuste Produktions- und Bootstrap-Bruecke voll ausgebaut. Das eigentliche Endziel ist danach ein in Freehold geschriebener Compiler-/Interpreter-/Image-Builder-Stack.

## Frage: Wann bauen wir den Go-Compiler fertig und den Interpreter?

Antwort: Der Interpreter kommt zuerst auf der Freehold-Seite. Der Go-Compiler kommt danach als stabiler Backend- und Toolchain-Ausbau.

Die Freehold-Seite ist die Referenz fuer die Sprache:

- Parser
- AST
- Verifier
- Diagnostics
- Control-Flow Analyzer
- Interpreter

Alles, was Sprachsemantik betrifft, wird zuerst dort eindeutig geklaert. Die Frage "Was bedeutet Freehold?" wird also im Freehold-Core beantwortet.

Der Interpreter gehoert primaer in den Freehold-Core als Referenz-Interpreter. Er laeuft auf dem verifizierten AST und ist die Grundlage fuer:

- Tests
- Beispiele
- Semantik-Klaerung
- CLI-Ausfuehrung
- spaetere Compiler-Golden-Tests

Der Go-Compiler wird sinnvoll fertiggebaut, sobald die mittlere Sprachebene stabil genug ist. AST-Paritaet und Diagnostic-Paritaet sind bereits stark, aber fuer Codegen brauchen wir stabile AST-Vertraege, eine klare Lowering-Schicht oder eine explizite IR.

Empfohlene Reihenfolge:

```text
Jetzt:
  Freehold-Semantik und Interpreter stabilisieren

Dann:
  Control-Flow, Proof, Result und Abort als Referenzsemantik abschliessen

Danach:
  Go-Compiler V0
    .fh -> Go AST/IR -> Go Code
    zuerst einfache Module, Records, Procedures, Functions

Spaeter:
  Go-Compiler V1
    Std.IO, Result, Json, Abort-Abbildung, Runtime-Lib

Noch spaeter:
  Native/Standalone Toolchain
```

Kurzfassung: Der Interpreter ist Freehold-Core. Der Go-Compiler ist der naechste grosse Toolchain-Schritt, aber erst nach einer stabilen Referenzsemantik.

## Frage: Bootstrapping erst nach Go-Compiler und Interpreter?

Antwort: Ja. Bootstrapping in Freehold beginnt erst nach vollstaendigem Interpreter und vollstaendigem Go-Compiler.

Der Grund ist wichtig: Beim Bootstrapping brauchen wir festen Boden. Wenn Interpreter und Go-Compiler noch wackeln, wissen wir bei Abweichungen nicht, ob der Fehler im neuen Freehold-Code, im Interpreter, im Compiler, in der Runtime oder in der Semantik steckt.

Mit vollstaendigem Interpreter und Go-Compiler haben wir drei Vergleichsebenen:

```text
Python/Freehold-Core Interpreter     = Referenzsemantik
Go-Compiler + Runtime                = Produktions-Backend
Freehold-geschriebener Compiler/Int. = Bootstrap-Ziel
```

Dann kann pro Testfall verglichen werden:

```text
Programm.fh + Input
  Python Interpreter output
  Go-compiled output
  Bootstrap-Freehold output
```

Nur wenn alle drei gleich sind, gilt der Bootstrap-Schritt als gruen.

Vor dem eigentlichen Bootstrapping sind nur Vorarbeiten sinnvoll:

- Spezifikation
- IR-Design
- Runtime-Kontrakte
- Vergleichsharness
- Golden-Tests

## Frage: Gibt es den finalen Image Builder / Native-Code-Builder nur in Freehold?

Antwort: Ja. Der finale Image Builder und Native-Code-Builder sollen am Ende in Freehold selbst existieren.

Die Staffelung sieht so aus:

```text
Phase 1:
  Python Freehold-Core
  = Referenz fuer Semantik, Verifier, Interpreter

Phase 2:
  Go-Compiler + Runtime
  = robuste Produktions-Toolchain und schnelle Zwischenstufe

Phase 3:
  Bootstrap-Freehold
  = Compiler, Interpreter und Tooling in Freehold selbst

Phase 4:
  Finaler Image Builder / Native Code
  = in Freehold geschrieben
```

Der Go-Compiler ist damit nicht das Endziel, sondern die Bruecke:

```text
Freehold Source
  -> Python-Referenz validiert Semantik
  -> Go-Compiler erzeugt lauffaehige Artefakte
  -> Freehold-Compiler wird damit bootstrapped
  -> Freehold-eigener Image Builder erzeugt finale Images / Native Code
```

Die Go-Seite darf spaeter weiter als Backend, CI-Vergleich und Bootstrap-Stufe existieren. Der eigentliche finale Builder gehoert aber zur Freehold-Seite.

## Strategischer Zielzustand

Der Zielzustand ist ein selbsttragendes Freehold-System:

```text
Freehold-Sprache
  -> Freehold-Core Referenz
  -> Freehold-Interpreter
  -> Go-Compiler als stabile Bruecke
  -> Freehold-Compiler und Freehold-Toolchain
  -> Freehold Image Builder / Native Code
```

Damit entsteht eine klare Evolutionslinie:

1. Semantik stabilisieren.
2. Referenz-Interpreter fertigstellen.
3. Go-Compiler und Runtime fertigstellen.
4. Interpreter-gegen-Compiler-Vergleichsharness aufbauen.
5. Freehold-Bootstrap starten.
6. Finalen Image Builder in Freehold bauen.

## Naechster sinnvoller Arbeitsblock

Der naechste grosse Block ist der Interpreter V1:

- verifizierte Programme ausfuehren
- `main` finden und starten
- Variablen und Assignments auswerten
- `if`, `case`, `while`, `return` ausfuehren
- Prozedur- und Funktionsaufrufe ausfuehren
- Records, Arrays, Result, String, Json und Abort schrittweise integrieren

Danach kann jede spaetere Go-Compiler-Ausgabe gegen den Referenz-Interpreter verglichen werden.