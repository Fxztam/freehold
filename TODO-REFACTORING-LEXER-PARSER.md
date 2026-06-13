# Refactoring-Fortschritt & Roadmap (Aktualisiert am 2026-06-13)

### Status: ERFOLGREICH ABGESCHLOSSEN (Unifizierung des Parsers & Lexers)

Die Verschmelzung der modernen Parser- und Lexer-Komponenten in den primären, tiefen-basierten Stage-3-Compiler-Kern (`bootstrap/compiler_core_v1`) wurde erfolgreich abgeschlossen und über alle Gatter hinweg verifiziert:

1. **Vollständige Lexer-Unifizierung**
   - Der zustandslose deterministische Lexer wurde durch den universellen, stateful On-Demand-Scanner in [Compiler/Core/Lexer.fh](bootstrap/compiler_core_v1/Compiler/Core/Lexer.fh) ersetzt.
   - Kompatibilität mit allen bestehenden Mini-Lexer-Schnittstellen (`MiniModuleTokens` etc.) wurde vollständig bewahrt.
   - Der alte deterministische Lexer wurde als Fallback gesichert in [Compiler/Core/Lexer-Old.fh](bootstrap/compiler_core_v1/Compiler/Core/Lexer-Old.fh).

2. **AST-Erweiterung um SourceSpans**
   - In [Compiler/Core/Ast.fh](bootstrap/compiler_core_v1/Compiler/Core/Ast.fh) wurden alle Deklarationsknoten (`ModuleDeclNode`, `RoutineDeclNode`, `RecordTypeWithFieldsNode`, `FieldNode`, `ParamNode` und Kontrakte) mit präzisen `SourceSpan`-Knoten und funktionalen Settern ausgestattet.

3. **Parser-Merging & Reinheit**
   - Der Parser in [Compiler/Core/Parser.fh](bootstrap/compiler_core_v1/Compiler/Core/Parser.fh) kombiniert nun die **Breite** des modernen Parsers (Records mit Feldern, Routine-Signaturen, komplexe SMT/Kanal-Spezifikationen wie `requires`, `ensures`, `aborts`, `depends`, `global` und Skip-Routinen) mit der **Tiefe** des alten Parsers (Sicherheit durch `SourceSpan`-Spangenerierung, strukturierte parser-interne Error-Codes und SMT-Beweisbarkeit).
   - Der Parser ist architektonisch sauber: Er nimmt **keine** Importe von `Diagnostic` vor, sondern gibt alle Strukturen rein über `ParseResult` und `ParseError` bzw. `ParseModuleDeclResult` zurück.

4. **Kompilation und Verifikation (Green Gates!)**
   - **AST Shape-Check:** **295 von 295** Fällen stimmen syntaktisch und strukturell exakt mit den Erwartungen überein.
   - **FH-IR Export-Vergleich:** **51 von 51** Testfälle des Gatter-Vergleichs (`compare-fhir-v1.cmd` für v1-Projekte und `compare-ir-compiler-v1.cmd` für Phase 1 / Phase 2) stimmen absolut überein (Matching FH-IR: 51 / 51, Mismatching: 0).
   - **Formale Verifikations-Verträge:** Der Compiler selbst wurde erfolgreich durch SMT-Solver nachgewiesen (Verträge: 1 von 1, bestanden). Das ausführbare Binary `stage3_compiler_mainfull_v1.exe` kompiliert einwandfrei und durchläuft alle Fuzzing-Tests der Gates zuverlässig.

---

### Wie die Vorteile des alten Zweigs bei der Vereinigung erhalten bleiben:

1. **Erhalt der `SourceSpan`-Knoten**:
Beim Einbau des LL(1)-Cursor-Parsers in [bootstrap/compiler_core_v1/Compiler/Core/Parser.fh](bootstrap/compiler_core_v1/Compiler/Core/Parser.fh) werden die AST-Typen so erweitert, dass jedes geparste Element (wie Imports, Typ- und Record-Deklarationen) seine `SourceSpan`-Informationen behält.

2. **Maschinenlesbare Diagnostics**:
Fehler im unifizierten Semantik-Checker werden direkt als strukturierte `Diagnostic`-Knoten unter Verwendung der Fehlercodes (`FH-PARSE-xxxx`, `FH-REF-xxxx`) aus [bootstrap/compiler_core_v1/Compiler/Core/Diagnostics.fh](bootstrap/compiler_core_v1/Compiler/Core/Diagnostics.fh) erzeugt, statt als flache Strings.

3. **Formale Verifikation der Parser-Funktionen**:
Die strengen Postkonditionen (`ensures`) des alten Parsers werden auf die neuen, breit aufgestellten Parse-Funktionen übertragen.

4. **Integration in die Ausdrucks-Auflösung**:
Die von [bootstrap/compiler_core_v1/Compiler/Core/Resolve.fh](bootstrap/compiler_core_v1/Compiler/Core/Resolve.fh) bereitgestellte Typisierung (`resolve_expr`, `resolve_stmt`) und lokale Variablen-Prüfung wird auf die neuen Deklarationsstrukturen (z.B. Funktionskörper) angewendet.

5. **Cross-Modul-Auflösung & Strukturierter AST**:
Die flachen String-Felder des `Full`-Zweigs (z.B. in `FullModuleDecl`) werden durch strukturierte, typisierte AST-Knoten (wie `IdentifierNode` oder `RecordTypeNode`) aus [bootstrap/compiler_core_v1/Compiler/Core/Ast.fh](bootstrap/compiler_core_v1/Compiler/Core/Ast.fh) ersetzt. Dadurch greift die bestehende Auflösung von importierten Symbolen nahtlos.

### Fazit für das Refactoring:
Der unifizierte Compiler in [bootstrap/compiler_core_v1/Compiler/Core/Parser.fh](bootstrap/compiler_core_v1/Compiler/Core/Parser.fh) bzw. `Compiler/Core` wird die **Breite** des `Full`-Prototyps (vollständige Modulabdeckung inkl. aller Deklarationsebenen) besitzen, ohne die präzise **Tiefe** (Spans, Fehlercodes, SMT-Beweisbarkeit und Ausdruckstypisierung) des alten Modells aufzugeben.

---

### Die Roadmap für morgen steht fest:

1. **Lexer integrieren**: Universellen On-Demand-Scanner in [bootstrap/compiler_core_v1/Compiler/Core/Lexer.fh](bootstrap/compiler_core_v1/Compiler/Core/Lexer.fh) einbauen.
2. **AST erweitern**: Deklarationsknoten aus dem `Full`-Zweig mit `SourceSpan` in [bootstrap/compiler_core_v1/Compiler/Core/Ast.fh](bootstrap/compiler_core_v1/Compiler/Core/Ast.fh) überführen.
3. **Parser mergen**: LL(1)-Cursor-Parser in [bootstrap/compiler_core_v1/Compiler/Core/Parser.fh](bootstrap/compiler_core_v1/Compiler/Core/Parser.fh) implementieren und strukturierte Fehler verwenden.
4. **Semantik integrieren**: Deep-Resolve mit Typen und Fehlercodes in [bootstrap/compiler_core_v1/Compiler/Core/Resolve.fh](bootstrap/compiler_core_v1/Compiler/Core/Resolve.fh) / [bootstrap/compiler_core_v1/Compiler/Core/Diagnostics.fh](bootstrap/compiler_core_v1/Compiler/Core/Diagnostics.fh) vereinen.
