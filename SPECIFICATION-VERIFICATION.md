# Freehold Formal Verification: Completed Features Specification
**Format Reference:** Google Open Knowledge Format (OKF) & Architectural Design Blueprint  

This specification lists the active, formally verified, and mathematically-proven language features supported by the Freehold Symbolic Verifier and compiler core. All features are fully implemented, automated, and tested within the E2E verification suites.

---

## 1. Transitive Context Propagation in Nested Blocks

Ensures complete, continuous propagation of imported definitions, module scopes, and local state assertions through deeply nested iterative blocks (`while`), conditional branches (`if`/`else`), pattern case divisions (`case`), and concurrent boundaries (`scope`).

### 1.1 Specification & SMT-LIB v2 Mapping
During the recursive post-order traversal (`walk_body`), the verification context (composed of variables environment `env`, path conditions, local substitutions, imported module routing, and choice sum type definitions) is threaded continuously:
* **Conditional Branching (`IfStmt`):**
  Yields parallel verification paths. On branch entry, path conditions are augmented with `cond_smt` (for `then`) and `(not cond_smt)` (for `else`).
* **Iterative Loops (`WhileStmt`):**
  Locally mutated variables are havoked directly in the substitutions maps. Loop invariants are assumed under `path_conditions` for the loop body and post-loop context, ensuring mathematical induction constraints across the nested scope.
* **Pattern Case Branches (`CaseStmt`):**
  Splits execution into distinct sub-walk paths. In constant branches, `(= expr_smt val_smt)` is asserted. In custom pattern-matching sum-type constructors, constructor-specific tags and deconstructed inner parameters are bound.

---

## 2. Tagged Union (Choice Typ) Exhaustiveness Analysis

Ensures that pattern-matching `case` checks on algebraic sum types (`choice`) are mathematically complete, guaranteeing that no unhandled state can cause a runtime crash.

### 2.1 Specification & SMT-LIB v2 Mapping
For a choice sum type $C$ with constructors $K_1, K_2, \dots, K_n$, the verifier issues a set of formal axioms and a proof obligation if no general `default` catch-all branch is declared:
1. **Sum-Type Coverage (Exhaustiveness Axiom):**
   Every value of type $C$ must belong to at least one of its constructors:
   $$(or\ \text{expr\_is\_}K_1\ \text{expr\_is\_}K_2\ \dots\ \text{expr\_is\_}K_n)$$
2. **Mutual Exclusivity Axiom:**
   No value can belong to more than one constructor simultaneously:
   $$\forall i < j.\ (not\ (and\ \text{expr\_is\_}K_i\ \text{expr\_is\_}K_j))$$
3. **Branch Completeness Proof Obligation:**
   Each pattern branch $i$ yields a clause $Branch_i \equiv \text{expr\_is\_}K_i \land Guard_i$. The verifier forces a proof obligation that the disjunction of all branches is a semantic tautology under top-level path conditions:
   $$\text{Obligation: } (or\ Branch_1\ Branch_2\ \dots\ Branch_k)$$
   Z3 evaluates the validity of the obligation. If there are unmapped configurations, Z3 returns a satisfiable counter-example state (`SAT`), and the verifier rejects the module.

---

## 3. Map (Associative Array) Finiteness and Termination

Enables formal termination proofs of loops iterators acting on dynamic, key-value collection mapping, overcoming SMT-LIB's default treatment of Maps as infinite functional arrays.

### 3.1 Specification & SMT-LIB v2 Mapping
To provide decidable finite cardinality on associative arrays `Map<Key, Value>`, Freehold implements uninterpreted size tracking functions constrained by inductive axioms:
1. **Empty Map Base Case Axiom:**
   $$(assert\ (= (Map\_size\ empty\_map)\ 0))$$
2. **Destructive Shrinkage Axiom:**
   In deleting an existing mapped key $k$ from map $m$, the resulting size decreases exactly by one:
   $$(assert\ (\forall ((m\ (Array\ String\ Value))\ (k\ String))$$
   $$\implies\ (not\ (= (select\ m\ k)\ default\_val))$$
   $$(= (Map\_size\ (store\ m\ k\ default\_val))\ (-\ (Map\_size\ m)\ 1))))$$
3. **Strict Loop Monotonicity Proof Obligation:**
   For loops processing maps dynamically (e.g., via popping/deleting keys using `Map.remove`), the loop variant $V(m) = \text{Map\_size}(m)$ must satisfy:
   - **Lower Bound Security:** $V(m_{after}) \ge 0$
   - **Decreasing Step Guarantee:** $V(m_{after}) < V(m_{before})$
   This guarantees that dynamic map iteration loops must terminate after a finite number of execution steps.

---

## 4. Formal Concurrency Verification (Spawns & Channels)

Guarantees thread safety, data alignment, and call-constraint validation across parallel threads of execution.

### 4.1 Channel Invariant Verifications
Ensures that all messages passed over FIFO pipelines (`Channel<T>`) follow the channel's declared state invariant.
* **On Send (`channel_send`/`channel_try_send`):**
  The sent value is substituted directly into the channel's invariant expression. The verifier pushes an active verification obligation (`kind: "channel_invariant"`) requiring Z3 to prove that the state satisfies the contract.
* **On Receive (`channel_receive`):**
  The invariant is assumed, propagating the contract properties downstream as active path conditions.

### 4.2 Task Spawn Precondition Checking
Statically proves that the arguments supplied to newly-spawned fibers satisfy the asynchronous routine's entry preconditions (`requires`).
* **On Spawn (`spawn`):**
  Caller-supplied variables are substituted into the callee routine's `requires` clauses. The solver evaluates the callee's precondition as an active proof obligation against the caller's current execution frame.

---

## 5. Specification-Only Sets (Ghost Sets)

Enables mathematical validation of collection properties, set containment, additions, and removals directly inside preconditions, postconditions, and loop invariants with exactly zero footprint inside the compiled executable.

### 5.1 Specification & SMT-LIB v2 Mapping
We model `Set<T>` natively in Z3 as functional boolean arrays:
$$\text{Set}\langle T \rangle \implies (\text{Array } T \text{ Bool})$$
where an element $x \in S \iff (\text{select } S\ x) = \text{true}$.

1. **Set Literal Expression:**
   A set literal declaring `{x1, x2, ..., xn}` is compiled inside [freehold/core/symbolic.py](freehold/core/symbolic.py) to a sequence of `store` updates on an empty constant array:
   $$((as\ const\ (Array\ T\ Bool))\ false)$$
   For each item $x_i$, a `store` operation is applied:
   $$(store\ S\ x_i\ true)$$

2. **Containment Axiom:**
   Evaluating if an element is present inside the Set maps directly to Z3's array selection theory in [freehold/core/symbolic.py](freehold/core/symbolic.py):
   $$\text{Set.contains}(S, x) \implies (select\ S\ x)$$

3. **Pure Element Operations (`Set.add` and `Set.remove`):**
   * **Addition (`Set.add`):**
     Adding an element $x$ returns a brand-new set $S'$ represented by a store operation:
     $$S' = \text{Set.add}(S, x) \implies (store\ S\ x\ true)$$
   * **Removal (`Set.remove`):**
     Removing an element $x$ yields a store operation resetting the index mapping to false:
     $$S' = \text{Set.remove}(S, x) \implies (store\ S\ x\ false)$$

4. **Set Cardinality (`Set.size`):**
   Similar to associative sizes, set cardinality maps to an uninterpreted function size tracker `Set_size` with the literal base and induction rules:
   $$\text{Set.size}(S) \implies (Set\_size\ S)$$
   $$\text{Set\_size}(S) \ge 0$$
   With set literal evaluation mapping directly to the constant:
   $$\text{Set.size}(\{e_1, \dots, e_k\}) = k$$

### 5.2 Ghost Validation Enforcements
To guarantee absolutely zero program runtime overhead, `Set<T>` usage is statically checked during syntax verification inside [freehold/core/verifier.py](freehold/core/verifier.py) and is strictly restricted:
- **No Executable Variables:** Any local `let` declaration holding a `Set<T>` variable is rejected.
- **No Parameter/Return Routine Footprints:** Functions and procedures are prohibited from accepting sets as parameters or returning set structures.
- **No State Fields:** Structs, records, and choice variants are completely restricted from declaring fields of type `Set<T>`.

In this way, Sets represent pure mathematical elements used only for writing robust loop invariants, preconditions, and postconditions.
