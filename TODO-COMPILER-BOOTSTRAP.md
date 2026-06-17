# TODO-COMPILER-BOOTSTRAP

Dieses Dokument trackt die ausstehenden Aufgaben und Erweiterungen, um den in Freehold geschriebenen, selbsthostenden Compiler-Kern (`bootstrap/compiler_core_v1`) von der vereinfachten, Token-basierten Übersetzung bei `--build-exe` auf die voll einkompilierte, AST- und Resolver-basierte native Code-Generierung umzustellen.

## Aktueller Status (Ist-Zustand)
- **Einkompilierter Kern:** Alle fortgeschrittenen Compiler-Module wie `Lexer.fh`, `Parser.fh`, `Resolve.fh`, `Transform.fh`, `Verifier.fh` und `Vm.fh` sind bereits vollständig in der `bin/stage3_compiler_core_v1.exe` einkompiliert und durchlaufen dort erfolgreich ihre internen Selbsttests/Fixtures.
- **Externer `--build-exe` Treiber:** Die Kommandozeilenargument-Aktion `--build-exe` greift für die Ingestion und Generierung von externen `.fh`-Quelldateien derzeit noch auf den vereinfachten Hilfspfad `compile_native_entry_go` zurück. Dieser parst Quellcodedateien primär über flaches Token-Streaming statt über die echten syntaktischen AST- und Resolving-Phasen.

---

## Geplante Erweiterungen & Roadmaps (Szenario C)

### 1. Umstellung auf AST-basierte Code-Generierung (statt Token-Streaming)
- [ ] Den echten, hierarchischen AST, der durch `parse_expr` und `parse_stmt` in `Compiler.Core.Parser.fh` erzeugt wird, im Treiber aktivieren.
- [ ] Den Go-Code-Generator (`Compiler.Core.Codegen.fh`) so anpassen, dass er aus dem echten AST-Baum korrekten Go-Code generiert.
- [ ] **Vorteil:** Unterstützung korrekter Operator-Präzedenzen und beliebig geschachtelter mathematischer sowie logischer Ausdrücke bei der Übersetzung beliebig anspruchsvoller Programme.

### 2. Native Multi-Modul-Kompilierung (Abhängigkeitsauflösung)
- [ ] Den Import-Parser so aufbohren, dass er alle deklarierten Abhängigkeiten (`import` Zeilen) einer Datei rekursiv analysiert.
- [ ] Das native `File`-Modul nutzen, um die importierten `.fh`-Dateien dynamisch vom Dateisystem nachzuladen und dem Compiler als Parser-Eingabe zuzuführen.
- [ ] Generierung einer strukturierten Go-Projekt-Ordner-Hierarchie für alle beteiligten Modul-Abhängigkeiten.
- [ ] **Vorteil:** Der selbstgenerierte native Compiler beherrscht komplexe, modulübergreifende Projekte völlig unabhängig und ohne Python-Hilfsskripte.

### 3. Ausbau der Kontrollfluss- und Typ-Unterstützung
- [ ] Unterstützung für Schleifen-Konstrukte (`while`-Blöcke mit Invarianten-Härtung) im nativen Codegen.
- [ ] Unterstützung für Record-Mutationen und hierarchische Strukturzuweisungen (z. B. `point.x := 10`).
- [ ] Unterstützung für statische Arrays (`Array<T, N>`).

### 4. Native Fehlerrückgaben & Systemexit
- [ ] Integration eines echten `System.exit(code)` oder entsprechenden Rückgabeparameters in Freehold, um bei Übersetzungsfehlern (Syntax, Typkonflikte) der nativen EXE einen non-zero Prozessstatus zurückzugeben.
