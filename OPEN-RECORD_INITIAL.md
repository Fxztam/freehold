# Open Record Initializers

This document captures the open design surface for constructing Freehold record values from named field values.

## Decision Direction

Record values should be initialized through the record type name as a constructor:

```fh
let person: Person = Person(
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: address
)
```

If type inference is allowed for record constructors, this should also be valid:

```fh
let person = Person(
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: address
)
```

The record type itself is the constructor. There is no separate `Person.template(...)` form.

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
let person = Person(
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: Address(
        street: street,
        city: city,
        zip: zip
    )
)
```

## Core Rules

```text
Record constructors use TypeName(field: expr, ...).
The constructor target must be a declared record type.
Constructor field names are Freehold record field names.
Constructor field values are ordinary Freehold expressions.
All required fields must be supplied.
Optional fields may be omitted.
Unknown fields are rejected.
Duplicate fields are rejected.
Each field expression must type-check against the record field type.
Nested record constructors are allowed where the expected field type is a record.
```

## Field Values Are Ordinary Expressions

A record constructor does not need a special template mechanism for field values.

This is valid because `String.template(...)` returns `String`:

```fh
let person = Person(
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: address
)
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

Record constructors use internal Freehold field names, not external JSON names.

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
let person = Person(
    first_name: first_name,
    email: String.template("${user}@example.com", user: user_name)
)
```

Invalid construction:

```fh
let person = Person(
    firstName: first_name
)
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
HINT => @json("firstName") applies to JSON input/output, not Record constructors.
```

## Relationship To JSON

Record construction and JSON template construction are related but distinct.

```fh
let person = Person(
    name: first_name,
    age: age,
    email: String.template("${user}@example.com", user: user_name),
    tags: tags,
    address: address
)
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
Person(...)
    Construct a record from Freehold expressions.

Json.template<Person>(...)
    Construct JSON-with-holes and validate it against Person.

Json.parse<Person>(text)
    Parse external JSON text and validate it against Person.
```

## Invalid Examples

Missing required field:

```fh
let person = Person(
    name: first_name,
    age: age
)
```

if `tags` and `address` are required.

Unknown field:

```fh
let person = Person(
    name: first_name,
    age: age,
    display_name: display_name,
    tags: tags,
    address: address
)
```

Duplicate field:

```fh
let person = Person(
    name: first_name,
    name: other_name,
    age: age,
    tags: tags,
    address: address
)
```

Wrong field type:

```fh
let person = Person(
    name: first_name,
    age: "42",
    tags: tags,
    address: address
)
```

## Diagnostics

Suggested stable range:

```text
FH-REC-4300..4399  record construction diagnostics
```

Suggested diagnostics:

```text
FH-REC-4301 unknown record constructor type
FH-REC-4302 constructor target is not a record
FH-REC-4303 missing required record field
FH-REC-4304 unknown record field
FH-REC-4305 duplicate record field
FH-REC-4306 record field type mismatch
FH-REC-4307 JSON field name used in Record constructor
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
record_constructor_minimal_required_fields
record_constructor_with_optional_field
record_constructor_with_nested_record
record_constructor_with_string_template_field
record_constructor_with_array_field
record_constructor_with_json_annotated_field_using_internal_name
record_constructor_result_return
record_constructor_inside_contract_checked_expression if contracts allow construction
```

Future invalid cases:

```text
record_constructor_missing_required_field
record_constructor_unknown_field
record_constructor_duplicate_field
record_constructor_wrong_field_type
record_constructor_uses_json_external_name
record_constructor_optional_wrong_inner_type
```

## Summary Rules

```text
Use TypeName(field: expr, ...) to construct records.
The record type name is the constructor.
Field values are ordinary expressions, so String.template(...) is valid in a field.
Constructor names are Freehold field names, not @json external names.
Optional fields may be omitted.
Nested record constructors are allowed.
Record constructors are distinct from Json.template<RecordType>(...).
```
