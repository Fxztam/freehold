# Freehold Specification: Record JSON
**Status:** Baseline record-to-JSON mapping, field aliases, strict parsing, schema validation, and JSON serialization rules  
**Audience:** Freehold authors, verifier implementers, conformance-test writers, API authors, and backend authors

This document explains how Freehold records map to JSON.

The core model is:

```text
type Person is record ... end record       Freehold schema
field: Type @json("externalName")          external JSON field name
Json.stringify(record_value)               record -> String
Json.parse<RecordType>(text)                String -> Result<RecordType, SchemaError>
```

Records are the canonical schema source. JSON parsing and serialization are derived from the Freehold record declaration.

---

## 1. Record Schema

A record declares the fields that must exist in JSON:

```freehold
type Person is record
    name: String
    age: Integer
    active: Boolean
end record
```

The equivalent JSON object shape is:

```json
{"name":"Ada","age":37,"active":true}
```

Each record field becomes a required JSON object field unless an external name is given with `@json`.

---

## 2. Record Construction

Freehold code constructs records with the Freehold field names:

```freehold
let person: Person = Person {
    name: "Ada",
    age: 37,
    active: true
}
```

The record constructor does not use external JSON names. It always uses the names from the Freehold record declaration.

---

## 3. External Field Names With `@json`

A record field can define its external JSON name:

```freehold
type Person is record
    first_name: String @json("firstName")
    age: Integer
end record
```

JSON then uses `firstName`:

```json
{"firstName":"Ada","age":37}
```

Freehold code still uses `first_name`:

```freehold
let parsed: Result<Person, SchemaError> = Json.parse<Person>(text)
check parsed.ok
check parsed.value.first_name = "Ada"
```

`@json` field names must be non-empty and unique within the record.

Invalid:

```freehold
type Person is record
    first_name: String @json("name")
    last_name: String @json("name")
end record
```

Both fields map to the same external JSON key, so the verifier rejects the record declaration.

---

## 4. Field Name Matching Is Exact

When a field has an external JSON name, the JSON input must use that name.

Given:

```freehold
type Person is record
    first_name: String @json("firstName")
    age: Integer
end record
```

Valid:

```json
{"firstName":"Ada","age":37}
```

Invalid:

```json
{"first_name":"Ada","age":37}
```

The JSON key `first_name` is unknown, and the required JSON key `firstName` is missing.

---

## 5. `Json.stringify`

`Json.stringify` serializes a record value to compact JSON text:

```freehold
type Person is record
    name: String
    age: Integer
    active: Boolean
end record

procedure main()
is
    let person: Person = Person {
        name: "Ada",
        age: 37,
        active: true
    }
    let text: String = Json.stringify(person)
    check text = "{\"name\":\"Ada\",\"age\":37,\"active\":true}"
end main
```

The top-level argument must be a record value.

Invalid:

```freehold
let text: String = Json.stringify("Ada")
```

`Json.stringify` accepts exactly one argument.

Invalid:

```freehold
let text: String = Json.stringify(person, person)
```

---

## 6. Stringify Field Types

`Json.stringify` supports record fields whose values are JSON-compatible Freehold values:

```text
String
Integer
Boolean
Double
record values
Array<T, N> where T is JSON-compatible
```

Nested records are serialized as nested JSON objects. Arrays are serialized as JSON arrays.

Unsupported values must be converted before serialization.

Invalid:

```freehold
type Payload is record
    hash: BigInteger
end record

procedure main()
is
    let hash: BigInteger = Big.int("123")
    let payload: Payload = Payload { hash: hash }
    let text: String = Json.stringify(payload)
end main
```

`BigInteger` is not a JSON-compatible field type in the current baseline. Convert it to `String` or another supported representation first.

---

## 7. `Json.parse<Record>`

`Json.parse` decodes JSON text into a record result:

```freehold
let text: String = "{\"name\":\"Ada\",\"age\":37,\"active\":true}"
let parsed: Result<Person, SchemaError> = Json.parse<Person>(text)
check parsed.ok
check parsed.value.name = "Ada"
check parsed.value.age = 37
check parsed.value.active = true
```

The type argument must be a record type. The return type is:

```freehold
Result<Person, SchemaError>
```

`SchemaError` is the built-in error type used when JSON does not match the requested record schema.

Invalid:

```freehold
let parsed: Result<Integer, SchemaError> = Json.parse<Integer>("37")
```

`Integer` is not a record type.

`Json.parse` requires exactly one type argument:

```freehold
let parsed: Result<Person, SchemaError> = Json.parse<Person>(text)
```

Invalid:

```freehold
let parsed: Result<Person, SchemaError> = Json.parse(text)
```

`Json.parse` also accepts exactly one value argument, the JSON text.

---

## 8. Literal JSON Validation

When the argument to `Json.parse<Record>` is a string literal, the verifier validates it at compile time:

```freehold
let parsed: Result<Person, SchemaError> = Json.parse<Person>("{\"name\":\"Ada\",\"age\":37,\"active\":true}")
```

For literal JSON, the object must match the record schema exactly:

- The text must be well-formed JSON.
- The top-level JSON value must be an object.
- Every required field must be present.
- No unknown fields are allowed.
- No duplicate object keys are allowed.
- Field values must match the Freehold field types.
- Integer values must be inside the supported JSON integer range.
- Range subtype bounds must hold.
- Array fields must have exactly the declared fixed length.

Invalid literal examples are semantic errors:

```freehold
let parsed: Result<Person, SchemaError> = Json.parse<Person>("{\"name\":")
```

```freehold
let parsed: Result<Person, SchemaError> = Json.parse<Person>("{\"name\":\"Ada\",\"name\":\"Grace\"}")
```

```freehold
let parsed: Result<Person, SchemaError> = Json.parse<Person>("{\"name\":\"Ada\",\"age\":\"old\",\"active\":true}")
```

---

## 9. Runtime JSON Validation

When the JSON text comes from a variable or runtime source, invalid JSON is represented as a `Result` failure:

```freehold
let bad_text: String = "{\"name\":\"Ada\",\"age\":\"old\",\"active\":true}"
let bad: Result<Person, SchemaError> = Json.parse<Person>(bad_text)
check bad.ok = false
```

Use this pattern for untrusted input from files, network messages, WebSocket payloads, gRPC bridges, and external APIs.

Do not access `parsed.value` until `parsed.ok` is known to be true:

```freehold
let parsed: Result<Person, SchemaError> = Json.parse<Person>(text)
check parsed.ok
check parsed.value.name = "Ada"
```

---

## 10. Nested Records

Records can contain other records:

```freehold
type Address is record
    city: String
    zip: Integer
end record

type Person is record
    first_name: String @json("firstName")
    address: Address
    active: Boolean
end record
```

Valid JSON:

```json
{"firstName":"Ada","address":{"city":"London","zip":12345},"active":true}
```

The nested object must match `Address` exactly. Unknown nested fields are rejected.

Invalid:

```json
{"firstName":"Ada","address":{"city":"London","zip":12345,"country":"UK"},"active":true}
```

The nested field `country` is not declared in `Address`.

---

## 11. Arrays in JSON Records

Records can contain fixed-size arrays:

```freehold
type Person is record
    first_name: String @json("firstName")
    tags: Array<String, 2>
    active: Boolean
end record
```

Valid JSON:

```json
{"firstName":"Ada","tags":["math","code"],"active":true}
```

The JSON array length must match the Freehold array size.

Invalid:

```json
{"firstName":"Ada","tags":["math"],"active":true}
```

`tags` has length 1, but the schema requires `Array<String, 2>`.

---

## 12. Range Subtypes

Range subtypes are enforced during JSON parsing.

```freehold
type ZipCode is Integer range 10000..99999

type Address is record
    city: String
    zip: ZipCode
end record
```

Valid:

```json
{"city":"London","zip":12345}
```

Invalid:

```json
{"city":"London","zip":999}
```

The value `999` is outside `ZipCode`.

---

## 13. WebSocket and API Payload Pattern

Records are the recommended way to define structured API and WebSocket payloads:

```freehold
type ChatPayload is record
    room: String
    text: String
end record

type ChatMessage is record
    kind: String
    client_id: String @json("clientId")
    payload: ChatPayload
end record

type BroadcastEnvelope is record
    event: String
    recipients: Array<String, 2>
    message: ChatMessage
end record
```

Parsing an incoming payload:

```freehold
let text: String = "{\"event\":\"broadcast\",\"recipients\":[\"client-a\",\"client-b\"],\"message\":{\"kind\":\"chat\",\"clientId\":\"client-a\",\"payload\":{\"room\":\"main\",\"text\":\"hello broadcast\"}}}"
let parsed: Result<BroadcastEnvelope, SchemaError> = Json.parse<BroadcastEnvelope>(text)
check parsed.ok
check parsed.value.message.client_id = "client-a"
```

Serializing a checked payload:

```freehold
let encoded: String = Json.stringify(parsed.value)
check encoded = text
```

This pattern makes the wire contract explicit and keeps schema failure inside `Result<_, SchemaError>`.

---

## 14. Missing and Unknown Fields

Every record field is required.

Given:

```freehold
type Person is record
    first_name: String @json("firstName")
    active: Boolean
end record
```

Invalid, missing `active`:

```json
{"firstName":"Ada"}
```

Invalid, unknown field `extra`:

```json
{"firstName":"Ada","active":true,"extra":true}
```

Freehold JSON records are strict by default. There is no implicit ignore-unknown-fields mode in the current baseline.

---

## 15. Null Values

The current baseline does not define nullable record fields. JSON `null` does not match `String`, `Integer`, `Boolean`, `Double`, record, or array fields.

Invalid:

```json
{"name":null,"age":37,"active":true}
```

Model absence explicitly with a choice type or another domain-specific representation when optional data is needed.

---

## 16. Common Failure Patterns

### 16.1 `Json.stringify` on a Scalar

Invalid:

```freehold
let text: String = Json.stringify("Ada")
```

Top-level stringify expects a record value.

### 16.2 Unsupported Field Type

Invalid:

```freehold
type Payload is record
    hash: BigInteger
end record
```

Convert unsupported fields before serialization.

### 16.3 Duplicate External Names

Invalid:

```freehold
type Person is record
    first_name: String @json("name")
    last_name: String @json("name")
end record
```

External JSON keys must be unique within one record.

### 16.4 Missing Parse Type Argument

Invalid:

```freehold
let parsed: Result<Person, SchemaError> = Json.parse(text)
```

Use:

```freehold
let parsed: Result<Person, SchemaError> = Json.parse<Person>(text)
```

### 16.5 Non-Record Parse Target

Invalid:

```freehold
let parsed: Result<Integer, SchemaError> = Json.parse<Integer>("37")
```

The parse target must be a record type.

### 16.6 Wrong External Field Name

Invalid:

```json
{"first_name":"Ada"}
```

If the field has `@json("firstName")`, the JSON key must be `firstName`.

### 16.7 Array Length Mismatch

Invalid:

```json
{"tags":["math"]}
```

If the field type is `Array<String, 2>`, the JSON array must contain exactly two strings.

---

## 17. Practical Checklist

Before committing Record JSON code, check:

- The top-level JSON schema is a Freehold record type.
- Every JSON field is represented by a record field.
- External field names use `@json("name")` only when the wire name differs from the Freehold name.
- All `@json` names are non-empty and unique within the record.
- Record constructors use Freehold field names, not external JSON names.
- `Json.stringify` receives exactly one record value.
- All serialized field types are JSON-compatible.
- `Json.parse<Record>` has exactly one record type argument.
- The parse result is stored as `Result<Record, SchemaError>`.
- Code checks `.ok` before using `.value`.
- Literal JSON parse calls are expected to pass compile-time schema validation.
- Dynamic JSON input is handled through `parsed.ok = false` on schema failure.
- Nested records and arrays match their schema exactly.
- Range subtypes are valid for all parsed numeric fields.

A good Freehold JSON boundary keeps the wire schema in record declarations, uses `@json` only for external names, and treats parsing as a checked `Result` operation.
