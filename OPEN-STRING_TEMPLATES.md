# Open String Templates

This document captures the open design surface for Freehold string templates.

## Current Status

String templates already exist as checked built-in calls:

```fh
let message: String = String.template("id=${}, active=${}", 7, true)
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
Named placeholders are not implemented yet.
Placeholder count must match the number of template values.
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

## Rejected Examples

Old placeholder form:

```fh
let message: String = String.template("id={}", 7)
```

Placeholder count mismatch:

```fh
let message: String = String.template("id=${}, active=${}", 7)
```

Named placeholders are still open:

```fh
let message: String = String.template("id=${id}", 7)
```

## Open Design Questions

### Named Placeholders

Potential future syntax:

```fh
let message: String = String.template("id=${id}", id: 7)
```

Open points:

```text
Should named template arguments use existing named_arg syntax?
Should all placeholders be named if one is named?
Should duplicate placeholder names be allowed?
Should extra named values be rejected?
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

Existing semantic diagnostics already classify template errors through legacy `VF-TPL*` names and can be normalized into stable Freehold diagnostics later.

Suggested stable range:

```text
FH-TPL-4000..4099  string template diagnostics
```

Suggested diagnostics:

```text
FH-TPL-4001 wrong template argument count
FH-TPL-4002 old placeholder form rejected
FH-TPL-4003 named templates not implemented
FH-TPL-4004 invalid template brace
FH-TPL-4005 template value type mismatch
FH-TPL-4006 duplicate named template argument
FH-TPL-4007 missing named template argument
FH-TPL-4008 extra named template argument
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
```

Future matrix targets:

```text
string_template_with_explicit_big_conversion
string_template_with_record_field_values
string_template_inside_contract_message_if diagnostics later support messages
named_string_template_values if named placeholders are accepted
```

## Summary Rules

```text
Use ${} placeholders.
Reject old {} placeholders.
Keep template values scalar unless explicitly converted to String.
Prefer explicit formatting over hidden serialization.
Keep named placeholders open until named argument semantics are settled.
```
