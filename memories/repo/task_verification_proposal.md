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

## 4. Integration in den Compiler

### 4.1 Parser / AST
Hinzufügen von `task_decl` in `freehold.lark`:
```lark
task_decl: "task" NAME "(" [param_list] ")" "is" stmt* "end" NAME
```

### 4.2 Go-Codegen Lowering
Auf Go-Ebene lässt sich ein `task` direkt auf ein leichtgewichtiges Goroutinen-Handling abbilden:
```go
func Producer(out chan int64) {
    out <- 42
}
```
Ein `spawn Producer(numbers)` generiert ein entsprechendes `FreeholdJoinHandle` und startet die Funktion asynchron über die Threading-Pools der Runtime.
