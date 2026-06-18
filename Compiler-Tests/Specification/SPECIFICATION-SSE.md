# Freehold Specification: SSE
**Status:** Baseline native Server-Sent Events runtime over HTTP, typed event records, channels, and Go transport mapping  
**Audience:** Freehold authors, verifier implementers, backend authors, and realtime HTTP API designers

This document explains how Server-Sent Events are modeled in Freehold.

SSE support is not new core syntax. It is a standard HTTP runtime surface built from ordinary Freehold concepts:

```text
Std.Connect.Http        HTTP client/server module
SseEvent                one server-sent event frame
SseStream               client-side stream result
Channel<SseEvent>       typed event transport inside Freehold
respond_sse(...)        server response as text/event-stream
open_sse(...)           client opens an SSE stream
```

The design goal is simple: SSE is one-way server-to-client streaming over HTTP, while Freehold code remains typed, async, and channel-based.

---

## 1. Protocol Model

Server-Sent Events use a long-lived HTTP response with content type:

```text
text/event-stream
```

Each event is encoded as one SSE frame:

```text
event: tick
data: value-1

```

Freehold represents this frame as a record:

```freehold
type SseEvent is record
    event_type: String
    data: String
end record
```

`event_type` maps to the SSE `event:` field.  
`data` maps to the SSE `data:` field.

---

## 2. Module Surface

The native SSE surface lives in `Std.Connect.Http` together with the HTTP client/server primitives:

```freehold
import Std.Connect.Http exposing Client, Request, ServerHandle, RequestContext, SseEvent, SseStream, new_client, new_request, new_sse_event, serve, accept_request, respond_sse, open_sse, stop_server
```

Shared connection primitives come from `Std.Connect.Common`:

```freehold
import Std.Connect.Common exposing Endpoint, ConnectError, localhost_http
```

The baseline SSE types are:

```freehold
type SseEvent is record
    event_type: String
    data: String
end record

type SseStream is record
    status_code: Integer
    event_count: Integer
    events: Receiver<SseEvent>
end record
```

`SseStream.events` is a typed receiver. Application code consumes events with `await channel_receive<SseEvent>(stream.events)`.

---

## 3. Creating Events

Use `new_sse_event` to construct the event record:

```freehold
function new_sse_event(event_type: String, data: String) returns SseEvent
is
    return SseEvent { event_type: event_type, data: data }
end new_sse_event
```

Example:

```freehold
let event: SseEvent = new_sse_event("tick", "value-1")
```

The current baseline carries two string fields only. Structured payloads should be encoded into `data`, commonly with `Json.stringify(record)` before constructing the event.

---

## 4. Server Response

The server sends SSE with `respond_sse`:

```freehold
async function respond_sse(request_context: RequestContext, event_count: Integer, events: Receiver<SseEvent>) returns Boolean
```

Parameters:

```text
request_context  accepted HTTP request context
event_count      number of events the server will send
events           receiver that supplies SseEvent values
```

A minimal server worker:

```freehold
async function server_worker(server: ServerHandle) returns Integer
is
    let accepted: Result<RequestContext, ConnectError> = await accept_request(server)
    if accepted.ok = false then
        return 1
    end if

    let event_channel: Channel<SseEvent> = channel<SseEvent>(8)
    let tx: Sender<SseEvent> = channel_sender<SseEvent>(event_channel)
    let rx: Receiver<SseEvent> = channel_receiver<SseEvent>(event_channel)

    let queued_a: Boolean = await channel_send<SseEvent>(tx, new_sse_event("tick", "value-1"))
    let queued_b: Boolean = await channel_send<SseEvent>(tx, new_sse_event("tick", "value-2"))
    let queued_c: Boolean = await channel_send<SseEvent>(tx, new_sse_event("done", "value-3"))

    let sent: Boolean = await respond_sse(accepted.value, 3, rx)
    if sent then
        return 0
    else
        return 1
    end if
end server_worker
```

The event count must match the number of events the receiver can provide for this response.

---

## 5. Native HTTP Mapping

The Go-native backend maps `respond_sse` to an HTTP/1.1 response with headers similar to:

```text
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
X-Event-Count: 3
Connection: close
```

Then it writes one frame per event:

```text
event: tick
data: value-1

```

If `event_type` is an empty string, the native writer omits the `event:` line and writes only `data:`.

The baseline response closes the connection after the declared `event_count` has been sent. This keeps the V1 runtime deterministic and easy to verify.

---

## 6. Client Open

The client opens an SSE stream with `open_sse`:

```freehold
async function open_sse(client: Client, request: Request) returns Result<SseStream, ConnectError>
```

The native client sends an HTTP request with:

```text
Accept: text/event-stream
Connection: close
```

It reads the response status, reads `X-Event-Count`, parses `event:` and `data:` lines, and exposes parsed events through `SseStream.events`.

Example:

```freehold
async function client_worker(client: Client) returns Integer
is
    let request: Request = new_request("GET", "/events")
    let opened: Result<SseStream, ConnectError> = await open_sse(client, request)
    if opened.ok = false then
        return 1
    end if

    if opened.value.status_code != 200 then
        return 1
    end if

    if opened.value.event_count != 3 then
        return 1
    end if

    let event_a: SseEvent = await channel_receive<SseEvent>(opened.value.events)
    let event_b: SseEvent = await channel_receive<SseEvent>(opened.value.events)
    let event_c: SseEvent = await channel_receive<SseEvent>(opened.value.events)

    return 0
end client_worker
```

Always check `opened.ok` before using `opened.value`.

---

## 7. End-to-End Pattern

A complete SSE program usually has these parts:

```text
1. Create an Endpoint.
2. Start an HTTP server with serve(endpoint).
3. Spawn a server worker that accepts one request.
4. Spawn a client worker that calls open_sse.
5. Server sends SseEvent values through a Channel<SseEvent>.
6. Client receives SseEvent values from SseStream.events.
7. Join both workers and stop the server.
```

Example skeleton:

```freehold
async function run_demo() returns Integer
is
    let endpoint: Endpoint = localhost_http(8109, "")
    let serve_result: Result<ServerHandle, ConnectError> = serve(endpoint)
    if serve_result.ok = false then
        return 1
    end if

    let server: ServerHandle = serve_result.value
    let client: Client = new_client(endpoint)

    scope demo_scope do
        spawn
            let server_handle: JoinHandle<Integer> = demo_scope.spawn<Integer>(server_worker(server))
            let client_handle: JoinHandle<Integer> = demo_scope.spawn<Integer>(client_worker(client))
        join
            let server_status: Integer = await demo_scope.join<Integer>(server_handle)
            let client_status: Integer = await demo_scope.join<Integer>(client_handle)
            call stop_server(server)
        result
            return server_status + client_status
    end scope
end run_demo
```

This pattern keeps the server lifetime, client lifetime, event channel, and joins visible in ordinary Freehold code.

---

## 8. Channels and Backpressure

SSE events move inside Freehold through `Channel<SseEvent>`:

```freehold
let event_channel: Channel<SseEvent> = channel<SseEvent>(8)
let tx: Sender<SseEvent> = channel_sender<SseEvent>(event_channel)
let rx: Receiver<SseEvent> = channel_receiver<SseEvent>(event_channel)
```

Senders and receivers must use the exact same payload type:

```freehold
let queued: Boolean = await channel_send<SseEvent>(tx, new_sse_event("tick", "value-1"))
let event: SseEvent = await channel_receive<SseEvent>(rx)
```

Use a channel capacity large enough for the expected producer/consumer shape. In the baseline deterministic demo, the channel is buffered and all events are queued before `respond_sse` drains them.

---

## 9. Event Count Contract

`event_count` is explicit in V1:

```freehold
let sent: Boolean = await respond_sse(accepted.value, 3, rx)
```

The native server sends exactly that many events. The native client reports the same value in:

```freehold
opened.value.event_count
```

This is intentionally simpler than an unbounded stream. It gives the compiler examples and runtime tests a deterministic completion condition.

For long-running production-style streams, a future runtime can replace or extend this with close signals, cancellation tokens, heartbeat events, or receiver-close semantics. The baseline rule is: declare how many events this response will send.

---

## 10. JSON Payloads in SSE

SSE transports text. For structured data, place JSON in `data`:

```freehold
type PriceTick is record
    symbol: String
    price: Double
end record

let tick: PriceTick = PriceTick { symbol: "FH", price: 42.5 }
let payload: String = Json.stringify(tick)
let event: SseEvent = new_sse_event("price", payload)
```

The receiving side can parse the event data with the Record JSON API:

```freehold
let parsed: Result<PriceTick, SchemaError> = Json.parse<PriceTick>(event.data)
if parsed.ok then
    check parsed.value.symbol = "FH"
end if
```

This keeps SSE framing separate from application payload validation.

---

## 11. Error Model

`open_sse` returns a checked result:

```freehold
Result<SseStream, ConnectError>
```

A failure means the client could not open or read the stream response. Check `.ok` before reading `.value`.

`respond_sse` returns `Boolean`:

```freehold
let sent: Boolean = await respond_sse(context, event_count, events)
```

`false` means the response could not be written or the runtime context was no longer available.

The baseline SSE layer does not use a separate `SseError` type. It reuses `ConnectError` for client-open failures and `Boolean` for server-send success.

---

## 12. Relationship to HTTP Streaming

Freehold also has generic HTTP streaming:

```freehold
respond_stream(request_context, status_code, content_type, chunk_count, chunks)
open_stream(client, request)
```

Use generic streaming for arbitrary chunked text bodies. Use SSE when the wire protocol should be `text/event-stream` with `event:` and `data:` frames.

SSE is therefore a typed specialization of HTTP streaming for event delivery.

---

## 13. Relationship to WebSockets

SSE and WebSockets solve different realtime problems.

Use SSE when:

- The server pushes events to the client.
- The client does not need to send messages on the same connection.
- HTTP infrastructure compatibility is important.
- Text event frames are sufficient.

Use WebSockets when:

- Both sides send many messages.
- The connection is a bidirectional session.
- The application needs connection-level message scopes or room/topic broadcast.

In Freehold terms, SSE is `HTTP + Receiver<SseEvent>`. WebSockets are bidirectional connection records with incoming and outgoing channels.

---

## 14. Common Failure Patterns

### 14.1 Not Checking `Result`

Invalid pattern:

```freehold
let opened: Result<SseStream, ConnectError> = await open_sse(client, request)
let event: SseEvent = await channel_receive<SseEvent>(opened.value.events)
```

Check `opened.ok` first.

### 14.2 Event Count Mismatch

Problematic pattern:

```freehold
let queued_a: Boolean = await channel_send<SseEvent>(tx, new_sse_event("tick", "value-1"))
let sent: Boolean = await respond_sse(context, 3, rx)
```

The server promised 3 events but queued only 1. In the baseline runtime, the response waits for the declared number of events or fails when the context ends.

### 14.3 Wrong Channel Type

Invalid pattern:

```freehold
let text_channel: Channel<String> = channel<String>(8)
let text_rx: Receiver<String> = channel_receiver<String>(text_channel)
let sent: Boolean = await respond_sse(context, 1, text_rx)
```

`respond_sse` requires `Receiver<SseEvent>`.

### 14.4 Treating SSE as Bidirectional

SSE is server-to-client. Do not model client commands as SSE events on the same stream. Use regular HTTP requests or WebSockets for client-to-server messages.

### 14.5 Mixing Framing and Payload Schema

Do not put application fields into the SSE frame shape itself. Keep `event_type` as the routing label and put structured data into `data`, usually as JSON.

---

## 15. Practical Checklist

Before committing SSE code, check:

- The program imports `SseEvent`, `SseStream`, `respond_sse`, and `open_sse` from `Std.Connect.Http`.
- The endpoint is created with a concrete host and port, such as `localhost_http(8109, "")`.
- The server starts with `serve(endpoint)` and checks `serve_result.ok`.
- The server accepts a request with `accept_request(server)` and checks `.ok`.
- Events are transported through `Channel<SseEvent>`.
- `respond_sse` receives a `Receiver<SseEvent>`.
- `event_count` matches the number of events that will be sent.
- The client calls `open_sse(client, request)` and checks `.ok`.
- The client checks `status_code` before consuming events.
- The client reads exactly the expected number of events from `SseStream.events`.
- Structured payloads in `data` are validated with `Json.parse<Record>`.
- Server and client workers run inside a structured `scope` and are joined.
- `stop_server(server)` is called after workers complete.

A good Freehold SSE program keeps HTTP lifetime, event count, channel type, and payload schema explicit. The result is a deterministic server-to-client event stream that remains ordinary typed Freehold code.
