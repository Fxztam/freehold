# Freehold Specification: Compiler Front-end
**Status:** Baseline compiler front-end architecture, parser/AST parity model, semantic verification handoff, and bootstrap-facing conformance gates  
**Audience:** Freehold compiler implementers, parser authors, verifier authors, Go frontend maintainers, bootstrap maintainers, and test-gate owners

This document specifies the current Freehold compiler front-end model.

The compiler front-end is the part of the toolchain that turns source text into a checked, deterministic program representation:

```text
source files
  -> comments and lexical structure
  -> parser
  -> AST
  -> module graph and imports
  -> semantic/type verification
  -> normalized diagnostics
  -> verified program metadata
  -> IR/codegen/backend handoff
```

Freehold currently keeps three front-end implementation lanes in sync:

```text
Python/Lark front-end       reference grammar, AST builder, module resolver, verifier, diagnostics, test gates
Go front-end                fast parser/AST/diagnostic reference with Go-native semantic V0 slices
FH-Native-V1 front-end      self-hosting compiler front-end written in Freehold under bootstrap/compiler_core_v1
```

The core requirement is not that every lane has identical internals. The requirement is that accepted programs, rejected programs, AST shape, semantic meaning, diagnostics, and bootstrap artifacts remain deterministic and comparable at the official gates.

---

## 1. Scope

The front-end owns:

- source file structure
- comment validation
- lexical classification
- reserved keyword handling
- parsing
- AST construction
- source locations and spans
- import and module resolution
- exposed-symbol checking
- syntax diagnostics
- semantic/type diagnostics
- semantic verification handoff
- control-flow analysis handoff
- conformance artifact generation
- frontend-to-backend boundary objects

The front-end does not own:

- Go code emission details
- gRPC Go binding emission details
- WhyML emission details
- runtime library behavior
- SMT solver internals
- binary artifact serialization details after the IR boundary

Backends consume a verified representation. They must not silently reinterpret syntax or redo semantic policy differently from the front-end.

---

## 2. Front-end Lanes

### 2.1 Python/Lark Reference Front-end

The Python lane is the broadest reference lane for current language coverage.

Key implementation areas:

```text
freehold/core/parser.py
freehold/core/parser_legacy.py
freehold/core/grammar_inline.py
freehold/grammar/freehold.lark
freehold/core/ast.py
freehold/core/module_resolver.py
freehold/core/verifier.py
freehold/core/control_flow.py
freehold/core/diagnostics.py
```

The parser loads the Lark grammar with:

```text
parser="lalr"
start="start"
propagate_positions=True
```

Before parsing, the source passes through comment validation. The parse tree is then converted into the Freehold AST by the AST builder.

This lane currently provides the complete semantic/type/control-flow verification path for the broadest feature set.

### 2.2 Go Front-end

The Go lane is the fast native parser and AST/diagnostic reference.

Key implementation areas:

```text
go-frontend/internal/lexer
go-frontend/internal/token
go-frontend/internal/parser
go-frontend/internal/ast
go-frontend/internal/diagnostic
go-frontend/internal/semantic
go-frontend/cmd
```

The Go lane is expected to preserve syntax and AST parity with the reference parser. It also contains Go-native semantic V0 slices for selected record, routine, array, record-literal, name, type, assignment, and project-loader diagnostics.

It is not yet the complete semantic verifier for all Freehold rules. The full semantic, contract, abort, concurrency, generic, JSON, record, gRPC, and control-flow surface remains governed by the Python verifier and normalized gates unless a specific Go-native slice is explicitly implemented and gated.

### 2.3 FH-Native-V1 Bootstrap Front-end

The FH-Native-V1 lane is the self-hosting compiler written in Freehold itself.

Key implementation areas:

```text
bootstrap/compiler_core_v1/App/Main.fh
bootstrap/compiler_core_v1/Compiler/Core/Ast.fh
bootstrap/compiler_core_v1/Compiler/Core/Diagnostics.fh
bootstrap/compiler_core_v1/Compiler/Core/Flow.fh
bootstrap/compiler_core_v1/Compiler/Core/Lexer.fh
bootstrap/compiler_core_v1/Compiler/Core/Names.fh
bootstrap/compiler_core_v1/Compiler/Core/ParseResult.fh
bootstrap/compiler_core_v1/Compiler/Core/Parser.fh
bootstrap/compiler_core_v1/Compiler/Core/Resolve.fh
bootstrap/compiler_core_v1/Compiler/Core/Token.fh
bootstrap/compiler_core_v1/Compiler/Core/Transform.fh
bootstrap/compiler_core_v1/Compiler/Core/Verifier.fh
```

This lane is validated by bootstrap gates. The key invariant is self-hosting determinism: a compiler stage can compile the compiler source again and produce the same canonical intermediate artifact as the previous stage.

---

## 3. Source File Shape

The root grammar shape is:

```ebnf
start ::= module_decl import_decl* declaration* module_end
```

A valid Freehold source file is one module:

```freehold
module App.Main

import Domain.Types exposing Customer, make_customer
import Std.IO

procedure main()
is
    call Std.IO.log("hello")
end main

end App.Main
```

The front-end must enforce this order:

```text
module declaration
imports
declarations
matching module end
```

The opening and closing module names must match exactly.

---

## 4. Module Names And File Paths

Freehold module names are qualified names:

```freehold
module Banking.Proofs
...
end Banking.Proofs
```

The module resolver maps a module name to a file path by splitting on dots:

```text
Banking.Proofs -> Banking/Proofs.fh
App.Main       -> App/Main.fh
```

When an entry file is resolved, the front-end checks that the entry file path matches the declared module name. If an imported file declares a different module name than requested, resolution fails.

The module resolver must reject:

- missing imported modules
- cyclic imports
- syntax errors in imported modules
- imported module name mismatches
- missing exposed symbols
- invalid runtime-module exposing clauses

---

## 5. Lexer Responsibilities

The lexer turns source text into classified tokens while preserving source location information.

Required behavior:

- track source name
- track line and column
- classify identifiers and reserved keywords
- classify literals
- classify punctuation and operators
- skip whitespace
- skip valid line comments
- skip valid block comments
- reject invalid comment forms according to comment rules
- preserve enough location information for structured diagnostics

The Go and FH-Native lanes use explicit token packages/modules. The Python lane uses Lark tokenization plus the AST builder and propagated positions.

Reserved keywords must not be accepted where an identifier is required. The Go parser was intentionally tightened to match the DHParser/reference direction for keyword-as-name failures.

---

## 6. Parser Responsibilities

The parser is syntax-only.

It must build structural AST nodes from source text without performing name resolution, symbol lookup, type checking, or contract proving.

The bootstrap parser specification states this separation as the parser purity rule:

```text
Parser: syntax and AST structure
Resolver/verifier: names, imports, types, contracts, control flow
```

A parser may report structural failures such as missing names, wrong delimiters, illegal statement order, invalid top-level tokens, or malformed declarations. It must not decide whether a record field exists, whether a routine argument type is compatible, or whether a contract is provable.

---

## 7. Grammar Surface

The current grammar includes these top-level declaration families:

```text
type declarations
record declarations
choice declarations
error declarations
service declarations
function declarations
procedure declarations
task declarations
```

It includes these statement families:

```text
let
assignment
field assignment
return
abort
if
while
case
scope
check
call
parallel
```

It includes expression support for:

```text
boolean, integer, double, string literals
success/failure/result/value/error contract atoms
array literals
record literals
map literals
set literals
field access
index access
function calls
qualified calls
spawn
await
unary and binary operators
universal and existential quantifiers
```

The parser must preserve enough structure for later semantic normalization and AST-shape comparison.

---

## 8. AST Boundary

The AST is the front-end's main structured output.

The AST must preserve:

- module name
- imports and exposing clauses
- declarations
- source spans or source positions where available
- typed declaration shapes
- statement structure
- expression structure
- contract clauses
- service/rpc declarations
- concurrency constructs
- literal and call forms

The AST must not depend on map iteration order or host-runtime nondeterminism. Any serialization used for comparison must be deterministic.

The Go AST and reference AST are compared in two layers:

```text
AST shape comparison       structural outline parity
semantic AST comparison    normalized semantic-node parity
```

Both layers exist because two ASTs can have the same broad shape while differing in meaningful expression details.

---

## 9. Parse Results And Diagnostics

Parser diagnostics are structured.

A syntax diagnostic should carry:

```text
stable diagnostic code
message
source name
line
column
expected token or construct when available
found token when available
hint when available
```

Freehold reserves syntax/parser diagnostic codes in the `FH-SYN-*` range. Semantic, type, abort, contract, and tooling diagnostics use their own ranges such as `FH-SEM-*`, `FH-TYP-*`, `FH-ABT-*`, `FH-CON-*`, and `FH-BLD-*`.

The bootstrap parser uses `ParseResult` and `FH-PARSE-*` style parser results internally. The external diagnostic normalization gates map implementation-specific errors into stable Freehold diagnostic surfaces.

Parser error wording is allowed to vary between implementations. Parser status, source location, diagnostic category, and stable code are the portable contract.

---

## 10. Module Resolution

After parsing, the module resolver builds the import graph.

The resolver algorithm is:

```text
parse entry file
infer or validate module root
check entry file path against module name
record entry module
resolve imports recursively
reject cycles
verify imported modules before consumers where needed
check exposing clauses
verify the entry module with imported verified modules in scope
```

For normal modules, `import A.B` loads:

```text
A/B.fh
```

For runtime modules, the resolver may accept a configured runtime module symbol set. Exposing clauses for runtime modules are checked against that symbol set.

---

## 11. Exposed Symbols

Exposed symbols are declarations made visible through an import clause:

```freehold
import Domain.Types exposing Customer, make_customer
```

The exported symbol set includes:

```text
type declarations
record declarations
error declarations
routine declarations
```

If an exposing clause names a symbol that is not exported by the imported module, the front-end rejects the program.

The verifier also protects against ambiguous exposed symbols when multiple imports expose the same unqualified name from different modules.

---

## 12. Semantic Verification Handoff

Semantic verification starts after parsing and module resolution.

The verifier owns:

- symbol tables
- type references
- record and choice validation
- routine signatures
- generic resolution
- expression type inference
- assignment compatibility
- import-aware name lookup
- contract checking
- abort checking
- concurrency safety rules
- ghost/specification-only restrictions
- control-flow summaries
- prover handoff where configured

A front-end implementation may contain Go-native semantic checks for selected slices, but those checks must match the official diagnostic and rule behavior. If a slice is not implemented in Go, the Python verifier remains the reference gate.

---

## 13. Control Flow Handoff

Control-flow analysis is part of semantic verification, not parsing.

The Python analyzer currently summarizes routine behavior such as:

```text
normal_return_possible
guaranteed_exit
declared_aborts
emitted_aborts
called_routines
propagated_aborts
```

It analyzes statements such as:

```text
return
abort
call
let
assignment
field assignment
check
if
while
case
```

The Go front-end currently has no complete Go-native control-flow analyzer. Any Go-native CFlow work must be introduced as an explicitly gated slice and compared against the Python semantics.

---

## 14. Go Front-end Status Model

The Go front-end is strong in syntax, AST, and structured diagnostics.

Current status from the tracked status documents:

```text
parser status parity:       all tracked parser cases matching DHParser/reference status
AST shape parity:           all comparable parse-ok cases matching
semantic AST parity:        all comparable parse-ok cases matching
Go diagnostic catalog:      syntax-heavy with selected type and semantic diagnostics
Go semantic implementation: V0 slices, not full verifier parity
Go control flow:            not complete as a dedicated analyzer
```

Implemented Go-native semantic slices include:

- record field access
- record literals
- array index expressions
- local and exposed routine calls
- variable and type names
- duplicate parameters and locals
- simple assignments
- project-loader import diagnostics
- selected Result/contract expression binding support

The practical boundary is important: parser parity is mature; full semantic and control-flow parity is still an active implementation frontier.

---

## 15. FH-Native Bootstrap Model

The FH-Native-V1 compiler front-end is part of the self-hosting compiler under `bootstrap/compiler_core_v1`.

Its compiler-core modules split responsibilities similarly to the reference architecture:

```text
Lexer.fh        tokenization
Token.fh        token model
Parser.fh       recursive-descent parsing
ParseResult.fh  parser results
Ast.fh          AST representation
Resolve.fh      name and type resolution
Flow.fh         control-flow support
Verifier.fh     formal verification support
Transform.fh    lowering/IR preparation
Codegen.fh      backend emission
Diagnostics.fh  diagnostic data
```

The bootstrap gate validates determinism through repeated compilation stages. The important artifact property is:

```text
sha256(stage1.fhirb) == sha256(stage2.fhirb)
```

That comparison means the compiler source compiled by the previous stage and the compiler source compiled by the newly produced compiler yield the same canonical binary intermediate representation.

---

## 16. Determinism Rules

Every front-end lane must preserve deterministic behavior.

Required properties:

- deterministic tokenization
- deterministic parse tree to AST conversion
- deterministic import traversal outcome
- deterministic exposed-symbol handling
- deterministic diagnostic normalization
- deterministic AST/IR serialization for comparison artifacts
- no dependence on unordered map iteration for emitted order
- stable source locations for diagnostics
- stable handling of reserved words
- stable handling of comments and whitespace

If an implementation uses maps internally, it must sort keys before producing user-visible or artifact-visible output.

---

## 17. Conformance Gates

The front-end is validated by comparison and verification gates rather than by informal inspection.

Core gates include:

```text
compare-parser-status.cmd
compare-parse-errors.cmd
compare-ast-shape.cmd
compare-ast-semantic.cmd
compare-semantic-diagnostics.cmd
verify-spec-diagnostics.cmd
verify-go-semantic-diagnostics.cmd
verify-go-semantic-projects.cmd
verify-go-project-semantic-diagnostics.cmd
compare-fhir-v1.cmd
compare-ir.cmd
verify-stage3-compiler-core-v1.cmd
verify-stage3-compiler-examples.cmd
```

Not every change must run every gate. The expected gate depends on the touched layer:

```text
lexer/parser change          parser status, parse errors, AST shape, semantic AST, Go tests
AST normalization change      AST shape, semantic AST, FHIR/IR comparisons
semantic rule change          semantic diagnostics, language modules, verifier tests
module resolver change        project semantic gates and import-resolution modules
bootstrap compiler change     stage3 compiler gates
backend boundary change       FHIR/IR/codegen comparison gates
```

---

## 18. Front-end To Backend Boundary

A backend receives a verified program representation. It may lower, serialize, or emit target code, but it must not accept programs that the front-end verifier rejects.

The boundary contract is:

```text
parse success
module resolution success
semantic/type verification success
control-flow checks satisfied
feature policy checks satisfied
verified metadata available
```

When a backend does not support a front-end-valid feature, it must reject the feature explicitly with an unsupported-codegen diagnostic rather than reinterpret the source.

Examples include V1 policy-only or unsupported backend slices where the verifier accepts or rejects source first, and the backend then reports a specific unsupported feature when appropriate.

---

## 19. Relationship To Other Specifications

This document is the architectural front-end umbrella.

Detailed language rules live in feature specifications such as:

```text
SPECIFICATION-FH-BASICS.md
SPECIFICATION-FH-STATEMENTS.md
SPECIFICATION-FUNCTION-PROCEDURE-VERIFY.md
SPECIFICATION-VERIFICATION.md
SPECIFICATION-ERROR-HANDLING.md
SPECIFICATION-LOOP-INVARIANT.md
SPECIFICATION-CHOICE-MAPPING.md
SPECIFICATION-ARRAYS.md
SPECIFICATION-MAP.md
SPECIFICATION-SETS.md
SPECIFICATION-GO-BACKEND.md
```

Detailed bootstrap parser architecture is covered by:

```text
bootstrap/compiler_core_v1/Compiler/SPECIFICATION-LEXER-PARSER-OKF.md
```

The high-level role split among front-end lanes is summarized by:

```text
FREEHOLD-FRONTENDS.md
```

---

## 20. Common Failure Patterns

### 20.1 Mixing Parser And Semantics

Invalid design:

```text
parse identifier
look it up in symbol table inside parser
choose AST shape based on resolved type
```

Correct design:

```text
parse identifier as syntax
build AST node with span
resolve name during semantic verification
```

### 20.2 Backend-only Type Rejection

Invalid pipeline:

```text
parse program
skip semantic verifier
generate Go
let Go compiler report type error
```

Correct pipeline:

```text
parse program
verify semantics and types
only then generate backend output
```

### 20.3 Treating Go Semantic V0 As Full Verifier

Go-native semantic checks are useful and growing, but the full semantic reference remains Python-side unless a rule has been explicitly ported and gated in Go.

### 20.4 Non-deterministic Module Traversal

Invalid behavior:

```text
emit declarations in hash-map iteration order
```

Correct behavior:

```text
preserve source order or use a documented deterministic order
```

---

## 21. Implementation Checklist

When changing the compiler front-end, check:

- The grammar accepts and rejects the intended source shapes.
- Reserved keywords are not accepted as names.
- Comments and whitespace behave consistently across front-end lanes.
- Parser diagnostics stay structured and stable.
- AST nodes preserve source positions where diagnostics need them.
- AST shape remains comparable across Go and reference artifacts.
- Semantic AST normalization still matches for accepted cases.
- Module file paths match declared module names.
- Import cycles are rejected.
- Exposing clauses are checked for normal and runtime modules.
- Semantic checks remain in the verifier layer unless a Go-native slice is deliberately implemented.
- New semantic diagnostics have stable codes and expected manifests.
- Backend unsupported-feature rejection happens after front-end validation.
- Bootstrap-facing changes preserve deterministic stage artifacts.

A healthy Freehold front-end keeps syntax, AST, diagnostics, semantic verification, and bootstrap determinism in separate but comparable layers. That separation is what lets Python tooling, Go tooling, and the self-hosting Freehold compiler evolve together without quietly accepting different languages.
