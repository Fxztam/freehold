# Open Record Initializers

This document captures the open design surface for constructing Freehold record values from named field values.

## Decision Direction

Decision: Freehold keeps one record initialization notation only.

Current secured status:

```text
The existing TypeName { field: expr, ... } syntax is the V1 record initializer syntax.
The alternative TypeName(field: expr, ...) constructor notation is dropped.
String.template(...) works as a record field expression inside TypeName { ... }.
This was smoke-tested through parser, verifier, and interpreter with a String field initialized by a named string template.
```

The String.template field-value check used this shape:

```fh
let person: Person = Person {
    name: "Ada",
    email: String.template("${user}@example.com", user: user_name)
}
```

and verified the resulting field value with:

```fh
check person.email = "ada@example.com"
```

Record values are initialized with the existing `{ }` record syntax:

```fh
let person: Person = Person {
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: address
}
```

If type inference is allowed for record initializers, this should also be valid:

```fh
let person = Person {
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: address
}
```

The `Person(...)` constructor form is explicitly not part of the language direction for V1. There is also no separate `Person.template(...)` form.

## Example Record

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

Valid construction:

```fh
let person = Person {
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: Address {
        street: street,
        city: city,
        zip: zip
    }
}
```

## Core Rules

```text
Record initializers use TypeName { field: expr, ... }.
The initializer target must be a declared record type.
Initializer field names are Freehold record field names.
Initializer field values are ordinary Freehold expressions.
All required fields must be supplied.
Optional fields may be omitted.
Unknown fields are rejected.
Duplicate fields are rejected.
Each field expression must type-check against the record field type.
Nested record initializers are allowed where the expected field type is a record.
The alternative TypeName(field: expr, ...) syntax is not accepted for record initialization.
```

## Field Values Are Ordinary Expressions

A record initializer does not need a special template mechanism for field values.

This is valid because `String.template(...)` returns `String`:

```fh
let person = Person {
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: address
}
```

The verifier checks this in two steps:

```text
String.template("${user}@example.com", user: user_name) => String
email: String => optional String
```

Recommended optional-field rule for v1:

```text
A value of type T may initialize a field of type optional T.
Omitting the field means absent.
```

If a future optional-value wrapper is introduced, this rule can be revisited.

## JSON Field Names Do Not Apply

Record initializers use internal Freehold field names, not external JSON names.

Example:

```fh
record Person
is
    first_name: String @json("firstName")
    email: optional String
end Person
```

Valid Freehold construction:

```fh
let person = Person {
    first_name: first_name,
    email: String.template("${user}@example.com", user: user_name)
}
```

Invalid construction:

```fh
let person = Person {
    firstName: first_name
}
```

Reason:

```text
firstName is the JSON external name.
first_name is the Freehold record field name.
```

Suggested diagnostic direction:

```text
FOUND => firstName
EXPECTED => first_name
HINT => @json("firstName") applies to JSON input/output, not Record initializers.
```

## Relationship To JSON

Record construction and JSON template construction are related but distinct.

```fh
let person = Person {
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: address
}
```

builds a Freehold `Person` value directly.

```fh
let person_result = Json.template<Person>(
    "{ \"name\": ${name}, \"age\": ${age} }",
    name: first_name,
    age: age
)
```

builds a JSON value structurally and validates it against the record-derived schema for `Person`.

Recommended distinction:

```text
Person { ... }
    Construct a record from Freehold expressions.

Json.template<Person>(...)
    Construct JSON-with-holes and validate it against Person.

Json.parse<Person>(text)
    Parse external JSON text and validate it against Person.
```

## Invalid Examples

Missing required field:

```fh
let person = Person {
    name: first_name,
    age: age
}
```

if `tags` and `address` are required.

Unknown field:

```fh
let person = Person {
    name: first_name,
    age: age,
    display_name: display_name,
    tags: tags,
    address: address
}
```

Duplicate field:

```fh
let person = Person {
    name: first_name,
    name: other_name,
    age: age,
    tags: tags,
    address: address
}
```

Wrong field type:

```fh
let person = Person {
    name: first_name,
    age: "42",
    tags: tags,
    address: address
}
```

## Diagnostics

Suggested stable range:

```text
FH-REC-4300..4399  record construction diagnostics
```

Suggested diagnostics:

```text
FH-REC-4301 unknown record initializer type
FH-REC-4302 initializer target is not a record
FH-REC-4303 missing required record field
FH-REC-4304 unknown record field
FH-REC-4305 duplicate record field
FH-REC-4306 record field type mismatch
FH-REC-4307 JSON field name used in record initializer
FH-REC-4308 optional field initializer mismatch
```

Diagnostics should report:

```text
FOUND => supplied field or expression type
EXPECTED => declared record field or field type
HINT => specific correction where obvious
```

## Positive Matrix Targets

Future valid cases:

```text
record_initializer_minimal_required_fields
record_initializer_with_optional_field
record_initializer_with_nested_record
record_initializer_with_string_template_field
record_initializer_with_array_field
record_initializer_with_json_annotated_field_using_internal_name
record_initializer_result_return
record_initializer_inside_contract_checked_expression if contracts allow construction
```

Future invalid cases:

```text
record_initializer_missing_required_field
record_initializer_unknown_field
record_initializer_duplicate_field
record_initializer_wrong_field_type
record_initializer_uses_json_external_name
record_initializer_optional_wrong_inner_type
record_constructor_parentheses_rejected
```

## Summary Rules

```text
Use TypeName { field: expr, ... } to construct records.
Do not add a second TypeName(field: expr, ...) notation for records.
Field values are ordinary expressions, so String.template(...) is valid in a field.
Initializer names are Freehold field names, not @json external names.
Optional fields may be omitted.
Nested record initializers are allowed.
Record initializers are distinct from Json.template<RecordType>(...).
```

=== CLOSED ===
