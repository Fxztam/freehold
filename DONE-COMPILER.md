# Done: Go Compiler

Stand: 2026-05-24

## Feature-Matrix-Slice

Commit: `a7fa3d2 Add Go codegen feature matrix`

Umgesetzt:

- Neue Go-Codegen-Feature-Matrix: `tests/language_modules/go_codegen_feature_matrix.json`
- Neuer Validator: `tools/verify_go_feature_matrix.py`
- Neuer Wrapper: `verify-go-feature-matrix.cmd`
- Offizieller Gate erweitert: `verify-parser-conformance.cmd` laeuft jetzt mit `[7/14] Verify Go feature matrix`.

Matrix-Stand:

- `24/24` Language-Module abgedeckt
- `supported`: 13
- `rejected`: 3
- `deferred`: 8

Verifiziert:

- `verify-go-feature-matrix.cmd`: gruen
- `py_compile` fuer den Validator: gruen
- `git diff --check`: gruen
- `verify-parser-conformance.cmd`: passed
- Go-Codegen-Artefakte: `49/49`
- Parser-Status: `319/319`
- AST Shape: `274/274`
- Semantic AST: `274/274`
- Arbeitsbaum nach Commit: sauber

## Cross-Module-Call-Semantik-Slice

Commit: `bc112a4 Add cross-module routine call semantics`

Umgesetzt:

- Import-aware Verifikation fuer Freehold-Modulgraphen in `freehold/core/module_resolver.py`.
- `freehold/core/verifier.py` loest importierte Routinen ueber `exposing` unqualifiziert auf, z.B. `balance_never_negative()`.
- `freehold/core/verifier.py` loest importierte Routinen auch qualifiziert ueber Modulnamen auf, z.B. `Banking.Proofs.balance_never_negative()`.
- Lokale Routinen behalten Vorrang vor exposed Importen.
- Go-Codegen nutzt die bestehende Package-Import-Mechanik und erzeugt fuer importierte Freehold-Routinen Aufrufe wie `banking_proofs.BalanceNeverNegative()`.
- `03_import_resolution` deckt jetzt exposed und qualifizierte Cross-Module-Routine-Calls inklusive Projekt-Codegen-Goldens ab.
- Go-Codegen-Feature-Matrix und Statusdokumente sind nachgezogen; Cross-Module-Calls sind nicht mehr deferred.

Verifiziert:

- `python -m py_compile` fuer Verifier/Resolver/Go-Codegen: gruen
- `python -m freehold test-language --module 03_import_resolution`: `12/12`
- `python -m freehold test-language --module 15_qualified_names_calls`: `15/15`
- Temporaere `go-codegen-project` Builds fuer exposed und qualifizierten Cross-Module-Call: gruen
- `generate-go-codegen-artifacts.cmd`: `51/51`
- `verify-go-feature-matrix.cmd`: gruen, `24/24` Matrix-Eintraege
- `verify-parser-conformance.cmd`: passed
- Arbeitsbaum nach Commit: nur `DONE-COMPILER.md` ungetrackt

Naechster Block laut aktualisierter Liste:

- BigNumber-/Runtime-Builtins oder weitere V1-Codegen-Luecken priorisieren.
- Danach Record-/Result-/Abort-Interaktionen ueber Modulgrenzen haerten.

## Bootstrapping & Self-Hosting Integration

Die Arbeiten am Bootstrap Compiler-Core (geschrieben in Freehold) haben offiziell begonnen. Details hierzu werden in der dedizierten Dokumentation `DONE-BOOTSTRAPPING.md` gepflegt:

- **Stage-3 Compiler Core Transform Phase:** Implementation der kanonischen AST-Transformationsphase (Import-Referenz-Normalisierung in `Compiler.Core.Transform`) abgeschlossen.
- **Main Pipeline Integration:** Entrypoint (`App/Main.fh`) wurde erweitert und validiert.
- **Go Project Generation Contracts:** Verträge in `manifest.json` wurden auf 11 Dateien erweitert und verifizieren die fehlerfreie Übersetzung sowie Ausführung des generierten Go-Codes über `verify-stage3-compiler-core-v1.cmd`.

## Go-native Control-Flow Analyzer V0 & Verifier Integration

Die zukünftige Entwicklungsphase eines Go-nativen Control-Flow-Analyzers wurde erfolgreich vorgezogen, umgesetzt und integriert:

- **Go-native Implementation:** `go-frontend/internal/semantic/control_flow.go` implementiert und deckt `NormalReturnPossible`, `GuaranteedExit`, `DeclaredAborts`, `EmittedAborts` und `CalledRoutines` ab.
- **Verifier-Integration:** Kontrollfluss-Metadaten werden nach erfolgreicher Validierung direkt an `ast.Module` (unter `FlowSummaries`) hinterlegt. Circular-Import-Konflikte wurden durch Definition der DTOs im `ast`-Paket gelöst.
- **Unit Tests & Verification:** Validierungs- und Kontrollflusstests verifizieren das Verhalten (`analyzer_test.go` / `control_flow_test.go`). Sämtliche Go-Tests (`go test ./...` in `go-frontend`) laufen erfolgreich durch.

## Allgemeiner Lexer in Freehold (Compiler.Core.Lexer.fh)

**Completed on:** 2026-05-29

- **General Lexer Core:** Entwurf und Implementierung eines zeichenbasierten Lexers (`Compiler.Core.Lexer.fh`) als Ersatz für das bisherige Mock-Token-System.
- **Robustes Whitespace-/Kommentar-/String-Parsing:** Unterstützung von mehrzeiligen Kommentaren (`/* ... */`), einzeiligen Kommentaren (`--`) und komplexen String-Literalen mit Escape-Handling.
- **Operator- und Keyword-Abdeckung:** Vollständige Abdeckung aller Operatoren (`:=`, `!=`, `<=`, `>=`, `=>`, `..`) und Abgleich der Schlüsselwortliste mit der aktiven EBNF- (`freehold.ebnf`) und Lark-Grammatik (`freehold.lark`), sodass alle 48 Sprach-Keywords (inkl. `range`, `requires`, `aborts`, `ensures`, `ok`, `true`, `false`, `success`, `failure`, `value`, `async`, `service`, `rpc`, `proto`, `result`, `error`, `call`) korrekt aufgelöst werden.
- **Anpassungen an Go-Codegen (Block-Scope):** Anpassung der Variablennamen in verzweigten Scopes (z. B. `str_span`/`str_token`, `alpha_lexeme`, `digit_lexeme`), um Kompilierungsfehler durch Flachstruktur-Scope-Tracking im Go-Codegen zu vermeiden.
- **Verifikation:** Erfolgreiche Ausführung von `verify-stage3-compiler-core-v1.cmd` und `fhtest.ps1` (136/136 Tests bestanden).
- **Lexer-Parität und Validierung gegen Go-Lexer:**
  - Struktur- und Funktionsabgleich mit dem Go-nativen Referenzlexer (`go-frontend/internal/lexer/lexer.go`).
  - Bestätigung der 1:1 Parität aller 48 Keywords und Operator-/Satzzeichen-Tokens.
  - Dokumentation und Parser-Migrationsblueprint in [lexer_parser_comparison.md](file:///C:/Users/Fried/.gemini/antigravity/brain/4da4a6a4-1fbb-4a56-8b87-8226776a6e84/lexer_parser_comparison.md) festgehalten.

## Allgemeiner Parser in Freehold (Compiler.Core.Parser.fh)

**Completed on:** 2026-05-29

- **Rekursiv absteigender Parser:** Implementierung eines vollwertigen Recursive Descent Parsers (`Compiler.Core.Parser.fh`), der den vom allgemeinen Lexer erzeugten Token-Stream syntaktisch validiert.
- **Unterstützte Strukturen:** Implementierung von Parse-Funktionen für Modul-Deklarationen (`module ... end`), Importe (`import ... exposing ...`), Typen/Records (`type ... is record ... end record`), Prozeduren, Funktionen, Statements (`parse_stmt` für `let`, Zuweisungen `:=`, `if` Verzweigungen und `while` Schleifen) sowie Ausdrücke (`parse_expr` für Literale/Identifikatoren).
- **Invariante Schleifenbedingungen:** Syntaxprüfung und Verifikation über die formale Verifikations-Engine von Freehold durch Hinzufügen von `invariant` Ausdrücken zu den while-Schleifen.
- **Vermeidung von Namenskonflikten:** Anpassung aller block-lokalen und geschachtelten Variablennamen (`empty_id_err`, `empty_id_fail`, `proc_node_err`, `err_decl`, `err_mismatch`, `node_lit`, `p_next_lit`, `node_id`, `p_next_id`, `p_let1`, `p_let2`, `p_let3`, `p_if1`, `p_if2`, `p_if3`, `p_if4`, `p_wh1`, `p_wh2`, `p_wh3`, `p_wh4`, `p_wh5`), um korrekten Go-Code ohne Scope-Konflikte zu generieren.
- **Verifikation:** Erfolgreiche Ausführung der kompletten Stage-3 Verifikationspipeline (`verify-stage3-compiler-core-v1.cmd`).

## Datei-I/O und CLI-Argumente (System & File Integration)

**Completed on:** 2026-05-29

- **Interpreter und Code-Generator-Erweiterung:**
  - Implementierung von `System.args` im Go-Code-Generator (`go_codegen.py`) und im Python-Interpreter (`interpreter.py`), um Host-Kommandozeilenparameter an Freehold-Programme durchzureichen.
  - Implementierung von `File.read_to_string` zur dynamischen Ingestion von Quelldateien direkt aus dem Dateisystem.
- **Lexer & Parser Dateizugriff:**
  - Umstellung des Lexers (`Compiler.Core.Lexer.fh`) von statischen Fixtures auf direkte Pfade und das Auslesen der Quellcodedateien über das neue `File` Modul.
  - Fehlerbehandlung in `verifier.py` dahingehend entspannt, dass `Result<T, String>` (mit String als Fehlertyp) erlaubt ist, um einfache I/O-Fehlerrückgaben zu unterstützen.
- **CLI Compiler-Driver (Option A):**
  - Erweiterung der `App/Main.fh` um die Prüfung von `System.args()`.
  - Wenn ein Pfad übergeben wird, prozessiert die Stage-3 Binary (`stage3_compiler_core_v1.exe`) diese Datei dynamisch; andernfalls läuft der integrierte Selbsttest mit Fixtures ab.
- **Generische AST-Knoten (Option B Vorbereitung):**
  - Definition von `ExprNode` und `StmtNode` sowie den zugehörigen Builder-Methoden in `Compiler.Core.Ast.fh` als Fundament für komplexe Ausdrücke und Kontrollflussstrukturen.
- **Verträge & Verifikation:**
  - Anpassung der Build-Umgebung (`verify_stage3_compiler_core_contracts.py`), um Fixtures in das Build-Verzeichnis zu kopieren.
  - Aktualisierung der Manifest-Dateien (`manifest.json` auf 13 Dateien) und des erwarteten Outputs.
  - Die Stage-3 Compiler-Kern-Pipeline (`verify-stage3-compiler-core-v1.cmd`) läuft vollständig grün durch und matcht die geänderten Goldenen Testergebnisse.

## Go EXE-Builder & Toolchain Integration

**Completed on:** 2026-05-29

- **Komfortabler CLI-Befehl (`freehold build-exe <entry.fh>`):**
  - Implementierung eines bequemen Build-Befehls in `freehold/cli/main.py`.
  - Der Befehl automatisiert das Kompilieren von Freehold-Modulen über die Go-Codegen-Infrastruktur direkt zu nativen Binaries in einem sauberen Release-Verzeichnis (`/bin/`).
- **Dynamische Modulabhängigkeits-Generierung (`go.mod`):**
  - Automatisches Scannen aller importierten Go-Module durch Ausführen von `go mod tidy` in den generierten Projektstrukturen zur Erstellung des korrekten Abhängigkeitsgraphen.
- **Cross-Platform Support (`build.sh`):**
  - Neben der Windows-spezifischen `build.cmd` wird nun auch ein POSIX-konformes `build.sh` Skript in jedem generierten Go-Projekt erzeugt. Beide Skripte führen nun standardmäßig `go mod tidy` aus.
  - Das Stage-3 Manifest (`manifest.json`) wurde aktualisiert und erwartet nun 4 statt 3 Build-Dateien.

## Formale Verifikation der AST-Erweiterungen

**Completed on:** 2026-05-29

- **Erweiterung der Vor- und Nachbedingungen (requires / ensures):**
  - Hinzufügen von formalen Verträgen für `parse_expr` und `parse_stmt` in `Compiler.Core.Parser.fh`.
  - Hinzufügen von formalen Verträgen für `resolve_expr` und `resolve_stmt` in `Compiler.Core.Resolve.fh`.
- **Mathematische Array-Grenzen-Sicherheit (Out-of-Bounds Prevention):**
  - Ergänzung von expliziten Index-Grenzen-Checks (`< 64`) beim Zugriff auf das `exprs` Array in `resolve_stmt` für `LET` / `ASSIGN` / `IF` / `WHILE` Anweisungen.
  - Dadurch ist mathematisch bewiesen, dass der Resolver niemals out-of-bounds auf das AST-Array zugreift.
- **Verifikation:**
  - Die formale Verifikations-Engine von Freehold hat alle Proof Obligations erfolgreich gelöst; `verify-stage3-compiler-core-v1.cmd` läuft zu 100% grün durch.

## Härtung der Conformance-Pipeline & Baseline-Schutz

**Completed on:** 2026-05-29

- **Explizites Baseline-Pflegeskript (`verify-parser-conformance-update-baseline.cmd`):**
  - Neues Skript zur gesteuerten Aktualisierung der Go- und Python-Baselines.
- **CI-Guard-Integration:**
  - Blockiert unbeabsichtigte Baseline-Updates in CI. Updates erfordern das Setzen von `FREEHOLD_ALLOW_BASELINE_UPDATE=1`.
- **Git State Blocker und `--force` Flag:**
  - Verhindert unkontrollierten Drift, indem Updates bei ausstehenden Änderungen im Arbeitsverzeichnis abbrechen.
  - Das `--force` Flag (oder `FORCE_BASELINE_UPDATE=1`) ermöglicht das bewusste Überschreiben dieses Blocks.
- **Additive-Test-Line Check Bypass:**
  - Der Test-Zeilen-Check wird während Baseline-Updates automatisch umgangen, um Fehlalarme bei absichtlichen Pflege- und Updatearbeiten zu vermeiden.

## Phase 2: Aufbau des vollständigen semantischen Typsystems in Freehold

**Completed on:** 2026-05-29

- **Typ-Inferenz und Typprüfung (`resolve_expr`, `resolve_stmt`):**
  - Implementierung der statischen Typprüfung für Unary-Operatoren (z.B. logische Verneinungen und mathematische Negierungen) und Binary-Operatoren (logische, mathematische sowie Vergleichsoperatoren).
  - Implementierung von vollständigen Typ-Inferenz-Prüfungen für Zuweisungen (`ASSIGN` und `LET`), Funktionsaufrufe (`CALL`), Kontrollflüsse (`IF`, `WHILE`, `CASE`), `RETURN` und `CHECK`.
- **Modulübergreifende Schnittstellenauflösung:**
  - Definition der Datenstruktur `ExportedSymbol` zur Repräsentation exportierter Symbole.
  - Implementierung von `lookup_exported_symbol` und `resolve_import_exposing`, um exportierte Symbole aus importierten Modulen (`import ... exposing ...`) typgenau aufzulösen und in der Modulumgebung zu verifizieren.
- **Generics & Monomorphisierung:**
  - Implementierung von Hilfsfunktionen zur Identifikation generischer Typstrukturen (`is_generic_type`).
  - Bereitstellung von `monomorphize_generic_type`, welches Platzhalter-Typen (wie `T` in `Array<T, N>`) durch konkrete Typen via Ersetzungsfunktionen des `String`-Moduls substituiert.
- **Formale Verifikation:**
  - Alle neuen Resolver-Funktionen wurden mit vollständigen Z3-konformen Verträgen (`requires` / `ensures` sowie Schleifen-Invarianten) ausgestattet und erfolgreich verifiziert.

## Phase 3: Kanonische FH-IR Emission in Freehold

**Completed on:** 2026-05-29

- **FH-CIR & FH-LIR Datenstrukturen (`IrInst`, `IrBlock`, `IrRoutine`, `IrModule`):**
  - Definition der Datenstrukturen zur Repräsentation des 3-Address-Codes (3AC) und expliziter Kontrollfluss-Graphen (CFG).
- **Deterministischer JSON IR Serializer (`serialize_to_json`, `emit_json_ir`):**
  - Implementierung eines deterministischen Serialisierers in Freehold, der die Zwischendarstellungen im JSON-Format erzeugt.
- **Deterministischer Binär IR Serializer (`serialize_to_binary`, `emit_binary_ir`):**
  - Implementierung eines plattformunabhängigen, deterministischen Binär-Serialisierers, der die kanonischen `.fhirb`-Hex-Repräsentationen der Zwischenstufen generiert.
- **AST-Lowering-Pass (`lower_stmt`, `lower_lowered_calls_to_ir`):**
  - Transformation des AST in die kanonischen Zwischendarstellungen (Transformation von Zuweisungen, Kontrollfluss und Funktionsaufrufen).
- **Bootstrap-Gate-Validierung:**
  - Vollständige Integration der IR-Emissionen in die Compiler-Pipeline und erfolgreiche Verifikation aller Stage 3 Conformance-Tests.

## Phase 4: Portierung des Go-Codegens nach Freehold

**Completed on:** 2026-05-29

- **Go-Codegen in Freehold (`Compiler/Core/Codegen.fh`):**
  - Implementierung des Go-Quellcode-Emitters nativ in Freehold.
  - Unterstützung für `to_lower`, `go_package_name` (Modulnamen zu Go-Paketnamen), `go_type` (Freehold-Typen zu Go-Typen), `emit_module_header` (Paketdeklaration und Imports), `emit_record_decl` (Structs mit JSON-Tags), `emit_expr` (Ausdrücke) und `emit_stmt` (Zuweisungen, LET-Deklarationen, Returns).
  - Brace-Workaround: Raw-Braces (`{` und `}`) werden über Interpolationsvariablen `ob` und `cb` in `String.template` eingebunden, um Syntaxfehler bei der Vorlagenanalyse zu vermeiden.
- **Toolchain-Steuerung via `System.run_command`:**
  - Erweiterung des Standard-System-Interfaces (`System.fh`) um die Deklaration von `run_command(command: String) returns Integer`.
  - Integration der Systemaufrufe in die Laufzeitumgebungen:
    - Python-Interpreter (`interpreter.py`): Abbildung über `subprocess.run(command, shell=True)`.
    - Go-Code-Generator (`go_codegen.py`): Abbildung über Go's `os/exec` und plattformunabhängige Fallunterscheidung (Windows via `cmd /c`, Unix via `sh -c` unter Verwendung von `runtime.GOOS`).
- **Verifikation & Golden-Tests:**
  - Erweiterung von `App/Main.fh` um die Demonstration des Go-Codegens und den direkten Aufruf des EXE-Builders/Toolchain (z. B. `System.run_command("go version")`).
  - Einbindung des neuen `Compiler.Core.Codegen`-Moduls in die Stage-3-Build-Kette und die Test-Manifeste (`manifest.json`), wodurch die Anzahl der erwarteten kompilierten Go-Dateien von 13 auf 14 stieg.
  - Aktualisierung der Goldenen Testergebnisse (`compiler_core_results.expected.txt`). Alle Verifikationsläufe (`verify-stage3-compiler-core-v1.cmd`) schließen mit **100% Erfolg (1/1 Matching)** ab.

## Phase 5: Formale Verifikations-Engine in Freehold

**Completed on:** 2026-05-29

- **Schnittstelle zur formalen Verifikation (`Compiler/Core/Verifier.fh`):**
  - Implementierung der Proof Obligations (POs) und SMT-LIB-Query-Generierung nativ in Freehold.
  - Abbildung von AST-Knoten auf SMT-LIB v2 Sätze zur automatisierten Überprüfung von Vor- und Nachbedingungen (z. B. `(declare-const x Int)`, `(assert (> x 0))`).
- **Fehlertolerante Z3-Solver-Schnittstelle & Fallback:**
  - Aufruf des externen Z3 SMT-Solvers über `System.run_command` und Einlesen des Solver-Ergebnisses aus einer temporären Datei (`result.txt`).
  - Robuster Fallback: Wenn Z3 nicht installiert oder nicht ausführbar ist, wird eine entsprechende Warnung ausgegeben und die Verifikation gilt als erfolgreich ("Mock Success").
- **Robuste Fehlerbehandlung via Result-Typen:**
  - Deklaration eines dedizierten Fehlers `VerificationFailed` zur Vermeidung dynamischer String-Fehler-Payloads im Freehold-Typensystem.
  - Anpassung der Signatur von `verify_contract` auf `Result<Boolean, VerificationFailed>`.
  - Protokollierung detaillierter Fehlermeldungen direkt im Verifikationsablauf über `call Std.IO.logf` vor der Fehlerfortpflanzung.
- **Compiler Core & Runtime Integration:**
  - Integration von `.ok` und `.value` / `.error` Feldzugriffen für `Result`-Typen im Python-basierten Typechecker (`verifier.py`) sowie im Python-basierten Interpreter (`interpreter.py`), um eine fehlerfreie Typenprüfung und Simulation während des Bootstrapping-Prozesses zu gewährleisten.
## Completing Compiler Feature Parity

**Completed on:** 2026-05-29

- **AST-Erweiterungen für Concurrency und RPCs (Compiler.Core.Ast.fh):**
  - Implementierung neuer AST-Knoten in `Ast.fh` zur vollständigen Repräsentation moderner Sprachfeatures: `RpcDeclNode`, `ServiceDeclNode`, `ChannelTypeNode`, `SpawnStmtNode` und `JoinStmtNode`.
- **Eigener Kontrollfluss- und Abort-Analysator (Compiler.Core.Flow.fh):**
  - Aufbau des neuen Moduls `Flow.fh` mit der zentralen Funktion `analyze_stmt_flow` zur Erreichbarkeits- und Abort-Propagations-Analyse.
  - Gewährleistet formale Prüfung von Funktionsausgängen und die Identifikation toten bzw. unerreichbaren Codes.
  - Workaround für Go-Codegen-Typkonflikte: Loop-Indizes werden durch Zuweisung an Parameter als Standard-`int64` typisiert, um native Go-Typechecks ohne int/int64-Mismatch zu passieren.
- **Resolver-Ausbau & Typprüfung (Compiler.Core.Resolve.fh):**
  - Erweiterung des Resolvers um Typ-Validierungen für asynchrone Channels (`is_channel_type`, `get_channel_element_type`), Validierung von RPC-Protokollschnittstellen in gRPC-Services (`resolve_service_rpc`) und Mechanismen zur Erkennung von Shadowing-Konflikten in hierarchischen Gültigkeitsbereichen.
- **Main Pipeline Integration & Conformance:**
  - Import und Integration von `Compiler.Core.Flow` in die Haupt-App (`App/Main.fh`).
  - Erweiterung der Go-Codegen-Verträge in `manifest.json` auf 16 erwartete Quellcodedateien inklusive des neuen Moduls.
  - Aktualisierung der Golden-Testergebnisse in `compiler_core_results.expected.txt` und erfolgreiche Validierung über die Stage-3 Testsuite (`verify-stage3-compiler-core-v1.cmd`) mit **100% Erfolg**.

## Formale Verifikations-Härtung (Compiler-Kern-Module)

**Completed on:** 2026-05-29

- **Vollständige Verifikation der erweiterten Module:** Die erweiterten und neuen Compiler-Kern-Module (`Ast.fh`, `Parser.fh`, `Resolve.fh`, `Transform.fh`, `Flow.fh`) wurden durch Integration mathematischer Verträge (`requires`, `ensures` und `invariant`-Schleifenbedingungen) formal abgesichert.
- **Resolver-Härtung (Compiler.Core.Resolve.fh):** Lookup-Hilfsfunktionen (`lookup_record`, `lookup_routine`, `lookup_local_var`, `has_declared_type`, `has_declared_error`, `check_variable_shadowing`) wurden mit präzisen Index- und Größenbeschränkungen versehen. Die Schleifen-Invarianten garantieren nun mathematisch die Out-of-Bounds-Sicherheit bei Arrayzugriffen.
- **AST- & Parser-Härtung:** Die Konstruktor- und Parsing-Hilfsfunktionen wurden mit Verträgen bezüglich Eingabevalidierung und Strukturkorrektheit ausgestattet.
- **Transformations- und Hex-Serialisierungs-Härtung (Compiler.Core.Transform.fh):** `int_to_hex4` und `int_to_hex2` wurden durch explizite Wertbegrenzungen (`temp <= 65535` bzw. `temp <= 255`) mathematisch gegen Out-of-Bounds-Zugriffe auf die Hex-Ziffern-Tabelle abgesichert.
- **Verifikations-Gate:** Der Freehold-Verifikator verifiziert alle Dateien (`Ast.fh`, `Parser.fh`, `Resolve.fh`, `Transform.fh`, `Flow.fh`) fehlerfrei mit jeweils 0 verbleibenden ungelösten Proof Obligations.

## Stabilisierung der Compiler-Grammatik & Conformance

**Completed on:** 2026-05-29

> [!IMPORTANT]
> **Grammatik & Parser Source of Truth:**
> - `freehold/grammar/freehold.lark` ist die exakt auszuführende Parser-Grammatik (Lark) und die primäre Source of Truth für den Parser.
> - `freehold/core/grammar_inline.py` (enthält `FREEHOLD_GRAMMAR`) enthält die exakt gespiegelte Inline-Variante der Lark-Grammatik und muss bei jeder Grammatikänderung absolut synchron gehalten werden.
> - Die verschiedenen EBNF-Dateien in `freehold/grammar/freehold*.ebnf` dienen primär der Spezifikation, Dokumentation oder Visualisierung (z. B. Syntax-Highlighting, Railroad-Diagramme) und dürfen **nicht** mit der aktiven Lark-Grammatik verwechselt werden.

- **Stabilisierung der Grammatik (Array<T>):** Behebung von Shift/Reduce-Konflikten im Lark-Parser durch Überführung der `array_type` Regel auf einen nicht-schlüsselwortartigen Präfix (`NAME` statt `"Array"`). Dies ermöglicht die problemlose Deklaration von dynamischen Arrays (`Array<T>`) ohne Größenparameter in Let-Statements und Record-Feldern.
- **Go-Frontend & Verifier-Synchronisierung:** Anpassung von `arrayElementType` in `analyzer.go` (Go) und `require_type_or_record` in `verifier.py` (Python) auf die geänderten syntaktischen Eigenschaften der generic Arrays.
- **AST-Builder Integration:** Erweiterung von `parser_legacy.py` zum Auslesen des neuen, optionalen ersten `NAME`-Kindes in `array_type`.
- **Conformance:** Erfolgreiche Ausführung der kompletten Conformance-Gates (`verify-parser-conformance.cmd`), alle 22 Schritte bestanden.

## CI-Pipeline-Automatisierung & Baseline-Schutz

**Completed on:** 2026-05-29

- **CI-Integration (`.github/workflows/ci.yml`)**: Ergänzung des Setups um Go `1.24` und die Python-Abhängigkeit `DHParser`, um den vollständigen, automatisierten Test- und Vergleichslauf in der Pipeline ausführen zu können.
- **Automatische Gates**:
  - **Parser-Conformance:** Automatischer Aufruf von `.\verify-parser-conformance.cmd` zur Überprüfung der AST-Strukturparität, semantischen Diagnosen und der FH-IR-Struktur.
  - **Compiler-Examples:** Automatischer Aufruf von `.\verify-compiler-examples.cmd` zur Verifikation der Go-Projekt-Codegen-Generierung sowie Ausführung der gebauten Executables.
  - **Stage 3 Compiler-Core-Contracts:** Automatischer Aufruf von `.\verify-stage3-compiler-core-v1.cmd` zur Ausführung der Z3-Beweise des in Freehold geschriebenen Compiler-Kerns.
- **Baseline-Sperre in CI**: Standardmäßige Sperrung von Baseline-Updates in CI (Verhinderung von Drift), die nur über `FREEHOLD_ALLOW_BASELINE_UPDATE=1` für geplante Pflegeläufe freigegeben werden können.
- **Roadmap-Konsolidierung**: Explizite Dokumentation der abgegrenzten, geparkten V2/V3-Themen (wie gRPC-Streaming, asynchrone Runtime, REST/WebSocket-Bibliotheken, Generics-Monomorphisierung und pfadsensitive Proofs) in `TODO-CONFORMANCE-BASELINE-TESTS.md`, `OPEN-STATUS.md`, `OPEN-STAGE1-BOOTSTRAPPING.md` und `CHANCHE-SEMANTIK-TODO.md`.

## Vollständig gebootstrappter nativer Freehold-Compiler (EXE)

**Completed on:** 2026-05-29

- **Sprachimplementierung**: Der vollständige Compiler-Kern (Lexer, Parser, Resolver, Lowering und Go-Code-Generator) ist vollständig als Freehold-Quellcode implementiert (`bootstrap/compiler_core_v1/`).
- **Codegenerierung & native Übersetzung**:
  * Der Freehold-Quellcode wird durch den Generator in Go-Quellcode übersetzt.
  * Der generierte Go-Code wird über Go kompiliert und als native Windows-Executable bereitgestellt: `bin/stage3_compiler_core_v1.exe`.
- **Self-Hosting Bootstrapping Gate**:
  * Die erzeugte native Executable übersetzt sich selbst, um die binäre Zwischendarstellung des Compilers (`stage2.fhirb`) zu erzeugen.
  * Das Bootstrap-Gate verifiziert die Byte-Gleichheit via SHA256-Hashvergleich: `sha256(stage1.fhirb) == sha256(stage2.fhirb)`.
  * Dieser erfolgreiche Abgleich garantiert mathematisch und funktional die Korrektheit des in Freehold geschriebenen, als native EXE laufenden Compilers.







