# Proposal: Task-basierte Verifikations-Einheiten in Freehold

Vorgeschlagen von: Entwickler-Team / User
Datum: 17. Juni 2026
Status: Entwurf (Roadmap V2/V3)

---

## 1. Motivation & Die 3 Ebenen der Concurrency

Freehold zeichnet sich durch beweisbar sicheren Quellcode aus. Bisher erfolgt die Concurrency-Abdeckung über syntaktische Konstrukte wie `scope ... spawn ... join ... result ... end scope` oder direkte `await`/Channels.

Um jedoch asynchrone Berechnungen und Nachrichtenströme auf Kanälen **vertraglich vollständig abzusichern (vertraglich prüfbare Einheiten)**, wird vorgeschlagen, das neue Schlüsselwort `task` einzuführen.

* **Go** startet Co-Routinen leichtgewichtig (`go func()`).
* **Freehold** startet Co-Routinen ebenfalls leichtgewichtig, **aber mathematisch beweisbar sicher**!

Hierzu stützt sich Freehold auf **drei funktionale Ebenen**:
1. **`spawn` für den Start:** `let task1 := spawn Calculate(100)` startet einen Task asynchron.
2. **`await` für kontrolliertes Warten:** `let result := await task1` blockiert, bis das Ergebnis vorliegt.
3. **`channel` für sichere Kommunikation:** `let ch := Channel()` vermittelt typisierten Nachrichtenaustausch.

---

## 2. Minimaler Freehold-Entwurf

Die folgende Syntax zeigt eine typische, minimale Producer-Consumer-Konstruktion unter Verwendung von `task` und typsicheren Kanälen:

```freehold
task Producer(out: Channel<Integer>)
is
    send out, 42
end Producer

task Consumer(input: Channel<Integer>)
is
    let value: Integer = receive input
    check value > 0
end Consumer

async procedure main()
is
    let numbers: Channel<Integer> = Channel<Integer>()

    let p: JoinHandle<Void> = spawn Producer(numbers)
    let c: JoinHandle<Void> = spawn Consumer(numbers)

    await p
    await c
end main
```

---

## 3. Formale Verifikationsregeln & Sicherheitsgarantien

Das Besondere an diesem System ist, dass ein asynchroner Aufruf:
```freehold
let t := spawn Worker(x)
```
**dieselbe formale Prüfung** im Verifier auslösen muss wie ein synchroner Prozedur- oder Funktionsaufruf (`call Worker(x)`), erweitert um spezifische Concurrency-Garantien.

Der Freehold-Verifier prüft konkret folgende **6 statischen Regeln**:

1. **Vollständiges Awaiting/Detaching:** Jede gestartete Task muss explizit per `await` abgeholt oder explizit als `detached` markiert werden, um Ressourcenlecks zu vermeiden.
2. **Keine unkontrollierte Datenweitergabe (No Shared Mutable State):**
   Veränderlicher State (Mutable State) darf nicht unkontrolliert zwischen parallel laufenden Tasks geteilt werden. Bei Verstößen bricht der Compiler mit einem klaren Fehler ab:
   ```
   Compile error: shared mutable state passed to multiple spawned tasks
   hint: use channel, ownership transfer, immutable value, or protected state
   ```
3. **Typisierte Kanäle:** Kanäle müssen strikt typisiert sein (`Channel<T>`).
4. **Kanal-Richtungskompatibilität (Directional Safety):** Die Operationen `send` und `receive` müssen mathematisch und statisch zur erlaubten Flussrichtung des Kanaltyps passen.
5. **Preconditions an der Spawn-Stelle:** Die Vorbedingungen (`requires`) einer Task gelten und werden zum Zeitpunkt des `spawn`-Aufrufs bewiesen.
6. **Postconditions nach dem Await:** Die Nachbedingungen (`ensures`) einer Task sind im übergeordneten Kontrollfluss unmittelbar nach dem `await`-Statement gültig und beweisbar.

Zusätzlich gelten weiterhin die bekannten Analysen:
* **Kanal-Invarianten (Channel Invariants):**
  Wenn ein Kanal deklariert wird mit `with invariant value > 0`, beweist der Verifier an jedem `send out, X` im `task Producer`, dass `X > 0` ist.
* **Terminierung und Liveness:**
  Task-interne Schleifen werden mittels `invariant` und `variant` auf Terminierung bewiesen, um Verstopfungen und Deadlocks auszuschließen.
* **Isoliertheit (State Isolation):**
  Ein `task` darf keinen ungeschützten globalen veränderlichen Zustand beziehungsweise Shared State manipulieren.

---

## 4. Fortgeschrittene physische Ressourcensteuerung & Parallelität

Um die Hardware-Leistung moderner Multi-Core-Prozessoren optimal auszunutzen, bietet das flache Concurrency-Modell ergonomische Modifikatoren ohne klobige Block-Schachtelungen.

---

## 4. Fortgeschrittene physische Ressourcensteuerung & Parallelität (Das Duale Kern-Modell)

Um maximale Systemsicherheit, Vorhersagbarkeit und Skalierbarkeit zu gewährleisten, unterscheidet Freehold strikt zwischen logischer Nebenläufigkeit und physischer Parallelität. 

### 4.1 Logische Nebenläufigkeit (Der Standard: 1-Core Execution)
Der Standardaufruf `spawn` startet eine kooperative, leichtgewichtige Co-Routine (Green Thread):
```freehold
let t1 := spawn Calculate(100) with (priority: 5, pool: "hardware_io", name: "sensor_producer")
```
* **Verhalten:** Ohne einen umschließenden `parallel`-Block laufen alle gestarteten Tasks strikt sequentiell und kooperativ auf **exakt einem einzigen physischen CPU-Kern** (Single-Threaded, kooperatives Multitasking). Die Tasks wechseln sich beim Blockieren (z. B. am Kanal) verzögerungsfrei ab.
* **Vorteil:** Nahezu kein Overhead, absolut deterministische Abläufe und garantierte Freiheit von physischen Race-Conditions auf Hardware-Ebene.

### 4.2 Physische Parallelität (Umschaltung auf N-Cores mit `parallel`)
Erst durch das explizite Schachteln in einer `parallel`-Region wird echte physische Mehrkern-Parallelität freigeschaltet:
```freehold
parallel (limit = 2) do
    let t1 := spawn ProcessBigData(1) with (priority: 5, name: "big_data_1")
    let t2 := spawn ProcessBigData(2) with (priority: 3, name: "big_data_2")
    let t3 := spawn ProcessBigData(3) with (priority: 1, name: "big_data_3")
    await t1, t2, t3
end parallel
```
* **Verhalten:** Dieser Block signalisiert dem Go-M:N-Scheduler, dass die darin enthaltenen Tasks physisch parallel über separate Betriebssystem-Threads auf echte, physikalische CPU-Kerne (bis zum deklarierten `limit`) verteilt werden dürfen.
* **Vorteil:** Explizites Opt-In für Multi-Core-Hardware-Parallelität. Der Verifier muss komplexe Anti-Aliasing- und Race-Proof-Obligations nur für die Blöcke innerhalb einer `parallel`-Region analysieren, was die formale Verifikation extrem beschleunigt.

### 4.3 Paralleles Rendezvous (`await all`)
Statt sequenziellem Blockieren auf einzelne Handles wird dem Scheduler mitgeteilt, dass die gesamte Taskgruppe parallel zusammengeführt werden soll (analog zu `sync.WaitGroup`):
```freehold
await all [t1, t2, t3]
```
Auswertung von Rückgabewerten in monomorphe Arrays:
```freehold
let results: Array<Integer, 3> = await all [t1, t2, t3]
```
* **Go Mapping:** Der Codegenerator emittiert ein homogenes Daten-Array, welches parallel von Go-Worker-Threads gefüllt und erst freigegeben wird, nachdem die `sync.WaitGroup` der Runtime `.Wait()` meldet.

---

## 5. Physisches Core-Mapping & M:N Thread-Pool

Der Go-Codegenerator (`go_codegen.py`) generiert eine maßgeschneiderte, gehärtete M:N-Laufzeitumgebung:
1. **CPU-Alignment:** Die Runtime fragt automatisch die echten Prozessorkerne ab (`runtime.NumCPU()`) und instanziiert exakt passende OS-Worker-Threads.
2. **Work-Stealing-Scheduler:** Jeder Worker-Thread verwaltet eine eigene Scheduling-Queue. Befindet sich ein physischer Prozessorkern im Leerlauf (Idle Core), greift er über ein hoch-effizientes Work-Stealing-Verfahren auf das hintere Ende der Warteschlangen benachbarter Kerne zu, um Arbeit aktiv aufzuteilen und Hardware-Verstopfungen zu vermeiden.
3. **Sicherheit:** Weil der Verifier durch das statische Anti-Aliasing beweist, dass kein veränderlicher geteilter Speicherbereich an die Spawns übergeben wird, ist diese ungedrosselte Multi-Core-Auslastung auf Betriebssystem-Ebene mathematisch absolut race-frei.

---

## 6. Integration in den Compiler

### 6.1 Parser / AST
Hinzufügen von `task_decl`, `spawn` mit optionalem Attribut-Tuple sowie `parallel`-Blocks in `freehold.lark`:
```lark
task_decl: "task" NAME "(" [param_list] ")" "is" stmt* "end" NAME

?spawn_expr: "spawn" call_expr ["with" "(" spawn_attribute_list ")"]
spawn_attribute_list: spawn_attribute ("," spawn_attribute)*
spawn_attribute: NAME ":" expression

parallel_stmt: "parallel" "(" "limit" "=" expression ")" "do" stmt* "end" "parallel"
await_all_stmt: "await" "all" "[" expression_list "]"
```,oldString:

### 6.2 Go-Codegen Lowering
Auf Go-Ebene lässt sich ein `task` direkt auf ein leichtgewichtiges Goroutinen-Handling abbilden:
```go
func Producer(out chan int64) {
    out <- 42
}
```
Ein `spawn Producer(numbers)` generiert ein entsprechendes `FreeholdJoinHandle` und startet die Funktion asynchron über die Threading-Pools der Runtime.
