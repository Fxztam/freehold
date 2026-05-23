# Open JSON Handlings

This document captures open decisions around JSON handling in Freehold and its tooling.

JSON appears in two places: existing toolchain/conformance artifacts, and the V1 `Json.stringify(record_value)` library builtin for Freehold programs.

Current V1 verification baseline:

```text
Json language module: 4/4
compare-semantic-diagnostics: 62/62, 0 mismatches
verify-spec-diagnostics: 87 specs, 87 emits, 0 failures
verify-parser-conformance: passed
Parser cases: 270 total, 227 OK, 43 expected FAIL
AST shape: 227/227
Semantic AST: 227/227
```

## Current Status

The current project already relies heavily on JSON artifacts:

```text
artifacts/go-ast
artifacts/dhparser-ast
artifacts/compare-parse-status
artifacts/compare-parse-errors
artifacts/compare-ast-shape
artifacts/compare-ast-semantic
artifacts/compare-semantic-diagnostics
tests/language_modules/expected_diagnostics.json
tests/language_modules/expected_semantic_diagnostics.json
tests/language_modules/positive_feature_matrix.json
```

These JSON files are verification and conformance contracts. They are deterministic machine-readable artifacts and should remain stable.

## Two Separate JSON Topics

Freehold should keep two JSON concerns separate.

### Tooling JSON

Tooling JSON is already active.

It includes:

```text
AST artifacts
diagnostic manifests
comparison summaries
feature matrices
CI summaries
```

Tooling JSON should prioritize:

```text
deterministic output
stable schema shape
explicit schema versions where useful
source locations for diagnostics
no hidden semantic meaning from comments
round-trip-friendly data
```

### Language JSON

Language JSON starts as a library/builtin feature, not as new Freehold syntax.

V1 target:

```fh
let text: String = Json.stringify(record_value)
```

This uses the existing qualified call syntax. No EBNF or parser grammar extension is required for V1.

## Tooling JSON Rules

Recommended rules for all conformance/tooling JSON:

```text
Use UTF-8.
Use stable key names.
Use deterministic ordering where practical.
Use explicit arrays rather than comma-separated strings.
Keep source locations structured as line/column objects.
Keep legacy codes only as traceability fields, not primary semantics.
Preserve both summary and detailed all-case reports for gates.
```

Recommended source location shape:

```json
{
  "location": {
    "line": 12,
    "column": 9
  }
}
```

Recommended diagnostic shape:

```json
{
  "severity": "error",
  "phase": "semantic",
  "category": "type",
  "code": "FH-TYP-2301",
  "number": 2301,
  "name": "assignment_type_mismatch",
  "message": "assignment type mismatch",
  "location": { "line": 6, "column": 5 },
  "found": "Boolean",
  "expected": "Integer",
  "hint": "..."
}
```

## JSON As Language Feature

V1 ships only deterministic record serialization:

```text
Json.stringify(record_value) -> String
```

Rules:

```text
Json.stringify accepts exactly one argument.
The top-level argument must be a record value.
Output is compact deterministic JSON.
Record fields are emitted in record declaration order.
String, Integer, Boolean, and Double field values are supported.
Nested record values are supported.
Arrays of supported values are supported where array values are available.
BigInteger, BigFloat, Result, parse, schema, optional, nullable, and @json names are Post-V1.
```

Diagnostics for V1 live in `FH-JSON-4201..4203`.

If JSON becomes a Freehold language feature, records should remain the canonical structure definition.

JSON should be a checked projection of Freehold record types, not a second schema language that duplicates records.

Potential future module:

```fh
import Json
```

Potential value model for dynamic JSON:

```text
Json.Value
Json.Object
Json.Array
```

Potential functions for dynamic JSON:

```fh
Json.parse(text: String) returns Result<Json.Value, Json.ParseError>
Json.stringify(value: Json.Value) returns String
Json.getString(value: Json.Value, key: String) returns Result<String, Json.TypeError>
Json.getInteger(value: Json.Value, key: String) returns Result<Integer, Json.TypeError>
```

This keeps JSON errors as value-level `Result<T, E>` returns rather than aborts.

For hard schema-checked JSON, prefer typed record parsing:

```fh
Json.parse<Person>(text) returns Result<Person, Json.SchemaError>
Json.stringify(person) returns String
Json.schema<Person>() returns Json.Schema
```

This makes the Freehold record the source of truth and lets JSON parsing validate the external text against that type.

## JSON And Records

Decision direction:

```text
Records define JSON schemas.
Json.parse<RecordType>(text) validates JSON hard against the record type.
Json.stringify(record_value) emits deterministic JSON for the record value.
Json.schema<RecordType>() can generate a JSON schema artifact from the record type.
```

Example:

```fh
record Address
is
  street: String
  city: String
  zip: String
end Address

record Person
is
  name: String
  age: Integer
  email: optional String
  tags: Array<String>
  address: Address
end Person
```

The record above implies a strict JSON object schema:

```text
required fields: name, age, tags, address
optional fields: email
unknown fields: rejected by default
field types: checked recursively
```

Usage:

```fh
function parse_person(text: String) returns Result<Person, Json.SchemaError>
is
  return Json.parse<Person>(text)
end parse_person
```

This avoids duplicate definitions such as a separate `json schema Person` block. The Freehold record is the one truth point; JSON is the checked external representation.

## JSON Field Names

By default, a record field name is also the JSON object field name.

When an external JSON API uses a different name, the record field can declare an explicit JSON name:

```fh
record Person
is
  first_name: String @json("firstName")
  age: Integer
end Person
```

Recommended rule:

```text
Freehold code uses the record field name.
JSON input/output uses the @json name when present.
The @json value must be a string literal.
Duplicate JSON field names inside one record are rejected.
```

Example mapping:

```text
Freehold field: first_name
JSON field:     firstName
```

This keeps internal naming stable while allowing integration with external camelCase APIs.

## JSON Optional And Nullable

`optional` should mean that the JSON field may be absent.

It should not automatically mean that JSON `null` is accepted.

Recommended distinction:

```fh
email: optional String
middle_name: nullable String
nickname: optional nullable String
```

Meaning:

```text
optional String
  field may be absent; if present, it must be String

nullable String
  field must be present; value may be String or null

optional nullable String
  field may be absent; if present, value may be String or null
```

`nullable` is not implemented yet and should remain an open language design item until the type system supports it cleanly.

## JSON Strictness

Recommended default:

```text
Json.parse<RecordType>(text) is strict by default.
```

Strict means:

```text
missing required field => SchemaError
unknown field => SchemaError
wrong field type => SchemaError
duplicate object key => SchemaError
null without nullable => SchemaError
integer outside supported range => SchemaError
```

An open mode can be considered later:

```fh
Json.parse<Person>(text, Json.open)
```

Open mode must define whether unknown fields are ignored, preserved, or rejected at serialization time.

## JSON Template Strings

JSON templates should be structural templates, not text templates.

Recommended v1 API:

```fh
Json.template("...", name: expr, ...)
```

Typed variant:

```fh
Json.template<RecordType>("...", name: expr, ...)
```

Untyped JSON template result:

```fh
Json.template("{ \"name\": ${name}, \"active\": ${active} }",
  name: first_name,
  active: is_active
) returns Json.Value
```

Typed JSON template result:

```fh
Json.template<Person>("{ \"name\": ${name}, \"age\": ${age} }",
  name: first_name,
  age: age
) returns Result<Person, Json.SchemaError>
```

The typed form performs all checks of the untyped form and then validates the produced JSON value against the record-derived schema for `Person`.

Core rule:

```text
JSON templates are JSON-with-holes.
Holes are filled as JSON values, never as raw text fragments.
```

This means:

```fh
Json.template("{ \"name\": ${name} }", name: first_name)
```

with `first_name = "Ada"` produces:

```json
{ "name": "Ada" }
```

It does not produce invalid JSON and it does not perform textual concatenation.

### JSON Template Rules

Recommended rules:

```text
The template argument must be a string literal.
The template syntax is JSON with ${name} holes.
Holes are allowed only at JSON value positions.
Holes are not allowed inside JSON strings.
All holes must be supplied as named arguments.
All named arguments must be used by holes.
Duplicate named arguments are rejected.
Bindings are inserted as JSON values.
No binding is inserted as raw text.
The final structure is parsed and validated as JSON.
Typed templates are additionally validated against the target record type.
```

Valid:

```fh
Json.template("{ \"name\": ${name}, \"age\": ${age} }",
  name: first_name,
  age: age
)
```

Invalid because the hole is inside a JSON string:

```fh
Json.template("{ \"name\": \"${name}\" }", name: first_name)
```

Use a JSON value-position hole instead:

```fh
Json.template("{ \"name\": ${name} }", name: first_name)
```

### JSON Template Values

Allowed binding values should be values with explicit JSON projection:

```text
String      inserted as JSON string
Integer     inserted as JSON number if range-valid
Double      inserted as JSON number if finite
Boolean     inserted as JSON boolean
Array<T>    inserted as JSON array when T is JSON-projectable
record      inserted as JSON object through record-derived schema
Json.Value  inserted as already-validated JSON value
```

Rejected or open in v1:

```text
raw unvalidated JSON text
procedure values
routine values
opaque external values without JSON projection
Double NaN or Infinity
```

### JSON Template Arrays And Records

Arrays are inserted structurally:

```fh
Json.template("{ \"tags\": ${tags} }", tags: tags)
```

If `tags` is `Array<String>`, the result contains a JSON array.

Records are inserted through the same record-derived JSON projection used by `Json.stringify`:

```fh
Json.template("{ \"owner\": ${owner} }", owner: person)
```

If `person` has `@json(...)` field mappings, those mappings are used inside the inserted object.

### No Raw JSON Insertion In V1

Do not add raw textual insertion in the first design.

Rejected direction:

```text
Json.template("{ \"x\": ${rawJson} }", rawJson: unchecked_text)
```

If callers already have JSON text, they must parse it first:

```fh
let value: Result<Json.Value, Json.ParseError> = Json.parse(text)
```

Only validated `Json.Value` may be inserted into a JSON template.

## JSON And String Templates

String templates should not perform hidden JSON escaping unless explicitly requested.

Open future API:

```fh
Json.escape(text: String) returns String
```

Recommended rule:

```text
String.template is text formatting.
Json.stringify/Json.escape handle JSON encoding.
```

## JSON And Diagnostics

JSON parsing and construction should have stable diagnostics if it becomes a language feature.

Suggested range:

```text
FH-JSON-4200..4299  JSON language and tooling diagnostics
```

Suggested diagnostics:

```text
FH-JSON-4201 invalid JSON text
FH-JSON-4202 JSON field not found
FH-JSON-4203 JSON type mismatch
FH-JSON-4204 JSON array index out of bounds
FH-JSON-4205 unsupported implicit JSON serialization
FH-JSON-4206 non-deterministic JSON artifact output
FH-JSON-4207 JSON schema version mismatch
FH-JSON-4208 missing required JSON field
FH-JSON-4209 unknown JSON field in strict record parse
FH-JSON-4210 duplicate JSON field name mapping
FH-JSON-4211 invalid @json field-name annotation
FH-JSON-4212 JSON null not allowed for non-nullable field
```

## Artifact Schema Versioning

For stable long-lived artifacts, consider adding schema versions:

```json
{
  "schema": "freehold.semantic_diagnostics.v1",
  "cases": {}
}
```

Recommended for future gates:

```text
new gate manifests should include schema ids
existing manifests may be migrated later
comparison tools should fail on unsupported schema versions
```

## Open Design Questions

```text
Should JSON be a standard module or a built-in type family?
Should Json.Value be opaque or structurally inspectable?
Should record <=> JSON conversion be generated for every record or opt-in per record/module?
Should JSON parse errors be Result values only?
Should strict parsing be the only first implementation mode?
Should nullable be introduced as a general type modifier or only for JSON projections?
Should tooling artifact schemas be versioned now or after one more stabilization pass?
```

## Positive Matrix Targets

Future language-level targets:

```text
json_parse_valid_object
json_parse_invalid_returns_result_error
json_parse_record_strict_success
json_parse_record_missing_required_field
json_parse_record_unknown_field_rejected
json_parse_record_field_name_annotation
json_parse_record_duplicate_json_name_rejected
json_get_string_field
json_get_integer_field
json_schema_generated_from_record
json_template_requires_explicit_escape
```

Implemented V1 target:

```text
json_stringify_record_deterministic
```

Tooling-level targets:

```text
schema_version_present_in_new_manifest
diagnostic_json_has_stable_code_and_location
compare_gate_rejects_unsupported_schema
artifact_output_is_deterministic
```

## Summary Rules

```text
Tooling JSON is already part of Freehold conformance.
Language JSON V1 implements Json.stringify(record_value) as a library builtin.
Records are the canonical JSON schema source.
Prefer Json.parse<RecordType>(text) for hard schema validation.
Use @json("externalName") for external JSON field names.
Strict record parsing rejects missing, unknown, and wrong-typed fields.
Prefer Result<T, E> for JSON parse/type errors.
Keep JSON artifact schemas stable and eventually versioned.
```
