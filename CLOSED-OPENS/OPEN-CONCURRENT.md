# Open: Async/Await, Structured Concurrency und Channels in Freehold

Stand: 2026-06-01

Status: V1 abgeschlossen mit formaler Verifikation; Concurrency-Verifikation (Kanal-Invarianten, Spawn-Vorbedingungen, sequentielles Scope-Pfadthreading) und Go-Codegen-Senkung für Scopes/Kanäle implementiert.

Dieses Dokument haelt die erste Diskussion und Grundsatzentscheidung zur Concurrent-/Async-Runtime in Freehold fest. V1 ist als statische Sprach-/Verifier-Schicht abgeschlossen: async/await-Grundlagen, Runtime-Kerntypen, Channel-Typregeln und strukturierte Scope-Lifetime-Regeln sind testbar. Formale Verifikationsregeln für Kanäle, Scopes, Spawn-Vorbedingungen und Z3/SMT-Modellierung sind vollständig integriert. Echte Scheduler-Cancellation und fortgeschrittenes Thread-Stealing bleiben für V2/V3 geparkt.

## Ausgangsfrage

Freehold hat noch keinen eingebauten `async`-Mechanismus. Kann man das zunaechst in eine Bibliothek auslagern, etwa als Runtime Task?

Zweite Frage: Wie passen Threads und Channels dazu, etwa in Richtung Go?

Dritte Entscheidung: Wenn gRPC von Anfang an wichtig ist, sollen `async`/`await`, `scope` und `Channel<T>` direkt als offizielle Concurrency-Saeulen festgelegt werden?

## Kurzantwort

Ja. Fuer gRPC sollte Freehold von Anfang an async-kompatibel entworfen werden. Die offizielle Zielarchitektur ist:

```text
Sprachmodell:
    async function, async fn, await

Structured Concurrency:
    runtime::scope(...), Scope.spawn(...), automatische Join-/Cancel-Regeln

Kommunikation:
    Channel<T>, Sender<T>, Receiver<T>, async send/receive

Runtime-Fundament:
    Executor, Task, JoinHandle<T>, spawn, spawn_blocking, block_on

Integration:
    gRPC-Server laeuft async auf Executor, jeder Request in eigenem Scope
```

Klares Votum: `async`/`await`, Structured Concurrency mit `scope` und `Channel<T>` sind offizielle Concurrency-Saeulen von Freehold. Der Task Executor ist nicht die Alternative dazu, sondern die Runtime-Schicht darunter.

## Offizielle Concurrency-Saeulen

Freehold legt fuer Concurrency drei sichtbare Saeulen und ein Runtime-Fundament fest:

```text
1. async/await
     Sichtbare Sprachsyntax fuer suspendierbare Funktionen und awaitbare Operationen.

2. Structured Concurrency
     Scopes begrenzen Task-Lebenszeiten, propagieren Cancellation und joinen Child-Tasks.

3. Channel<T>
     Statisch typisierte Kommunikation mit Backpressure, besonders fuer Streaming.

4. Executor/Task Runtime
     Scheduler, Worker, Blocking-Pool, Timer und I/O-Reactor unterhalb der Sprache.
```

Diese Entscheidung ist wichtig fuer gRPC: Server, Handler, Streaming und Cancellation sollen nicht nachtraeglich auf Async umgebaut werden muessen.

## Grundsatzentscheidung

Freehold soll Concurrency nach aussen als `async`-faehige Sprache mit Runtime-Bibliothek modellieren:

```fh
use runtime
```

### Statische Typisierung, Sichtbarkeitsregeln und JoinHandle-Lifetime (V1d)

Aktueller Pruefstand: V1d ist als statische Sprach-/Verifier-Schicht angelegt. Die vorlaeufige testbare API nutzt `scope()`, `scope_spawn<T>(scope, handle)` und `scope_join<T>(scope, handle)`, bis die spaetere `runtime::scope(async fn(...))`-/`Scope.spawn(...)`-Syntax festgelegt ist.

Freehold führt ein statisches Scope-Modell als offizielle Structured-Concurrency-Säule ein, um verlorene Tasks und unsichere Lebensdauern zu vermeiden:

- **`runtime::scope(async fn(Scope) -> T) -> T`**: Erzeugt einen neuen Scope, in dem Tasks sicher gespawnt und am Ende automatisch gejoint werden.
- **`Scope.spawn(async fn() -> T) -> JoinHandle<T>`**: Startet einen neuen Task im aktuellen Scope, der garantiert vor Verlassen des Scopes gejoint wird.
- **Join- und Lifetime-Regeln**: Tasks dürfen den Scope, in dem sie erzeugt wurden, nicht überleben. Der Verifier prüft, dass alle JoinHandles im Scope gejoint werden und keine Handles nach außen "leaken".
- **Sichtbarkeit und Typregeln**: Scopes begrenzen die Lebensdauer und Sichtbarkeit von Tasks. JoinHandles sind typisiert und awaitbar, aber außerhalb des Scopes nicht mehr gültig.
- **Keine echte Parallelität in V1d**: Die statische API und alle Typ-/Sichtbarkeitsregeln werden vorbereitet, echte Parallelität und Cancellation folgen in V1e.

Beispiel:

```fh
async function process_files(files: Array<String>) returns Array<Result<Document, CompileError>>
is
    return await runtime::scope(async fn(scope: runtime::Scope) {
        let handles = []
        for file in files do
            let handle = scope.spawn(async fn() {
                return await runtime::spawn_blocking(fn() {
                    return compiler::parse_and_analyze(file)
                })
            })
            handles.push(handle)
        end
        return await runtime::join_all(handles)
    })
end process_files
```

**Vorteile:**
- Keine verlorenen Tasks, alle werden am Scope-Ende gejoint.
- Fehler und Cancellation können sauber propagiert werden.
- gRPC-Requests und andere Nebenläufigkeit sind sicher und statisch überprüfbar.

**Regel für den Verifier:**  
Alle JoinHandles, die in einem Scope erzeugt werden, müssen vor Verlassen des Scopes gejoint werden. Handles dürfen nicht aus dem Scope herausgegeben werden.

### Lesbare Scope-Block-Struktur

Die spaetere Blocksyntax soll nicht nur eine Lifetime-Grenze setzen, sondern im Code sichtbar machen, welche nebenlaeufige Arbeit vorbereitet, gestartet, eingesammelt und abgeschlossen wird. Die bevorzugte Zielstruktur ist deshalb ein klarer Scope-Block mit gewoehnlichen Statements, aber einer empfohlenen inneren Ordnung:

```fh
async function handle_request(req: Request) returns Response
is
    scope request_scope do
        let parse_handle: JoinHandle<Document> =
            request_scope.spawn<Document>(parse_document(req.body))

        let auth_handle: JoinHandle<User> =
            request_scope.spawn<User>(authenticate(req.token))

        let doc: Document = await request_scope.join<Document>(parse_handle)
        let user: User = await request_scope.join<User>(auth_handle)

        return build_response(user, doc)
    end scope
end handle_request
```

Pruefbare Struktur im Scope:

- **Scope-Bindung:** `scope request_scope do` bindet genau einen lokalen Scope-Namen.
- **Handle-Erzeugung:** Jeder `spawn` innerhalb des Blocks erzeugt einen `JoinHandle<T>`, der diesem Scope gehoert.
- **Handle-Verbrauch:** Jeder Scope-Handle muss im selben Scope durch `join` verbraucht werden.
- **Exit-Pruefung:** Vor `return`, `abort` und `end scope` muss der Scope keine offenen Handles mehr besitzen.
- **Escape-Verbot:** Scope-Handles duerfen nicht zurueckgegeben, in aeussere Variablen geschrieben oder in einen anderen Scope verschoben werden.

Fuer sehr grosse Scopes kann die Lesbarkeit durch lokale Namenskonventionen verbessert werden: Handles enden auf `_handle`, die gejointen Werte tragen den fachlichen Namen. Dadurch bleibt der Lebensweg im Code klar sichtbar:

```fh
let invoice_handle: JoinHandle<Invoice> = request_scope.spawn<Invoice>(load_invoice(id))
let customer_handle: JoinHandle<Customer> = request_scope.spawn<Customer>(load_customer(id))

let invoice: Invoice = await request_scope.join<Invoice>(invoice_handle)
let customer: Customer = await request_scope.join<Customer>(customer_handle)
```

Eine spaetere strengere Syntax kann diese Ordnung als eigene Unterbloecke ausdruecken, falls die Sprache mehr Fuehrung geben soll:

```fh
scope request_scope do
    spawn
        let invoice_handle: JoinHandle<Invoice> = request_scope.spawn<Invoice>(load_invoice(id))
        let customer_handle: JoinHandle<Customer> = request_scope.spawn<Customer>(load_customer(id))
    join
        let invoice: Invoice = await request_scope.join<Invoice>(invoice_handle)
        let customer: Customer = await request_scope.join<Customer>(customer_handle)
    result
        return render_invoice(invoice, customer)
end scope
```

Diese Unterblock-Variante waere besonders gut maschinell pruefbar, fuehrt aber neue Grammatik ein. Der naechste konservative Schritt bleibt daher: `scope <name> do ... end scope` als Lifetime-Grenze, mit Verifier-Regeln fuer offene Handles und Handle-Escape.

```fh
    executor.block_on(async fn() {
        let handle = runtime::spawn(async fn() {
            return compute_answer()
        })

        let answer = await handle
        print(answer)
    })

    return 0
end main
```

Das sichtbare Sprachmodell bleibt bewusst klein: `async`, `await`, `scope` und generische Runtime-Typen. Die Runtime bekommt spezielle interne Unterstuetzung fuer Suspend/Resume, Scheduling, Cancellation und I/O.

## Warum diese Saeulen fuer Freehold passen

Freehold hat inzwischen Generics als sichtbares Sprachmodell. Das passt direkt zu Runtime-Typen:

```fh
type JoinHandle<T> is record
    handle: RuntimeHandle
end

type Channel<T> is record
    inner: RuntimeChannel
end
```

Wichtige Vorteile:

- `JoinHandle<T>` ist statisch typisiert.
- `Channel<T>` ist statisch typisiert.
- Fehler koennen als `Result<T, E>` modelliert werden.
- gRPC-Handler koennen von Anfang an nonblocking modelliert werden.
- Schwere Compilerarbeit wird kontrolliert ueber `spawn_blocking` ausgelagert.
- `async`-Funktionen sind fuer den Verifier sichtbar.
- Cancellation und Request-Lebenszeiten koennen strukturiert geprueft werden.

## Kern-APIs der Runtime

Erste API-Skizze fuer ein Modul `runtime`:

```fh
module runtime

type JoinHandle<T> is record
    // Interner Handle, fuer normalen Freehold-Code nicht direkt manipulierbar.
end

type Executor is record
    // Intern: Worker, Queues, Blocking-Pool, Shutdown-State.
end

function Executor::new() returns Executor
is
    return Executor::new_with_threads(0)
end new

function Executor::new_with_threads(thread_count: Integer) returns Executor
is
    // 0 bedeutet auto, typischerweise cpu::core_count().
end new_with_threads

function Executor::block_on<T>(self: Executor, f: async fn() -> T) returns T
is
    // Startet einen Root-Task und blockiert den aufrufenden Thread,
    // bis der Root-Task abgeschlossen ist.
end block_on

function spawn<T>(f: async fn() -> T) returns JoinHandle<T>
is
    // Plant leichte Runtime-Arbeit auf dem aktiven Executor ein.
end spawn

function spawn_blocking<T>(f: fn() -> T) returns JoinHandle<T>
is
    // Plant blockierende oder CPU-intensive Arbeit auf einem separaten Pool ein.
end spawn_blocking

async function join_all<T>(handles: Array<JoinHandle<T>>) returns Array<T>
is
    // Wartet auf alle Handles und sammelt die Ergebnisse.
end join_all

async function sleep(duration: Duration) returns Unit
is
    // Timer-basierte Pause, parkt idealerweise den Task statt den Worker zu blockieren.
end sleep

function yield_now() returns Unit
is
    // Gibt Kontrolle an den Scheduler zurueck.
end yield_now
```

Offene Syntaxfrage: Die Typen `fn() -> T` und `async fn() -> T` sind hier als Designnotation gemeint. Falls Freehold eine andere Funktions-Typ-Syntax bekommt, muss die Runtime-API daran angepasst werden.

## JoinHandle und await als Sprachkonstrukt

`await` ist fuer die Zielarchitektur ein Sprachkonstrukt. `JoinHandle<T>` ist awaitbar:

```fh
async function compile(req: CompileRequest) returns CompileResponse
is
    let handle = runtime::spawn_blocking(fn() {
        return compiler::compile(req.source_code)
    })

    return await handle
end compile
```

Semantische Regel fuer V1:

```text
Wenn handle den Typ JoinHandle<T> hat,
dann hat await handle den Typ T.
```

Zusaetzliche Runtime-Regel:

```text
await darf nur in einem async Kontext laufen:
  - innerhalb von Executor::block_on(...)
  - innerhalb eines mit runtime::spawn(...) gestarteten Tasks
  - innerhalb eines runtime::scope(...)
```

Diese Regel sollte vom Verifier geprueft werden. Runtime-Checks bleiben als Sicherheitsnetz moeglich, aber `await` ausserhalb eines async Kontextes ist ein statischer Fehler.

Neben `await handle` bleiben normale Methoden sinnvoll:

```fh
impl<T> JoinHandle<T>
is
    function cancel(self: JoinHandle<T>) returns Unit
    is
        runtime::internal::request_cancel(self)
    end cancel

    function is_finished(self: JoinHandle<T>) returns Boolean
    is
        return runtime::internal::is_finished(self)
    end is_finished
end
```

## Error Handling

Tasks sollten Fehler nicht als Sonderfall der Runtime verstecken. Freehold sollte starke Result-Typen nutzen:

```fh
function spawn_fallible<T, E>(f: fn() -> Result<T, E>) returns JoinHandle<Result<T, E>>
is
    return spawn(f)
end spawn_fallible
```

Beispiel:

```fh
let handle = runtime::spawn(fn() {
    return parse_file(path)
})

let result = await handle
```

Wenn `parse_file` den Typ `Result<Document, ParseError>` hat, dann hat `handle` den Typ `JoinHandle<Result<Document, ParseError>>`.

## Executor-Modell

Moegliche Runtime-Modelle:

```text
Single-threaded Event Loop:
  niedrige Komplexitaet, guter Start fuer I/O, begrenzte CPU-Skalierung

Thread Pool 1:1:
  einfache Umsetzung, aber schlechte Skalierung bei sehr vielen Tasks

Goroutine-aehnliches M:N-Modell:
  sehr ergonomisch, mittlere bis hohe Runtime-Komplexitaet

Multi-threaded Work-Stealing:
  beste Langfrist-Option, gute CPU-Auslastung, hoehere Komplexitaet
```

Empfehlung fuer Freehold:

```text
V1:
  Executor-API festlegen und intern einfach starten.

V2:
  Multi-threaded Executor mit globaler Queue und optionalen lokalen Worker-Queues.

V3:
  Work-Stealing, Timer, I/O-Reactor, Blocking-Pool sauber trennen.
```

Die API sollte bereits so aussehen, dass spaeter ein Work-Stealing-Executor dahinter liegen kann.

## Minimales Executor-Geruest

Pseudocode fuer die interne Struktur:

```fh
module runtime::internal

type TaskState is enum
    Pending
    Running
    Completed
    Cancelled
    Failed
end

type Task<T> is record
    id: Integer
    state: TaskState
    result: Option<T>
    waiters: Array<Continuation>
end

type Executor is record
    workers: Array<Worker>
    global_queue: Channel<RawTask>
    blocking_queue: Channel<RawTask>
    next_task_id: AtomicInteger
    shutdown: AtomicBoolean
end

type Worker is record
    id: Integer
    local_queue: Deque<RawTask>
end
```

Scheduler-Skizze:

```fh
function Executor::schedule(self: Executor, task: RawTask) returns Unit
is
    if runtime::internal::has_current_worker() then
        let worker = runtime::internal::current_worker()

        if worker.local_queue.has_space() then
            worker.local_queue.push_back(task)
            return
        end
    end

    self.global_queue.send(task)
end schedule

function Executor::run_worker(self: Executor, worker: Worker) returns Unit
is
    while not self.shutdown.load() do
        let task = worker.local_queue.pop_back()

        if task.is_none() then
            task = self.steal_work(worker.id)
        end

        if task.is_none() then
            task = self.global_queue.receive()
        end

        if task.is_some() then
            runtime::internal::run_task(task.unwrap())
        end
    end
end run_worker

function Executor::steal_work(self: Executor, worker_id: Integer) returns Option<RawTask>
is
    for attempt in 0..4 do
        let victim = self.random_worker_except(worker_id)
        let stolen = victim.local_queue.steal_front()

        if stolen.is_some() then
            return stolen
        end
    end

    return self.global_queue.try_receive()
end steal_work
```

## spawn und spawn_blocking

`spawn` ist fuer leichte, gut kooperierende Runtime-Arbeit gedacht:

```fh
function spawn<T>(f: async fn() -> T) returns JoinHandle<T>
is
    let executor = runtime::default_executor()
    let task = runtime::internal::Task::new<T>(f)

    executor.schedule(task.raw())

    return JoinHandle<T>{ task: task.handle() }
end spawn
```

`spawn_blocking` ist fuer CPU-intensive oder blockierende Arbeit gedacht:

```fh
function spawn_blocking<T>(f: fn() -> T) returns JoinHandle<T>
is
    let executor = runtime::default_executor()
    let task = runtime::internal::Task::new<T>(f)

    executor.blocking_queue.send(task.raw())

    return JoinHandle<T>{ task: task.handle() }
end spawn_blocking
```

Grundsatz:

```text
spawn:
  kurze, kooperative Tasks

spawn_blocking:
  Parser, Verifier, Codegen, Datei-I/O, Netzwerk-Clients ohne nonblocking API
```

## Channels nach Go-Vorbild

Freehold sollte Channels stark typisieren:

```fh
type Sender<T> is record
    inner: RuntimeChannel
end

type Receiver<T> is record
    inner: RuntimeChannel
end

function channel<T>(capacity: Integer) returns (Sender<T>, Receiver<T>)
is
    // capacity = 0 bedeutet unbuffered, also synchrone Uebergabe.
end channel
```

Sender-API:

```fh
impl<T> Sender<T>
is
    async function send(self: Sender<T>, value: T) returns Unit
    is
        runtime::internal::channel_send<T>(self, value)
    end send

    function try_send(self: Sender<T>, value: T) returns Boolean
    is
        return runtime::internal::channel_try_send<T>(self, value)
    end try_send

    function close(self: Sender<T>) returns Unit
    is
        runtime::internal::channel_close(self)
    end close
end
```

Receiver-API:

```fh
impl<T> Receiver<T>
is
    async function receive(self: Receiver<T>) returns Option<T>
    is
        return runtime::internal::channel_receive<T>(self)
    end receive

    function try_receive(self: Receiver<T>) returns Option<T>
    is
        return runtime::internal::channel_try_receive<T>(self)
    end try_receive

    function is_closed(self: Receiver<T>) returns Boolean
    is
        return runtime::internal::channel_is_closed(self)
    end is_closed
end
```

Wichtige Entscheidung: `await receive()` sollte bei geschlossenem Channel `Option<T>` liefern. Das ist sauberer als ein Sentinel-Wert und passt besser zu starker Typisierung.

Beispiel:

```fh
executor.block_on(async fn() {
    let (tx, rx) = runtime::channel<String>(10)

    let producer = runtime::spawn(async fn() {
        for i in 0..5 do
            await tx.send("Wert " + i.to_string())
        end

        tx.close()
    })

    let consumer = runtime::spawn(async fn() {
        loop do
            let value = await rx.receive()

            if value.is_none() then
                break
            end

            print(value.unwrap())
        end
    })

    await runtime::join_all<Unit>([producer, consumer])
})
```

## Interne Channel-Struktur

Pseudocode:

```fh
type ChannelState<T> is record
    queue: RingBuffer<T>
    capacity: Integer
    closed: AtomicBoolean
    mutex: Mutex
    senders: WaitQueue
    receivers: WaitQueue
end
```

Send-Skizze:

```fh
function channel_send<T>(channel: RuntimeChannel, value: T) returns Unit
is
    let guard = channel.mutex.lock()

    if channel.closed.load() then
        guard.unlock()
        abort "send on closed channel"
    end

    if channel.receivers.has_waiting() then
        channel.receivers.wake_one_with_value(value)
        guard.unlock()
        return
    end

    if not channel.queue.is_full() then
        channel.queue.push(value)
        guard.unlock()
        return
    end

    channel.senders.wait_with_value(guard, value)
end channel_send
```

Receive-Skizze:

```fh
function channel_receive<T>(channel: RuntimeChannel) returns Option<T>
is
    let guard = channel.mutex.lock()

    if not channel.queue.is_empty() then
        let value = channel.queue.pop()
        channel.senders.wake_one_if_possible()
        guard.unlock()
        return Some(value)
    end

    if channel.closed.load() then
        guard.unlock()
        return None
    end

    return channel.receivers.wait_for_value(guard)
end channel_receive
```

## select-artige API

Go hat `select` als Sprachkonstrukt. Freehold kann fuer V1 eine Builder-API anbieten:

```fh
runtime::select()
    .receive(rx1, fn(msg: Message) {
        print(msg)
    })
    .receive(rx2, fn(event: Event) {
        handle_event(event)
    })
    .default(fn() {
        runtime::yield_now()
    })
    .execute()
```

Das ist weniger elegant als ein Keyword, aber fuer eine Bibliotheksloesung ausreichend. Ein spaeteres `select`-Keyword kann darauf abgebildet werden.

## Structured Concurrency

Freehold legt ein Scope-Modell als offizielle Structured-Concurrency-Saeule fest, um verlorene Tasks zu vermeiden:

```fh
async function scope<T>(f: async fn(Scope) -> T) returns T
is
    let scope = Scope::new()
    let result = await f(scope)

    await scope.wait_all()

    return result
end scope
```

Scope-API:

```fh
type Scope is record
    tasks: Array<AnyJoinHandle>
end

impl Scope
is
    function spawn<T>(self: Scope, f: async fn() -> T) returns JoinHandle<T>
    is
        let handle = runtime::spawn<T>(f)
        self.tasks.push(handle.erase_type())
        return handle
    end spawn

    function spawn_blocking<T>(self: Scope, f: fn() -> T) returns JoinHandle<T>
    is
        let handle = runtime::spawn_blocking<T>(f)
        self.tasks.push(handle.erase_type())
        return handle
    end spawn_blocking

    async function wait_all(self: Scope) returns Unit
    is
        for task in self.tasks do
            await task
        end
    end wait_all
end
```

Beispiel:

```fh
async function process_files(files: Array<String>) returns Array<Result<Document, CompileError>>
is
    return await runtime::scope(async fn(scope: runtime::Scope) {
        let handles = []

        for file in files do
            let handle = scope.spawn(async fn() {
                return await runtime::spawn_blocking(fn() {
                    return compiler::parse_and_analyze(file)
                })
            })

            handles.push(handle)
        end

        return await runtime::join_all(handles)
    })
end process_files
```

Vorteile:

- Keine verlorenen Tasks.
- Fehler koennen gesammelt oder propagiert werden.
- Cancellation kann vom Scope auf Child-Tasks weitergegeben werden.
- gRPC-Requests koennen ihre internen Tasks sicher begrenzen.

## Cancellation

Cancellation ist eine offizielle Nebenregel der Structured Concurrency und sollte cooperative sein, nicht forced.

Grundsatzentscheidung:

```text
Cancellation in Freehold:
    cooperative, nicht forced

Propagation:
    von Scope zu Child-Tasks

gRPC:
    Request-Abbruch cancelt den Request-Scope

await:
    awaitbare Operationen sind Cancellation Points

Channel<T>:
    send/receive koennen cancellation-aware warten

spawn_blocking:
    blockierende Arbeit bekommt Token und muss regelmaessig pruefen
```

Forced Cancellation wird bewusst vermieden. Ein Task wird also nicht mitten in einem beliebigen Ausdruck hart beendet. Stattdessen wird ein Cancellation-Signal gesetzt, und Tasks reagieren an sicheren Punkten: vor oder nach `await`, in Schleifen, bei Channel-Operationen und in laenger laufender Blocking-Arbeit.

Kern-API:

```fh
type CancellationToken is record
    inner: RuntimeCancellationState
end

impl CancellationToken
is
    function is_cancelled(self: CancellationToken) returns Boolean
    is
        return runtime::internal::is_cancelled(self)
    end is_cancelled

    async function cancelled(self: CancellationToken) returns Unit
    is
        await runtime::internal::wait_for_cancelled(self)
    end cancelled

    function throw_if_cancelled(self: CancellationToken) returns Unit
    is
        if self.is_cancelled() then
            abort "task cancelled"
        end
    end throw_if_cancelled
end
```

`is_cancelled()` prueft sofort. `cancelled()` wartet async auf das Signal. `throw_if_cancelled()` ist fuer lange Schleifen und `spawn_blocking` gedacht.

Scope-Regel fuer V1:

```text
Wenn ein Scope fehlschlaegt oder verlassen wird,
dann werden alle noch laufenden Child-Tasks cooperative cancelled
und danach gejoint.
```

Beispiel mit Scope:

```fh
await runtime::scope(async fn(scope: runtime::Scope) {
    let token = scope.cancellation_token()

    let worker = scope.spawn(async fn() {
        loop do
            token.throw_if_cancelled()

            let item = await rx.receive(token)

            if item.is_cancelled() then
                return
            end

            if item.value().is_none() then
                break
            end

            await process(item.value().unwrap())
        end
    })

    await worker
})
```

Channel-Operationen sollten cancellation-aware Varianten bekommen:

```fh
impl<T> Receiver<T>
is
    async function receive(self: Receiver<T>, token: CancellationToken) returns Result<Option<T>, Cancelled>
    is
        return await runtime::internal::channel_receive_or_cancel<T>(self, token)
    end receive
end

impl<T> Sender<T>
is
    async function send(self: Sender<T>, value: T, token: CancellationToken) returns Result<Unit, Cancelled>
    is
        return await runtime::internal::channel_send_or_cancel<T>(self, value, token)
    end send
end
```

Damit kann ein Task nicht unbegrenzt auf einem leeren oder vollen Channel haengen, wenn der Scope bereits cancelled wurde.

`spawn_blocking`-Regel:

```fh
let job = scope.spawn_blocking(fn() {
    token.throw_if_cancelled()
    let parsed = parser::parse(req.source_code)

    token.throw_if_cancelled()
    let checked = semantic::analyze(parsed.ast)

    token.throw_if_cancelled()
    return compiler::generate_wasm(checked)
})
```

Blocking-Arbeit kann nicht an jedem beliebigen Punkt suspendieren. Darum muss sie an sinnvollen Grenzen explizit das Token pruefen.

gRPC-Regel:

```text
Wenn der Client einen Request abbricht,
dann cancelt der gRPC-Kontext den zugehoerigen runtime::Scope.
Der Scope propagiert Cancellation an alle Child-Tasks,
wartende Channel-Operationen werden geweckt,
und danach werden alle Child-Tasks gejoint.
```

Offene Frage: Ob Cancellation als `Result<T, Cancelled>` sichtbar wird oder als eigenes Abort-/Diagnostic-Modell erscheint, muss mit dem bestehenden Abort-/Result-Design abgeglichen werden.

## Zusammenspiel mit gRPC Server

Ein gRPC-Server ist ein idealer Treiber fuer die Runtime:

```fh
use runtime
use grpc
use parser
use semantic
use compiler

type FreeholdServiceImpl is record
end

impl grpc::Service for FreeholdServiceImpl
is
    async function compile(self: FreeholdServiceImpl, req: CompileRequest) returns CompileResponse
    is
        return await runtime::spawn_blocking(fn() {
            let parse_result = parser::parse(req.source_code)

            if not parse_result.success then
                return CompileResponse{
                    success: false,
                    diagnostics: parse_result.diagnostics,
                    output: ""
                }
            end

            let semantic_result = semantic::analyze(parse_result.ast)

            if not semantic_result.valid then
                return CompileResponse{
                    success: false,
                    diagnostics: semantic_result.diagnostics,
                    output: ""
                }
            end

            let codegen_result = compiler::generate_wasm(parse_result.ast)

            return CompileResponse{
                success: true,
                diagnostics: semantic_result.diagnostics,
                output: codegen_result.output,
                wasm_binary: codegen_result.binary
            }
        })
    end compile
end
```

Server-Main:

```fh
function main() returns Integer
is
    let executor = runtime::Executor::new_with_threads(0)

    executor.block_on(async fn() {
        let server = grpc::Server::new("0.0.0.0:50051")
            .add_service(FreeholdServiceImpl{})
            .build()

        print("Freehold gRPC Server gestartet auf :50051")

        await server.serve()
    })

    return 0
end main
```

Wichtig fuer gRPC:

```text
Normale Handler:
  kurze Arbeit direkt im Handler, schwere Arbeit ueber spawn_blocking

Streaming Handler:
  Scope pro Request, Channel fuer Diagnose-/Event-Streams

Request-Abbruch:
  gRPC Cancellation wird in CancellationToken uebersetzt

Server-Shutdown:
  Executor stoppt neue Tasks, cancelt laufende Request-Scopes, joint sauber
```

Streaming-Skizze:

```fh
async function stream_diagnostics(
    self: FreeholdServiceImpl,
    req: DiagnosticsRequest,
    stream: grpc::ServerStream<Diagnostic>
) returns Unit
is
    await runtime::scope(async fn(scope: runtime::Scope) {
        let (tx, rx) = runtime::channel<Diagnostic>(64)

        let analyzer = scope.spawn_blocking(fn() {
            semantic::incremental_analyze(req.source_code, tx)
            tx.close()
        })

        let sender = scope.spawn(async fn() {
            loop do
                let diag = await rx.receive()

                if diag.is_none() then
                    break
                end

                await stream.send(diag.unwrap())
            end
        })

        await analyzer
        await sender
    })
end stream_diagnostics
```

## Minimaler V1-Slice

Ein sinnvoller erster Implementierungs-Slice waere bewusst klein:

```text
Concurrent V1a: Offizielle Concurrency-Syntax festlegen
    - async function als suspendierbare Funktionsform
    - await EXPR als Sprachkonstrukt
    - await nur im async Kontext erlauben
    - Design-Tests fuer gueltige und ungueltige await-Kontexte

Concurrent V1b: Runtime-Kerntypen festlegen
    - runtime::Executor, JoinHandle<T>, Scope, Channel<T>, Sender<T>, Receiver<T>
    - async fn als Funktionsliteral-/Callback-Zielnotation klaeren
    - block_on(async fn() -> T) -> T
    - spawn(async fn() -> T) -> JoinHandle<T>
    - spawn_blocking(fn() -> T) -> JoinHandle<T>

Concurrent V1c: Channel<T> als offizielle Kommunikationssaeule
    - channel<T>(capacity) -> (Sender<T>, Receiver<T>)
    - await Sender<T>.send(value)
    - await Receiver<T>.receive() -> Option<T>
    - Backpressure und close-Regeln dokumentieren

Concurrent V1d: Structured Concurrency
    - runtime::scope(async fn(Scope) -> T) -> T
    - Scope.spawn
    - automatische Join-/Cancel-Regeln
    - Request-Scope als gRPC-Grundmodell

Concurrent V1e: Cooperative Cancellation
    - CancellationToken
    - Scope.cancel und Scope.cancellation_token
    - cancellation-aware await points
    - Channel send/receive mit CancellationToken
    - spawn_blocking prueft Token an sicheren Grenzen

Concurrent V1f: Referenzruntime in Python/Go-Pseudocode
  - einfacher Executor
  - spawn/spawn_blocking
    - await auf JoinHandle<T>
    - async Channel send/receive/close

Concurrent V2: gRPC Integration
    - async grpc::Server::serve()
    - async Handler
  - Request-Scope
  - CancellationToken aus gRPC-Kontext
  - Streaming ueber Channel<T>

Concurrent V3: Scheduler-Qualitaet
  - Work-Stealing
  - Timer
  - I/O-Reactor
  - Blocking-Pool-Tuning
```

## Validierter Stand fuer V1a

Concurrent V1a ist als erster Sprach-Slice umgesetzt:

```text
Syntax:
    async function name(...) returns T
    await EXPR

AST:
    RoutineDecl.is_async
    AwaitExpr

Semantik:
    await ist nur im async Funktionskontext erlaubt
    async Funktionsaufrufe sind awaitbar
    await auf synchronen Ausdruecken wird abgelehnt

Diagnostics:
    VF-ASY001 / FH-CON-3101 await_outside_async_function
    VF-ASY002 / FH-CON-3102 await_requires_awaitable_expression

Tests:
    tests/language_modules/23_concurrency
```

Validiert wurde:

```text
23_concurrency:
    4/4 gruen

Semantic Diagnostics:
    79/79 matching

Spec Diagnostics:
    101 specs, 101 rule emits, 0 failures

Parser Conformance:
    parse status 295/295 matching
    AST shape 251/251 matching
    semantic AST 251/251 matching
    Go tests gruen
```

Noch nicht Teil von V1a: `async fn` als anonyme Funktionsliteral-Syntax. Der Begriff bleibt in der Ziel-API erhalten, wird aber praktisch erst mit Runtime-Kerntypen und `spawn(async fn() { ... })` in V1b/V1f konkretisiert.

## Umsetzungsstand V1b: Runtime-Kerntypen

V1b legt die statische Typoberflaeche der Runtime fest, ohne bereits Executor-/Spawn-Laufzeitverhalten einzubauen.

Implementiert sind derzeit unqualifizierte Built-in-Typen, weil `type_ref` in der aktuellen Sprache noch keine `runtime::`- oder qualifizierten Typnamen traegt:

```text
Executor
Scope
JoinHandle<T>
Channel<T>
Sender<T>
Receiver<T>
```

Semantik:

```text
Executor und Scope sind nicht-generische Runtime-Typen.
JoinHandle<T>, Channel<T>, Sender<T> und Receiver<T> verlangen exakt ein Typargument.
await auf JoinHandle<T> liefert T.
await auf Executor, Scope, Channel<T>, Sender<T> oder Receiver<T> bleibt ungueltig, bis konkrete async Operationen definiert sind.
```

Diagnostics:

```text
Generic-Arity-Fehler verwenden die bestehenden FH-GEN-5010..5012 Regeln.
await auf nicht-awaitbaren Runtime-Typen verwendet FH-CON-3102.
```

Noch nicht Teil von V1b: `block_on`, `spawn`, `spawn_blocking`, `async fn` als Literal-/Callback-Notation und echte Runtime-Ausfuehrung. Diese Namen bleiben im Zielmodell, werden aber in spaeteren Slices konkretisiert.

## Umsetzungsstand V1c: Channel<T>

V1c macht `Channel<T>` statisch nutzbar, ohne bereits echte Queue-/Scheduler-Laufzeit einzubauen.

Da die Sprache aktuell weder Tupel-Rueckgaben noch Methodensyntax als offiziellen Runtime-Mechanismus besitzt, verwendet der erste Slice kleine eingebaute Funktionsformen:

```text
channel<T>(capacity: Integer) -> Channel<T>
channel_sender<T>(channel: Channel<T>) -> Sender<T>
channel_receiver<T>(channel: Channel<T>) -> Receiver<T>
channel_send<T>(sender: Sender<T>, value: T) -> Awaitable<Boolean>
channel_receive<T>(receiver: Receiver<T>) -> Awaitable<T>
```

Semantik:

```text
Alle Channel-Funktionen verlangen ein explizites Typargument T.
capacity ist Integer.
Sender<T>, Receiver<T> und Payload T muessen exakt zusammenpassen.
channel_send<T> und channel_receive<T> sind awaitbar.
await channel_send<T>(...) liefert Boolean.
await channel_receive<T>(...) liefert T.
```

Diagnostics:

```text
fehlende/falsche Typargumente verwenden die bestehenden FH-GEN-5030..5031 Regeln.
falsche Channel-Argumentzahl verwendet FH-CON-3111.
falsche Channel-Argumenttypen verwenden FH-CON-3112.
```

Noch nicht Teil von V1c: `channel<T>(capacity) -> (Sender<T>, Receiver<T>)` als Tupel-API, Methoden wie `sender.send(value)`, Close-/Backpressure-Laufzeitverhalten, `Option<T>` fuer geschlossene Receiver und CancellationToken-Integration.

## Offene Designfragen

1. Wie genau sieht die Freehold-Syntax fuer Funktions-Typen aus, insbesondere `async fn() -> T`?
2. Gibt es Tupel-/Mehrfach-Rueckgaben fuer `channel<T>() -> (Sender<T>, Receiver<T>)`?
3. Soll `await rx.receive()` `Option<T>` liefern oder bei geschlossenem Channel ein Result mit Closed-Fehler?
4. Wie werden Panic/Abort/Result in Tasks exakt zusammengefuehrt?
5. Muss `spawn` ohne expliziten Executor immer einen Default-Executor nutzen?
6. Wie stark prueft der Verifier `await`-Kontext, `async`-Propagation und nicht-awaitete Handles?
7. Wie werden globale Tasks beim Shutdown behandelt?
8. Wird `select` dauerhaft Builder-API oder spaeter eigene Sprachsyntax?

## Vorlaeufiges Fazit

Freehold sollte Concurrency offiziell auf drei sichtbaren Saeulen und einem Runtime-Fundament bauen:

```text
async/await:
    Sprachsyntax fuer suspendierbare Funktionen und awaitbare Operationen

Structured Concurrency:
    scope begrenzt Task-Lebenszeiten, Cancellation und Join

Cooperative Cancellation:
    CancellationToken, Scope-Propagation, gRPC-Request-Abbruch, keine forced cancellation

Channel<T>:
    typisierte Kommunikation mit Backpressure, besonders fuer Streaming

Executor:
    Runtime-Fundament fuer Scheduling, Worker, Timer, Blocking-Pool und I/O

JoinHandle<T>:
    typisierter Task-Handle, auf den await angewendet werden kann

gRPC:
    natuerlicher Hauptnutzer: async Server, async Handler, Request-Scopes, Streaming
```

Die Sprache bleibt dadurch klein, aber nicht halbherzig: `async`/`await`, `scope` und `Channel<T>` sind Teil des offiziellen Zielmodells. Die Runtime kann darunter schrittweise wachsen, ohne die gRPC-API spaeter neu denken zu muessen.

=== CLOSED ===
