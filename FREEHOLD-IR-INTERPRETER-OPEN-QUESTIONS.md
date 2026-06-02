# Freehold IR & Interpreter: Open Questions

Diese Datei haelt die offenen Umsetzungsfragen fest, die vor dem Start der FH-IR- und Interpreter-Arbeiten geklaert werden sollten. Ziel ist, die neue IR, den Interpreter, die vorhandenen Compare-IR/FHIR-Gates und die spaetere LLVM-/WhyML-Schiene konsistent auszurichten.

## 1. Kanonische IR vs. Compare-IR

Es gibt bereits Compare-IR/FHIR-artige JSON-Exporter und Gates. Das neue IR-Design beschreibt zusaetzlich eine ausfuehrbare CFG-/Basic-Block-IR mit `alloca`, `load`, `store` und Terminatoren.

Offene Frage:

- Wird die neue FH-IR die ausfuehrbare kanonische IR, waehrend Compare-IR nur Test-, Paritaets- und Coverage-Format bleibt?

Vorentscheidung:

- FH-IR wird die kanonische, ausfuehrbare IR.
- Compare-IR bleibt ein reines Paritaets-, Test- und Coverage-Format.

Konsequenz:

- Die neue IR-Datenstruktur wird in `Compiler.Core.Ir` definiert.
- Bestehende Compare-IR-Generatoren und Gates bleiben unveraendert, damit Paritaetschecks stabil bleiben.

## 2. IR Vor Oder Nach Monomorphisierung

User-defined generics sind im Go-Codegen noch bewusst rejected/deferred. Fuer IR und Interpreter muss entschieden werden, ob generische Formen selbst Teil der IR sind.

Offene Fragen:

- Enthaelt FH-IR generische Routinen und Typen?
- Oder lowern wir nur bereits instanziierte/monomorphisierte Formen?
- Falls Generics in der IR bleiben: Wie werden Typ-Parameter, Bounds und konkrete Instanziierungen im Interpreter modelliert?

Vorentscheidung:

- IR wird nach Monomorphisierung beziehungsweise nach Aufloesung auf konkrete Typen erzeugt.
- Der erste IR-Slice enthaelt keine generischen Typparameter.
- Diese Festlegung gilt fuer den ersten ausfuehrbaren IR-/Interpreter-Slice, nicht fuer alle denkbaren zukuenftigen IR-Schichten.

Konsequenz:

- Der AST-to-IR-Pass setzt voraus, dass Typen bereits konkret aufgeloest wurden.
- Generics-/Monomorphisierung bleibt ein eigener vorgelagerter Slice, bevor generische Programme vollstaendig in FH-IR laufen.

## 3. Wert- Vs. Referenzsemantik Fuer Records Und Arrays

Das IR-Design setzt auf ein Stack-Slot-Muster mit `alloca`, `load` und `store`. Fuer Aggregatwerte ist die Semantik vor dem Interpreter besonders wichtig.

Offene Fragen:

- Sind Record- und Array-Werte im Interpreter kopierte Werte?
- Sind sie mutable Stack-Slots?
- Oder werden sie als referenzierte Aggregate modelliert?
- Wie wirken sich diese Entscheidungen auf Field-Assignment, Array-Index-Update und Alias-Pruefung aus?

Vorentscheidung:

- Primitive Werte wie `Integer`, `Boolean` und `String` haben Wertsemantik.
- Aggregate wie Records, Arrays und Channels werden in der VM-Implementierung als Heap-Referenzen modelliert.
- Diese Implementierungsreferenz ist nicht automatisch user-visible Reference Semantics.

Konsequenz:

- `alloca` erzeugt einen Stack-Slot.
- Fuer Primitive speichert der Slot den Wert direkt.
- Fuer Records, Arrays und Channels speichert der Slot eine Heap-Referenz.
- Field- und Index-Updates manipulieren das referenzierte Objekt im VM-Heap.

## 4. Contracts In IR

`requires`, `ensures`, `invariant`, `variant`, `global` und `depends` sind fuer Verifikation und Laufzeitchecks semantisch relevant.

Offene Fragen:

- Bleiben Contracts als Metadaten an Routinen, Blocks und Instruktionen?
- Werden sie zusaetzlich zu ausfuehrbaren `check`- oder Proof-Obligation-Instruktionen gelowert?
- Soll die IR bereits getrennte Proof-Obligation-Knoten tragen, damit WhyML/SMT aus IR statt AST erzeugt werden kann?

Vorentscheidung:

- Contracts bleiben im ersten Slice deklarative Metadaten an Routinen und gegebenenfalls Blocks.
- Contracts werden nicht in VM-Opcodes uebersetzt.
- Die VM fuehrt nur explizite `check`-Instruktionen aus.

Konsequenz:

- `IrRoutine` erhaelt optionale Contract-Felder fuer statische Analyse- und Debug-Zwecke.
- Proof-Obligation- und WhyML-Erzeugung bleibt zunaechst ausserhalb der ausfuehrenden VM-Schicht.

## 5. Abort, Result Und Return

Die geplante IR kennt `return` und `abort` als Terminatoren. Freehold hat zugleich `Result<T,E>` als expliziten Werttyp.

Offene Fragen:

- Wird `Result<T,E>` rein als normaler Wert modelliert, waehrend `abort` eigener Kontrollfluss bleibt?
- Wie wird ein abortender Call in der VM propagiert?
- Gibt es fuer abortende Calls eigene IR-Instruktionen oder nur Call-Instruktionen mit Effekt-/Contract-Metadaten?
- Wie werden `return`, `abort` und spaetere Handler-Syntax im gleichen Control-Flow-Graph dargestellt?

Vorentscheidung:

- `Result<T,E>` wird als regulaerer Datenwert modelliert.
- `abort` bleibt ein expliziter Terminator im Kontrollfluss.

Konsequenz:

- Eine `abort`-Instruktion beendet den aktuellen Call-Frame sofort und propagiert den Fehler.
- Call-Instruktionen tragen Metadaten darueber, ob und welche Aborts sie propagieren koennen.
- Handler-Syntax bleibt spaeterer Slice; der erste IR-Slice braucht nur Return- und Abort-Terminatoren.

## 6. Quantifier-Ausfuehrung

`for all` und `for some` sind im v2.3/Python-Pfad verifiziert, aber Go-/FH-Native-Porting und WhyML-Integration sind noch relevante Arbeitsflaechen.

Offene Fragen:

- Werden `for all` und `for some` in FH-IR als eigene Expr-Knoten erhalten?
- Oder werden endliche Integer-Ranges direkt zu Schleifen gelowert?
- Wie werden Quantifier fuer SMT/WhyML beibehalten, wenn der Interpreter sie als Schleifen ausfuehrt?
- Wie werden Array-Literal-SMT-Mappings und typed array declarations in der IR repraesentiert?

Vorentscheidung:

- Quantoren bleiben als eigene logische IR-Ausdruecke erhalten.
- Der Interpreter evaluiert sie zur Laufzeit durch lineare Iteration ueber die endliche Range.

Konsequenz:

- Die mathematische Struktur bleibt fuer SMT/WhyML und Debugging sichtbar.
- Der Interpreter bekommt eine einfache, deterministische Quantifier-Auswertung fuer endliche Integer-Ranges.

## 7. Concurrency Im Interpreter

Async, Scope, JoinHandle, Channel, Sender und Receiver sind in der Oberflaeche vorhanden. Vollstaendige scheduler-backed Async-/Channel-Runtime-Ausfuehrung ist aber noch deferred.

Offene Fragen:

- Soll der erste Interpreter async/scope/channel nur deterministisch-sequenziell simulieren?
- Oder braucht die IR schon Scheduler-, Await- und Blocking-Semantik?
- Wie werden `await`, `scope.spawn`, `scope.join`, `channel_send` und `channel_receive` als IR-Instruktionen oder Host-Calls modelliert?
- Wie werden Channel-Invarianten, Task-Preconditions und Scope-Path-Conditions im Interpreter sichtbar gemacht?

Vorentscheidung:

- Der erste Interpreter nutzt kooperatives, deterministisch-sequenzielles Scheduling ueber eine Microtask-/Event-Loop.
- Ein vollstaendiger multithreaded Scheduler bleibt ausserhalb des ersten Slice.
- Diese Event-Loop ist Test-/VM-Semantik fuer den ersten Interpreter, nicht die endgueltige produktive Runtime-Semantik.

Konsequenz:

- `scope.spawn` reiht einen Task in die VM-Queue ein.
- Blockierende Channel-Operationen suspendieren den aktuellen Task.
- Der Scheduler wechselt zum naechsten bereiten Task.
- Diese Semantik reicht fuer reproduzierbare Tests von Channels, Scopes und Await-Verhalten.

## 8. Builtins Und Host-Calls

Die VM soll Standardbibliothek und Builtins integrieren, unter anderem `Std.IO`, `String`, `Math`, `Big`, `Json` und Channel-/Scope-Runtime.

Offene Fragen:

- Sind Builtins native VM-Opcodes?
- Sind sie Host-Functions?
- Oder werden sie als normale importierte Module mit speziell gebundenen Implementierungen behandelt?
- Wie werden Seiteneffekte von `Std.IO`, Channel-Operationen und spaeteren Netzwerk-APIs im IR-Effektmodell abgebildet?

Vorentscheidung:

- Builtins werden als standardisierte Host-Calls modelliert, nicht als eigene VM-spezifische Opcodes.

Konsequenz:

- Der VM-Befehlssatz bleibt klein.
- Ein generischer Host-Call wie `call_host "Std.IO.log"` ruft registrierte Host-Funktionen der jeweiligen Plattform auf.
- Neue Builtins koennen modular registriert werden, ohne den Opcode-Satz zu erweitern.

## 9. WhyML Aus AST Oder IR

WhyML wird aktuell parallel im Python-, Go- und FH-Native-Pfad stabilisiert. Langfristig sollte klar sein, ob WhyML aus dem AST/Semantikmodell oder aus FH-IR entsteht.

Offene Fragen:

- Soll WhyML langfristig aus AST/Semantikmodell erzeugt werden?
- Oder soll FH-IR die zentrale Quelle fuer WhyML werden?
- Falls WhyML aus FH-IR erzeugt wird: Welche Contract-, Type- und Proof-Metadaten muss die IR zwingend tragen?

Vorentscheidung:

- WhyML-Codegenerierung erfolgt weiterhin aus AST und Resolution-Context, nicht aus FH-IR.
- Diese Entscheidung gilt fuer den ersten Slice und schliesst spaetere IR-basierte Audit- oder Aequivalenz-Gates nicht aus.

Konsequenz:

- FH-IR muss keine komplexen WhyML-Rekonstruktionsmetadaten tragen.
- WhyML behaelt Zugriff auf die reichere semantische Struktur von AST, Namespaces und Typauflösung.
- Die IR bleibt auf Ausfuehrung, Debugging und spaeteres LLVM-Lowering fokussiert.

## 10. Decompiler-Scope Fuer Den Ersten Slice

Das IR-Design enthaelt IR-to-Source, LLVM-to-IR und Debug-Symbol-Rueckweg. Fuer den ersten Implementierungsschnitt sollte der Scope enger gefasst werden.

Offene Fragen:

- Soll der erste IR/Interpreter-Slice nur Pretty-Print aus FH-IR enthalten?
- Bleiben LLVM-to-FH-IR und native Rueckdekompilierung bis nach dem Interpreter geparkt?
- Welche Metadaten muessen trotzdem schon frueh erhalten bleiben, damit spaetere Decompilation nicht verbaut wird?

Vorentscheidung:

- Der erste Slice enthaelt nur einen einfachen IR-to-Text Pretty-Printer.
- Vollstaendige IR-to-Source-, LLVM-to-FH-IR- und native Rueckdekompilierung bleiben spaetere Slices.

Konsequenz:

- Ein `ir_to_string`-Pfad reicht fuer Debugging der IR-Erzeugung.
- Debug-/Source-Metadaten sollten frueh konservativ erhalten werden, ohne bereits einen vollstaendigen Decompiler zu bauen.

## Wesentliche Hinweise Gegen Architektur-Verbauung

Die folgenden Vorentscheidungen sind fuer den ersten IR-/Interpreter-Slice sinnvoll und pragmatisch. Sie duerfen aber nicht so hart gelesen werden, dass spaetere Compiler- oder Runtime-Schichten verbaut werden.

### IR Nach Monomorphisierung

IR nach Monomorphisierung ist fuer den ersten Slice praktisch gut, weil die ausfuehrbare IR keine generischen Typparameter tragen muss. Falls Generics spaeter selbst analysiert, optimiert oder als generische Artefakte ausgegeben werden sollen, kann vor der konkreten FH-IR eine hoehere generische IR-Schicht oder Pre-IR eingefuehrt werden.

Leitplanke:

- Monomorphisierung vor FH-IR ist eine Entscheidung fuer den ersten ausfuehrbaren IR-Slice.
- Sie ist keine Absage an eine spaetere generische Zwischenrepraesentation.

### Heap-Referenzen Fuer Records Und Arrays

Records und Arrays als Heap-Referenzen zu modellieren ist fuer VM, Mutation und Interpreter-Ergonomie gut. Es darf aber nicht automatisch bedeuten, dass Freehold fuer Nutzer sichtbare Reference Semantics bekommt.

Leitplanke:

- VM-Implementierungsreferenz ist nicht automatisch Sprachsemantik.
- Die Sprache muss separat festlegen, wann Records und Arrays kopiert, geteilt oder mutiert werden duerfen.
- Alias-Verhalten darf fuer Nutzer nicht ueberraschend aus der VM-Implementierung heraus entstehen.

### WhyML Weiter Aus AST

WhyML weiter aus AST und Resolution-Context zu erzeugen ist kurzfristig richtig, weil dort die reichere semantische Struktur vorhanden ist. Langfristig darf daraus keine doppelte, divergierende Semantik entstehen.

Leitplanke:

- AST-Verifikation und IR-Lowering brauchen spaeter ein Aequivalenz-Gate.
- Dieses Gate muss beweisen oder zumindest regressionsfest pruefen, dass verifizierte AST-Semantik und ausgefuehrte IR-Semantik zusammenpassen.

### Deterministische Event-Loop

Eine kooperative, deterministisch-sequenzielle Event-Loop ist fuer den ersten Interpreter ideal, weil Tests reproduzierbar bleiben. Sie ist aber Test-/VM-Semantik fuer den ersten Slice, nicht die endgueltige produktive Runtime-Semantik.

Leitplanke:

- Scheduler-backed Runtime, Threadpool, Work-Stealing, Cancellation und Deadlines bleiben spaetere Runtime-Slices.
- Die sichtbaren Sprachgarantien von `async`, `await`, `scope` und `Channel<T>` muessen getrennt von der ersten VM-Implementierung beschrieben werden.

### Hauptrisiken

Am ehesten koennten zwei Entscheidungen spaetere Wege verbauen, wenn sie zu hart festgeschrieben werden:

1. Monomorphisierung vor IR.
2. Heap-Referenzmodell fuer Aggregate.

Beide Risiken sind beherrschbar, solange die IR-Typen sauber bleiben und die Festlegungen ausdruecklich als erster Slice dokumentiert sind.

## Getroffene Entscheidungen (Status: Finalisiert & Bestätigt)

Diese Architekturentscheidungen wurden am 02. Juni 2026 verbindlich festgesetzt und bilden das Fundament des ersten IR-/Interpreter-Slice:

1. **FH-IR wird kanonische ausführbare IR**; Compare-IR bleibt ein Paritäts-/Testformat.
2. **Generics & Monomorphisierung**: Das IR-Lowering erfolgt nach der Typauflösung; der erste IR-Slice enthaelt keine generischen Typparameter im Ausführungspfad (Monomorphisierung). `IrType` ist jedoch strukturell vorbereitet.
3. **Wert- vs. Referenzsemantik**: Die IR selbst ist speicher-neutral (abstrakte Slots). Der Interpreter (VM) nutzt Heap-Referenzsemantik für Records/Arrays/Channels, während native Backends (LLVM) Stack/Value-Semantik abbilden können.
4. **Contracts**: Bleiben deklarative Metadaten in der IR für statische Analyseschritte und werden nicht in VM-Opcodes übersetzt. Der Interpreter evaluiert nur explizite `check`-Instruktionen.
5. **Abort & Result**: `Result<T,E>` ist ein normaler Record-Wert in der IR; `abort` ist ein expliziter Terminator für die Ausführung.
6. **Quantoren**: Bleiben als logische IR-Ausdrücke erhalten und werden im Interpreter durch lineare Iteration ausgewertet.
7. **Concurrency**: Der erste Interpreter simuliert Concurrency kooperativ, deterministisch und sequenziell.
8. **Builtins**: Werden als Host-Calls (`call_host`) an Go/Python angebunden.
9. **WhyML**: Entsteht weiterhin direkt aus dem AST, nicht aus der gelösten IR.
10. **Decompiler**: Der erste Scope ist ein einfacher IR Pretty-Printer (`ir_to_string`).

---

* [x] **IR-Datenstruktur definiert**: Die Datei `bootstrap/compiler_core_v1/Compiler/Core/Ir.fh` wurde angelegt und enthält alle benötigten IR-Datenstrukturen (`IrType`, `IrInstruction`, `IrBasicBlock`, `IrRoutine`).
* [x] **Stage-3 Compiler-Core Integration**: Das neue Modul wurde erfolgreich in `Main.fh` eingebunden und die gesamte Pipeline kompiliert und läuft grün (43/43 Tests passed).
* [x] **AST-to-IR Lowering-Pass implementiert**: Die erste Version des Lowering-Passes für Zuweisungen, grundlegende Ausdrücke und Routinen in `Lowering.fh` ist fertiggestellt und verifiziert.
* [x] **Nächster Schritt (Erweiterung des Lowerings)**: Einbau von fortgeschrittenem Kontrollfluss (`if/else`, `while`-Schleifen) und Funktions-/Hostaufrufen (`BRANCH_COND`, `JUMP`, `CALL_HOST`) in `Lowering.fh`.
* [x] **VM-Infrastruktur & Interpreter**: Aufbau des VM-Interpreter-Kerns (`Vm.fh`) mit Frames, Registern, Heap und der zentralen Befehlsschleife zur Ausführung der IR.
* [x] **Host-Call-Anbindung erweitert**: Der VM-Interpreter (`Vm.fh`) verfügt nun über einen vollständig integrierten Host-Call-Dispatcher mit nativer Anbindung für alle standardmäßigen mathematischen Funktionen (`Math.*`), BigInt/BigFloat-Arithmetik (`Big.*`) sowie String-Operationen (`String.*`). Die Auswertung erfolgt typsicher über automatische Konvertierungen im Interpreter.
