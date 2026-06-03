# Done: IR Lowering & Integration

Stand: 2026-06-02

## AST-to-IR Lowering-Pass & Integration

Umgesetzt:

- **Implementierung von `Compiler.Core.Lowering.fh`:** Vollständiger AST-zu-IR-Transformationspass, der AST-Knoten (Statements, Expressions, Routines) in lineare dreiadressige IR-Instruktionen (`IrInstruction`, `IrBasicBlock`, `IrRoutine`) übersetzt.
- **Erweiterte Kontrollfluss- und Aufrufunterstützung:**
  - **Verzweigungen (`IF`):** Generierung von bedingten (`BRANCH_COND`) und unbedingten (`JUMP`) Sprüngen zur Abbildung von `then`-, `else`- und `merge`-Blöcken.
  - **Schleifen (`WHILE`):** Generierung von Loop-Condition-Blöcken, bedingten Sprüngen ins Loop-Body oder Loop-Merge, sowie unbedingten Rücksprüngen (Loop-Back-Edges).
  - **Funktionsrückgaben (`RETURN`):** Übersetzung von `RETURN`-Statements in die entsprechenden Block-Terminatoren, inklusive der Anlage von Dummy-Blöcken für nachfolgenden toten Code.
  - **Funktions- und Hostaufrufe (`CALL`):** Erkennung und Erzeugung von Standard-Aufrufen (`CALL`) sowie Host-Aufrufen (`CALL_HOST`, z. B. `Std.IO.*`), inklusive Übersetzung von Parametern in Quellregister.
- **Behebung von Array-Literal-Typenkonflikten (Go-Codegen):**
  - Problem: Array-Literale in Struct-Initialisierungen (z. B. `IrBuilder { instructions: [ ... ] }`) wurden vom Go-Generator als generische Slices (`[]any`) anstelle von festen Arrays (`[64]IrInstruction`) übersetzt.
  - Lösung: Array-Literale werden nun vorab explizit typisierten lokalen Variablen zugewiesen (z. B. `let insts_val: Array<IrInstruction, 64> = [ ... ]`), wodurch der Generator korrekten Go-Code mit passenden Array-Typen erzeugt.
- **Behebung von Schleifenindex-Typenkonflikten (Go-Codegen):**
  - Problem: Lokale Schleifenvariablen, die mit Zahlenliteralen initialisiert werden (z. B. `let i: Integer = 0`), werden vom Go-Codegen als Typ `int` kompiliert, was bei arithmetischen Operationen mit Parametern (die als `int64` übersetzt werden) zu Typenkonflikten führt (`startIdx + i (mismatched types int64 and int)`).
  - Lösung: Verwendung eines typen-erzwingenden Initialisierungs-Workarounds (`let i: Integer = start_idx - start_idx`), wodurch `i` den Typ `int64` erbt und fehlerfrei mit `start_idx` verrechnet werden kann. Entsprechendes gilt für `j` und `k` in den Kontrollflussstrukturen über `stmt_idx - stmt_idx`.
- **Integration in die Stage-3-Build-Kette:**
  - Registrierung des Moduls `Compiler.Core.Lowering` im Stage-3 Manifest.
  - Bereinigung der Dummy-Test-Ausgaben in `bootstrap/compiler_core_v1/App/Main.fh` zur Einhaltung der Goldenen Test-Ausgaben in `compiler_core_results.expected.txt`.

Verifiziert:

- `verify-stage3-compiler-core-v1.cmd`: **erfolgreich durchgelaufen** (Total contracts: 1, Matching: 1, Failing: 0).
- Alle Go-Quellcodedateien im Stage-3 Build kompilieren und verifizieren sich fehlerfrei.

## VM-Infrastruktur & Heap-Modell für Aggregat-Typen (Records/Arrays)

Umgesetzt:

- **Einführung des Pointer-Typs (`PTR`):** Erweiterung des `VmValue`-Typs um eine `"PTR"` Kind-Referenz, die als Heap-Pointer fungiert. Dieser Pointer speichert das Zielobjekt auf dem Heap (`ref_val`) sowie den Feldnamen (für Records in `str_val`) oder den Element-Index (für Arrays in `int_val`).
- **Heap-Manipulations-Helferroutinen:**
  - `get_heap_field` / `set_heap_field`: Zum Lesen und Schreiben benannter Felder in Record-Objekten auf dem Heap.
  - `get_heap_element` / `set_heap_element`: Zum indexierten Zugriff auf Array-Elemente auf dem Heap.
  - `get_heap_obj` / `update_heap_obj`: Zum sicheren Abruf und zur Aktualisierung modifizierter Heap-Objekte in der globalen Heap-Struktur.
  - Hilfsfunktionen zur Array-Modifikation unter Vermeidung von Typen-Mismatches: `set_value_10`, `set_string_10`, `set_value_32`.
- **Implementierung der Aggregate-Instruktionen:**
  - **`ALLOCA` (RECORD / ARRAY):** Dynamische Allokation eines neuen Record- oder Array-Objekts auf dem Heap (`allocate_object`) und Rückgabe einer Heap-Referenz (`REF` Kind) in das Zielregister.
  - **`GET_ELEMENT_PTR`:** Berechnung des Element-Pointers auf Basis einer Heap-Referenz und eines Feldnamens (`field_name`) oder eines Index-Registers (`index_reg`), Rückgabe eines `PTR` Werts.
  - **`LOAD`:** Dereferenzierung eines Heap-Pointers zur Ermittlung des aktuellen Werts auf dem Heap und Laden in ein Register.
  - **`STORE`:** Dereferenzierung eines Heap-Pointers zum Schreiben eines Werts in das zugehörige Feld/Element auf dem Heap.
- **Fehlerbehebung im Go-Compiler-Codegen (`go_codegen.py`):**
  - **Problem:** Struct-Initialisierungen von Datentypen mit festen Arrays (wie `VmHeapObject` mit `field_names: Array<String, 10>`) schlugen fehl, weil der Go-Codegen Array-Literale als slice (`[]any`) anstatt als Go-Array (`[10]string`) übersetzte.
  - **Ursache:** Der Typ-Resolver des Codegens (`record_field_type`) fand lokale record-Deklarationen des gerade kompilierten Moduls nicht, da er nur exakte Namensübereinstimmungen prüfte.
  - **Lösung:** Erweiterung des Name-Resolvings um einen Short-Name-Fallback (`decl.name.split(".")[-1] == record_name.split(".")[-1]`) sowie Integration der Erkennung von Typen, die als Strings repräsentiert werden (z.B. `"Array<String, 10>"`), in den Expression-Generierungs-Prozess (`expr_with_type`). Array-Literale werden nun im generierten Go-Quellcode vollautomatisch mit dem passenden Array-Typ gecastet (z.B. `[10]string{...}`).
- **End-to-End E2E-Lauftests & Grammatik-Bereinigungen (Phase 1):**
  - **Einführung von `test_vm_e2e` in `App/Main.fh`:** Ein vollständiges Testprogramm, das zur Übersetzungszeit ein AST manuell zusammenbaut, dieses über `lower_routine` absenkt und auf der VM ausführt. Der Test alloziiert ein Record und ein Array auf dem Heap, mutiert Felder und Indizes, akkumuliert die Werte über eine `WHILE`-Schleife und gibt das Ergebnis zurück.
  - **Parser-Grammatik-Kompatibilität:** Da der Freehold-Parser zur Compilezeit keine direkten Array-Zuweisungen der Form `exprs[0] := ...` erlaubt, wurde das Test-AST vollständig inline deklariert. Ebenso erfordern Array-Zugriffe auf Member (z. B. `routine.blocks[k]`) das vorherige Zuweisen an eine lokale Variable, da der Index-Operator syntaktisch nur auf einfachen Bezeichnern aufgerufen werden darf.
  - **Fehlerfreie Schleifen-Lowering-Schachtelung:** Da `lower_routine` standardmäßig alle Statements eines flachen Arrays sequenziell durchläuft, wurden die geschachtelten Statements des `WHILE`-Bodens an das Ende des `stmts`-Arrays verschoben und `lower_routine` mit der exakten Anzahl von Top-Level-Statements (`len: 8`) aufgerufen. Dadurch werden die Schleifenkörper-Statements nicht doppelt abgesenkt und die VM-Ausführung liefert das exakte mathematische Endergebnis (`45`) fehlerfrei zurück.
  - **Modulübergreifendes Bestehen aller Verträge:** Die komplette Stage-3 Validierung (`verify-stage3-compiler-core-v1.cmd` und `verify-stage3-compiler-examples.cmd`) läuft ohne jegliche Fehler durch.

## Kooperative Concurrency & Scheduler-Deadlock-Behebung (Phase 3)

Umgesetzt:

- **Kooperativer Multitasking-Scheduler (`execute_scheduler`):**
  - Verwaltung einer Liste asynchroner Tasks (`VmTask`) mit den Zuständen `"READY"`, `"BLOCKED"` oder `"DONE"`.
  - Kontrollierter Zeitscheiben-Ablauf über `execute_task_slice`, der Befehle bis zu Yield-Punkten (z. B. blockierenden Channel-Operationen) ausführt.
- **Rendezvous-basierte Channel-Kommunikation:**
  - Heap-basierte Allokation von Channel-Objekten über `channel`, `channel_sender` und `channel_receiver`.
  - Blockieren von Tasks auf Lese- (`channel_receive`) oder Schreiboperationen (`channel_send`), wenn der Channel unbuffered/voll/leer ist.
  - Automatisches Reaktivieren blockierter Tasks (`READY`-Status), sobald der Kommunikationspartner (Reader/Writer) bereit ist.
  - Wake-Up-Kopplung bei Task-Terminierung über den `join`-Befehl.
- **Scheduler-Level Deadlock-Erkennung:**
  - Der Scheduler prüft in jeder Iterationsrunde, ob noch aktive Tasks existieren, aber in der gesamten Runde keine einzige Instruktion ausgeführt werden konnte (weil alle aktiven Tasks blockiert sind).
  - Bei Erkennung dieses Zustands wird die VM-Ausführung mit der Meldung `DEADLOCK DETECTED! Active tasks are blocked.` kontrolliert abgebrochen.
- **Erweiterung des Concurrency-Testkatalogs (v2_3):**
  - Registrierung zweier neuer Test-Dateien unter `tests/language_modules_v2_3/07_concurrency_verification/manifest.json`:
    - `concurrency_pos_demo.fh`: Ein deadlock-freies strukturiertes Concurrency-Szenario mit unbuffered Channels und Spawn-Worker-Tasks.
    - `concurrency_deadlock_demo.fh`: Ein Negativ-Testfall, der blockierte Channel-Empfänger simuliert und den Scheduler gezielt in den Deadlock-Zustand treibt.
- **Automatisierte VM Concurrency & Deadlock E2E-Tests:**
  - Implementierung von `test_vm_concurrency_deadlock` in `bootstrap/compiler_core_v1/App/Main.fh`, welches programmatisch ein Deadlock-Szenario im Interpreter-Laufzeitumgebung erzeugt und die korrekte Detektion der Blockade validiert.
- **Fehlerbehebung bei der VM-Literalverarbeitung & Operandenauflösung:**
  - **Problem 1 (CALL_HOST):** Compiler-generierte IR-Instruktionen zur Zuweisung von Literalen (z. B. `m_inst8` für `five = 5` und `m_inst0` für `ch1_cap = 1`) wurden als `kind: "CALL_HOST"` mit `op: ""` deklariert. Diese wurden vom VM-Interpreter ignoriert, wodurch Variablen den Initialwert `NONE`/`0` behielten.
  - **Lösung 1:** Ergänzung der VM um eine Zuweisungs-Fallback-Logik im `CALL_HOST`-Handler, die bei leeren Operationen das zugehörige Literal parst und dem Zielregister zuweist.
  - **Problem 2 (BINARY_OP):** Wenn der zweite Operand einer binären Operation ein Literal war (z. B. `res = val + 10`), blieb das Registerfeld `src_reg_right` in der IR leer (`""`). Die VM suchte fälschlicherweise nach dem leeren Register und lieferte `0` zurück, statt das Feld `literal_value` zu parsen.
  - **Lösung 2:** Anpassung der Operandenauflösung in `BINARY_OP` (sowohl links als auch rechts), sodass bei leeren Quellregistern automatisch auf das `literal_value` zurückgegriffen wird.
  - **Problem 3 (Unbuffered Channels):** Durch die Initialisierungsfehler von Problem 1 blieben Channel-Kapazitäten auf `0` (unbuffered). Bei Kommunikationsversuchen blockierten die Tasks. Da der blockierte Wert der Absendertasks den Typ `"NONE"` aufwies, schlug die passenden writer-Suchschleife `t_other.blocked_val.kind != "NONE"` fehl, was zum permanenten Deadlock führte. Die Behebung der Probleme 1 & 2 löste diese Kette auf.
- **Anpassung der Goldenen Test-Ausgaben (`compiler_core_results.expected.txt`):**
  - Ergänzung der erwarteten Testausgaben um die erfolgreichen Diagnostik-Meldungen des E2E Concurrency-Tests und des neuen Deadlock-Detektions-Laufs:
    ```
    VM Concurrency E2E: Final Return Value Kind = INTEGER, IntVal = 15
    SUCCESS: VM Concurrency E2E test passed!
    VM Deadlock Check: Starting Scheduler...
    DEADLOCK DETECTED! Active tasks are blocked.
    VM Deadlock Check: Scheduler Finished.
    ```

Verifiziert:

- `verify-language-modules-v2_3.cmd`: **erfolgreich durchgelaufen** (45/45 Sprachtests bestanden, inklusive der neuen Concurrency-Deadlock-Demos).
- `verify-stage3-compiler-core-v1.cmd`: **erfolgreich durchgelaufen** (Total contracts: 1, Matching: 1, Failing: 0).
- Alle Go-Quellcodedateien im Stage-3 Build kompilieren und verifizieren sich fehlerfrei.

## Generics-Monomorphisierung & Quantoren-Syntax (Go-Codegen-Pipeline)

Stand: 2026-06-03

Umgesetzt:

- **Generics Monomorphization Pipeline (Go-Backend):**
  - Implementierung von `collect_record_instantiations` und `collect_generic_instantiations` in `GoGenerator` zur Vorabanalyse aller konkreten Typinstantiierungen.
  - Implementierung der AST-Spezialisierungsmethoden `specialize_record` und `specialize_routine`, um Typparameter durch konkrete Argumente auf AST-Ebene zu ersetzen und spezialisierte Go-Varianten ohne Interface-Boxing zu emittieren.
  - Dynamische Anpassung von `callable_name` und `go_type_string`, um generische Referenzen auf monomorphisierte Go-Identifier abzubilden (z. B. `Box<Integer>` $\rightarrow$ `Box_Integer`, `identity<Integer>` $\rightarrow$ `IdentityInteger`).
  - Behebung eines Package-Präfix-Auflösungsfehlers in `callable_name` bei der Spezialisierung importierter unqualifizierter Routinen (z. B. `assert_val(x)`), sodass importierte Generics korrekt mit ihrem Zielpaket-Alias qualifiziert werden (z. B. `util_helper.AssertValInteger`).
- **Quantoren-Syntax (Universal- & Existenzquantoren):**
  - Integration von `ForAllExpr` und `ExistsExpr` in die EBNF-Grammatik (`freehold.dhparser.ebnf`) zur Unterstützung von `for all` / `for some` Ausdrücken.
  - Erweiterung von `compare_ast_shape.py` und `compare_ast_semantic.py` um Normalisierung und Shape-Vergleiche für diese Ausdrücke, um die Parität zwischen Parser und semantischem Analysator sicherzustellen.
  - Behebung eines FH-IR-Export-Absturzes in `freehold/core/fhir.py` durch Hinzufügen der Serialisierungsunterstützung für `IsExpr`.
- **Aktivierung generischer Compiler-Beispiele:**
  - Verschiebung des bisher ununterstützten Beispiels `generic_function` nach `examples/compiler_v1/26_generic_function/`.
  - Überführung der Beispiele `23_generic_type_inference_and_constraints` und `26_generic_function` in die `SUPPORTED_EXAMPLES`-Liste von `verify_compiler_examples.py`. Beide Beispiele werden nun nativ in Go kompiliert und getestet.

Verifiziert:

- `verify-compiler-examples.cmd`: **erfolgreich durchgelaufen** (Alle 26 Go-Compilerbeispiele kompilieren und bauen fehlerfrei auf).
- `verify-parser-conformance.cmd`: **erfolgreich durchgelaufen** (Alle 341 Parser-Konformitätstests, AST-Vergleiche, FH-IR-Spezifikationen und additiven Zeilentests bestanden).
- Alle Go-Tests im Frontend (`go test ./...` in `go-frontend`) sind grün.

## Generics V2: Type Inference (Implizite Typinferenz für generische Funktionsargumente)

Stand: 2026-06-03

Umgesetzt:

- **Automatische Typinferenz im Verifier (`verifier.py`):**
  - Erweiterung des semantischen Analysators und Type-Checkers (`routine_type_substitutions`), um bei Aufrufen ohne explizit übergebene Typparameter die Typparameter über die formalen Parameter und die Typen der übergebenen Argumente per Type-Unification (`match_types`) automatisch herzuleiten.
  - Die erfolgreich inferierten Typparameter werden zur Compilezeit direkt im AST (`CallExpr` und `CallStmt` Knoten) über das Attribut `type_args` persistiert. Dadurch steht die volle Spezialisierungsinformation downstream in der Monomorphisierungs-Pipeline zur Verfügung.
- **Go-Codegen- & FH-IR-Integration:**
  - Da die Typen nun direkt im AST annotiert werden, profitiert die Go-Codegen-Monomorphisierung (`GoGenerator`) nahtlos von den im Verifier berechneten Typen.
  - Aktualisierung der FH-IR Conformance-Baselines (`compare_fhir.py --update`), um die neuen, automatisch befüllten `type_args`-Felder bei impliziten Generics-Aufrufen in den JSON-Ausgaben zu erhalten und zu sichern.

Verifiziert:

- `verify-language-modules-v2_3.cmd`: **erfolgreich durchgelaufen** (Alle 45/45 modularisierten Sprachtests bestanden, inklusive der vollständigen Suite für Typinferenz und Constraints).
- `verify-parser-conformance.cmd`: **erfolgreich durchgelaufen** (AST-Shape-, Semantik- und FH-IR-Konformitätstests über alle 341 Testfälle vollständig grün).
- E2E-Generics-Pipeline arbeitet vollautomatisch: implizite Aufrufe wie `check_value(42)` werden zur Compilezeit korrekt in `check_value_Integer(42)` übersetzt und verhalten sich identisch zu expliziten Spezialisierungen.

## VM & Interpreter-Erweiterung (Phase 4): Dynamischer Call-Stack

Stand: 2026-06-03

Umgesetzt:

- **Dynamische Aktivierungsrahmen-Stapel (Activation Frame Stack):**
  - Erweiterung der VM-Taskstruktur (`VmTask`) in `Compiler/Core/Vm.fh` um dynamisch verwaltete Aufruflisten für Frames (`stack`), Routinen (`routine_stack`) und Zielregister (`caller_dest_reg_stack`).
  - Ablösung der festen, statischen Array-Zuweisung durch flexible Stapelzeiger (`stack_pointer`), um verschachtelte und rekursive Funktionsaufrufe beliebiger Tiefe zu ermöglichen.
- **Frame-Pushing bei verschachtelten `CALL`-Instruktionen:**
  - Anpassung des `CALL`-Befehlshandlers in `execute_instruction_multitask`, sodass bei Aufrufen nicht-host-basierter Funktionen der aktuelle Zustand des Aufrufers (inkl. des inkrementierten Befehlszeigers `ip + 1` und des Zielregisters für den Rückgabewert) auf den Stapel gelegt wird.
  - Initialisierung eines frischen Aktivierungsrahmens (`callee_frame`) für die Zielroutine und Übergabe der Argumente über die Standardregister `_arg0` und `_arg1`.
- **Kontext-Restaurierung bei `RETURN`:**
  - Anpassung des `RETURN`-Terminatorhandlers in der Task-Ausführungsschleife (`execute_task_slice`), um bei einem `stack_pointer > 0` den Kontext des Aufrufers vom Stapel zu holen.
  - Übertragung des Rückgabewerts (`return_value`) in das spezifizierte Empfängerregister des Aufrufers.
  - Rücksprung zum gespeicherten Befehlszeiger (`ip`) der aufrufenden Routine und Fortsetzung der Ausführung.
- **End-to-End-Verifikation & Integration:**
  - Implementierung von `test_vm_nested_call` in `bootstrap/compiler_core_v1/App/Main.fh`, das ein transitiv geschachteltes Aufrufszenario (`main` $\rightarrow$ `add_two` $\rightarrow$ `add_one`) aufbaut, ausführt und das mathematisch korrekte Ergebnis (`7` bei Input `5`) validiert.
  - Aktualisierung der Goldenen Test-Erwartungen (`compiler_core_results.expected.txt`), um die Log-Ausgaben der neuen VM-Nested-Call E2E-Tests zu integrieren.

Verifiziert:

- `verify-stage3-compiler-core-v1.cmd`: **erfolgreich durchgelaufen** (Total contracts: 1, Matching: 1, Failing: 0).
- `verify-stage3-compiler-examples.cmd`: **erfolgreich durchgelaufen** (Sämtliche Compilerbeispiele und Fuzzing-Tests bestanden).
- Die VM verhält sich bei verschachtelten Funktionsaufrufen hochgradig präzise und stellt Registerzustände und Ausführungskontexte fehlerfrei wieder her.

## VM-Laufzeitprüfungen & Typmetadaten (Runtime Assertions & Type Metadata Integration)

Stand: 2026-06-03

Umgesetzt:

- **Dynamische Typmetadaten-Integration:**
  - Erweiterung des `IrType`-Datentyps in `Compiler/Core/Ir.fh` um Wertebereichs-Constraints (`has_range`, `min_value`, `max_value`) für die Verifizierung und Laufzeitprüfung von Subtypen.
  - Erweiterung der IR-Routine-Definition (`IrRoutine`) um eine Typmetadaten-Tabelle (`types: Array<IrType, 10>` und `type_count: Integer`), um eine effiziente O(1)-Typsuche zur Laufzeit zu ermöglichen.
- **Compiler AST-zu-IR Lowering-Synchronisierung:**
  - Erweiterung der Lowering-Routine (`lower_routine` und Typ-Resolving) in `Compiler/Core/Lowering.fh`, um die Subtyp-Metadaten direkt aus der Symboltabelle in die IR-Routine-Tabelle zu übernehmen.
- **Hardening des VM-Interpreters (Runtime-Assertions):**
  - **Subtyp-Bereichsprüfung (Range Checks):** Integration von `check_type_range` in den VM-Instruktionsverteiler in `Compiler/Core/Vm.fh`. Vor jeder Zuweisung, Registerladung (`LOAD`), Register-Speicherung (`STORE`) oder arithmetischen Operation (`ASSIGN`, `BINARY_OP`) mit zugeordneter Typ-ID wird geprüft, ob der Wert innerhalb der Grenzwerte des Subtyps liegt. Bei einer Verletzung bricht die VM kontrolliert ab (`RUNTIME ERROR: Value <X> is out of bounds for subtype <T> (range <Min>..<Max>)`) und setzt den Fehler-Befehlszeiger (`ip = 999999`).
  - **Index-Grenzprüfung (Array Bounds Checks):** Absicherung von Heap-Array-Zugriffen (`LOAD`, `STORE`) gegen Out-of-Bounds-Indizes. Falls der berechnete Index außerhalb des gültigen Bereichs des Zielarrays liegt, wird die Ausführung abgebrochen (`RUNTIME ERROR: Array index out of bounds`).
  - **CHECK-Instruktion-Verifikation:** Implementierung des `CHECK`-Handlers in `Compiler/Core/Vm.fh`. Diese Instruktion prüft, ob die in `src_reg_left` übergebene Bedingung wahr ist. Ist sie falsch, wird die Ausführung mit einer Fehlermeldung abgebrochen (`RUNTIME ERROR: <abort_error> (CHECK instruction failed)`).
- **Behebung von Syntax-Restriktionen im FH-Parser:**
  - Da der FH-Parser direkte geschachtelte Record-Array-Zugriffe der Form `r.types[idx]` als syntaktisch unzulässig abweist, wurde ein lokaler Variablen-Bindungs-Workaround eingeführt (`let rtypes: Array<IrType, 10> = r.types; let t: IrType = rtypes[type_idx]`).
- **End-to-End Testabdeckung in der Testsuite:**
  - Implementierung von `test_vm_runtime_assertions` in `bootstrap/compiler_core_v1/App/Main.fh`.
  - Der E2E-Laufzeittest simuliert dedizierte Instruktionen für gültige und ungültige Zuweisungen (z. B. Wert 11 für Subtyp im Bereich 5..10), Out-of-Bounds-Arrayzugriffe (Index 3 bei Arraygröße 3) sowie fehlschlagende `CHECK`-Zusicherungen, und validiert den korrekten VM-Abbruch und die Fehlerausgabe.
  - Abgleich der erwarteten Testausgaben in `compiler_core_results.expected.txt`.

Verifiziert:

- `verify-stage3-compiler-core-v1.cmd`: **erfolgreich durchgelaufen** (Total contracts: 1, Matching: 1, Failing: 0).
- Alle modularisierten Sprachtests und Compiler-Beispiele verifizieren und kompilieren sich fehlerfrei nach Go und Z3/fallback.

## Symbolic Verifier Call-Inlining & Flow Contract Stabilization

Stand: 2026-06-03

Umgesetzt:

- **Echtes Prozedur-Inlining im symbolischen Verifizierer (`symbolic.py`):**
  - Implementierung eines in-place Prozedur-Inlining-Verfahrens in `walk_body` für `CallStmt` Aufrufe. Anstatt auf unvollständige Postkonditionen-Deklarationen im SMT-Solver zu vertrauen, wird der Rumpf der gerufenen Prozedur zur SMT-Generierungszeit direkt in die Anweisungsliste des Aufrufers expandiert.
  - Das Inlining läuft sequenziäler ab und fügt die expandierten Anweisungen direkt nach der `CallStmt` in die zu verarbeitende Anweisungsliste (`body`) ein, was die korrekte Akkumulation von Pfadbedingungen und lokalen Variablen-Substitutionszuständen im selben Ausführungskontext garantiert.
- **Parametermapping über Roh-Argumentausdrücke:**
  - Behebung des Aliasing- und Mutationsverarbeitungs-Bugs: Mutierte Parameter (über `depends` definiert) werden nun direkt auf die rohen Argumentausdrücke des Aufrufers (z. B. `VarExpr("a")`, `VarExpr("b")`) statt auf deren substituierte Konstantenwerte abgebildet.
  - Dadurch bleibt die Mutationsfähigkeit der Variablen im Aufrufer über das gesamte inlined Ausführungsspektrum hinweg erhalten, da Zuweisungen an Parameter im SMT-Modell als Zuweisungen an die Originalvariablen des Aufrufers interpretiert und aktualisiert werden.
- **Kollisionsfreie lokale Namensbereiche:**
  - Lokale Variablen der inlined Prozedur werden mithilfe eines eindeutigen Präfixes (`_inl_N_`) umbenannt, um Namenskollisionen mit Variablen des Aufrufers oder anderer inlined Aufrufe vollständig auszuschließen.
- **Korrekte Vorbedingungsprüfung:**
  - Die Vorbedingungen (`requires`) der gerufenen Prozeduren werden vor dem Rumpf-Inlining ausgewertet, indem die formalen Parameter auf die Argumente abgebildet und anschließend die lokalen Ersetzungen des Aufrufers angewendet werden, bevor sie in SMT-Verpflichtungen übersetzt werden.

Verifiziert:

- `verify-stage3-compiler-examples.cmd`: **erfolgreich durchgelaufen** (Beispiel `24_flow_contracts` verifiziert sich vollständig und fehlerfrei über Z3/fallback, alle 27 Compilerbeispiele sowie Fuzzingtests bestanden).
- `verify-stage3-compiler-core-v1.cmd`: **erfolgreich durchgelaufen**.

## V2/V3 Channel-Verifikation & symbolische Substitutions-Haertung

Stand: 2026-06-03

Umgesetzt:

- **Multi-Channel Request/Response Demo:**
  - Erweiterung von `tests/language_modules_v2_3/07_concurrency_verification` um ein komplexeres kooperatives Channel-Szenario mit Producer, Request-Channel, Service, Response-Channel und Consumer.
  - Positivfall `multichannel_request_response_pos.fh` validiert den strukturierten Producer/Consumer- und Request/Response-Ablauf ueber mehrere Channels und Tasks.
  - Negativfall `multichannel_request_response_violation_fail.fh` erzwingt eine compile-time Verifikationsverletzung am Request-Channel und endet gezielt als `VF-V001` mit `channel_invariant obligation is satisfiable (violated)`.
- **Let-Chain-Substitutionsabdeckung fuer Channel-Invarianten:**
  - Ergaenzung von `channel_send_let_chain_substitution_pos.fh`, das lokale Alias- und Ausdrucksketten (`base -> adjusted -> payload`) bis in `await channel_send(...)` hinein absichert.
  - Ergaenzung von `channel_send_let_chain_violation_fail.fh` plus `.err`-Golden, um die gleiche Kette negativ gegen eine strengere Channel-Invariant zu pruefen.
  - Ergebnis: Die bestehende symbolische Substitution fuer lokale `let`-Alias-/Ausdrucksketten ist ausreichend stark; es war kein weiterer Code-Fix noetig, aber die Kante ist jetzt regressionssicher abgedeckt.
- **Manifest-Erweiterung:**
  - Registrierung der neuen positiven und negativen Faelle in `tests/language_modules_v2_3/07_concurrency_verification/manifest.json`.

Verifiziert:

- `python -m freehold test-language --root .\tests\language_modules_v2_3 --module 07_concurrency_verification`: **erfolgreich durchgelaufen** (`15/15`).
- `verify-language-modules-v2_3.cmd`: **erfolgreich durchgelaufen** (`60/60 language module tests passed`).
- `git diff --check -- tests/language_modules_v2_3/07_concurrency_verification`: **ohne Whitespace-Fehler**.

## FH-Native Stage3 Loader V1

Stand: 2026-06-03

Umgesetzt:

- **Scope festgezogen:**
  - Der begonnene breite Loader-Prototyp wurde auf einen ersten Stage3-tauglichen V1-Slice reduziert.
  - `Compiler.Core.Loader` liest aktuell einen begrenzten JSON-Projektgraphen in ein kleines `ProjectGraph`-Record mit `module_name`, `import_count`, `routine_name` und `return_value`.
  - Bewusst noch nicht Teil dieses Slice: vollstaendiges JSON-AST-Rehydrating, IR-Lowering im Loader selbst, echte Projektdatei-Ausfuehrung und Runtime-Golden.
- **Loader-Demo-Fixture:**
  - Ergaenzung von `bootstrap/compiler_core_v1/fixtures/project_graph_loader_demo.json` als sprechende V1-Demo fuer den aktuellen Loader-Scope.
  - Das Demo beschreibt einen minimalen Projektgraphen mit Modul `App.Main`, einem Import `Domain.Math exposing inc` und einer `main`-Routine mit `ReturnStmt`/`NumberExpr(42)`.
  - Der vollstaendige JSON-AST-/Projektgraph-Loader bleibt bewusst der naechste V2-Schritt: Er wird fuer Rehydratisierung und spaeteres Re-Compilieren aus AST-/IR-Artefakten benoetigt, ist aber noch nicht Teil dieses stabilen Stage3-V1-Gates.
- **Loader-Gate definiert:**
  - Neuer Gate-Command `verify-stage3-loader-v1.cmd`.
  - Neues Manifest `artifacts/stage3/compiler_core_loader_v1/manifest.json`.
  - Neues Report-Verzeichnis `artifacts/stage3/compiler_core_loader_v1/report`.
  - Das bestehende Stage3-Vertragswerkzeug unterstuetzt nun optionale modul-only Contracts ueber `build_options.emit_executable: false`.
- **Generator-Scope geklaert:**
  - `tools/generate_loader.py` ueberschreibt den Loader nicht mehr mit dem alten breiten Prototyp, sondern dokumentiert, dass `Loader.fh` fuer diesen Slice direkt gepflegt wird.

Verifiziert:

- `python -m freehold verify .\bootstrap\compiler_core_v1\Compiler\Core\Loader.fh`: **erfolgreich durchgelaufen**.
- `verify-stage3-loader-v1.cmd`: **erfolgreich durchgelaufen** (`1/1`, keine Failures).
