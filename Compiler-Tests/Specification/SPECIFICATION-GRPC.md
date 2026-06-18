# Freehold Specification: gRPC IDL and Bindings
**Status:** Baseline gRPC IDL, proto3 generation, streaming RPCs, and Go binding model  
**Audience:** Freehold authors, verifier implementers, backend authors, and service-interface designers

This document explains how Freehold describes gRPC services. Freehold treats gRPC as an IDL layer built from records and service declarations:

```text
record + proto field ids  -> protobuf message
service + rpc             -> protobuf service
stream marker             -> gRPC streaming method
```

The goal is stable interface definition first, with generated proto3 and Go gRPC bindings as build artifacts.

---

## 1. Minimal Unary Service

A unary service uses one request message and one response message:

```freehold
module Grpc.Basic

type UserRequest is record
    id: String proto 1
end record

type UserReply is record
    name: String proto 1
    active: Boolean proto 2
end record

service UserService is
    rpc GetUser(request: UserRequest): UserReply
end UserService

end Grpc.Basic
```

This generates proto3 in this shape:

```proto
syntax = "proto3";

package grpc.basic;

message UserRequest {
  string id = 1;
}

message UserReply {
  string name = 1;
  bool active = 2;
}

service UserService {
  rpc GetUser (UserRequest) returns (UserReply);
}
```

---

## 2. Records as Protobuf Messages

Freehold records used by gRPC RPCs become protobuf messages.

Every field in a gRPC message must have a stable protobuf field id:

```freehold
type UserReply is record
    name: String proto 1
    active: Boolean proto 2
end record
```

The `proto N` number is part of the external wire schema. Once published, it should not be reused for a different field.

Normal Freehold records may exist without `proto N`, but records used as RPC request or response messages need proto ids on all fields, including nested record fields reached from the message graph.

---

## 3. Proto Field ID Rules

Valid proto ids are positive integers:

```freehold
type UserRequest is record
    id: String proto 1
end record
```

Invalid:

```freehold
type UserRequest is record
    id: String proto 0
end record
```

Duplicate ids in one record are rejected:

```freehold
type UserReply is record
    name: String proto 1
    active: Boolean proto 1
end record
```

Missing proto ids are rejected for records used by services:

```freehold
type UserRequest is record
    id: String
end record

type UserReply is record
    name: String proto 1
end record

service UserService is
    rpc GetUser(request: UserRequest): UserReply
end UserService
```

The request type is a gRPC message, so `UserRequest.id` must declare a proto id.

---

## 4. Service Declarations

A service declaration groups one or more RPCs:

```freehold
service UserService is
    rpc GetUser(request: UserRequest): UserReply
    rpc ListUsers(request: ListUsersRequest): ListUsersReply
end UserService
```

The grammar shape is:

```ebnf
service_decl ::= 'service' NAME 'is' rpc_decl+ 'end' NAME
rpc_decl     ::= 'rpc' NAME '(' NAME ':' stream_marker? type_ref ')' ':' stream_marker? type_ref
stream_marker ::= 'stream'
```

The request parameter name is part of the Freehold IDL declaration:

```freehold
rpc GetUser(request: UserRequest): UserReply
```

The request and response types must name declared record types. Generic result types such as `Result<T,E>` are not protobuf messages and should not be used directly as RPC request or response types.

---

## 5. Unary RPCs

A unary RPC has one request and one response:

```freehold
service UserService is
    rpc GetUser(request: UserRequest): UserReply
end UserService
```

Generated proto:

```proto
service UserService {
  rpc GetUser (UserRequest) returns (UserReply);
}
```

Use unary RPCs for request/response operations such as:

- lookup by id,
- create/update commands,
- validation calls,
- small queries with bounded response size.

---

## 6. Streaming RPCs

Use `stream` before the request type, the response type, or both.

```freehold
type StreamRequest is record
    query: String proto 1
end record

type StreamResponse is record
    response_data: String proto 1
end record

service RouteService is
    rpc GetRoute(request: StreamRequest): stream StreamResponse
    rpc RecordRoute(request: stream StreamRequest): StreamResponse
    rpc Chat(request: stream StreamRequest): stream StreamResponse
end RouteService
```

Generated proto:

```proto
service RouteService {
  rpc GetRoute (StreamRequest) returns (stream StreamResponse);
  rpc RecordRoute (stream StreamRequest) returns (StreamResponse);
  rpc Chat (stream StreamRequest) returns (stream StreamResponse);
}
```

Streaming forms:

| Freehold RPC | gRPC Form | Meaning |
| :--- | :--- | :--- |
| `rpc Get(request: Req): Resp` | unary | one request, one response |
| `rpc Get(request: Req): stream Resp` | server streaming | one request, response sequence |
| `rpc Send(request: stream Req): Resp` | client streaming | request sequence, one response |
| `rpc Chat(request: stream Req): stream Resp` | bidirectional streaming | request sequence, response sequence |

---

## 7. Supported Protobuf Type Mapping

Freehold maps the currently supported IDL field types to protobuf as follows:

| Freehold Field Type | Protobuf Field Type |
| :--- | :--- |
| `String` | `string` |
| `Boolean` | `bool` |
| `Integer` | `int64` |
| `Double` | `double` |
| record type | message type |
| `Array<T>` | `repeated T` |

Example:

```freehold
type NestedMessage is record
    label: String proto 1
end record

type MappingRequest is record
    name: String proto 1
    active: Boolean proto 2
    count: Integer proto 3
    ratio: Double proto 4
    nested: NestedMessage proto 5
    tags: Array<String> proto 6
    children: Array<NestedMessage> proto 7
end record
```

Generated proto:

```proto
message NestedMessage {
  string label = 1;
}

message MappingRequest {
  string name = 1;
  bool active = 2;
  int64 count = 3;
  double ratio = 4;
  NestedMessage nested = 5;
  repeated string tags = 6;
  repeated NestedMessage children = 7;
}
```

Unsupported field types are rejected for gRPC messages:

```freehold
type UserReply is record
    balance: BigInteger proto 1
end record
```

`BigInteger`, `BigFloat`, `Result<T,E>`, generic records, ranges, and specification-only types need explicit mapping rules before they can become protobuf fields.

---

## 8. Nested Message Closure

When a record is used as an RPC request or response, all nested records reachable through its fields also become part of the gRPC message graph.

```freehold
type Address is record
    city: String proto 1
end record

type Customer is record
    id: String proto 1
    address: Address proto 2
end record

type CustomerRequest is record
    customer: Customer proto 1
end record

service CustomerService is
    rpc Save(request: CustomerRequest): CustomerRequest
end CustomerService
```

`Address`, `Customer`, and `CustomerRequest` all need valid proto field ids because the service exposes them transitively.

---

## 9. Package Naming

The generated proto package is derived from the Freehold module name.

```freehold
module GrpcIdl.UnaryServiceProtoFields
```

Generates:

```proto
package grpcidl.unaryserviceprotofields;
```

Use stable module names for published APIs. Renaming a module changes the generated protobuf package and is therefore an interface-breaking change.

---

## 10. Proto Generation

Generate proto3 from a Freehold gRPC IDL file with:

```powershell
python -m freehold grpc-proto path\to\service.fh
```

Write to a file:

```powershell
python -m freehold grpc-proto path\to\service.fh --output service.proto
```

The generator verifies the Freehold module before emitting proto output. Invalid field ids, unknown RPC types, unsupported proto field types, and duplicate RPC names are reported before code is generated.

---

## 11. Go gRPC Bindings

Generate Go gRPC bindings with:

```powershell
python -m freehold grpc-go-bindings path\to\service.fh
```

Write to a file:

```powershell
python -m freehold grpc-go-bindings path\to\service.fh --output service_grpc_bindings.go
```

The generated Go bindings provide:

- a service handler interface,
- a server adapter around the handler,
- a registration helper,
- client wrapper interfaces,
- status mapping through `freeholdGrpcStatus`,
- context-aware handling for unary and streaming calls,
- a `FreeholdGrpcErrorRegistry` for custom runtime status mappings.

For a streaming service, the generated handler interface has shapes like:

```go
type RouteServiceHandler interface {
    GetRoute(request *pb.StreamRequest, stream pb.RouteService_GetRouteServer) error
    RecordRoute(stream pb.RouteService_RecordRouteServer) error
    Chat(stream pb.RouteService_ChatServer) error
}
```

The generated adapter maps handler errors through the gRPC status helper before returning them to the transport.

---

## 12. Error and Status Mapping

Freehold gRPC bindings keep transport failures separate from domain errors.

The generated Go status helper preserves common context failures:

```text
context.Canceled          -> gRPC Canceled
context.DeadlineExceeded -> gRPC DeadlineExceeded
other unmapped errors     -> gRPC Unknown
```

Generated bindings also expose a registry concept:

```go
type FreeholdGrpcErrorMapping struct {
    Code     codes.Code
    Metadata map[string]string
}

var FreeholdGrpcErrorRegistry = map[string]FreeholdGrpcErrorMapping{}
```

This allows runtime mapping of domain error strings to gRPC status codes and metadata.

In Freehold source, `Result<T,E>`, `return error E`, `abort E`, and `aborts E` are language-level error mechanisms. A gRPC service IDL should not expose `Result<T,E>` directly as a protobuf message. Instead, map service-level failures to transport status codes or explicit response records.

---

## 13. Common Diagnostics

### 13.1 Missing Proto Field ID

Invalid:

```freehold
type UserRequest is record
    id: String
end record

service UserService is
    rpc GetUser(request: UserRequest): UserRequest
end UserService
```

The record is used as an RPC message, so `id` must be assigned a stable proto id.

### 13.2 Duplicate Proto Field ID

Invalid:

```freehold
type UserReply is record
    name: String proto 1
    active: Boolean proto 1
end record
```

Each proto field id must be unique inside one record.

### 13.3 Invalid Proto Field ID

Invalid:

```freehold
type UserRequest is record
    id: String proto -1
end record
```

Use positive integers such as `proto 1`, `proto 2`, and so on.

### 13.4 Unknown RPC Type

Invalid:

```freehold
service UserService is
    rpc GetUser(request: MissingRequest): MissingReply
end UserService
```

Request and response types must be declared records.

### 13.5 Unsupported Proto Field Type

Invalid:

```freehold
type UserReply is record
    balance: BigInteger proto 1
end record
```

Only supported protobuf-compatible field types are allowed in gRPC messages.

### 13.6 Duplicate RPC Name

Invalid:

```freehold
service UserService is
    rpc GetUser(request: UserRequest): UserReply
    rpc GetUser(request: UserRequest): UserReply
end UserService
```

Each RPC name may appear only once inside a service.

---

## 14. Schema Evolution Rules

The core rule is simple:

```text
Never reuse a published proto field id for a different meaning.
```

Recommended practice:

- Add new fields with new proto ids.
- Do not change the type of an existing field after publishing.
- Do not move a field name to a different proto id.
- Do not reuse deleted field ids.
- Keep module names stable because they define proto package names.
- Keep service and RPC names stable for public APIs.

Future Freehold versions may add explicit reserved field ids, but the current safe practice is to track deleted ids in API documentation.

---

## 15. IDL Versus Implementation

A Freehold `service` declaration describes the gRPC interface. It is not the service implementation body.

```freehold
service UserService is
    rpc GetUser(request: UserRequest): UserReply
end UserService
```

Implementation is provided by generated Go bindings and user handler code, or by later Freehold-to-service binding layers.

The separation is intentional:

```text
Freehold service IDL -> proto and binding contracts
Freehold routines    -> ordinary verified computation
Go handlers          -> transport adapter implementation today
```

This keeps the wire schema explicit and prevents accidental coupling between RPC names and unrelated routine names.

---

## 16. Practical Checklist

Before committing a gRPC IDL module, check:

- Every RPC request and response type is a declared record.
- Every exposed record field has a positive `proto N` id.
- Proto ids are unique inside each record.
- Nested records used by messages also have complete proto ids.
- Field types are protobuf-compatible: `String`, `Boolean`, `Integer`, `Double`, records, or arrays of supported types.
- Streaming RPCs use `stream` on the side that is a sequence.
- RPC names are unique inside each service.
- Module names are stable because they generate proto package names.
- Public field ids are treated as permanent wire-schema numbers.
- Generated proto and Go bindings are regenerated after IDL changes.

A Freehold gRPC file is a contract. Treat every `proto N`, service name, RPC name, and message field as part of the public API once generated artifacts are published.
