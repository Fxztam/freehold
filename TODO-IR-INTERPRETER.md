# TODO: IR Interpreter & VM

Stand: 2026-06-02

Diese Roadmap und Anforderungsliste beschreibt die nächsten Arbeitsschritte für die VM-Infrastruktur sowie den Interpreter und dokumentiert die Vorkehrungen für den Rückübersetzungsprozess (Decompiler).

## 1. Decompiler-to-Source Kompatibilität

Um eine spätere Rückübersetzung (Decompilation) von IR zu Freehold-Quellcode sauber zu ermöglichen, wurden beim IR-Aufbau und im Lowering-Pass folgende Entwurfsentscheidungen getroffen und müssen beibehalten werden:

- **Source-Verknüpfung (`SourceSpan`):** Jede `IrInstruction` trägt die ursprünglichen Zeilen- und Spaltenkoordinaten im Feld `span`. Jedes Lowering-Statement muss das `span`-Feld des AST an die generierten Instruktionen vererben.
- **Erhalt von Variablennamen:** Bei `LET`- und `ASSIGN`-Statements wird für `ALLOCA` und `STORE` der originale Variablenname (`stmt.var_name`) als Speicherplatz-Identifikator verwendet, anstatt anonyme Stack-Offsets zu erzeugen.
- **Strukturierte Block-Labels:** Basic Blocks müssen sprechende Labels generieren, die den syntaktischen Kontrollfluss widerspiegeln (z. B. `block_then_X`, `block_else_X`, `loop_cond_X`), um die Rekonstruktion geschachtelter `if`- und `while`-Strukturen zu vereinfachen.

---

## 2. Nächste Schritte: VM & Interpreter

Folgende Module und Komponenten müssen aufgebaut werden, um die emittierte IR ausführbar zu machen:

### Phase 1: VM-Infrastruktur (`Compiler/Core/Vm.fh`) [ERLEDIGT]
- [x] **Definition von `ActivationFrame`:**
  - Stack-Bereich für lokale Register und Argumente.
  - Speicherung des Programm-Counters / Instruction Pointers (IP).
  - Speicherung des Labels des aktuell ausgeführten Basic Blocks.
- [x] **VM Heap-Modellierung:**
  - Referenzierungsmodell für Records, Arrays und Channels.
  - Zuweisung von Heap-Adressen bei Aggregat-Erstellung und Mutation über GetElementPtr/Stores.
- [x] **Ausführungsschleife (Execution Loop):**
  - Eine zentrale Routine `execute(routine: IrRoutine, arguments: Array<String, 10>)`.
  - Dispatching-Logik für alle `IrInstruction.kind` Typen (z. B. Berechnen von `BINARY_OP`, Ausführen von `LOAD`/`STORE`).
  - Behandlung der Block-Terminatoren (`JUMP`, `BRANCH_COND`, `RETURN`, `ABORT`).

### Phase 2: Host-Calls & Builtins [ERLEDIGT]
- [x] **Host-Call Anbindung (`CALL_HOST`):**
  - Übersetzung und Weiterleitung von Aufrufen wie `Std.IO.println`/`Std.IO.print` an die native Laufzeit (Go/Python).
- [x] **Erweiterung von Host-Call Anbindung:**
  - Schnittstelle für die Injektion externer Hilfsfunktionen und `Std.IO.logf` Support.

### Phase 3: Kooperative Concurrency [ERLEDIGT]
- [x] **Microtask Scheduler:**
  - Deterministisch-sequenzielle Event-Loop für asynchrone Tasks.
  - Verwaltung einer Task-Queue für über `spawn` erzeugte Routinen.
  - Suspendierung von Tasks bei blockierenden Channel-Operationen (`send`/`receive`) und Fortsetzung durch den Scheduler.

### Phase 4: Zukünftige VM- & Interpreter-Erweiterungen (V2/V3)
- [ ] **Dynamischer Call-Stack für verschachtelte Funktionsaufrufe:**
  - Implementierung eines frame-basierten Stacks innerhalb jedes `VmTask`.
  - Unterstützung für die Instruktion `CALL` (nicht-Host-Routinen) durch Pushing eines neuen `ActivationFrame`.
  - Abgleich des Registersatzes und Wiederherstellung des aufrufenden Kontexts bei `RETURN`.
- [ ] **Runtime-Assertions & dynamische Sicherheitsprüfungen:**
  - Einbau von dynamischen Wertebereichsprüfungen für Subtypen und Array-Zugehörigkeiten direkt in der Ausführungsschleife.
  - Auslösen kontrollierter VM-Exceptions bei Index-Grenzen-Verletzungen.
- [ ] **Dynamischer IR-Loader für Projektdateien:**
  - Entwicklung einer Lade-Routine, die das emittierte `.fhir` JSON-Projekt-Graph und `manifest.json` einliest und direkt auf der VM startet.

