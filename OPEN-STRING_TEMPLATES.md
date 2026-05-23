# Open String Templates

This document captures the open design surface for Freehold string templates.

## Current Status

V1 status: fulfilled and verified.

The V1 goal for string templates is implemented end to end:

```text
Grammar accepts positional and named template calls.
Python parser, verifier, and runtime support named template bindings.
Go parser and AST support named call arguments for conformance artifacts.
DHParser grammar and AST normalizers are aligned with the Go/Python shape.
Diagnostics FH-TPL-4001..4009 are specified, mapped, and covered by tests.
Positive and negative language-module tests cover positional, named, missing, unused, duplicate, old-brace, invalid-brace, and mixed-mode cases.
```

The V1 verification baseline is:

```text
compare-semantic-diagnostics: 58/58, 0 mismatches
verify-spec-diagnostics: 84 specs, 84 emits, 0 failures
verify-parser-conformance: passed
Parser cases: 264 total, 221 OK, 43 expected FAIL
AST shape: 221/221
Semantic AST: 221/221
Go tests: passed
```

Open items below are post-V1 design questions, not blockers for the V1 fulfillment.

String templates already exist as checked built-in calls:

```fh
let message: String = String.template("id=${}, active=${}", 7, true)
```

Named templates are now accepted in v1 form by using named call arguments:

```fh
let message: String = String.template("id=${id}, active=${active}", id: id, active: active)
```

`Std.IO.logf` also supports template-style formatting:

```fh
call Std.IO.logf("value=${}", 3)
```

The positive feature matrix also includes templates inside `Std.IO.logf`:

```fh
call Std.IO.logf(String.template("code=${}", code))
```

## Current Rules

The current checked rules are:

```text
String.template expects at least one argument.
The first argument must be String.
Template placeholders use ${}.
Old {} placeholders are rejected.
Named placeholders use ${name}.
Named bindings use name: expr after the template string.
Positional and named template modes cannot be mixed in one call.
Positional placeholder count must match the number of template values.
Named placeholders and bindings must match exactly.
Template values are currently scalar: String, Integer, Boolean, or Double.
```

`Std.IO.logf` follows the same placeholder-count and scalar-value idea.

## Accepted Examples

```fh
let message: String = String.template("id=${}, active=${}, rate=${}", 7, true, 2.5)
```

```fh
call Std.IO.logf("value=${}", 3)
```

```fh
call Std.IO.logf(String.template("code=${}", code))
```

```fh
let message: String = String.template("id=${id}, active=${active}", id: id, active: true)
```

## Rejected Examples

Old placeholder form:

```fh
let message: String = String.template("id={}", 7)
```

Placeholder count mismatch:

```fh
let message: String = String.template("id=${}, active=${}", 7)
```

Missing named binding:

```fh
let message: String = String.template("id=${id}")
```

Unused named binding:

```fh
let message: String = String.template("id=${id}", id: id, active: true)
```

Duplicate named binding:

```fh
let message: String = String.template("id=${id}", id: id, id: id)
```

## Open Design Questions

### Named Placeholders

The v1 syntax is fixed:

```fh
let message: String = String.template("id=${id}", id: 7)
```

Rules:

```text
Named template arguments use the shared named call-argument syntax.
If one placeholder is named, all placeholders in that template must be named.
Every named placeholder must have exactly one binding.
Every binding must be used.
Duplicate binding names are rejected.
```

### Record And Array Values

Current template values are scalar. It is open whether records and arrays should be accepted directly.

Possible conservative rule:

```text
Records and arrays are rejected unless explicitly converted to String.
```

Example:

```fh
let text: String = Account.toString(account)
let message: String = String.template("account=${}", text)
```

This keeps formatting deterministic and avoids hidden serialization semantics.

### Big Number Values

`BigInteger` and `BigFloat` currently have explicit string conversion functions:

```fh
let text: String = Big.toString(value)
let text: String = Big.format(value, 5)
```

Recommended rule:

```text
BigInteger and BigFloat should require explicit conversion before template insertion.
```

This avoids accidental precision or formatting policy leaks.

### Escaping

Open escaping decisions:

```text
How to emit a literal ${}?
How to emit a literal ${name} if named templates are later added?
Should backslash escaping or doubled delimiters be preferred?
```

Candidate:

```text
Use $${} for a literal ${}.
```

This is open and should be tested before implementation.

## Diagnostics

Semantic diagnostics classify template errors through legacy `VF-TPL*` names and normalize them into stable Freehold diagnostics.

Stable range:

```text
FH-TPL-4000..4099  string template diagnostics
```

Diagnostics:

```text
FH-TPL-4001 template placeholder count mismatch
FH-TPL-4002 old placeholder form rejected
FH-TPL-4003 invalid named template placeholder
FH-TPL-4004 invalid template brace
FH-TPL-4005 template value type mismatch
FH-TPL-4006 duplicate named template binding
FH-TPL-4007 missing named template binding
FH-TPL-4008 unused named template binding
FH-TPL-4009 mixed positional/named template mode
```

Diagnostics should report:

```text
FOUND => actual placeholder/value shape
EXPECTED => required placeholder/value shape
LOCATION => template string or offending argument
```

## Positive Matrix Targets

Already covered:

```text
string_template_values
string_template_no_placeholder
string_template_spaced_placeholder
std_io_logf_template
string_template_inside_logf
string_template_named_values
string_template_missing_binding
string_template_unused_binding
string_template_duplicate_binding
```

Future matrix targets:

```text
string_template_with_explicit_big_conversion
string_template_with_record_field_values
string_template_inside_contract_message_if diagnostics later support messages
```

## Summary Rules

```text
Use ${} placeholders.
Use ${name} placeholders with name: expr bindings for named templates.
Reject old {} placeholders.
Reject missing, unused, or duplicate named bindings.
Reject mixed positional/named template modes.
Keep template values scalar unless explicitly converted to String.
Prefer explicit formatting over hidden serialization.
```
