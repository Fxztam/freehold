# FH-Native-V1 Statistiken und Statement-Zählung

*Erstellt am: 31.05.2026, 17:47:02 (Lokalzeit)*
*Workspace: freehold*

Diese Auswertung zählt und kategorisiert die Quellcode-Zeilen des nativen, selbst-hostenden Freehold-Compilers (`FH-Native-V1`), der sich unter dem Pfad `bootstrap/compiler_core_v1/` befindet.

## Metriken-Definition

Die Zeilen des Compilers wurden in vier Gruppen eingeteilt:
* **Leerzeilen (Blank Lines)**: Zeilen, die leer sind oder nur aus Whitespace bestehen.
* **Kommentarzeilen (Comment Lines)**: Reine Kommentarzeilen (beginnend mit `--` oder Blockkommentare `/* ... */`).
* **Deklarationen (Declaration Lines)**: Zeilen, die strukturelle Definitionen enthalten (`module`, `import`, `type ... is record`, `end record`, `function ...`, `procedure ...`, `requires ...`, `ensures ...`, `aborts ...`, `is` sowie das schließende `end name` von Routinen und Modulen).
* **Effektive Statements (Statement Lines)**: Die tatsächlich ausgeführten Anweisungen (wie `let`, Zuweisungen `:=`, `return`, `check`, `if`, `while`, `case`, `scope/spawn/join/result` und eigenständige Prozeduraufrufe). Inline-Kommentare am Ende von Code-Statements wurden für die Zählung herausgefiltert.

*Hinweis: Testdateien unter `bootstrap/compiler_core_v1/fixtures/` wurden nicht mitgezählt.*

---

## Code-Verteilung nach Dateien

| Datei (unter `bootstrap/compiler_core_v1/`) | Gesamtzeilen | Leerzeilen | Kommentare | Deklarationen | Effektive Statements |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`App/Main.fh`** | 774 | 65 | 2 | 49 | **658** |
| **`Compiler/Core/Ast.fh`** | 712 | 102 | 0 | 368 | **242** |
| **`Compiler/Core/Codegen.fh`** | 158 | 10 | 0 | 24 | **124** |
| **`Compiler/Core/Diagnostics.fh`** | 43 | 7 | 0 | 25 | **11** |
| **`Compiler/Core/Fixtures.fh`** | 29 | 4 | 0 | 11 | **14** |
| **`Compiler/Core/Flow.fh`** | 62 | 7 | 0 | 10 | **45** |
| **`Compiler/Core/Lexer.fh`** | 1020 | 86 | 0 | 224 | **710** |
| **`Compiler/Core/Names.fh`** | 43 | 8 | 0 | 28 | **7** |
| **`Compiler/Core/ParseResult.fh`** | 72 | 11 | 0 | 40 | **21** |
| **`Compiler/Core/Parser.fh`** | 1334 | 134 | 0 | 284 | **916** |
| **`Compiler/Core/Resolve.fh`** | 434 | 32 | 1 | 118 | **283** |
| **`Compiler/Core/Token.fh`** | 62 | 9 | 0 | 33 | **20** |
| **`Compiler/Core/Transform.fh`** | 486 | 47 | 0 | 93 | **346** |
| **`Compiler/Core/Verifier.fh`** | 267 | 21 | 0 | 36 | **210** |
| **`File.fh`** | 13 | 3 | 0 | 8 | **2** |
| **`Std/IO.fh`** | 23 | 6 | 0 | 17 | **0** |
| **`System.fh`** | 20 | 5 | 0 | 11 | **4** |
| **GESAMT** | **5552** | **557** | **3** | **1379** | **3613** |

---

## Aufschlüsselung nach Statement-Typen

Die insgesamt **3.613 effektiven Code-Statements** teilen sich wie folgt auf:

* **`let` (Deklaration mit Zuweisung)**: **857** (23,7 %)
  * *Beispiel: `let x: Integer = 5`*
* **`assign` (Zuweisung an bestehende Variablen/Felder)**: **415** (11,5 %)
  * *Beispiel: `x := 10`*
* **`return` (Rückgaben wie `return`, `return ok`, `return error`)**: **453** (12,5 %)
  * *Beispiel: `return ok res`*
* **`if_else` (Verzweigungen & Blöcke)**: **663** (18,4 %)
  * *Inklusive `if`, `else` und `end if`*
* **`while` (Schleifen & Schleifenverträge)**: **139** (3,8 %)
  * *Inklusive `while`, `end while`, `invariant` und `variant`*
* **`case` (Musterabgleiche / Case-Statements)**: **4** (0,1 %)
  * *Inklusive `case`, `when`, `default` und `end case`*
* **`scope_concurrency` (Strukturierte Nebenläufigkeit)**: **12** (0,3 %)
  * *Inklusive `scope`, `spawn`, `join`, `result` und `end scope`*
* **`check` (Zusicherungen / Assertions)**: **1** (0,0 %)
  * *Beispiel: `check val > 0`*
* **`call_or_other` (Prozeduraufrufe & Sonstiges)**: **1069** (29,6 %)
  * *Einfache Funktions-/Prozeduraufrufe als eigenständiges Statement (z. B. `call Std.IO.log(...)`)*
