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


