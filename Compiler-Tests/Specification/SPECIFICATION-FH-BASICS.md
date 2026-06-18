# Freehold Specification: Program Basics, Modules, and Imports
**Status:** Baseline language structure, module resolution, and import model  
**Audience:** Authors of Freehold programs, examples, tests, and generated modules

This document explains the safe basic structure of a Freehold program, beginning with the module principle and the nested module naming model. It also describes the available import forms and the rules that keep multi-module programs deterministic and verifiable.

---

## 1. Source File Shape

A Freehold source file is one module. The top-level grammar shape is:

```ebnf
start ::= module_decl import_decl* declaration* module_end
```

In practice, this means every file follows this order:

```freehold
module App.Main

import Domain.Types exposing Customer, make_customer
import Std.IO

type LocalId is Integer range 0..2147483647

procedure main()
is
    call Std.IO.log("hello")
end main

end App.Main
```

The safe rule is simple: declare the module first, then imports, then declarations, and close the file with the exact same module name.

---

## 2. Module Names and Nested Module Principle

### 2.1 Qualified Module Names

Freehold modules use qualified names:

```freehold
module App.Main
...
end App.Main
```

A qualified name is an identifier path separated by dots:

```ebnf
qualified_name ::= IDENT ('.' IDENT)*
```

Examples:

```text
App.Main
Banking.Types
Banking.Proofs
Compiler.Core.Parser
Domestic.Reports
Partner.Shared
```

### 2.2 Nested Modules Are Naming and File-Tree Structure

Freehold does not place one module declaration inside another module body. Instead, nesting is expressed by the qualified module name and the file path used by the resolver.

The conceptual mapping is:

```text
Banking.Types  -> Banking/Types.fh
Banking.Proofs -> Banking/Proofs.fh
App.Main       -> App/Main.fh
```

This gives Freehold a stable namespace tree without introducing nested lexical module scopes inside a single source file.

### 2.3 Module End Must Match

The closing module declaration must repeat the exact module name:

```freehold
module App.Main

procedure main()
is
    check true
end main

end App.Main
```

This is rejected:

```freehold
module App.Main

procedure main()
is
    check true
end main

end App.Other
```

Matching the closing name protects generated code, diagnostics, and import resolution from accidentally binding a file to the wrong namespace.

---

## 3. Safe Program Skeleton

### 3.1 Minimal Executable Module

An executable-style module normally exposes a `main` procedure:

```freehold
module Hello

procedure main()
is
    check true
end main

end Hello
```

For command-line or demo modules, keep `main` small. It should orchestrate calls, create top-level values, and delegate domain work into functions or procedures.

### 3.2 Recommended Declaration Order

Within a module, use this order unless there is a strong reason not to:

1. `type` aliases and ranged scalar types
2. `record` types
3. `choice` types
4. `error` declarations
5. `service` declarations
6. pure functions
7. procedures and tasks
8. `main`

Example:

```freehold
module Domain.Customers

type CustomerId is Integer range 1..2147483647

type Customer is record
    id: CustomerId
    name: String
end record

error NotFound

function make_customer(id: CustomerId, name: String) returns Customer
ensures result.id = id
is
    return Customer { id: id, name: name }
end make_customer

end Domain.Customers
```

### 3.3 Contracts Before Bodies

Routine contracts are written between the routine signature and `is`:

```freehold
function inc(x: Integer) returns Integer
requires x < 2147483647
ensures result = x + 1
is
    return x + 1
end inc
```

For mutating routines, declare the mutation frame explicitly:

```freehold
type Cell is record
    val: Integer
end record

procedure bump(c: Cell)
modifies c.val
is
    c.val := c.val + 1
end bump
```

The safe habit is: if a routine writes to a parameter, field, array element, or global, write the corresponding `modifies` clause before the body.

---

## 4. Import Model

### 4.1 Plain Import

A plain import makes the module available by its qualified name:

```freehold
module App.Main

import Std.IO
import Domain.Customers

procedure main()
is
    call Std.IO.log("starting")
end main

end App.Main
```

Use plain imports when you want to keep call sites explicit and avoid local-name conflicts.

### 4.2 Import With Exposing

An exposing import brings selected symbols into the local namespace:

```freehold
module App.Main

import Domain.Customers exposing Customer, make_customer

procedure main()
is
    let c: Customer = make_customer(1, "Ada")
    check c.id = 1
end main

end App.Main
```

The exposing list may contain exported types, records, errors, and routines declared by the imported module.

### 4.3 Multiple Imports

A module may import multiple modules:

```freehold
module App.Main

import Banking.Types
import Banking.Proofs exposing balance_never_negative, transfer_preserves_total
import Std.IO

procedure main()
is
    call Std.IO.log("banking checks ready")
end main

end App.Main
```

Each imported module may appear only once in the same file.

### 4.4 Qualified Access Versus Exposed Access

Prefer qualified access when two imported modules may export the same symbol names:

```freehold
module App.Main

import Domestic.Reports
import Partner.Reports

function total(seed: Integer) returns Integer
requires seed > 0
is
    let domestic: Domestic.Reports.DomesticReport = Domestic.Reports.load_domestic(seed)
    let partner: Partner.Reports.PartnerReport = Partner.Reports.load_partner(seed)
    return domestic.order.address.city_id + partner.order.address.city_id
end total

end App.Main
```

Use exposing when the names are intentionally part of the local vocabulary and there is no ambiguity:

```freehold
import Domain.Orders exposing Order, load_orders
```

### 4.5 Runtime and Standard Modules

Runtime modules such as `Std.IO` are imported the same way as user modules:

```freehold
import Std.IO

procedure main()
is
    call Std.IO.log("hello")
end main
```

The same principle applies to other standard/runtime modules as they are added: keep imports explicit and prefer qualified calls for operational effects.

---

## 5. Import Safety Rules

### 5.1 No Self Imports

A module cannot import itself:

```freehold
module App.Main
import App.Main
end App.Main
```

Move shared definitions into a third module when two modules need common declarations.

### 5.2 No Duplicate Imports

This is rejected:

```freehold
import Banking.Proofs
import Banking.Proofs
```

Keep each module import unique. If you need both qualified and exposed access, use one import with an exposing list and call qualified names only when they remain available through the module namespace.

### 5.3 No Duplicate Exposed Symbols

This is rejected:

```freehold
import Banking.Proofs exposing balance_never_negative, balance_never_negative
```

Each symbol may appear only once in the exposing list.

### 5.4 Exposed Symbols Must Exist

This is rejected if `NonExistentType` is not declared by `Test.Support`:

```freehold
import Test.Support exposing Point, NonExistentType
```

The resolver checks exposed names against the imported module's exported declarations.

### 5.5 Ambiguous Exposed Symbols

If two imports expose the same local name, the local namespace becomes ambiguous. Prefer qualified imports in that case:

```freehold
import Domestic.Orders
import Partner.Orders
```

Then call routines through their module path rather than exposing both into the same local scope.

### 5.6 No Cyclic Imports

Imports must not form a cycle. This pattern is invalid:

```text
A imports B
B imports A
```

Refactor shared declarations into a third module:

```text
Shared.Types
A imports Shared.Types
B imports Shared.Types
```

---

## 6. Building a Safe Multi-Module Program

### 6.1 Split by Responsibility

Use modules to separate responsibilities:

```text
Domain.Types       records, ranged types, choices, errors
Domain.Validation  functions that prove domain invariants
Domain.Services    service declarations and RPC records
App.Main           orchestration and executable entry point
```

This keeps import direction predictable: application modules depend on domain modules, not the other way around.

### 6.2 Put Shared Types Low in the Tree

When multiple modules need the same record or error type, place it in a low-level shared module:

```freehold
module Domain.Types

type Address is record
    city_id: Integer
    label: String
end record

error NotFound

end Domain.Types
```

Then import it where needed:

```freehold
import Domain.Types exposing Address, NotFound
```

### 6.3 Avoid Wide Exposing Lists in Application Modules

Wide exposing lists are convenient, but they can make large programs harder to audit. Prefer this pattern:

```freehold
import Domain.Types exposing Customer, Order
import Domain.Orders
```

Use exposed names for data types that are central to the file, and qualified calls for routines that perform work:

```freehold
let orders: Array<Order, 2> = Domain.Orders.load_orders(customer.id)
```

### 6.4 Make Effects Visible

Procedures, tasks, I/O calls, channel operations, and record/array updates should be easy to spot. Safe modules make effects visible through:

- `call` statements for procedures,
- qualified runtime calls such as `Std.IO.log`,
- `modifies` clauses for mutation,
- channel types for concurrent communication,
- `aborts` clauses for declared failure paths.

---

## 7. File and Module Resolution

The module resolver expects the imported file to declare the module name used by the import. If a file is loaded as `Banking.Proofs`, it must begin with:

```freehold
module Banking.Proofs
```

and end with:

```freehold
end Banking.Proofs
```

If the file declares a different module name, resolution fails with an imported module name mismatch.

The resolver also checks that imported files parse before they are verified. Syntax errors in imported modules must be fixed at the source module, not worked around at the importing site.

---

## 8. Minimal Project Example

### 8.1 `Domain/Customers.fh`

```freehold
module Domain.Customers

type CustomerId is Integer range 1..2147483647

type Customer is record
    id: CustomerId
    name: String
end record

function make_customer(id: CustomerId, name: String) returns Customer
ensures result.id = id
is
    return Customer { id: id, name: name }
end make_customer

end Domain.Customers
```

### 8.2 `App/Main.fh`

```freehold
module App.Main

import Domain.Customers exposing Customer, make_customer
import Std.IO

procedure main()
is
    let customer: Customer = make_customer(1, "Ada")
    check customer.id = 1
    call Std.IO.log("customer loaded")
end main

end App.Main
```

This structure is safe because:

- each file declares exactly one module,
- qualified module names match their closing `end` declarations,
- imports appear before declarations,
- only required symbols are exposed locally,
- I/O remains qualified through `Std.IO`,
- the domain module has no dependency on the application module.

---

## 9. Practical Checklist

Before committing a Freehold module, check:

- The file starts with `module Name`.
- The file ends with `end Name` using the exact same qualified name.
- Imports are listed before declarations.
- The module does not import itself.
- No module is imported twice.
- Every exposed symbol is actually declared by the imported module.
- Exposing does not create ambiguous local names.
- Shared types live in lower-level modules.
- Mutating routines declare `modifies` clauses.
- Entry modules keep `main` small and delegate domain logic.

The result is a program structure that is easy to resolve, easy to verify, and predictable for all Freehold frontends and backends.