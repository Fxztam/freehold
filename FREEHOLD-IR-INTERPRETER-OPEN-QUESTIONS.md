# Freehold IR & Interpreter: Open Questions

Diese Datei haelt die offenen Umsetzungsfragen fest, die vor dem Start der FH-IR- und Interpreter-Arbeiten geklaert werden sollten. Ziel ist, die neue IR, den Interpreter, die vorhandenen Compare-IR/FHIR-Gates und die spaetere LLVM-/WhyML-Schiene konsistent auszurichten.

## 1. Kanonische IR vs. Compare-IR

Es gibt bereits Compare-IR/FHIR-artige JSON-Exporter und Gates. Das neue IR-Design beschreibt zusaetzlich eine ausfuehrbare CFG-/Basic-Block-IR mit `alloca`, `load`, `store` und Terminatoren.

Offene Frage:

- Wird die neue FH-IR die ausfuehrbare kanonische IR, waehrend Compare-IR nur Test-, Paritaets- und Coverage-Format bleibt?

## 2. IR Vor Oder Nach Monomorphisierung

User-defined generics sind im Go-Codegen noch bewusst rejected/deferred. Fuer IR und Interpreter muss entschieden werden, ob generische Formen selbst Teil der IR sind.

Offene Fragen:

- Enthaelt FH-IR generische Routinen und Typen?
- Oder lowern wir nur bereits instanziierte/monomorphisierte Formen?
- Falls Generics in der IR bleiben: Wie werden Typ-Parameter, Bounds und konkrete Instanziierungen im Interpreter modelliert?

## 3. Wert- Vs. Referenzsemantik Fuer Records Und Arrays

Das IR-Design setzt auf ein Stack-Slot-Muster mit `alloca`, `load` und `store`. Fuer Aggregatwerte ist die Semantik vor dem Interpreter besonders wichtig.

Offene Fragen:

- Sind Record- und Array-Werte im Interpreter kopierte Werte?
- Sind sie mutable Stack-Slots?
- Oder werden sie als referenzierte Aggregate modelliert?
- Wie wirken sich diese Entscheidungen auf Field-Assignment, Array-Index-Update und Alias-Pruefung aus?

## 4. Contracts In IR

`requires`, `ensures`, `invariant`, `variant`, `global` und `depends` sind fuer Verifikation und Laufzeitchecks semantisch relevant.

Offene Fragen:

- Bleiben Contracts als Metadaten an Routinen, Blocks und Instruktionen?
- Werden sie zusaetzlich zu ausfuehrbaren `check`- oder Proof-Obligation-Instruktionen gelowert?
- Soll die IR bereits getrennte Proof-Obligation-Knoten tragen, damit WhyML/SMT aus IR statt AST erzeugt werden kann?

## 5. Abort, Result Und Return

Die geplante IR kennt `return` und `abort` als Terminatoren. Freehold hat zugleich `Result<T,E>` als expliziten Werttyp.

Offene Fragen:

- Wird `Result<T,E>` rein als normaler Wert modelliert, waehrend `abort` eigener Kontrollfluss bleibt?
- Wie wird ein abortender Call in der VM propagiert?
- Gibt es fuer abortende Calls eigene IR-Instruktionen oder nur Call-Instruktionen mit Effekt-/Contract-Metadaten?
- Wie werden `return`, `abort` und spaetere Handler-Syntax im gleichen Control-Flow-Graph dargestellt?

## 6. Quantifier-Ausfuehrung

`for all` und `for some` sind im v2.3/Python-Pfad verifiziert, aber Go-/FH-Native-Porting und WhyML-Integration sind noch relevante Arbeitsflaechen.

Offene Fragen:

- Werden `for all` und `for some` in FH-IR als eigene Expr-Knoten erhalten?
- Oder werden endliche Integer-Ranges direkt zu Schleifen gelowert?
- Wie werden Quantifier fuer SMT/WhyML beibehalten, wenn der Interpreter sie als Schleifen ausfuehrt?
- Wie werden Array-Literal-SMT-Mappings und typed array declarations in der IR repraesentiert?

## 7. Concurrency Im Interpreter

Async, Scope, JoinHandle, Channel, Sender und Receiver sind in der Oberflaeche vorhanden. Vollstaendige scheduler-backed Async-/Channel-Runtime-Ausfuehrung ist aber noch deferred.

Offene Fragen:

- Soll der erste Interpreter async/scope/channel nur deterministisch-sequenziell simulieren?
- Oder braucht die IR schon Scheduler-, Await- und Blocking-Semantik?
- Wie werden `await`, `scope.spawn`, `scope.join`, `channel_send` und `channel_receive` als IR-Instruktionen oder Host-Calls modelliert?
- Wie werden Channel-Invarianten, Task-Preconditions und Scope-Path-Conditions im Interpreter sichtbar gemacht?

## 8. Builtins Und Host-Calls

Die VM soll Standardbibliothek und Builtins integrieren, unter anderem `Std.IO`, `String`, `Math`, `Big`, `Json` und Channel-/Scope-Runtime.

Offene Fragen:

- Sind Builtins native VM-Opcodes?
- Sind sie Host-Functions?
- Oder werden sie als normale importierte Module mit speziell gebundenen Implementierungen behandelt?
- Wie werden Seiteneffekte von `Std.IO`, Channel-Operationen und spaeteren Netzwerk-APIs im IR-Effektmodell abgebildet?

## 9. WhyML Aus AST Oder IR

WhyML wird aktuell parallel im Python-, Go- und FH-Native-Pfad stabilisiert. Langfristig sollte klar sein, ob WhyML aus dem AST/Semantikmodell oder aus FH-IR entsteht.

Offene Fragen:

- Soll WhyML langfristig aus AST/Semantikmodell erzeugt werden?
- Oder soll FH-IR die zentrale Quelle fuer WhyML werden?
- Falls WhyML aus FH-IR erzeugt wird: Welche Contract-, Type- und Proof-Metadaten muss die IR zwingend tragen?

## 10. Decompiler-Scope Fuer Den Ersten Slice

Das IR-Design enthaelt IR-to-Source, LLVM-to-IR und Debug-Symbol-Rueckweg. Fuer den ersten Implementierungsschnitt sollte der Scope enger gefasst werden.

Offene Fragen:

- Soll der erste IR/Interpreter-Slice nur Pretty-Print aus FH-IR enthalten?
- Bleiben LLVM-to-FH-IR und native Rueckdekompilierung bis nach dem Interpreter geparkt?
- Welche Metadaten muessen trotzdem schon frueh erhalten bleiben, damit spaetere Decompilation nicht verbaut wird?

## Empfohlene Vorentscheidungen

Vor Implementierungsbeginn sollten mindestens diese drei Entscheidungen getroffen werden:

1. FH-IR wird kanonische ausfuehrbare IR; Compare-IR bleibt Paritaets-/Testformat.
2. Der erste IR-Slice arbeitet mit nicht-generischen oder bereits instanziierten Formen; volle Generics-/Monomorphisierung bleibt ein eigener Slice.
3. Der erste Interpreter simuliert Concurrency deterministisch-sequenziell; scheduler-backed Runtime bleibt nachgelagert.
