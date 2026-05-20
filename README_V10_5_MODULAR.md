# Freehold v11f Native Strings

Goal: **formal verification system for AI**.

v10.5 restructures the compiler so future language features can be added as controlled compiler add-ons.

## Structure

```text
freehold/
  core/
    ast.py
    parser.py
    verifier.py
    interpreter.py
    cfg.py
    symbolic.py
    registry.py
    feature.py
  grammar/
    freehold.ebnf
    freehold.lark
  features/
    core/
    control/
    arrays/
    result/
    records/
    cfg_smt/
  tests/
    regression_cases.py
    run_modular_tests.py
```

## Run

```bash
python run_modular_tests.py --log modular.log --json-summary modular_summary.json
```

## Current expected result

```text
82/82 tests matched expectation
```

## Security policy

```text
No preprocessor.
No hidden compiler flags.
No automatic semantic changes from comments.
External grammar required.
Features must ship tests.
```


## Generated EBNF

v10.5 now includes a generator:

```bash
python tools/lark_to_ebnf.py
python -m freehold ebnf --dialects
```

It reads:

```text
freehold/grammar/freehold.lark
```

and writes:

```text
freehold/grammar/freehold.generated.ebnf
```

With `--dialects`, it also writes:

```text
freehold/grammar/freehold.generated.forge.ebnf
freehold/grammar/freehold.generated.forge.ir.json
freehold/grammar/freehold.generated.rr.ebnf
freehold/grammar/freehold.generated.vscode.ebnf
freehold/grammar/freehold.generated.pyebnf.ebnf
freehold/grammar/freehold.generated.parseebnf.ebnf
```

Recommended policy:

```text
freehold.lark            executable parser grammar / source of truth
freehold.generated.ebnf  generated review/documentation grammar
freehold.generated.forge.ebnf  generated EBNF Forge validator dialect
freehold.generated.forge.ir.json generated EBNF Forge JSON IR
freehold.generated.rr.ebnf     generated railroad/W3C-style dialect
freehold.generated.vscode.ebnf generated VS Code EBNF plugin dialect
freehold.generated.pyebnf.ebnf generated pyebnf Python checker dialect
freehold.generated.parseebnf.ebnf generated parse-ebnf PyPI test dialect
freehold.ebnf            curated human language specification
```

Use `freehold.generated.vscode.ebnf` for the VS Code EBNF plugin. The RR file is intended for railroad/W3C-style tools and may use syntax the VS Code plugin does not accept.
Use `freehold.generated.parseebnf.ebnf` for the `parse-ebnf` PyPI parser, which requires alphanumeric rule identifiers.
Use `freehold.generated.forge.ebnf` for the EBNF Forge `ebnff` validator. Use `tools/ebnff.exe` to regenerate `freehold.generated.forge.ir.json`. Use `freehold.generated.pyebnf.ebnf` for the Python `pyebnf` checker.

TODO:

```text
Keep tools/ebnff.exe in sync with _tools/EBNF-Forge/ebnff.exe when the Forge validator changes.
```

## v11a assignment rule

```text
let x: T = expr       Definition / binding
x := expr             Mutation / state change
record.field := expr  Field mutation / state change
x = y                 Equality expression only
```


## v11b import rule

```freehold
module App.Main

import Banking.Proofs
import Banking.Proofs exposing balance_never_negative
import Banking.Types exposing Account, Customer
```

Current v11b scope:

```text
imports are parsed into AST
duplicate imports are rejected
self-import is rejected
duplicate exposing symbols are rejected
multi-file resolution is planned later
qualified calls remain a design goal
```


## v11c qualified end rule

```freehold
module App.Main
procedure main()
is
    if true then
        check true
    end if
end main
end App.Main
```

Rules:

```text
module       -> end Module.Name
function     -> end function_name
procedure    -> end procedure_name
record       -> end record
if           -> end if
while        -> end while
naked end    -> syntax error
wrong names  -> parser/verifier error
```


## v11d case rule

```freehold
case expr is
    when value =>
        ...
    default =>
        ...
end case
```

Rules: mandatory default, no fallthrough, type-compatible branch values, duplicate literal branches rejected.


## v11e comments

```freehold
-- line comment

/*
block comment
*/

/**
@ai intent:
Structured AI/documentation comment.
*/
```

Policy:

```text
comments are ignored by parser/verifier/interpreter
no preprocessor
no hidden compiler flags
no automatic semantic change from comments
```

## Numeric base types

```text
Double is Freehold's IEEE-754 64-bit floating point type.
Its intended role is equivalent to Go float64.
No separate Float64 alias is currently defined.
BigInteger and BigFloat are arbitrary-precision types exposed by module Big.
```

## v11f native strings

```freehold
let s: String = "hello"
let t: String = String.concat(s, " world")
let p: String = String.substr(t, 0, 5)
let r: String = String.replace(t, "world", "Freehold")
let i: Integer = String.instr(t, "Flow")
```

Rules:

```text
String is a native base type.
String.* operations are explicit.
String.substr is bounds checked.
String.instr returns 0-based index or -1.
String arithmetic is rejected.
```
