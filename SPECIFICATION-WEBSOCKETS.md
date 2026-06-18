# Freehold Specification: WebSockets
**Status:** Baseline WebSocket runtime module, typed JSON messaging, broadcast validation, and Go-native transport mapping  
**Audience:** Freehold authors, verifier implementers, backend authors, and realtime application designers

This document explains how WebSockets are modeled in Freehold. WebSocket support is not new core syntax. It is a trusted standard module and runtime binding:

```text
Std.Connect.WebSocket  -> Freehold module surface
Connection             -> bidirectional text channel pair
ConnectionScope        -> long-lived connection lifetime
MessageScope           -> one inbound message lifetime
Json.parse<Record>     -> typed incoming message validation
Json.stringify(record) -> deterministic outgoing JSON text
```

The design goal is to keep WebSocket programs ordinary Freehold programs: typed records, `Result<T,E>`, async functions, channels, scopes, and JSON schema validation.

---

## 1. Module Surface

The primary WebSocket module is:

```freehold
import Std.Connect.WebSocket exposing Connection, ConnectionScope, MessageScope, TextMessage, FramePolicy, CloseStatus, Server, WebSocketError, connect, listen, accept, new_connection_scope, new_message_scope, default_frame_policy, receive_text, send_text, try_send_text, close_with_status, close, close_server
```

The module declares a dedicated error:

```freehold
error WebSocketError
```

Connection and server handles:

```freehold
type Connection is record
    id: String
    incoming: Receiver<String>
    outgoing: Sender<String>
end record

type Server is record
    id: String
end record
```

The connection is represented as two text channels:

```text
incoming: Receiver<String>  messages received from peer
outgoing: Sender<String>    messages sent to peer
```

---

## 2. Connection and Server API

Client connection:

```freehold
async function connect(url: String) returns Result<Connection, WebSocketError>
```

Server listen:

```freehold
function listen(addr: String) returns Result<Server, WebSocketError>
```

Server accept:

```freehold
async function accept(server: Server) returns Result<Connection, WebSocketError>
```

Close operations:

```freehold
procedure close(conn: Connection)
procedure close_server(server: Server)
```

Example client:

```freehold
async function client_worker(url: String) returns Integer
is
    let client_res: Result<Connection, WebSocketError> = await connect(url)
    if client_res.ok then
        let client_conn: Connection = client_res.value
        let sent: Boolean = await channel_send<String>(client_conn.outgoing, "Hello WebSocket")
        check sent = true
        let reply: String = await channel_receive<String>(client_conn.incoming)
        call close(client_conn)
        return 0
    else
        return 1
    end if
end client_worker
```

Example server worker:

```freehold
async function server_worker(server: Server) returns Integer
is
    let accept_res: Result<Connection, WebSocketError> = await accept(server)
    if accept_res.ok then
        let conn: Connection = accept_res.value
        let msg: String = await channel_receive<String>(conn.incoming)
        let sent: Boolean = await channel_send<String>(conn.outgoing, String.concat("Echo: ", msg))
        check sent = true
        call close(conn)
        return 0
    else
        return 1
    end if
end server_worker
```

---

## 3. Connection Scope

A WebSocket connection is long-lived, so Freehold gives it a named scope record:

```freehold
type ConnectionScope is record
    runtime_scope: Scope
    connection: Connection
    incoming: Receiver<String>
    outgoing: Sender<String>
end record
```

Create a connection scope from a connection:

```freehold
function new_connection_scope(conn: Connection) returns ConnectionScope
```

Example:

```freehold
let connected: Result<Connection, WebSocketError> = await connect(url)
if connected.ok then
    let client_scope: ConnectionScope = new_connection_scope(connected.value)
    let sent: Boolean = await send_text(client_scope, "hello")
end if
```

`runtime_scope` exists because the WebSocket lifetime participates in the same structured-concurrency model as other Freehold scopes. The field is named `runtime_scope` because `scope` is a Freehold keyword.

---

## 4. Message Scope

A message scope describes work for a single inbound message:

```freehold
type MessageScope is record
    runtime_scope: Scope
    connection: ConnectionScope
    message_id: String
    raw: String
end record
```

Factory:

```freehold
function new_message_scope(conn_scope: ConnectionScope, message_id: String, raw: String) returns MessageScope
```

Example:

```freehold
let text_message: TextMessage = await receive_text(conn_scope)
let msg_scope: MessageScope = new_message_scope(conn_scope, "incoming-chat", text_message.text)
let parsed: Result<ChatMessage, SchemaError> = Json.parse<ChatMessage>(msg_scope.raw)
```

Use `MessageScope` when a handler needs a stable id, raw payload, and access to the enclosing connection.

---

## 5. Text Send and Receive

The high-level text API uses `ConnectionScope`:

```freehold
async function receive_text(conn_scope: ConnectionScope) returns TextMessage
async function send_text(conn_scope: ConnectionScope, text: String) returns Boolean
async function try_send_text(conn_scope: ConnectionScope, text: String) returns Boolean
```

`receive_text` wraps an inbound string:

```freehold
type TextMessage is record
    text: String
end record
```

Send example:

```freehold
let sent: Boolean = await send_text(conn_scope, Json.stringify(message))
check sent
```

Receive example:

```freehold
let inbound: TextMessage = await receive_text(conn_scope)
let parsed: Result<ChatMessage, SchemaError> = Json.parse<ChatMessage>(inbound.text)
```

`send_text` is the normal send path. `try_send_text` is the backpressure-aware send path.

---

## 6. Backpressure

WebSocket delivery should not assume every outgoing queue can accept a message immediately. Use `try_send_text` or `channel_try_send` when overload must be observable.

```freehold
async function broadcast_to_room(registry: ConnectionRegistry, room: String, text: String) returns BroadcastResult
is
    let queued_a: Boolean = await try_send_text(registry.client_a.conn, text)
    let queued_b: Boolean = await try_send_text(registry.client_b.conn, text)
    return BroadcastResult { queued_a: queued_a, queued_b: queued_b }
end broadcast_to_room
```

A failed queue attempt should usually result in one of these policies:

- drop the message,
- close the client,
- mark the room delivery as partial,
- retry inside a scoped timeout.

Example queue probe:

```freehold
async function backpressure_probe() returns Boolean
is
    let queue_channel: Channel<String> = channel<String>(1)
    let queue_sender: Sender<String> = channel_sender<String>(queue_channel)
    let first: Boolean = await channel_try_send<String>(queue_sender, "queued")
    let second: Boolean = await channel_try_send<String>(queue_sender, "dropped")
    return first and second = false
end backpressure_probe
```

---

## 7. Frame Policy

The baseline frame policy is text JSON only:

```freehold
type FramePolicy is record
    text_json_only: Boolean
    fragmented_supported: Boolean
    binary_supported: Boolean
    close_on_unsupported: Boolean
end record
```

Default policy:

```freehold
function default_frame_policy() returns FramePolicy
```

Equivalent shape:

```freehold
function websocket_frame_policy() returns FramePolicy
is
    return FramePolicy {
        text_json_only: true,
        fragmented_supported: false,
        binary_supported: false,
        close_on_unsupported: true
    }
end websocket_frame_policy
```

Classifying frames:

```freehold
function classify_frame_policy(frame_kind: String, fragmented: Boolean) returns DeliveryStatus
is
    let policy: FramePolicy = websocket_frame_policy()
    if fragmented then
        return DeliveryStatus { accepted: false, error_sent: false, disconnect_client: policy.close_on_unsupported, disconnect_room: false }
    else
        if frame_kind = "text" then
            return DeliveryStatus { accepted: policy.text_json_only, error_sent: false, disconnect_client: false, disconnect_room: false }
        else
            return DeliveryStatus { accepted: false, error_sent: false, disconnect_client: policy.close_on_unsupported, disconnect_room: false }
        end if
    end if
end classify_frame_policy
```

Binary messages are represented in the module surface, but the baseline application policy rejects binary and fragmented frames unless explicitly supported.

---

## 8. Close Status

Close status is represented as data:

```freehold
type CloseStatus is record
    closed: Boolean
    reason: String
end record
```

Close with reason:

```freehold
function close_with_status(conn_scope: ConnectionScope, reason: String) returns CloseStatus
```

Example:

```freehold
let closed: CloseStatus = close_with_status(conn_scope, "idle timeout")
check closed.closed
```

Use clear reasons such as:

```text
idle timeout
invalid json
unsupported frame
broadcast complete
keepalive failed
```

---

## 9. Typed JSON Messages

WebSocket payloads are text. Freehold applications should model those texts as typed records and use JSON conversion at the boundary.

Example message records:

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
```

Parse inbound text:

```freehold
let parsed: Result<ChatMessage, SchemaError> = Json.parse<ChatMessage>(raw)
if parsed.ok then
    let room: String = parsed.value.payload.room
end if
```

Serialize outbound text:

```freehold
let outgoing: String = Json.stringify(parsed.value)
let sent: Boolean = await send_text(conn_scope, outgoing)
```

The `@json("clientId")` annotation maps an external JSON key to an internal Freehold field name.

---

## 10. Broadcast Envelope

A typed broadcast should have an explicit envelope:

```freehold
type BroadcastEnvelope is record
    event: String
    recipients: Array<String, 2>
    message: ChatMessage
end record
```

Roundtrip example:

```freehold
procedure main()
is
    let text: String = "{\"event\":\"broadcast\",\"recipients\":[\"client-a\",\"client-b\"],\"message\":{\"kind\":\"chat\",\"clientId\":\"client-a\",\"payload\":{\"room\":\"main\",\"text\":\"hello broadcast\"}}}"
    let parsed: Result<BroadcastEnvelope, SchemaError> = Json.parse<BroadcastEnvelope>(text)
    check parsed.ok
    check parsed.value.event = "broadcast"
    check parsed.value.message.kind = "chat"
    check parsed.value.message.client_id = "client-a"
    check parsed.value.message.payload.room = "main"
    let encoded: String = Json.stringify(parsed.value)
    check encoded = text
end main
```

This is the preferred shape for multi-client delivery because it separates:

```text
event       what happened
recipients  who should receive it
message     typed domain payload
```

---

## 11. Registry and Room Broadcast

A room registry maps clients to rooms and outgoing scopes or channels.

```freehold
type ClientSlot is record
    client_id: String
    room: String
    conn: ConnectionScope
end record

type ConnectionRegistry is record
    client_a: ClientSlot
    client_b: ClientSlot
end record
```

Broadcast with timeout scope:

```freehold
scope broadcast_scope do
    spawn
        call broadcast_scope.timeout(500)
        let handle: JoinHandle<BroadcastResult> = broadcast_scope.spawn<BroadcastResult>(broadcast_to_room(registry, parsed.value.payload.room, payload))
    join
        let delivered: BroadcastResult = await broadcast_scope.join<BroadcastResult>(handle)
    result
        return delivered.queued_a and delivered.queued_b
end scope
```

The scoped timeout gives delivery a bounded lifetime. This is important for realtime systems where a slow or disconnected client must not block the room.

---

## 12. Keepalive

Ping/pong keepalive messages should be typed records:

```freehold
type PingPayload is record
    nonce: String
end record

type PingMessage is record
    kind: String
    client_id: String @json("clientId")
    payload: PingPayload
end record

type PongPayload is record
    nonce: String
end record

type PongMessage is record
    kind: String
    client_id: String @json("clientId")
    payload: PongPayload
end record
```

Classify a pong:

```freehold
function classify_pong(raw: String, expected_client: String, expected_nonce: String) returns KeepaliveStatus
is
    let parsed: Result<PongMessage, SchemaError> = Json.parse<PongMessage>(raw)
    if parsed.ok and parsed.value.kind = "pong" and parsed.value.client_id = expected_client and parsed.value.payload.nonce = expected_nonce then
        return KeepaliveStatus { ping_sent: true, pong_received: true, timed_out: false, should_close: false }
    else
        return KeepaliveStatus { ping_sent: true, pong_received: false, timed_out: false, should_close: true }
    end if
end classify_pong
```

Keepalive state:

```freehold
type KeepaliveStatus is record
    ping_sent: Boolean
    pong_received: Boolean
    timed_out: Boolean
    should_close: Boolean
end record
```

A failed pong validation should usually close the connection or mark it for cleanup.

---

## 13. Error Messages

Invalid inbound data should produce a typed error message before closing when possible:

```freehold
type ErrorPayload is record
    code: String
    message: String
end record

type ErrorMessage is record
    kind: String
    client_id: String @json("clientId")
    payload: ErrorPayload
end record
```

Example classifier:

```freehold
function classify_chat_message(raw: String) returns DeliveryStatus
is
    let parsed: Result<ChatMessage, SchemaError> = Json.parse<ChatMessage>(raw)
    if parsed.ok then
        return DeliveryStatus { accepted: true, error_sent: false, disconnect_client: false, disconnect_room: false }
    else
        let error_message: ErrorMessage = ErrorMessage {
            kind: "error",
            client_id: "server",
            payload: ErrorPayload { code: "INVALID_JSON", message: "invalid chat message envelope" }
        }
        let encoded: String = Json.stringify(error_message)
        let reparsed: Result<ErrorMessage, SchemaError> = Json.parse<ErrorMessage>(encoded)
        return DeliveryStatus { accepted: false, error_sent: reparsed.ok, disconnect_client: true, disconnect_room: true }
    end if
end classify_chat_message
```

This gives the sender a structured reason while still preserving the server's policy to disconnect invalid clients.

---

## 14. Static and Runtime JSON Validation

`Json.parse<Record>(text)` returns:

```freehold
Result<Record, SchemaError>
```

For string literals, the verifier can reject schema mismatches at semantic time.

Invalid example:

```freehold
let parsed: Result<BroadcastEnvelope, SchemaError> = Json.parse<BroadcastEnvelope>("{\"event\":\"broadcast\",\"recipients\":[\"client-a\",\"client-b\"],\"message\":{\"kind\":\"chat\",\"payload\":{\"room\":\"main\",\"text\":\"hello broadcast\"}}}")
```

The JSON is missing `clientId`, which is required by `ChatMessage` through `@json("clientId")`.

For dynamic text received from a socket, schema failure becomes a runtime `Result` error:

```freehold
let inbound: TextMessage = await receive_text(conn_scope)
let parsed: Result<ChatMessage, SchemaError> = Json.parse<ChatMessage>(inbound.text)
if parsed.ok then
    ...
else
    ...
end if
```

This distinction is important:

```text
literal JSON  -> semantic schema diagnostics when invalid
dynamic JSON  -> Result failure at runtime
```

---

## 15. Native Go Runtime Mapping

`Std.Connect.WebSocket` is a trusted runtime module. The Go backend maps it to native WebSocket transport code.

The runtime implements:

- `connect` with `ws://` and `wss://` support,
- client handshake validation,
- `listen` with TCP listener registration,
- `accept` with WebSocket upgrade validation,
- `Sec-WebSocket-Accept` calculation,
- read/write loops bridged to Freehold channels,
- graceful close of outgoing channels and listener handles.

The Freehold source still sees ordinary records, channels, `Result`, async functions, and procedures. Transport details stay in the backend runtime.

---

## 16. Common Failure Patterns

### 16.1 Ignoring `Result` From `connect` or `accept`

Avoid assuming a socket exists:

```freehold
let connected: Result<Connection, WebSocketError> = await connect(url)
let conn: Connection = connected.value -- unsafe idea unless success is known
```

Prefer:

```freehold
if connected.ok then
    let conn: Connection = connected.value
else
    return 1
end if
```

### 16.2 Sending Untyped JSON Text

Avoid ad hoc strings for domain messages:

```freehold
let sent: Boolean = await send_text(conn_scope, "{bad json}")
```

Prefer typed records:

```freehold
let message: ChatMessage = ChatMessage { kind: "chat", client_id: "client-a", payload: ChatPayload { room: "main", text: "hello" } }
let sent: Boolean = await send_text(conn_scope, Json.stringify(message))
```

### 16.3 No Backpressure Policy

Avoid assuming every client can receive every broadcast:

```freehold
let sent: Boolean = await send_text(conn_scope, text)
```

For broadcast paths, prefer observable queue behavior:

```freehold
let queued: Boolean = await try_send_text(conn_scope, text)
if queued = false then
    let status: CloseStatus = close_with_status(conn_scope, "backpressure")
end if
```

### 16.4 Missing Message Scope

When message handling needs ids, raw payload, and connection context, create a `MessageScope`:

```freehold
let msg_scope: MessageScope = new_message_scope(conn_scope, "chat", inbound.text)
```

This keeps logging, validation, and response routing tied to the same message lifetime.

### 16.5 Accepting Unsupported Frames

If the baseline policy is text JSON only, reject binary or fragmented frames:

```freehold
let policy: FramePolicy = default_frame_policy()
check policy.binary_supported = false
check policy.fragmented_supported = false
```

---

## 17. Practical Checklist

Before committing WebSocket code, check:

- `connect`, `listen`, and `accept` results are checked with `.ok` before `.value` is used.
- Each long-lived connection has a `ConnectionScope`.
- Each significant inbound message has a `MessageScope` when raw text, ids, or scoped work matter.
- Inbound JSON is parsed with `Json.parse<Record>` into a typed message record.
- Outbound JSON is created with `Json.stringify(record)`.
- JSON field naming uses `@json("externalName")` where protocol names differ from Freehold field names.
- Broadcast code has a backpressure policy using `try_send_text` or `channel_try_send`.
- Delivery work is bounded by scopes or timeouts where slow clients could block progress.
- Frame policy explicitly rejects unsupported binary or fragmented frames.
- Keepalive ping/pong records include a nonce and client identity.
- Invalid messages produce a typed error response or a clear close reason.
- `close` or `close_with_status` is called when a connection must end.

A good Freehold WebSocket program treats the socket as an untrusted text stream at the boundary and converts it immediately into typed, verified records.
