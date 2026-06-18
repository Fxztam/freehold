# TASK-VERIFICATION-PROPOSAL

## 1. Das Drei-Ebenen-Concurrency-Modell für Freehold

Freehold kombiniert die Leichtigkeit von Gos Concurrency-Modell mit der strikten, mathematischen Korrektheitsgarantie von SPARK Ada. Dieses Dokument beschreibt die offizielle Spezifikation für erstklassige Tasks, asynchrones Spawning, Kommunikationskanäle und physische Hardware-Steuerung (Priorisierung und Drosselung) für die Phasen V2 und V3.

Das Modell stützt sich auf drei fundamentale Sprachebenen:

1. **`spawn` für den asynchronen Start:** 
   `let t1 := spawn Calculate(100)` startet einen Task entkoppelt auf einem freien Kern.
2. **`await` für das blockierende Warten:** 
   `let result := await t1` blockiert den synchronen Strom, bis das Ergebnis der Berechnung bereitsteht.
3. **`channel` für sichere Kommunikation:** 
   `let ch := Channel<Integer>()` ermöglicht den typsicheren Nachrichtenaustausch über asynchrone Grenzen hinweg.

---

## 2. Minimaler Freehold-Entwurf (Producer-Consumer-Muster)

Die Definition von asynchronen Einheiten geschieht über das neue Schlüsselwort `task`. Ein Task deklariert präzise seine Daten- und Zustandsschnittstellen, um Daten-Races statisch auszuschließen.

```freehold
-- Definition der vertraglich geschützten Arbeitseinheiten (Tasks)
task Producer(out: Channel<Integer>)
is
    send out, 42
end Producer

task Consumer(input: Channel<Integer>)
is
    let value: Integer = receive input
    check value > 0
end Consumer

-- Hauptprogramm zur Steuerung und physischen Verteilung
async procedure main()
is
    -- Erstellt den typsicheren Kommunikationskanal für die Kerne
    let numbers: Channel<Integer> = Channel<Integer>()

    -- SPAWN verteilt diese Tasks direkt auf separate Go-Routines / Cores
    let p: JoinHandle<Void> = spawn Producer(numbers)
    let c: JoinHandle<Void> = spawn Consumer(numbers)

    -- AWAIT blockiert den Hauptthread, bis die Kerne ihre Arbeit beendet haben
    await p
    await c
end main
```

---

## 3. Formale Verifikationsregeln & Sicherheitsgarantien (Z3 SMT-Checking)

Asynchrone Aufrufe über `spawn` lösen im Verifier (`verifier.py` & Z3) dieselbe mathematische Präzision aus wie synchrone Aufrufe, erweitert um spezifische Concurrency-Absicherungen.

### Die 6 statischen Verifikationsregeln:

1. **Vollständiges Awaiting/Detaching:**  
   Jedes gestartete `JoinHandle` muss im Kontrollfluss explizit per `await` abgeholt oder als `detached` markiert werden, um unkontrollierte Zombie-Prozesse und Ressourcenlecks auszuschließen.
2. **Keine unkontrollierte Datenweitergabe (No Shared Mutable State):**  
   Veränderlicher Zustand (Mutable State) darf nicht parallel an mehrere Tasks übergeben oder im Hauptstrom nach dem `spawn` weitergenutzt werden. Bei Verletzung bricht der Compiler sofort mit folgendem Fehler ab:
   ```text
   Compile error: shared mutable state passed to multiple spawned tasks
   hint: use channel, ownership transfer, immutable value, or protected state
   ```
3. **Strikte Kanaltypisierung:**  
   Kanäle müssen explizit typisiert sein (`Channel<T>`), um Speicher- und Spezifikationsinkonsistenzen an asynchronen Datengrenzen unmöglich zu machen.
4. **Richtungskonformität (Directional Safety):**  
   Die Operatoren `send` und `receive` werden statisch gegen die deklarierte Flussrichtung geprüfter Zugriffsknoten (`Sender<T>` und `Receiver<T>`) validiert.
5. **Preconditions an der Spawn-Grenze:**  
   Wird eine Task mit `spawn Worker(x)` gestartet, beweist der SMT-Solver die Vorbedingungen (`requires`) der Funktion exakt an der **Spawn-Stelle** im Kontext des Aufrufers.
6. **Postconditions nach dem Await:**  
   Sobald der Aufrufer den Wert per `await t1` einsammelt, fließen die Nachbedingungen (`ensures`) der Task unmittelbar in die aktiven Pfadbedingungen des synchronen Kontrollflusses ein.

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
Erst durch das explizite Schachteln in einer `parallel`-Region wird echte physische Mehrkern-Parallelität freigeschaltet. Um die Lesbarkeit und Strukturierung in großen Softwaresystemen zu perfektionieren, kann der `parallel`-Block mit einem optionalen Identifikationsnamen versehen werden. Der Compiler erzwingt dann zwingend, dass am Blockende exakt dieser Name deklariert wird (Named block parity):

```freehold
parallel core_allocation_block (limit = 2) do
    let t1 := spawn ProcessBigData(1) with (priority: 5, name: "big_data_1")
    let t2 := spawn ProcessBigData(2) with (priority: 3, name: "big_data_2")
    let t3 := spawn ProcessBigData(3) with (priority: 1, name: "big_data_3")
    await t1, t2, t3
end parallel core_allocation_block
```
* **Verhalten:** Dieser Block signalisiert dem Go-M:N-Scheduler, dass die darin enthaltenen Tasks physisch parallel über separate Betriebssystem-Threads auf echte, physikalische CPU-Kerne (bis zum deklarierten `limit`) verteilt werden dürfen.
* **Sicherheits-Garantie:** Der Parser prüft statisch die Namensübereinstimmung (`core_allocation_block` am Anfang und am Ende). Dies verhindert fehlerhafte Klammerungen oder Schachtelungsdreher bei komplexen parallelen verschachtelten Regionen.
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
