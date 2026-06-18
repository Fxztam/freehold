# Freehold Specification: HTTP REST
**Status:** Baseline HTTP client/server runtime, REST resource helpers, JSON request/response conventions, middleware model, and request-scope rules  
**Audience:** Freehold authors, verifier implementers, backend authors, API designers, and runtime/codegen maintainers

This document explains Freehold's current HTTP and REST model.

HTTP/REST support is not new core language syntax. It is a standard library and native Go runtime surface built from ordinary Freehold concepts:

```text
Std.Connect.Common       shared endpoint, headers, body, deadline, and ConnectError types
Std.Connect.Http         HTTP client, server, request, response, middleware, streaming, and SSE primitives
Std.Connect.Rest         resource-oriented REST helpers layered on Std.Connect.Http
Json.stringify           typed record -> JSON body
Json.parse<T>            JSON body -> typed record or SchemaError
Result<T, ConnectError>  checked transport boundary
Result<T, SchemaError>   checked JSON schema boundary
RequestScope             per-request lifetime context
Scope / JoinHandle<T>    structured concurrency for server/client workers
```

The design goal is to keep HTTP transport explicit, model REST as typed JSON resource operations, and make every fallible boundary visible through `Result` checks.

---

## 1. Layer Model

Freehold separates transport from resource semantics:

```text
Std.Connect.Common
    endpoint, headers, body, timeout/deadline, ConnectError

Std.Connect.Http
    concrete HTTP requests/responses, client send, server accept/respond,
    middleware context, chunked streams, SSE

Std.Connect.Rest
    resource route, resource request, resource response, problem details,
    conversion back to HTTP response

Application records
    typed DTOs parsed from or serialized to JSON
```

`Std.Connect.Http` owns HTTP mechanics. `Std.Connect.Rest` owns resource-shaped convenience helpers. Application code owns domain routing and typed JSON schemas.

---

## 2. Shared Connection Types

The shared connection module is `Std.Connect.Common`:

```freehold
module Std.Connect.Common

error ConnectError

type Endpoint is record
    scheme: String
    host: String
    port: Integer
    path_prefix: String
end record

type Headers is record
    accept: String
    content_type: String
    authorization: String
    request_id: String
end record

type Body is record
    text: String
    content_type: String
end record

type Timeout is record
    milliseconds: Integer
end record

type Deadline is record
    epoch_millis: Integer
end record
```

Helpers:

```freehold
function localhost_http(port: Integer, path_prefix: String) returns Endpoint
function empty_headers() returns Headers
function json_headers() returns Headers
function with_request_id(headers: Headers, request_id: String) returns Headers
function with_authorization(headers: Headers, authorization: String) returns Headers
function empty_body() returns Body
function text_body(text: String) returns Body
function json_body(text: String) returns Body
function no_deadline() returns Deadline
```

The current baseline header record is intentionally small: `Accept`, `Content-Type`, `Authorization`, and `X-Request-Id` are first-class fields.

---

## 3. HTTP Module Surface

The HTTP module is `Std.Connect.Http`:

```freehold
import Std.Connect.Http exposing Client, Request, Response, ServerHandle, RequestContext, RequestScope, MiddlewareContext, StreamResponse, SseEvent, SseStream, new_client, new_request, text_request, json_request, with_headers, text_response, json_response, not_found, send, get, post_json, serve, accept_request, respond, stop_server
```

Core types:

```freehold
type Client is record
    endpoint: Endpoint
end record

type Request is record
    method: String
    path: String
    query: String
    headers: Headers
    body: Body
end record

type Response is record
    status_code: Integer
    headers: Headers
    body: Body
end record

type RequestContext is record
    id: String
    request: Request
end record

type ServerHandle is record
    id: String
end record
```

Client helpers:

```freehold
function new_client(endpoint: Endpoint) returns Client
function new_request(method: String, path: String) returns Request
function text_request(method: String, path: String, text: String) returns Request
function json_request(method: String, path: String, text: String) returns Request
function with_headers(request: Request, headers: Headers) returns Request
async function send(client: Client, request: Request) returns Result<Response, ConnectError>
async function get(client: Client, path: String) returns Result<Response, ConnectError>
async function post_json(client: Client, path: String, text: String) returns Result<Response, ConnectError>
```

Server helpers:

```freehold
function serve(endpoint: Endpoint) returns Result<ServerHandle, ConnectError>
async function accept_request(server: ServerHandle) returns Result<RequestContext, ConnectError>
async function respond(request_context: RequestContext, response: Response) returns Boolean
procedure stop_server(server: ServerHandle)
```

Response helpers:

```freehold
function text_response(status_code: Integer, text: String) returns Response
function json_response(status_code: Integer, text: String) returns Response
function not_found(path: String) returns Response
```

---

## 4. REST Module Surface

REST helpers live in `Std.Connect.Rest`:

```freehold
import Std.Connect.Rest exposing ResourceRoute, ResourceRequest, ResourceResponse, ProblemDetails, get_resource, post_resource, ok_json, created_json, problem, problem_json, missing_resource, to_http_response, new_resource_scope
```

Types:

```freehold
error RestError

type ResourceRoute is record
    method: String
    path_template: String
end record

type ResourceRequest is record
    route: ResourceRoute
    http_request: Request
    resource_id: String
    body_json: String
end record

type ResourceResponse is record
    http_response: Response
    body_json: String
end record

type ProblemDetails is record
    status_code: Integer
    code: String
    message: String
end record
```

Helpers:

```freehold
function route(method: String, path_template: String) returns ResourceRoute
function get_resource(path: String, resource_id: String) returns ResourceRequest
function post_resource(path: String, body_json: String) returns ResourceRequest
function ok_json(body_json: String) returns ResourceResponse
function created_json(body_json: String) returns ResourceResponse
function problem(status_code: Integer, code: String, message: String) returns ProblemDetails
function problem_json(details_json: String, status_code: Integer) returns ResourceResponse
function missing_resource(path: String) returns ResourceResponse
function to_http_response(response: ResourceResponse) returns Response
function new_resource_scope(request: ResourceRequest) returns RequestScope
```

`RestError` is declared for REST-layer evolution, but the current baseline helpers mostly return concrete response records rather than `Result<_, RestError>`.

---

## 5. Endpoint Construction

Use `localhost_http` for local examples and tests:

```freehold
let endpoint: Endpoint = localhost_http(8080, "/api")
let client: Client = new_client(endpoint)

check client.endpoint.scheme = "http"
check client.endpoint.path_prefix = "/api"
```

The endpoint fields map to URL construction:

```text
scheme       http by default in normal HTTP send
host         required for client send
port         appended as host:port when greater than zero
path_prefix  prepended to request.path
```

Example:

```text
Endpoint { scheme: "http", host: "127.0.0.1", port: 8104, path_prefix: "/api" }
Request  { method: "GET", path: "/users/42" }

-> http://127.0.0.1:8104/api/users/42
```

The Go runtime normalizes empty base/request paths to `/`.

---

## 6. Request Construction

Plain request:

```freehold
let request: Request = new_request("GET", "/users/42")
```

Text body:

```freehold
let request: Request = text_request("POST", "/messages", "hello")
```

JSON body:

```freehold
let payload: CreateUserRequest = CreateUserRequest { name: "Grace", email: "grace@example.test" }
let request: Request = json_request("POST", "/users", Json.stringify(payload))
```

`json_request` sets JSON headers and JSON body content type through `json_headers()` and `json_body(text)`.

Attach headers by constructing `Headers` and calling `with_headers`:

```freehold
let authorized_headers: Headers = with_authorization(empty_headers(), "token-abc")
let authorized_request: Request = with_headers(new_request("GET", "/users/42"), authorized_headers)
```

---

## 7. Client GET/POST Pattern

`get` and `post_json` are convenience wrappers around `send`:

```freehold
let get_result: Result<Response, ConnectError> = await get(client, "/users/42")
if get_result.ok = false then
    call Std.IO.log("HTTP GET /users/42 failed")
    return 1
end if
```

Check transport success first, then HTTP status, then JSON schema:

```freehold
if get_result.value.status_code != 200 then
    call Std.IO.log("HTTP GET /users/42 returned wrong status")
    return 1
end if

let parsed_user: Result<UserDto, SchemaError> = Json.parse<UserDto>(get_result.value.body.text)
if parsed_user.ok = false or parsed_user.value.name != "Ada" then
    call Std.IO.log("HTTP GET /users/42 returned invalid JSON")
    return 1
end if
```

POST with typed JSON:

```freehold
let create_payload: CreateUserRequest = CreateUserRequest { name: "Grace", email: "grace@example.test" }
let post_result: Result<Response, ConnectError> = await post_json(client, "/users", Json.stringify(create_payload))
if post_result.ok = false then
    call Std.IO.log("HTTP POST /users failed")
    return 1
end if
```

---

## 8. JSON DTO Pattern

Define request and response records explicitly:

```freehold
type UserDto is record
    id: String
    name: String
    email: String
end record

type CreateUserRequest is record
    name: String
    email: String
end record
```

Serialize outgoing bodies with `Json.stringify`:

```freehold
let create_payload: CreateUserRequest = CreateUserRequest { name: "Grace", email: "grace@example.test" }
let body_json: String = Json.stringify(create_payload)
```

Parse incoming bodies with `Json.parse<T>`:

```freehold
let parsed: Result<CreateUserRequest, SchemaError> = Json.parse<CreateUserRequest>(request.body_json)
if parsed.ok then
    let user: UserDto = UserDto { id: "43", name: parsed.value.name, email: parsed.value.email }
    return created_json(Json.stringify(user))
else
    let details: ProblemDetails = problem(400, "INVALID_CREATE_USER", "request body did not match CreateUserRequest")
    return problem_json(Json.stringify(details), details.status_code)
end if
```

JSON schema errors are separate from transport errors. A malformed body is normally a `400` resource response, not a `ConnectError`.

---

## 9. REST Resource Helpers

Use `get_resource` for resource reads:

```freehold
let get_request: ResourceRequest = get_resource("/users/42", "42")
let get_response: ResourceResponse = load_user(get_request)
let get_http: Response = to_http_response(get_response)
```

Use `post_resource` for resource creation:

```freehold
let post_request: ResourceRequest = post_resource("/users", Json.stringify(create_payload))
let create_response: ResourceResponse = create_user(post_request)
let create_http: Response = to_http_response(create_response)
```

Successful JSON responses:

```freehold
return ok_json(Json.stringify(user))       -- 200
return created_json(Json.stringify(user))  -- 201
```

Missing or invalid resources:

```freehold
let details: ProblemDetails = problem(404, "USER_NOT_FOUND", "user resource was not found")
return problem_json(Json.stringify(details), details.status_code)
```

`ResourceResponse` carries both the HTTP response and the JSON body string for typed follow-up parsing in examples.

---

## 10. Problem Details

The baseline `ProblemDetails` record is:

```freehold
type ProblemDetails is record
    status_code: Integer
    code: String
    message: String
end record
```

Some application DTOs may choose a JSON field alias:

```freehold
type ProblemDetails is record
    status_code: Integer @json("statusCode")
    code: String
    message: String
end record
```

Return problem details when the request is syntactically valid HTTP but invalid for the resource operation:

```text
400 INVALID_CREATE_USER
404 USER_NOT_FOUND
401 unauthorized
```

Keep the transport error boundary for failures such as connect, bind, accept, read, or write failures.

---

## 11. Server Accept/Respond Pattern

Start a server:

```freehold
let endpoint: Endpoint = localhost_http(8106, "")
let serve_result: Result<ServerHandle, ConnectError> = serve(endpoint)
if serve_result.ok = false then
    call Std.IO.log("HTTP server failed to bind")
    return 1
end if
let server: ServerHandle = serve_result.value
```

Accept one request and respond:

```freehold
async function handle_one(server: ServerHandle) returns Integer
is
    let accepted: Result<RequestContext, ConnectError> = await accept_request(server)
    if accepted.ok then
        let response: Response = route_request(accepted.value.request)
        let sent: Boolean = await respond(accepted.value, response)
        if sent then
            return 0
        else
            return 1
        end if
    else
        return 1
    end if
end handle_one
```

Stop the server when the request lifecycle is complete:

```freehold
call stop_server(server)
```

`respond` returns `Boolean` because the request context can be missing or the socket write can fail.

---

## 12. Routing Pattern

A minimal route function checks method and path:

```freehold
function route_request(request: Request) returns Response
is
    if request.method = "GET" and request.path = "/users/42" then
        let user: UserDto = UserDto { id: "42", name: "Ada", email: "ada@example.test" }
        return json_response(200, Json.stringify(user))
    else
        if request.method = "POST" and request.path = "/users" then
            let parsed: Result<CreateUserRequest, SchemaError> = Json.parse<CreateUserRequest>(request.body.text)
            if parsed.ok then
                let created: UserDto = UserDto { id: "43", name: parsed.value.name, email: parsed.value.email }
                return json_response(201, Json.stringify(created))
            else
                return json_response(400, "{}")
            end if
        else
            return not_found(request.path)
        end if
    end if
end route_request
```

The current baseline uses ordinary Freehold conditionals for routing. There is no separate route-table syntax yet.

---

## 13. Request Scope

HTTP request work should be tied to a request lifetime.

The HTTP layer defines:

```freehold
type RequestScope is record
    runtime_scope: Scope
    request: Request
    response: ResponseBuilder
    deadline: Deadline
end record

function new_request_scope(request: Request) returns RequestScope
```

The REST layer exposes:

```freehold
function new_resource_scope(request: ResourceRequest) returns RequestScope
```

Example:

```freehold
let get_request: ResourceRequest = get_resource("/users/42", "42")
let get_scope: RequestScope = new_resource_scope(get_request)
check get_scope.request.method = "GET"
```

For concurrent server/client demos, use a normal `scope` block and join every spawned task before leaving the scope:

```freehold
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
```

The verifier's scope/handle rules are transport-independent.

---

## 14. Middleware Model

Middleware is modeled with `MiddlewareContext`:

```freehold
type MiddlewareContext is record
    request: Request
    trace: String
    short_circuit: Boolean
    response: Response
end record
```

Helpers:

```freehold
function new_middleware_context(request: Request) returns MiddlewareContext
function context_with_trace(context: MiddlewareContext, entry: String) returns MiddlewareContext
function context_short_circuit(context: MiddlewareContext, response: Response) returns MiddlewareContext
function with_trace_header(response: Response, trace: String) returns Response
```

A before middleware can short-circuit:

```freehold
function auth_before(context: MiddlewareContext) returns MiddlewareContext
is
    if context.request.headers.authorization = "" then
        let rejected: MiddlewareContext = context_with_trace(context, "auth:reject")
        return context_short_circuit(rejected, text_response(401, "unauthorized"))
    else
        return context_with_trace(context, "auth:ok")
    end if
end auth_before
```

The pipeline decides whether to call the handler:

```freehold
if authed.short_circuit then
    let closed: MiddlewareContext = logging_after(authed)
    return with_trace_header(closed.response, closed.trace)
else
    let handled: Response = route_request(authed.request)
    let after_handler: MiddlewareContext = context_with_trace(authed, "handler")
    return with_trace_header(handled, after_handler.trace)
end if
```

The demo stores the trace in `X-Request-Id` via `with_trace_header`.

---

## 15. Native Go Runtime Mapping

The Go-native HTTP backend special-cases `Std.Connect.Http`.

Client `send` maps to `net/http`:

```text
Endpoint + Request -> http.NewRequestWithContext -> http.Client{Timeout: 30s}.Do
```

It maps request headers:

```text
Accept         -> Accept
Content-Type   -> Content-Type
Authorization  -> Authorization
request_id     -> X-Request-Id
```

It maps the response into:

```freehold
Response { status_code, headers, body }
```

Server `serve` opens a TCP listener and returns a `ServerHandle` id. `accept_request` accepts one connection, parses the HTTP request, registers the connection by id, and returns a `RequestContext`.

`respond` writes an HTTP/1.1 response with:

```text
status line
Content-Type when available
X-Request-Id when available
Content-Length
Connection: close
body text
```

Then it closes and unregisters the connection.

---

## 16. HTTP Streaming and SSE Boundary

HTTP streaming is in `Std.Connect.Http`:

```freehold
async function respond_stream(request_context: RequestContext, status_code: Integer, content_type: String, chunk_count: Integer, chunks: Receiver<String>) returns Boolean
async function open_stream(client: Client, request: Request) returns Result<StreamResponse, ConnectError>
```

Streaming uses chunked transfer and a declared `chunk_count`. The client exposes chunks through `StreamResponse.chunks`.

SSE is documented separately in `SPECIFICATION-SSE.md`, but it is implemented on the same HTTP surface:

```freehold
async function respond_sse(request_context: RequestContext, event_count: Integer, events: Receiver<SseEvent>) returns Boolean
async function open_sse(client: Client, request: Request) returns Result<SseStream, ConnectError>
```

Use regular HTTP/REST for request/response resource operations, generic HTTP streaming for chunk sequences, and SSE for server-to-client event streams.

---

## 17. Error Boundaries

There are three common boundaries:

```text
Transport boundary       Result<Response, ConnectError>
Server accept boundary   Result<RequestContext, ConnectError>
JSON schema boundary     Result<Record, SchemaError>
```

Pattern:

```freehold
let response: Result<Response, ConnectError> = await get(client, "/users/42")
if response.ok = false then
    call Std.IO.log("transport failed")
    return 1
end if

if response.value.status_code != 200 then
    call Std.IO.log("unexpected HTTP status")
    return 1
end if

let user: Result<UserDto, SchemaError> = Json.parse<UserDto>(response.value.body.text)
if user.ok = false then
    call Std.IO.log("invalid response schema")
    return 1
end if
```

Do not collapse all failures into one generic branch. Transport failure, HTTP status, and JSON schema mismatch mean different things.

---

## 18. Common Failure Patterns

### 18.1 Not Checking ConnectError

Invalid:

```freehold
let result: Result<Response, ConnectError> = await get(client, "/users/42")
let text: String = result.value.body.text
```

Check `.ok` first.

### 18.2 Treating HTTP 404 as Transport Failure

A 404 response is a successful HTTP exchange with an application/resource error. Model it as a `ProblemDetails` response where possible.

### 18.3 Parsing JSON Before Checking Status

Invalid:

```freehold
let user: Result<UserDto, SchemaError> = Json.parse<UserDto>(response.value.body.text)
```

Check transport and status first.

### 18.4 Logging Authorization Headers

Invalid:

```freehold
call Std.IO.log(request.headers.authorization)
```

Authorization headers are secret-bearing values.

### 18.5 Leaving Spawned Workers Unjoined

Every `JoinHandle<T>` created in a request/demo scope must be joined before leaving the scope.

### 18.6 Forgetting stop_server

Server demos should call `stop_server(server)` after client/server workers complete so the listener is closed.

### 18.7 Using REST Helpers for Long Streams

`Std.Connect.Rest` is for resource request/response semantics. Use `respond_stream`/`open_stream` or SSE for long-running server-to-client data.

### 18.8 Hiding Schema Errors

A `SchemaError` from `Json.parse<T>` should normally become a clear `400` or domain-specific problem response, not an empty success body.

---

## 19. Practical Checklist

Before committing HTTP/REST code, check:

- Endpoint host, port, and path prefix are explicit.
- Requests use `json_request` or `post_json` when sending JSON.
- `Result<_, ConnectError>` is checked before `.value` is read.
- HTTP status is checked separately from transport success.
- JSON response bodies are parsed with `Json.parse<T>` and checked.
- JSON request bodies are validated before resource creation or mutation.
- Problem responses use a typed problem record with status, code, and message.
- Authorization headers and tokens are not logged.
- Middleware short-circuit paths still produce a valid response.
- Server code checks `serve`, `accept_request`, and `respond` results.
- Spawned client/server workers are joined inside their scope.
- `stop_server` is called when the server lifecycle ends.
- Streaming and SSE are used only for stream-shaped workflows, not ordinary REST resources.
- REST helpers remain a layer over HTTP; they do not bypass transport error handling.

A good Freehold HTTP/REST program keeps transport, status, schema, and resource errors distinct. The result is ordinary typed Freehold code that can expose JSON resources over HTTP while preserving explicit lifetimes and checked boundaries.
