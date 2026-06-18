# Freehold Specification: Concurrency & Parallelism Model
**Format Reference:** Google Open Knowledge Format (OKF) & Architectural Design Blueprint  
**Status:** Implemented baseline, v2.3 language module coverage present  
**Conformance Anchor:** `tests/language_modules_v2_3/15_concurrent_parallel`

This specification describes Freehold's execution architecture, highlighting the clear operational, semantic, and verification-based differences between logical concurrency (`async`/`await`), message-passing asynchrony (`task` via channels), and explicitly bounded physical parallelism (`parallel`).

---

## 1. The Dual-Core Execution Model (Duales Kern-Modell)

Freehold enforces a strict structural distinction between cooperative logical concurrency on a single processor core and physical parallel multicore execution. This guarantees deterministic thread safety by default, switching on hardware parallelism only inside explicit boundaries.

```mermaid
graph TD
    subgraph Single-Core default
        A[Cooperative Event Loop] -->|Schedule M:1| B[Green-Thread A]
        A -->|Schedule M:1| C[Green-Thread B]
    end
    subgraph Multi-Core parallel block
        D[parallel limit=N do] -->|Allocate N Cores| E[Worker Core 1]
        D -->|Allocate N Cores| F[Worker Core 2]
        E -->|M:N Scheduler| G[Spawned Task/Handler]
        F -->|M:N Scheduler| H[Spawned Task/Handler]
    end
```

### 1.1 Non-Parallel (Logical Concurrency) Default
By default, all spawned asynchronous processes operate cooperatively on **exactly one physical thread**. 
* **Mechanics:** Cooperatively yielded tasks (via `await` or channel blockages) back off to a deterministic microtask scheduler.
* **Benefits:** Complete preservation of thread safety without hardware-level race conditions. No mutex locking overhead is required.

### 1.2 Parallel (Physical Multi-Core) Work-Stealing
Hardware-level multi-core execution is exclusively toggled when executing statements enclosed in a `parallel` block specifying explicit core limits.
```freehold
parallel (limit = 2)
do
    -- Underneath this block, tasks are scheduled M:N on up to 2 OS threads.
    -- Explicit concurrency mechanics are active.
end parallel
```

Named parallel blocks are supported by the parser and verifier when a block name is provided. The minimum portable form is the unqualified block shown above.

### 1.3 Physical Boundary Rule
`parallel` is an explicit boundary. Inside the boundary, Freehold may map runnable tasks to physical worker threads up to the `limit` value. Outside this boundary, concurrency remains cooperative and deterministic by default.

The verifier enforces that `limit` has type `Integer`. Non-integer limits are semantic errors and are covered by the `parallel_limit_type_neg` conformance test.

---

## 2. Functional Concurrency (`async`/`await` model)

### 2.1 Intended Use Cases
Ideal for data-centric async pipelines with clear computation branches whose execution flows toward a consolidated final outcome. Here, variables represent values that are awaited to resolve dependencies sequentially or concurrently.

### 2.2 Syntax and Typings
Functions declare an `async` modifier and specify a functional return value type `T`. Spawning an `async` routine yields a highly typed `JoinHandle<T>`:
```freehold
async function ComputeSensor(sender: Sender<Integer>) returns SensorData
    ensures result.id = 1
is
    ...
    return SensorData { id: 1, val: 42 }
end ComputeSensor
```

### 2.3 Data Communication & Synthesis
Data is collected by blocking the caller on its generated join handle with `await` which yields the final returned payload of type `T`:
```freehold
let handle: JoinHandle<SensorData> = spawn ComputeSensor(sender)
let data: SensorData = await handle -- blocks until resolved, then returns SensorData
```

---

## 3. Message-Passing Asynchrony (`task` model)

### 3.1 Intended Use Cases
Ideal for long-running, self-contained background workers, listeners, and stream-processors running reactive control loops. They operate independently of the orchestrating execution scope, mapping directly to the **CSP (Communicating Sequential Processes)** model.

### 3.2 Syntax and Typings
These routines use the native `task` keyword. A `task` is structurally restricted to a pure `Void` return type. As an architectural choice and syntactic shortcut, **tasks are forbidden from returning values via functional returns**:
```freehold
task DataListener(receiver: Receiver<Integer>, res_sender: Sender<String>)
is
    let value: Integer = await channel_receive<Integer>(receiver)
    let processed: Boolean = await channel_send<String>(res_sender, "COMPLETED")
    -- Implicitly returns Void. No "return <val>" expression is valid here.
end DataListener
```

Attempting to return a value from a `task` is rejected by semantic verification and is covered by the `task_return_value_neg` conformance test.

### 3.3 Data Communication & Synthesis
Data outputs are conveyed asynchronously via **strictly isolated, typed channels** (`Channel<T>`) rather than terminal values on the handle. 
To guarantee mathematical correctness and thread-safety during parallel work-stealing, channel invariants are enforced:
```freehold
-- Create result channel with a formal safety contract
let res_chan: Channel<String> = channel<String>(8) with invariant value = "COMPLETED"
let res_sender: Sender<String> = channel_sender<String>(res_chan)
let res_receiver: Receiver<String> = channel_receiver<String>(res_chan)

let h: JoinHandle<Void> = spawn DataListener(receiver, res_sender)
let status: String = await channel_receive<String>(res_receiver) -- receives result via CSP

await h -- awaits synchronization barrier only (ensuring task is completely cleaned up)
```

---

## 4. Key Differences Summary Matrix

| Metric | Functional Concurrency (`async`) | Message-Passing Asynchrony (`task`) |
| :--- | :--- | :--- |
| **Syntactic Target** | `async function` / `async procedure` | `task` (syntactic sugar for `Void` processes) |
| **Return Schema** | Explicitly typed `returns T` | Implicitly `Void` |
| **Result Retrieval** | Blocking read of handle: `result: T = await handle` | Channel message passing: `msg: T = await channel_receive(rcv)` |
| **Handle Verification**| Spawns yield a `JoinHandle<T>` | Spawns yield a `JoinHandle<Void>` |
| **Primary Paradigm** | Functional Data-Flow Pipeline | Communicating Sequential Processes (CSP) |
| **Z3 Proof Mapping** | `ensures` postconditions of routine return values | `invariant` bounds checked on channel read/write boundaries |

---

## 5. Spawn Semantics and Join Handles

### 5.1 Valid Spawn Targets
The `spawn` expression requires a routine invocation as its target. The target routine must be either:
- an `async function`,
- an `async procedure`, or
- a `task`.

Spawning a synchronous non-async routine is a semantic error and is covered by `spawn_non_async_neg`.

### 5.2 Join Handle Type Mapping
Spawned routines map to join handles as follows:

| Spawn Target | Join Handle Type |
| :--- | :--- |
| `async function f(...) returns T` | `JoinHandle<T>` |
| `async procedure p(...)` | `JoinHandle<Void>` |
| `task t(...)` | `JoinHandle<Void>` |

Awaiting a join handle synchronizes with completion and yields the handle payload type. For `JoinHandle<Void>`, the result is a synchronization token, not a data transport mechanism.

### 5.3 Spawn Attributes
Spawn expressions may carry execution attributes:

```freehold
let h: JoinHandle<Void> = spawn Worker(sender) with (
    priority: 5,
    pool: "hardware_io",
    name: "pipeline_worker"
)
```

The verifier currently recognizes:
- `priority: Integer`
- `pool: String`
- `name: String`

Unknown attributes or attributes with the wrong type are semantic errors.

---

## 6. Parallel Safety Rules

### 6.1 No Shared Mutable State Across Parallel Spawns
Freehold's physical parallelism model forbids passing the same mutable root value into multiple spawned tasks inside the same parallel boundary.

Mutable roots currently include:
- `Array` values,
- record values,
- indexed or field paths whose root resolves to an array or record.

The following is rejected:

```freehold
type SharedBuffer is record
    reading: Integer
end record

task Worker(buffer: SharedBuffer)
is
    let observed: Integer = buffer.reading
end Worker

async procedure Main()
is
    let shared: SharedBuffer = SharedBuffer { reading: 42 }

    parallel (limit = 2)
    do
        let first: JoinHandle<Void> = spawn Worker(shared)
        let second: JoinHandle<Void> = spawn Worker(shared)

        let first_done: Void = await first
        let second_done: Void = await second
    end parallel
end Main
```

The diagnostic is:

```text
shared mutable state passed to multiple spawned tasks
```

This rule is implemented by scanning `parallel` bodies and scope spawn bodies for spawn targets, collecting argument root variables, and rejecting duplicate mutable roots. The current implementation intentionally treats records and arrays conservatively: even read-only task parameters are rejected when the same mutable root is passed to multiple spawned tasks. This keeps the v2.3 baseline race-free while future ownership or read-only borrowing rules are designed.

### 6.2 Nested Parallel Boundaries
The shared-state scan does not descend into nested `parallel` or nested `scope` boundaries while checking the current boundary. Each boundary owns its own safety check. This prevents unrelated nested scheduling regions from being conflated into one alias set.

### 6.3 Channels as the Preferred Parallel Data Path
When multiple tasks must coordinate inside `parallel`, data should flow through typed channels instead of shared records or arrays. Channel sender/receiver endpoints are the expected way to express safe concurrent communication:

```freehold
let chan: Channel<Integer> = channel<Integer>(8) with invariant for all X in 0 .. 0 => X > 0
let sender: Sender<Integer> = channel_sender<Integer>(chan)
let receiver: Receiver<Integer> = channel_receiver<Integer>(chan)
```

Channel contracts are checked independently from shared mutable root analysis.

---

## 7. Formal Z3 Verification Rules

The validation of async workflows and channel properties are proved statically during the semantic verification pass:

### 7.1 Async Routine Postconditions (`ensures`)
For `async function` calls, Z3 validates routine postconditions directly:
$$\forall \vec{x}. \text{Requires}(\vec{x}) \implies \text{Ensures}(\vec{x}, \text{Result})$$

### 7.2 Channel Invariant Assertions
For channels declaring a state constraint (e.g. `with invariant value > 0`):
1. **On Send (`channel_send`):** The verifier asserts that the value to be queued satisfies the channel's invariant contract.
2. **On Receive (`channel_receive`):** The verifier assumes the retrieved local variable behaves strictly according to the channel's invariant contract throughout subsequent statements.

### 7.3 Parallel Rule Classification
The no-shared-mutable-state check is a semantic type/safety rule, not an SMT obligation. It runs before backend code generation and rejects invalid programs even if no external prover is configured.

---

## 8. Conformance Coverage

The v2.3 language module `15_concurrent_parallel` is the current acceptance suite for this specification.

Positive cases:
- `concurrent_async_pos.fh`: logical async data-flow with `JoinHandle<T>`.
- `concurrent_task_pos.fh`: task-based CSP communication through channels.
- `parallel_async_pos.fh`: explicit parallel block with async functions and typed join results.
- `parallel_task_pos.fh`: explicit parallel block with tasks, channel result transport, and `JoinHandle<Void>` synchronization.
- `task_control_pos.fh`: task control signaling and cancellation-oriented surface coverage.

Negative cases:
- `parallel_limit_type_neg.fh`: non-integer `parallel` limit is rejected.
- `task_return_value_neg.fh`: `task` cannot return a value.
- `spawn_non_async_neg.fh`: `spawn` target must be async or task.
- `shared_mutable_state_neg.fh`: duplicate mutable root passed to multiple spawned tasks is rejected.

The expected baseline is:

```text
15_concurrent_parallel: 9/9
9/9 language module tests passed
```

---

## 9. Implementation Notes

The authoritative verifier implementation is in `freehold/core/verifier.py`:
- `SpawnExpr` validation enforces async/task targets and spawn attribute types.
- `ParallelStmt` validation enforces integer `limit` and then checks the parallel body.
- `ScopeStmt` validation checks scope spawn bodies under the same shared mutable state rule.
- `check_shared_mutable_state` rejects duplicate mutable roots for arrays and records.

The rule deliberately lives in semantic verification instead of Go code generation. This ensures every frontend/backend shares the same safety model.

---

## 10. Future Extensions

The current v2.3 rule is intentionally conservative. Future specifications may refine it with:
- explicit immutable/read-only parameter modes,
- ownership transfer for spawned tasks,
- borrow scopes for disjoint record fields or disjoint array ranges,
- richer diagnostics naming the conflicting spawn targets,
- backend scheduling metadata for pools and priorities.

Until those extensions are formalized, the safe default is: share data through channels, not by passing the same mutable root into multiple parallel spawns.

---

## 11. Statische "No-Blocking"-Garantie im limitierten Pool

### 11.1 Das Problem der Pool-Verstopfung (Pool Starvation / Deadlocks)
Wenn physischer Parallelismus mit einem limitierten Thread-Pool (z. B. `parallel (limit = N)`) kombiniert wird, können blockierende Synchronisationsoperationen (wie unbegrenztes Senden/Empfangen von Kanalkombinationen oder synchrones Warten) zu einer vollständigen Verstopfung des Systems d.h. Thread-Hungersnot (Pool Starvation) führen.

Falls alle $N$ verfügbaren Worker-Threads durch blockierte Tasks blockiert sind, können keine anderen wartenden Tasks geplant werden, um die Blockierungsbedingungen (z. B. das Empfangen einer Nachricht) aufzuheben. Dies führt zu einem statisch deterministischen Deadlock.

### 11.2 Formale Verifikation der "No-Blocking"-Eigenschaft
Freehold verhindert dieses schwerwiegende Stabilitätsproblem komplett zur Compilezeit durch eine statische Kontrollfluss- und Semantikanalyse:

1. **Kontext-Klassifikation (`in_spawned`):**
   * Der Verifier verfolgt rekursiv während der semantischen Analyse alle Programmpfade und markiert jeglichen Kontrollfluss innerhalb von `spawn`-Anweisungen im Standardpool der parallelen Umgebung mit der Eigenschaft `in_spawned = True`.
   * Besitzt ein `spawn` ein explizites, separates Pool-Attribut (z. B. `pool: "dsp_worker"`), so wird die Eigenschaft `in_spawned = False` gesetzt, da diese Tasks nicht auf dem limitierten Haupt-Pool konkurrieren.

2. **Statische Verbotsschranke:**
   * Findet der Verifier im Kontext `in_spawned = True` eine der folgenden blockierenden Operationen, bricht er die Übersetzung mit einem semantischen Validierungsfehler (`TypeCheckError`) ab:
     * `channel_receive` (blockierendes CSP-Empfangen)
     * `channel_send` (blockierendes CSP-Senden)
   * Das Verwenden von nicht-blockierenden Kanaloperationen wie `channel_try_send` ist stattdessen uneingeschränkt gestattet und typsicher garantiert.

3. **Formale Transitivitäts-Garantie:**
   * Der Verifier führt diese Analyse transitiv über alle aufgerufenen Unterprogramme (`routine`) durch. Ruft eine in einem limitierten Pool gespawnte Task eine Funktion auf, die tief im Aufrufbaum eine blockierende Kanaloperation besitzt, wird dies statisch erkannt und ebenfalls abgewiesen:
     $$\forall \text{ call } C \in \text{Body}(T). \text{ trans_block}(C) \implies \text{TypeError}$$

Dies stellt sicher, dass Entwickler fehlerfreien, hoch-performanten Parallelcode schreiben können, ohne Laufzeit-Deadlocks durch Thread-Hungersnöte befürchten zu müssen.
