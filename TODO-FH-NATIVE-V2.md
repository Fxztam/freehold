# TODO: FH-Native-V2 Compiler Core & Language Specification
**Format Reference:** Google Open Knowledge Format (OKF) & Architectural Design Blueprint  
**Status:** Planned Roadmap (Post-Bootstrapping Stage-5 & Stage-6 Features)  
**Target Domain:** Language Design, Compiler Architecture, SMT Verification & Async Execution  

---

## 1. Executive Summary & V2 Vision

The second generation of the native, self-hosted Freehold compiler (**`FH-Native-V2`**) elevates the language from its minimalist, bootstrap-centric core to a fully-featured, mathematically-verified systems programming language.

While `FH-Native-V1` focused strictly on the minimal, safe compiler dialect required to achieve byte-identical self-compilation, `FH-Native-V2` introduces advanced type systems, structured exception recoveries, dynamic collection mapping, and distributed workflow modeling.

---

## 2. Topic 1: Choice & Pattern Matching (Tagged Unions)

By introducing algebraic sum types (named `choice` to prevent keywords conflict with loop variants) and structured `case`-based destructuring (`pattern matching`), Freehold advances to a level of formal safety and declaration power comparable to modern functional-imperative systems languages.

### 2.1 Keyword Conflict Resolution: `variant` vs. `choice`
Freehold originally suffered from a critical name collision regarding the term `variant`:
1. **Loop Termination Variant (`while ... variant ...`):** An existing, fully supported mathematical expression checked by Z3 to guarantee loop termination (e.g. `variant 3 - i`).
2. **Type Variant (Sum Type):** The structural choice representing multiple discrete data payloads.

Using `variant` for both features introduces severe cognitive load for developers and parsing ambiguities inside LL(1) deterministic lookahead parsers. Thus, Freehold officially designates the keyword **`choice`** for declaring algebraic sum types.

### 2.2 SMT-LIB and Z3 Mathematical Verifiability
* **Native Z3 Datatype Modeling:** Sum types represent directly as `(declare-datatypes ...)` in SMT-LIB v2 without state-space explosion.
* **Reduction of Tag Constraints:** Simulating optional records with variable tags requires complex boolean invariant equations. SMT Solvers natively resolve algebraic sum types, drastically accelerating verification time.
* **Exhaustiveness Analysis:** Z3 mathematically proves complete coverage of cases, discarding hazardous and imprecise "default" branches.

### 2.3 Syntax and Language Specification
```freehold
choice Option<T> =
    Some(val: T)
  | None
end Option

choice Result<T, E> =
    Ok(value: T)
  | Err(error: E)
end Result

choice List<T> =
    Nil
  | Cons(head: T, tail: List<T>)
end List
```

### 2.4 Pattern Matching & Destructuring
Extracting payload variables and verifying constructor choices are fused into a single atomic compile-time checked step:
```freehold
case message is
    ValidateOrder(id) when String.length(id) > 10 =>
        -- Matched only if ID length complies
    ValidateOrder(id) =>
        -- Fallback
end case
```

### 2.5 Lowering & Transpiler Engineering
* **Go Transpilation:** Transpiles to a closed Go interface utilizing an unexported guard method (preventing outward extension) and concrete structs matching the interface, mapped natively to Go Type Switches.
* **Python Transpilation:** Maps down directly to Python 3.10 native `match-case` blocks.

---

## 3. Topic 2: Native Map (Associative Arrays) & Sequence Simulation

To implement dynamic lookups, configuration mappings, and service registry patterns efficiently, Freehold requires a native, safe, and easily verifiably finite mapping structure.

### 3.1 Syntax & Language Integration
```freehold
-- Map from String to Integer
let scores: Map<Integer> = Map<Integer> {
    "Alice": 95,
    "Bob": 88
}
```

### 3.2 Bounded Record Iteration
To ensure termination and bounded iteration loops in SMT/Z3, we extract a statically-bounded array of keys and the registration size:
```freehold
let registry_keys: Array<String, 16> = Map.keys(player_registry)
let registry_size: Integer = Map.size(player_registry)

let i: Integer = 0
while i < registry_size invariant i >= 0 and i <= registry_size do
    let current_key: String = registry_keys[i]
    case player_registry[current_key] is
        Ok(player) =>
            -- Handle safe row elements access
        Err(_) =>
            -- Declared unreachable by formal proof constraints
    end case
    i := i + 1
end
```

### 3.3 SMT-LIB and Z3 Mathematical Modeling
Strings and associative mappings are represented using SMT-LIB's native **Theory of Arrays** mapping keys to value options:
$$\text{Map}\langle\text{Key}, \text{Value}\rangle \implies (\text{Array } \text{Key } \text{Value})$$
* **Insertion:** Mapped to SMT `(store map key (Ok val))`
* **Retrieval:** Mapped to SMT `(select map key)`

### 3.4 The Functional Minimalism Principle (Lists via Maps)
Instead of forcing two complex structures (Lists and Maps) through the Parser during bootstrapping, Freehold uses maps to simulate lists:
```freehold
type List<T> is record
    data: Map<Integer, T>  -- Sequential index mapping
    length: Integer         -- Count of populated elements
end record
```
1. **SMT Convergence:** Z3 handles lists and maps uniformly, minimizing SMT translation engine complexity.
2. **Post-Bootstrapping SDK (`List.fh`):** Immediately after bootstrapping, dynamic list sequences are defined in pure Freehold within `List.fh` wrapping Map collections, providing high-level helper functions (`push`, `pop`, `get`).

---

## 4. Topic 3: Set Specification and Verification

A Set (`Set<T>`) is a collection of unique, unordered values of type `T`. It is extremely powerful for writing declarative contracts (`requires`, `ensures`) but lacks standard, zero-overhead Go runtimes.

### 4.1 Two-Phased Roadmap Strategy
1. **Phase 1: "Ghost" / Specification-Only Sets:** Sets are introduced initially only inside contracts. This allows maximum Z3 proof power (uniqueness checks, domains registration) and are completely stripped from compiled Go/Python execution code (absolute Zero-Footprint).
2. **Phase 2: Native Runtime Sets:** Compile sets down to Go structmaps (`map[T]struct{}`) and Python native `set[T]` collections.

### 4.2 SMT Integration
SMT-LIB v2 represents sets as functional maps to Booleans:
$$\text{Set}\langle T \rangle \implies (\text{Array } T \text{ Bool})$$

---

## 5. Topic 4: Named Structured Try-Catch Recovery

To provide resilient transactional behavior, `FH-Native-V2` upgrades unrecoverable `abort <ErrorName>` actions into localizable Try-Catch blocks utilizing strict, named boundaries.

### 5.1 Syntax Design
```freehold
try db_transaction
    try api_call
        if id < 0 then
            abort ConnectionError
        end if
        return User { id: id, active: true }
    on ConnectionError do
        if id = -42 then
            abort DBError -- Escapes connection block and targets parent
        end if
        return User { id: 0, active: false }
    end try api_call
on DBError, SchemaError do
    return User { id: -1, active: false }
end try db_transaction
```
* **Name Match Guards:** The parser validates that `try <id>` matches `end try <id>` strictly, preventing silent block nesting overlaps.
* **Go Lowering Parity:** Mapped elegantly using anonymous closures preserving Go's structural `panic` / `recover` semantics.

---

## 6. Topic 5: State Machine Workflows, Spawns & Channels

Business workflows are asynchronous, parallel, and state-dependent. Freehold models processes as Deterministic Finite Automata (DFA) using `choice` structures coupled with lightweight scheduling actors.

```mermaid
sequenceDiagram
    participant Main as Supervisor Thread
    participant Chan as Channel<CheckoutAction>
    participant Proc as Spawned Stateful Worker
    
    Main->>Proc: spawn worker(Chan)
    Note over Proc: Enters continuous read loop
    Main->>Chan: channel_push(ProcessCheckout(150))
    Chan-->>Proc: channel_receive()
    Proc->>Proc: transition(newState)
```

### 6.1 State Transitions Safety
```freehold
function transition(state: CheckoutState, action: CheckoutAction) returns CheckoutState
ensures case state is Completed(_) => result = state | _ => true end
is
    case state is
        CartCreated =>
            case action is
                ProcessCheckout(amt) => return PaymentPending(amt)
                _                    => return Failed("Invalid action")
            end case
        PaymentPending(amt) =>
            case action is
                ConfirmSuccess(tx) => return Completed(tx)
                _                  => return state
            end case
        Completed(_) => return state
        Failed(_)    => return state
    end case
end transition
```

### 6.2 Spawns & Channels Architecture
* **`Channel<T>`:** Typed thread-safe FIFO message pipelines.
* **`spawn`:** Initiates independent, memory-isolated green fibers running concurrent loops:
  ```freehold
  spawn start_checkout_worker(queue)
  ```
* **Verification Targets:** SMT checking validates deadlock absence (buffer capacity proofs) and confirms that terminal sink states like `Completed` can never be reverted back to pending/failed.
