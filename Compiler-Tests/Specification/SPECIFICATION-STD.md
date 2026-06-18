# Freehold Specification: Standard Library
**Status:** Baseline specification for trusted standard runtime modules covering Math, Big numbers, Std.IO, and logging  
**Audience:** Freehold authors, standard-library maintainers, verifier implementers, runtime/backend authors, and test writers

This document specifies the current Freehold standard-library foundation for the modules most commonly used by compiler and application code:

```text
Math        numeric helper functions over Integer/Double
Big         arbitrary-precision BigInteger and BigFloat helpers
Std.IO      console logging and formatted logging procedures
String      template support used by Std.IO.logf
```

The standard library is not all implemented as ordinary source files. Some modules are trusted runtime modules that are known to the verifier, interpreter, and Go backend. They are still used through normal Freehold import and qualified-call syntax.

---

## 1. Standard Library Model

Freehold's standard library currently has two visible forms:

```text
source-level wrapper modules
trusted runtime modules
```

A source-level wrapper module is a normal `.fh` module whose declarations expose stable signatures. The root `Big.fh` module is an example.

A trusted runtime module is a module whose implementation is provided by the host runtime or backend. `Math` and `Std.IO` are examples in the current Go/Python runtime path.

The user-facing rule is the same in both cases:

```freehold
import Std.IO exposing log, logf

procedure main()
is
    call Std.IO.log("hello")
end main
```

Standard-library calls are not syntax. They are ordinary qualified names with special verifier/runtime knowledge behind them.

---

## 2. Runtime Module Imports

The current Go backend recognizes these runtime module exports:

```text
Math    sin cos tan sqrt pow abs min max floor ceil
Std.IO  log logf log_int log_bool log_double
Big     int integer fromInteger float floatFromInteger
        addInt subInt mulInt divInt negInt absInt signInt
        addFloat subFloat mulFloat divFloat sqrt absFloat signFloat
        toString format
```

Runtime modules may be imported like ordinary modules:

```freehold
import Std.IO
import Std.IO exposing logf
```

When `exposing` is used, the exposed name must exist in the runtime module's export set. A misspelled exposed runtime symbol is a semantic error.

The backend maps runtime modules to explicit Go imports:

```text
Math    -> math
Std.IO  -> fmt
Big     -> math/big
```

This keeps runtime dependencies visible in generated code rather than treating them as invisible global functions.

---

## 3. Math Module

`Math` is a top-level trusted runtime module.

It is used through qualified expression calls:

```freehold
Math.sin(value)
Math.sqrt(value)
Math.pow(base, exponent)
```

Math calls are expressions, not `call` statements.

Valid examples:

```freehold
function higher(a: Double, b: Double) returns Double
ensures result >= a, result >= b
is
    return Math.max(a, b)
end higher

function floor_val(d: Double) returns Integer
is
    return Math.floor(Math.max(d, 0.0))
end floor_val
```

---

## 4. Math Operations

The current Math surface is:

```text
Math.sin(value)          -> Double
Math.cos(value)          -> Double
Math.tan(value)          -> Double
Math.sqrt(value)         -> Double
Math.pow(base, exponent) -> Double
Math.abs(value)          -> Integer or Double, matching the argument category
Math.min(left, right)    -> Integer if both Integer, otherwise Double
Math.max(left, right)    -> Integer if both Integer, otherwise Double
Math.floor(value)        -> Integer
Math.ceil(value)         -> Integer
```

Argument rules:

- Math arguments must be numeric expressions.
- Trigonometric and square-root operations produce `Double`.
- `Math.pow` accepts two numeric expressions and produces `Double`.
- `Math.floor` and `Math.ceil` are intended for `Double` input and produce `Integer`.
- `Math.abs` preserves `Integer` when the argument is integer-like, otherwise produces `Double`.
- `Math.min` and `Math.max` preserve `Integer` only when both arguments are `Integer`; mixed or double input produces `Double`.

Known diagnostics:

```text
VF-MA001 wrong Math argument count
VF-MA002 Math argument type mismatch
```

The diagnostic hints describe Math arguments as numeric and show call shapes such as `Math.sin(value)`, `Math.sqrt(value)`, `Math.pow(base, exponent)`, and `Math.min(left, right)`.

---

## 5. Math Runtime Mapping

The interpreter maps Math calls to host math functions:

```text
Math.sin    -> math.sin
Math.cos    -> math.cos
Math.tan    -> math.tan
Math.sqrt   -> math.sqrt, with domain check for negative input
Math.pow    -> math.pow
Math.abs    -> abs
Math.min    -> min
Math.max    -> max
Math.floor  -> math.floor
Math.ceil   -> math.ceil
```

The Go backend maps Math calls to the Go `math` package:

```text
Math.sin    -> math.Sin(float64(value))
Math.cos    -> math.Cos(float64(value))
Math.tan    -> math.Tan(float64(value))
Math.sqrt   -> math.Sqrt(float64(value))
Math.pow    -> math.Pow(float64(base), float64(exponent))
Math.floor  -> int64(math.Floor(float64(value)))
Math.ceil   -> int64(math.Ceil(float64(value)))
Math.abs    -> math.Abs(float64(value)), cast to int64 when Integer is expected
Math.min    -> math.Min(float64(left), float64(right)), cast to int64 when Integer is expected
Math.max    -> math.Max(float64(left), float64(right)), cast to int64 when Integer is expected
```

`Math.sqrt` must reject a negative runtime value in interpreter-style execution with a domain error.

---

## 6. Big Number Types

Freehold has two arbitrary-precision base types:

```text
BigInteger
BigFloat
```

They are base types in the language grammar and are distinct from `Integer` and `Double`.

Use `BigInteger` for arbitrary-precision integer values:

```freehold
let big: BigInteger = Big.fromInteger(99)
```

Use `BigFloat` for arbitrary-precision decimal-style floating values with an explicit precision:

```freehold
let pi: BigFloat = Big.float("3.1415926535", 256)
```

Big number operations do not implicitly convert ordinary `Integer` or `Double` arguments. Convert explicitly.

---

## 7. Big Module

`Big` is a trusted runtime arbitrary-precision number module.

The root `Big.fh` wrapper documents the public shape and forwards each declaration to the trusted `Big.*` implementation.

Construction and conversion:

```text
Big.int(text: String) -> BigInteger
Big.integer(text: String) -> BigInteger
Big.fromInteger(item: Integer) -> BigInteger
Big.float(text: String, precisionBits: Integer) -> BigFloat
Big.floatFromInteger(item: BigInteger, precisionBits: Integer) -> BigFloat
Big.toString(item: BigInteger) -> String
Big.format(item: BigFloat, digits: Integer) -> String
```

Integer operations:

```text
Big.addInt(left: BigInteger, right: BigInteger) -> BigInteger
Big.subInt(left: BigInteger, right: BigInteger) -> BigInteger
Big.mulInt(left: BigInteger, right: BigInteger) -> BigInteger
Big.divInt(left: BigInteger, right: BigInteger) -> BigInteger
Big.negInt(item: BigInteger) -> BigInteger
Big.absInt(item: BigInteger) -> BigInteger
Big.signInt(item: BigInteger) -> Integer
```

Float operations:

```text
Big.addFloat(left: BigFloat, right: BigFloat) -> BigFloat
Big.subFloat(left: BigFloat, right: BigFloat) -> BigFloat
Big.mulFloat(left: BigFloat, right: BigFloat) -> BigFloat
Big.divFloat(left: BigFloat, right: BigFloat) -> BigFloat
Big.sqrt(item: BigFloat) -> BigFloat
Big.absFloat(item: BigFloat) -> BigFloat
Big.signFloat(item: BigFloat) -> Integer
```

---

## 8. BigInteger Rules

`BigInteger` operations require `BigInteger` operands.

Valid:

```freehold
function big_sum(a: Integer, b: Integer) returns BigInteger
requires a >= 0, b >= 0
is
    let ba: BigInteger = Big.fromInteger(a)
    let bb: BigInteger = Big.fromInteger(b)
    return Big.addInt(ba, bb)
end big_sum
```

Invalid:

```freehold
function bad_add(a: Integer, b: Integer) returns BigInteger
is
    return Big.addInt(a, b)
end bad_add
```

Reason: `Big.addInt` expects `BigInteger`, not `Integer`.

`Big.divInt` rejects division by zero during interpreter/runtime evaluation.

The Python runtime implements `Big.divInt` with truncation toward zero for signed integer division.

---

## 9. BigFloat Rules

`BigFloat` values carry a precision in bits.

A precision argument must be a positive `Integer`:

```freehold
let value: BigFloat = Big.float("1.25", 128)
```

Invalid precision values are runtime/verification errors in the trusted runtime boundary.

`Big.floatFromInteger` converts from `BigInteger`, not from ordinary `Integer`:

```freehold
let n: BigInteger = Big.fromInteger(42)
let f: BigFloat = Big.floatFromInteger(n, 256)
```

Float arithmetic preserves or combines precision according to runtime rules. The current Python runtime uses the maximum precision of both operands for binary BigFloat operations.

`Big.divFloat` rejects division by zero. `Big.sqrt` rejects negative input.

`Big.format(value, digits)` requires a non-negative integer digit count and returns a decimal string.

---

## 10. Big Runtime Mapping

The Python runtime uses `decimal.Decimal` and wrapper values for `BigIntegerValue` and `BigFloatValue`.

The Go backend maps Big types and operations to `math/big`:

```text
BigInteger -> *big.Int
BigFloat   -> *big.Float
```

Selected Go mappings:

```text
Big.int(text)                         -> freeholdBigInt(text)
Big.integer(text)                     -> freeholdBigInt(text)
Big.fromInteger(item)                 -> big.NewInt(item)
Big.float(text, precisionBits)        -> freeholdBigFloat(text, precisionBits)
Big.floatFromInteger(item, precision) -> freeholdBigFloatFromInteger(item, precision)
Big.addInt(left, right)               -> new(big.Int).Add(left, right)
Big.subInt(left, right)               -> new(big.Int).Sub(left, right)
Big.mulInt(left, right)               -> new(big.Int).Mul(left, right)
Big.divInt(left, right)               -> new(big.Int).Quo(left, right)
Big.negInt(item)                      -> new(big.Int).Neg(item)
Big.absInt(item)                      -> new(big.Int).Abs(item)
Big.signInt(item)                     -> int64(item.Sign())
Big.addFloat(left, right)             -> new(big.Float).SetPrec(left.Prec()).Add(left, right)
Big.subFloat(left, right)             -> new(big.Float).SetPrec(left.Prec()).Sub(left, right)
Big.mulFloat(left, right)             -> new(big.Float).SetPrec(left.Prec()).Mul(left, right)
Big.divFloat(left, right)             -> new(big.Float).SetPrec(left.Prec()).Quo(left, right)
Big.sqrt(item)                        -> new(big.Float).SetPrec(item.Prec()).Sqrt(item)
Big.absFloat(item)                    -> freeholdBigFloatAbs(item)
Big.signFloat(item)                   -> int64(item.Sign())
Big.toString(item)                    -> item.String()
Big.format(item, digits)              -> item.Text('f', int(digits))
```

The Go backend marks Big usage as requiring helper functions for parsing and BigFloat construction.

---

## 11. Std.IO Module

`Std.IO` is the current console output module.

The public baseline surface is:

```text
Std.IO.log(value)
Std.IO.logf(template, values...)
```

Additional typed backend/runtime exports exist for compatibility:

```text
Std.IO.log_int
Std.IO.log_bool
Std.IO.log_double
```

The normal user-facing APIs are `log` and `logf`.

`Std.IO` procedures are called with `call`:

```freehold
procedure main()
is
    call Std.IO.log("hello")
    call Std.IO.logf("answer = ${}", 42)
end main
```

Do not use `Std.IO.logf(...)` as an expression. It is a procedure call.

---

## 12. Logging Semantics

`Std.IO.log(value)` prints one value.

`Std.IO.logf(template, values...)` renders a Freehold string template and prints the rendered string.

Valid examples:

```freehold
procedure log_integer(n: Integer)
is
    call Std.IO.logf("n = ${}", n)
end log_integer

procedure log_two(a: Integer, b: String)
is
    call Std.IO.logf("a=${}, b=${}", a, b)
end log_two

procedure log_static()
is
    call Std.IO.logf("Programm gestartet")
end log_static
```

The interpreter maps:

```text
Std.IO.log  -> print(value)
Std.IO.logf -> render template, then print(result)
```

The Go backend maps:

```text
Std.IO.log(value)         -> fmt.Println(value)
Std.IO.logf(template)     -> fmt.Println(template)
Std.IO.logf(template, xs) -> fmt.Println(rendered template)
```

---

## 13. String Template Rules For logf

`Std.IO.logf` uses the same string-template rules as `String.template`.

Placeholders are:

```text
${}       positional placeholder
${name}   named placeholder
```

The older `{}` form is intentionally not accepted.

The template argument count must match the placeholders:

```freehold
call Std.IO.logf("a=${}, b=${}", a, b)
```

Invalid:

```freehold
call Std.IO.logf("${} und ${}", n)
```

Reason: the template has two positional placeholders but only one value.

Template values must be scalar display values:

```text
String
Integer
Boolean
Double
```

The current template diagnostics share the string-template diagnostic family and hints, including exact placeholder count, named binding, duplicate binding, unused binding, and display-value type errors.

---

## 14. Import And Exposing Patterns

Both qualified and exposed forms are valid:

```freehold
import Std.IO
import Std.IO exposing log, logf
```

Even when exposing is used, examples often keep the fully qualified call for readability:

```freehold
call Std.IO.logf("x = ${}", x)
```

The resolver checks exposed runtime symbols against the runtime module's known export set. This is the same safety principle used for ordinary modules, except the symbol source is the trusted runtime export table.

---

## 15. Verification Boundary

The standard library is partly trusted, but calls are still type checked.

The verifier must reject:

- wrong Math argument count
- wrong Math argument type
- wrong Big argument count
- wrong Big exact argument type
- `Big.*Int` called with `Integer` instead of `BigInteger`
- `Big.*Float` called with non-`BigFloat`
- invalid `Std.IO.logf` template placeholder count
- invalid `Std.IO.logf` template binding names
- unsupported template value types
- unknown exposed runtime symbols

The trusted runtime boundary does not mean arbitrary calls are accepted. It means the implementation of accepted calls is provided by the runtime/backend rather than by ordinary Freehold source.

---

## 16. Backend Boundary

A backend may map standard modules to host libraries, but it must preserve Freehold's type and call shape.

Current Go imports:

```text
Math    uses math
Std.IO  uses fmt
Big     uses math/big
```

The generated Go should include these imports only when the corresponding runtime module is actually used.

Standard library calls should remain explicit in import metadata, including whether an imported module is a runtime module and whether it was used.

---

## 17. Relationship To Other Specifications

This document covers the current foundational standard library modules.

Related specifications:

```text
SPECIFICATION-FH-BASICS.md       module/import structure
SPECIFICATION-FH-STATEMENTS.md   call statement and expression rules
SPECIFICATION-MAP.md             runtime Map helpers
SPECIFICATION-RECORD-JSON.md     Json.stringify / Json.parse surface
SPECIFICATION-CRYPTO.md          Std.Crypto trusted runtime/FFI modules
SPECIFICATION-KEYPASS.md         KeePass-related runtime integration
SPECIFICATION-GO-BACKEND.md      Go runtime module mapping and codegen policy
SPECIFICATION-COMIPLER-FRONTEND.md frontend/runtime module resolution boundary
```

Future standard library specs may split String, System, File, Json, Crypto, Connect, and other `Std.*` modules into dedicated documents.

---

## 18. Common Failure Patterns

### 18.1 Calling Math As A Procedure

Invalid:

```freehold
call Math.sqrt(4.0)
```

Math calls are expressions:

```freehold
let x: Double = Math.sqrt(4.0)
```

### 18.2 Passing Integer Directly To Big.addInt

Invalid:

```freehold
return Big.addInt(a, b)
```

Convert first:

```freehold
return Big.addInt(Big.fromInteger(a), Big.fromInteger(b))
```

### 18.3 Using Big.floatFromInteger With Integer

Invalid:

```freehold
let f: BigFloat = Big.floatFromInteger(42, 128)
```

Convert to `BigInteger` first:

```freehold
let n: BigInteger = Big.fromInteger(42)
let f: BigFloat = Big.floatFromInteger(n, 128)
```

### 18.4 Mismatched logf Placeholders

Invalid:

```freehold
call Std.IO.logf("left=${}, right=${}", left)
```

Provide one value for each placeholder:

```freehold
call Std.IO.logf("left=${}, right=${}", left, right)
```

### 18.5 Treating Std.IO As Syntax

Invalid mental model:

```text
log is a keyword or compiler directive
```

Correct model:

```text
Std.IO.log is a trusted runtime procedure reached through normal qualified-call syntax
```

---

## 19. Practical Checklist

When using or extending the standard library, check:

- Runtime modules are imported explicitly when source code refers to them.
- Exposed runtime symbols exist in the runtime module export set.
- Math calls are expressions and have numeric arguments.
- Math return types match the operation's type rule.
- Big operations use exact `BigInteger` or `BigFloat` operands.
- Ordinary numeric values are converted explicitly before Big operations.
- BigFloat precision arguments are positive integers.
- `Std.IO.log` and `Std.IO.logf` are procedure calls.
- `Std.IO.logf` templates use `${}` or `${name}` placeholders.
- Template placeholder counts and named bindings match exactly.
- Template display values are scalar display values.
- Backend mappings use explicit host imports such as `math`, `fmt`, and `math/big`.
- Runtime-backed operations remain stable across interpreter, verifier, and backend paths.

A good Freehold standard-library call looks ordinary in source code, is checked like the rest of the language, and lowers to an explicit trusted runtime binding only after the front-end has accepted its type and call shape.
