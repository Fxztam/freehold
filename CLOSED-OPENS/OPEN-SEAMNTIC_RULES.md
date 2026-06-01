# Open Semantic Rules

This document captures the open design for a small semantic rule language beside the Freehold grammar.

The filename intentionally follows the current requested open-flank name: `OPEN-SEAMNTIC_RULES.md`.

## Motivation

EBNF and parser grammars describe syntax:

```text
What can be parsed?
```

Freehold also needs a stable, machine-readable layer for semantics:

```text
What does the AST mean?
What names are bound?
What types are checked?
Which contracts apply?
Which diagnostics are emitted?
Which completions and hovers can the editor provide?
```

This layer should help convert design documents into implementation, tests, diagnostics, and editor support.

## Proposed Files

Recommended starting point:

```text
spec/freehold.rules
spec/freehold.diag
```

Current initial files:

```text
spec/freehold.rules
spec/freehold.diag
```

These files currently describe the existing syntax, semantic, and type diagnostics plus the fixed v1 nested-Result rule.

Optional later split:

```text
spec/semantics/records.rules
spec/semantics/results.rules
spec/semantics/strings.rules
spec/semantics/json.rules
spec/semantics/aborts.rules
spec/diagnostics/freehold.diag
spec/editor/freehold.complete
spec/editor/freehold.hover
```

The first implementation should stay small. A single `freehold.rules` and `freehold.diag` file is enough to start.

## Layering

Recommended responsibility split:

```text
freehold.lark / freehold.dhparser.ebnf
    Syntax and parse tree shape.

freehold.rules
    Binding, typing, semantic constraints, and diagnostic emission rules.

freehold.diag
    Stable diagnostic catalog: codes, names, categories, messages, found/expected/hints.

expected_*.json
    Concrete expected outcomes for test cases.

VS Code extension / language server
    Uses parser, rules, diagnostics, and symbol tables for edit-mode diagnostics and assistance.
```

This keeps grammar, semantics, diagnostics, and tests separate but connected.

## Rule Language Shape

The rule language should be intentionally simple. It is not a general programming language.

Core statements:

```text
rule
when
require
emit
else
found
expected
hint
end
```

Recommended style:

```text
rule <stable_name>
when <ast_or_semantic_pattern>
require <predicate>
else emit <diagnostic_code>
    found <expression>
    expected <expression>
    hint <string>
end
```

No loops, side effects, mutation, or arbitrary host-language execution should be allowed in v1.

## Diagnostic Catalog Shape

`freehold.diag` should define stable diagnostic identities separately from the rule that emits them.

Example:

```text
diag FH-RES-4107 nested_result_payload_not_supported
category semantic
severity error
message "nested Result payloads are forbidden in v1"
found "Result<..., ...>"
expected "non-Result value type"
hint "Use an error family or future error set instead."
end
```

The rule can then reference only the code:

```text
rule nested_result_payload_forbidden
when ResultType(ok: ResultType(_, _), error: _)
emit FH-RES-4107
end
```

This avoids duplicating message text across implementations.

## Diagnostic Process

The verification step that turns rules and catalog entries into concrete diagnostics is called the Diagnostic Process.

Recommended terminology:

```text
Semantic Rules
    freehold.rules describes the semantic conditions and which diagnostic code is emitted.

Diagnostic Catalog
    freehold.diag describes stable diagnostic codes, categories, messages, FOUND/EXPECTED defaults, and hints.

Diagnostic Process
    evaluates freehold.rules over the parsed program, resolves diagnostic definitions from freehold.diag,
    fills found/expected/hint fields, and emits stable structured diagnostics for CLI, tests, and editor tooling.
```

The Diagnostic Process consumes:

```text
source file
AST
symbol table
type information
contract context
freehold.rules
freehold.diag
```

and produces:

```text
structured diagnostics
stable code
phase
category
location
message
FOUND
EXPECTED
HINT
legacy code when applicable
```

Conceptual flow:

```text
parse source
build AST
build symbol table
infer/check types
evaluate freehold.rules
resolve each emitted code in freehold.diag
fill dynamic found/expected/hint data
emit JSON diagnostics
```

Example:

```text
Rule:
    nested_result_payload_forbidden_v1 emits FH-RES-4107

Catalog:
    FH-RES-4107 nested_result_payload_not_supported

Diagnostic Process:
    sees Result<Result<Integer, NotFound>, NetworkError>
    emits FH-RES-4107 with FOUND => Result<Integer, NotFound>
    and EXPECTED => non-Result value type
```

Different execution contexts can reuse the same Diagnostic Process:

```text
CLI Diagnostic Process
    runs freehold check file.fh --json.

Conformance Diagnostic Process
    compares emitted diagnostics against expected_diagnostics.json and expected_semantic_diagnostics.json.

Edit Mode Diagnostic Process
    runs interactively for VS Code diagnostics and later through LSP.
```

The term Diagnostic Process should therefore refer to the concrete runtime/check-time pipeline, not to the rule language or the catalog alone.

## Example Semantic Rules

### Nested Result Forbidden In V1

```text
rule nested_result_payload_forbidden
when ResultType(ok: ResultType(_, _), error: _)
emit FH-RES-4107
    found ok
    expected "non-Result value type"
    hint "Nested Result is forbidden in v1 so success, failure, value, and error remain unambiguous."
end
```

### Result Error Type Must Be Declared Error

```text
rule result_error_type_must_be_declared_error
when ResultType(ok: _, error: E)
require is_declared_error(E)
else emit FH-RES-4110
    found E
    expected "declared error name"
end
```

### Record Constructor Unknown Field

```text
rule record_constructor_unknown_field
when RecordConstructor(type: T, field: F)
require has_field(T, F)
else emit FH-REC-4304
    found F
    expected fields(T)
end
```

### JSON External Name Used In Record Constructor

```text
rule record_constructor_json_name_used
when RecordConstructor(type: T, field: F)
require not is_json_external_name(T, F)
else emit FH-REC-4307
    found F
    expected freehold_field_for_json_name(T, F)
    hint "@json(...) applies to JSON input/output, not Record constructors."
end
```

### String Template Missing Named Binding

```text
rule string_template_missing_named_binding
when StringTemplate(placeholders: P, bindings: B)
require all placeholders(P) in names(B)
else emit FH-TPL-4007
    found names(B)
    expected placeholders(P)
end
```

### JSON Template Hole Must Be Value Position

```text
rule json_template_hole_value_position
when JsonTemplateHole(location: L)
require is_json_value_position(L)
else emit FH-JSON-4213
    found "hole inside JSON string or key"
    expected "JSON value position"
end
```

## Edit-Mode Verification

The same rule files should support VS Code diagnostics in edit mode.

Recommended first architecture:

```text
VS Code extension
    calls Freehold CLI on changed .fh files

Freehold CLI
    parses file
    builds AST and symbol table
    evaluates freehold.rules
    formats diagnostics using freehold.diag
    returns JSON diagnostics

VS Code
    displays diagnostics in editor and Problems panel
```

Potential CLI:

```text
freehold check path/to/file.fh --json
```

Diagnostic JSON should include:

```json
{
  "code": "FH-REC-4307",
  "severity": "error",
  "message": "JSON field name used in Record constructor",
  "location": { "line": 12, "column": 9 },
  "found": "firstName",
  "expected": "first_name",
  "hint": "@json(\"firstName\") applies to JSON input/output, not Record constructors."
}
```

This CLI-first approach can later become a proper Language Server Protocol implementation.

## Language Server Protocol

LSP means Language Server Protocol.

It is the standard protocol between an editor and a language-specific service:

```text
VS Code
    editor surface and UI

Freehold Language Server
    parser, symbol table, semantic rules, diagnostics, completions, hovers, quick fixes

Language Server Protocol
    message protocol between VS Code and the Freehold Language Server
```

The editor sends events and requests:

```text
file opened
file changed
cursor moved
completion requested
hover requested
code action requested
go-to-definition requested
rename requested
```

The Freehold Language Server answers with language intelligence:

```text
diagnostics
completion items
hover text
quick fixes
definition locations
references
formatting edits
rename edits
```

Example edit-mode diagnostic flow:

```text
User edits Person(firstName: first_name)
VS Code sends the changed document to the Freehold Language Server
Language Server parses and evaluates freehold.rules
Language Server formats FH-REC-4307 using freehold.diag
VS Code displays the diagnostic as a squiggle and Problems entry
```

Example completion flow:

```text
User types inside Person(|)
VS Code asks for completion at the cursor
Language Server sees a RecordConstructor context
Language Server returns the remaining record fields
VS Code displays name:, age:, email:, tags:, address:
```

Recommended implementation order:

```text
Start with CLI-based edit-mode diagnostics.
Use freehold check file.fh --json from the VS Code extension.
Stabilize parser, symbol table, freehold.rules, and freehold.diag.
Then evolve the same logic into a Freehold Language Server.
```

This avoids hard-wiring Freehold only to VS Code. Any editor that supports LSP can later use the same Freehold Language Server.

## VS Code Completion

Semantic rules and symbol tables should also drive completion.

### Record Constructor Field Completion

Example source:

```fh
let person = Person(
    name: first_name,
    |
)
```

Completion should offer remaining fields only:

```text
age:
email:
tags:
address:
```

Pseudo completion rule:

```text
completion record_constructor_field
when cursor inside RecordConstructor(type: T)
provide fields(T) excluding supplied_fields()
end
```

### String Template Binding Completion

Example source:

```fh
String.template("Hello ${firstName}, ${age}", firstName: first_name, |)
```

Completion should offer:

```text
age:
```

Pseudo completion rule:

```text
completion string_template_binding
when cursor inside StringTemplateBindingList(template: S)
provide placeholders(S) excluding supplied_bindings()
end
```

### JSON Template Binding Completion

Example source:

```fh
Json.template<Person>("{ \"name\": ${name}, \"age\": ${age} }", |)
```

Completion should offer:

```text
name:
age:
```

Pseudo completion rule:

```text
completion json_template_binding
when cursor inside JsonTemplateBindingList(template: S)
provide json_holes(S) excluding supplied_bindings()
end
```

## VS Code Hover

Rules and diagnostics should provide hover text.

Examples:

```fh
Result<Result<Integer, NotFound>, NetworkError>
```

Hover or diagnostic detail:

```text
FH-RES-4107
Nested Result payloads are forbidden in v1.
success, failure, value, and error must always refer to exactly one Result layer.
```

For JSON field mapping:

```fh
first_name: String @json("firstName")
```

Hover:

```text
JSON field name mapping.
Freehold field: first_name
JSON field: firstName
Applies to Json.parse, Json.stringify, and Json.template.
Does not change Record constructor field names.
```

## VS Code Quick Fixes

Rules should expose enough structured data for simple code actions.

Example:

```fh
Person(firstName: first_name)
```

Diagnostic:

```text
FH-REC-4307
FOUND => firstName
EXPECTED => first_name
```

Quick fix:

```text
Rename field to first_name
```

Missing required fields can offer insertions:

```text
Add missing field age:
Add missing field tags:
Add missing field address:
```

Nested Result diagnostics should usually not auto-fix, but can provide a hint:

```text
Use an error family or future error set instead of Result<Result<T, E1>, E2>.
```

## Implementation Path

Recommended staged implementation:

```text
1. Write OPEN-SEAMNTIC_RULES.md as design anchor.
2. Create spec/freehold.diag with the first stable diagnostic definitions.
3. Create spec/freehold.rules with the first semantic rules.
4. Add verify-spec-diagnostics to parse the simple rule/diag files and gate coverage.
5. Connect the existing verifier to emit diagnostics using freehold.diag codes.
6. Add freehold check file.fh --json.
7. Teach the VS Code extension to call the CLI for edit-mode diagnostics.
8. Add completion for record constructors and template bindings.
9. Move from CLI polling to LSP when the behavior is stable.
```

Current implemented diagnostic-spec gate:

```text
verify-spec-diagnostics.cmd
tools/verify_spec_diagnostics.py
artifacts/verify-spec-diagnostics
```

The gate currently checks:

```text
every emit FH-* in spec/freehold.rules exists in spec/freehold.diag
every code in expected_diagnostics.json exists in spec/freehold.diag
every code in expected_semantic_diagnostics.json exists in spec/freehold.diag
every CODE_MAP target from compare_semantic_diagnostics.py exists in spec/freehold.diag
expected diagnostic names match spec diagnostic names
CODE_MAP names match spec diagnostic names
```

## First Rule Targets

Use the current open design documents as the first rule source:

```text
OPEN-RETURN_RESULTS.md
    nested Result forbidden in v1
    Result error type must be declared error
    Result ok type expressions such as Array<T, N>
    value.field only for record ok types

OPEN-RECORD_INITIAL.md
    TypeName(field: expr, ...)
    missing/unknown/duplicate fields
    field type mismatch
    @json external names rejected in constructors

OPEN-STRING_TEMPLATES.md
    named placeholder binding
    missing/extra/duplicate bindings
    placeholder count and placeholder syntax

OPEN-JSON_HANDLINGS.md
    record-derived JSON schemas
    @json field mapping
    Json.template holes only at JSON value positions
    no raw JSON text insertion in v1

OPEN-ABORT_HANDLING.md
    abort declarations
    missing propagation
    requires-space constraint
```

## Summary Rules

```text
Keep EBNF for syntax.
Use freehold.rules for semantic constraints and diagnostic emission.
Use freehold.diag for stable diagnostic identities and messages.
Use the same rule data to power VS Code diagnostics, completion, hover, and quick fixes.
Start CLI-first; evolve to LSP after behavior stabilizes.
Keep the rule language small, declarative, and side-effect free.
```

=== CLOSED ===
