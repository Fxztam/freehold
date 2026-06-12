# Open: Concurrent Scopes fuer gRPC, WebSocket und REST

Stand: 2026-06-11

Status: V1 Architekturentscheidung, WebSocket-Runtime-Implementierung, HTTP/REST-Typoberflaeche, native HTTP-Client-Smokes, native HTTP-Server-Handler-Runtime, HTTP-Middleware-Onion, native HTTP-Streaming-Runtime und native SSE-Runtime abgeschlossen und verifiziert

Dieses Dokument haelt die Entscheidung fest, wie Freehold Scopes fuer gRPC, WebSocket, REST, SSE und aehnliche Schnittstellen modellieren soll. V1 ist fuer die gemeinsame Scope-Architektur, die Go-native WebSocket-Runtime, eine HTTP/REST-Typoberflaeche und die native HTTP-Client-Runtime abgeschlossen. Die WebSocket-Smokes reichen inzwischen von einfacher Verbindung ueber Multi-Client und Go-Backend bis zu typed JSON Broadcast, Runtime-Schemafehlern und Room/Topic-Broadcast. HTTP/REST ist als typed Request-/Response-/Resource-Slice vorhanden; `Std.Connect.Http.send`, `get` und `post_json` laufen im Go-Codegen gegen `net/http` und werden in Beispiel 35 gegen ein Go-Backend verifiziert. Die native HTTP-Server-Runtime (`serve`, `accept_request`, `respond`, `stop_server`) wird in Beispiel 36 verifiziert, in dem ein Freehold-Server GET-/POST-Requests des nativen Clients im selben Prozess bedient. Eine datengetriebene Middleware-Onion (`MiddlewareContext`, `context_with_trace`, `context_short_circuit`, `with_trace_header`) wird in Beispiel 37 verifiziert. Natives HTTP-Streaming (`respond_stream`/`open_stream`) liefert chunked Bodies (HTTP/1.1 `Transfer-Encoding: chunked`) ueber Freehold-Channels und wird in Beispiel 38 verifiziert. Native SSE (`respond_sse`/`open_sse`) liefert `text/event-stream`-Events (`event:`/`data:`-Frames) ueber einen `Channel<SseEvent>` und wird in Beispiel 39 verifiziert.

## Kurzentscheidung

Native Scope-Operationen gehoeren in die allgemeine Concurrent-/Runtime-Lib.

gRPC-, WebSocket-, REST- und andere Schnittstellen-Libs sollen diese nativen Scope-Operationen verwenden und darauf fachlich benannte Kontexttypen aufbauen.

```text
Concurrent / Runtime
    Definiert das universelle Scope-Modell:
    Scope, JoinHandle<T>, spawn, join, cancel, Channel<T>, Sender<T>, Receiver<T>.

Transport-Libs
    Verwenden Concurrent.Scope und ergaenzen fachlichen Kontext:
    Grpc.RequestScope, Http.RequestScope, WebSocket.ConnectionScope, WebSocket.MessageScope.
```

Der Verifier prueft nur das gemeinsame Concurrent-Scope-Modell. Transport-Libs liefern Namen, Kontextdaten und ergonomische APIs, aber keine eigenen unabhaengigen Lifetime-Regeln.

## Warum nicht pro Schnittstelle eigene Scope-Mechanik?

Wenn gRPC, WebSocket und REST jeweils eigene Scope-Regeln haetten, muesste der Verifier mehrere fast gleiche Modelle verstehen:

```text
GrpcScope
WebSocketScope
HttpRequestScope
WorkerScope
StreamScope
```

Das wuerde die Sprache unruhig machen und Diagnose-/Verifier-Regeln verdoppeln.

Besser ist ein einziges strukturiertes Concurrency-Modell:

```text
Concurrent.Scope
    besitzt JoinHandles
    erzwingt join/cancel vor Scope-Ende
    verhindert Handle-Escape
    traegt Cancellation und Deadline semantisch weiter
```

Darauf koennen Transport-Libs ihre fachlichen Lebensraeume abbilden.

## Native Concurrent-Lib

Die allgemeine Concurrent-Lib definiert die primitiven Operationen.

Konzeptionell:

```fh
module Concurrent

type Scope is record
end record

type JoinHandle<T> is record
end record

type Channel<T> is record
end record

type Sender<T> is record
end record

type Receiver<T> is record
end record

function scope() returns Scope

function spawn<T>(scope: Scope, task: Awaitable<T>) returns JoinHandle<T>

async function join<T>(scope: Scope, handle: JoinHandle<T>) returns T

function cancel<T>(scope: Scope, handle: JoinHandle<T>) returns Unit
```

Aktueller V1d-Pruefstand nutzt noch die vorlaeufige testbare Form:

```fh
let request_scope: Scope = scope()
let handle: JoinHandle<Response> = scope_spawn<Response>(request_scope, raw_handle)
let response: Response = await scope_join<Response>(request_scope, handle)
```

Die spaetere Ziel-API kann diese Operationen als Methoden oder modulqualifizierte Funktionen sichtbar machen:

```fh
let handle: JoinHandle<Response> = Concurrent.spawn<Response>(request_scope, task)
let response: Response = await Concurrent.join<Response>(request_scope, handle)
```

oder:

```fh
let handle: JoinHandle<Response> = request_scope.spawn<Response>(task)
let response: Response = await request_scope.join<Response>(handle)
```

Die semantische Regel bleibt in allen Varianten gleich:

```text
Jeder JoinHandle, der einem Scope gehoert, muss vor Verlassen dieses Scope gejoint oder explizit gecancelt werden.
Ein Scope-JoinHandle darf nicht aus seinem Scope entkommen.
```

## Transport-Libs als fachliche Wrapper

Transport-Libs sollen keine eigene Scope-Mechanik erfinden. Sie stellen Kontexttypen bereit, die intern einen `Concurrent.Scope` besitzen und zusaetzliche Transportdaten tragen.

Beispiel gRPC:

```fh
module Grpc

type RequestScope is record
    runtime_scope: Concurrent.Scope
    metadata: Metadata
    peer: Peer
    deadline: Deadline
    cancellation: CancellationToken
end record
```

Beispiel HTTP/REST:

```fh
module Http

type RequestScope is record
    runtime_scope: Concurrent.Scope
    request: Request
    response: ResponseBuilder
    deadline: Deadline
end record
```

Beispiel WebSocket:

```fh
module Std.Connect.WebSocket

type ConnectionScope is record
    runtime_scope: Concurrent.Scope
    socket: Connection
    incoming: Receiver<ClientMessage>
    outgoing: Sender<ServerMessage>
end record

type MessageScope is record
    runtime_scope: Concurrent.Scope
    connection: ConnectionScope
    message_id: String
end record
```

Dadurch bekommen Programme sprechende fachliche Namen, waehrend der Verifier nur `Concurrent.Scope` und `JoinHandle<T>` verstehen muss.

Aktualisierung 2026-06-11: `Std.Connect.WebSocket` ist jetzt als echter Modulpfad umgesetzt. Die WebSocket-Beispiele 27/28/29/30 importieren `Std.Connect.WebSocket` direkt; der Go-Codegen behandelt diesen Modulnamen als native WebSocket-Runtime und erzeugt den Paketpfad `std/connect/websocket`. Die Oberflaeche umfasst `ConnectionScope`, `MessageScope`, `TextMessage`, `BinaryMessage`, `FramePolicy`, `CloseStatus`, `new_connection_scope`, `new_message_scope`, `default_frame_policy`, `receive_text`, `send_text`, `try_send_text` und `close_with_status`. Das Scope-Feld heisst `runtime_scope`, weil `scope` ein reserviertes Freehold-Wort ist. Die Factory-Namen beginnen mit `new_`, damit ihr Go-Exportname nicht mit den Typnamen kollidiert. Diese echte-Modulpfad-Policy gilt auch fuer die spaeteren `Std.Connect.*`- und `Std.*`-Module; Alias-Tabellen sind nicht die Standardstrategie.

Aktualisierung HTTP/REST 2026-06-11: `Std.Connect.Common`, `Std.Connect.Http` und `Std.Connect.Rest` sind als echte Modulpfade angelegt. HTTP bringt `Request`, `Response`, `ResponseBuilder`, `RequestScope`, `Client`, `Server`, Text-/JSON-Builder sowie die Go-native Client-Runtime fuer `send`, `get` und `post_json` mit. REST baut darauf mit `ResourceRoute`, `ResourceRequest`, `ResourceResponse`, `ProblemDetails` und JSON-Mapping auf; `new_resource_scope` delegiert auf `Std.Connect.Http.new_request_scope`, REST hat also keine eigene Scope-Mechanik. `34_http_rest_contract_demo` verifiziert GET/POST, typed JSON-Payloads, `ProblemDetails` und den HTTP-RequestScope ohne Netzwerk. `35_http_client_go_backend_demo` verifiziert echte GET-/POST-/404-Roundtrips gegen ein kleines Go-Backend auf Port 8104. `36_http_server_demo` verifiziert die native HTTP-Server-Runtime (`serve`/`accept_request`/`respond`/`stop_server`), die einen Freehold-Server gegen den nativen Client auf Port 8106 bedient. `37_http_middleware_demo` verifiziert eine datengetriebene Middleware-Onion (Logging + Auth) auf dem Server: ein autorisierter Request durchlaeuft alle Schichten inkl. Handler, ein anonymer Request wird von der Auth-Schicht mit 401 kurzgeschlossen (Port 8107). `38_http_streaming_demo` verifiziert natives HTTP-Streaming: der Server sendet drei Chunks ueber einen `Channel<String>` und `respond_stream` als HTTP/1.1 chunked Body, der native Client liest sie via `open_stream` ueber einen `Receiver<String>` wieder ein (Port 8108). `39_http_sse_demo` verifiziert native SSE: der Server sendet drei `SseEvent`-Werte ueber einen `Channel<SseEvent>` und `respond_sse` als `text/event-stream` (`event:`/`data:`-Frames), der native Client liest sie via `open_sse` ueber einen `Receiver<SseEvent>` wieder ein (Port 8109).

## Scope-Namen und Lebensraeume

Scope-Namen sind normale lokale Namen. Sie beschreiben die fachliche Lebensdauer, nicht einen neuen Sprachtyp.

Typische Namen:

```text
request_scope
    Ein HTTP/gRPC Request-Response-Lebensraum.

connection_scope
    Eine lange WebSocket-Verbindung.

stream_scope
    Ein gRPC-, SSE- oder HTTP-Streaming-Lebensraum.

send_scope
    Ausgehende Sendearbeit, besonders bei Streaming oder WebSocket.

receive_scope
    Eingehende Empfangsarbeit, besonders bei Client-Streaming oder WebSocket.

message_scope
    Bearbeitung einer einzelnen WebSocket- oder Stream-Nachricht.

operation_scope
    Fachliche Teiloperation innerhalb eines groesseren Requests.
```

Diese Namen sind Konventionen. Die Sprache reserviert sie nicht.

## REST

Einfache REST-Operationen brauchen nicht zwingend einen expliziten Scope.

```fh
function get_user(id: UserId) returns UserResponse
is
    let user: User = load_user(id)
    return UserResponse(user: user)
end get_user
```

Sobald parallele Arbeit, Timeout, Cancellation oder Streaming ins Spiel kommt, sollte die HTTP-Lib einen Request-Scope bereitstellen.

```fh
async function get_dashboard(id: UserId) returns Dashboard
is
    scope request_scope do
        let user_handle: JoinHandle<User> =
            request_scope.spawn<User>(load_user(id))

        let stats_handle: JoinHandle<Stats> =
            request_scope.spawn<Stats>(load_stats(id))

        let user: User = await request_scope.join<User>(user_handle)
        let stats: Stats = await request_scope.join<Stats>(stats_handle)

        return Dashboard(user: user, stats: stats)
    end scope
end get_dashboard
```

REST braucht normalerweise keinen eigenen `send_scope`, weil die Antwort meist ein einzelner Rueckgabewert ist. Ein `send_scope` lohnt sich bei Streaming, grossen Downloads, Backpressure oder mehreren Produzenten.

## gRPC

gRPC nutzt `request_scope` als aeusseren Lebensraum fuer einen RPC.

Unary RPC:

```fh
async function GetUser(req: GetUserRequest) returns GetUserResponse
is
    scope request_scope do
        let user_handle: JoinHandle<User> =
            request_scope.spawn<User>(load_user(req.id))

        let user: User = await request_scope.join<User>(user_handle)
        return GetUserResponse(user: user)
    end scope
end GetUser
```

Server Streaming kann zusaetzlich einen `send_scope` verwenden, wenn mehrere Produzenten ausgehende Nachrichten erzeugen.

```fh
async function StreamPrices(req: PriceRequest, out: Sender<PriceUpdate>) returns Unit
is
    scope request_scope do
        scope send_scope do
            let market_handle: JoinHandle<Unit> =
                send_scope.spawn<Unit>(send_market_prices(req, out))

            let alert_handle: JoinHandle<Unit> =
                send_scope.spawn<Unit>(send_price_alerts(req, out))

            let _: Unit = await send_scope.join<Unit>(market_handle)
            let _: Unit = await send_scope.join<Unit>(alert_handle)
        end scope

        return unit
    end scope
end StreamPrices
```

Client Streaming kann analog einen `receive_scope` verwenden. Bidirectional Streaming kann `send_scope` und `receive_scope` als Geschwister unter einem `stream_scope` oder `request_scope` nutzen.

## WebSocket

WebSockets sind keine einzelnen Requests, sondern lange Verbindungen mit vielen Nachrichten. Deshalb ist der aeussere Lebensraum ein `connection_scope`.

```fh
async function handle_socket(socket: WebSocket.Connection) returns Unit
is
    scope connection_scope do
        let incoming: Channel<ClientMessage> = channel<ClientMessage>(64)
        let outgoing: Channel<ServerMessage> = channel<ServerMessage>(64)

        let receive_handle: JoinHandle<Unit> =
            connection_scope.spawn<Unit>(receive_loop(socket, incoming))

        let send_handle: JoinHandle<Unit> =
            connection_scope.spawn<Unit>(send_loop(socket, outgoing))

        let dispatch_handle: JoinHandle<Unit> =
            connection_scope.spawn<Unit>(dispatch_loop(incoming, outgoing))

        let _: Unit = await connection_scope.join<Unit>(receive_handle)
        let _: Unit = await connection_scope.join<Unit>(dispatch_handle)
        let _: Unit = await connection_scope.join<Unit>(send_handle)
    end scope
end handle_socket
```

Eine einzelne eingehende Nachricht kann bei Bedarf einen `message_scope` bekommen, wenn ihre Bearbeitung parallelisierte Teilaufgaben hat.

```fh
async function dispatch_one(msg: ClientMessage, out: Sender<ServerMessage>) returns Unit
is
    scope message_scope do
        let validation_handle: JoinHandle<Validation> =
            message_scope.spawn<Validation>(validate_message(msg))

        let domain_handle: JoinHandle<DomainResult> =
            message_scope.spawn<DomainResult>(run_domain_logic(msg))

        let validation: Validation = await message_scope.join<Validation>(validation_handle)
        let result: DomainResult = await message_scope.join<DomainResult>(domain_handle)

        let response: ServerMessage = build_response(validation, result)
        let sent: Boolean = await channel_send<ServerMessage>(out, response)
    end scope
end dispatch_one
```

## Verifier-Regeln

Der Verifier soll transportunabhaengig bleiben.

Er prueft:

```text
1. Scope-Bindung
   Ein Scope-Block oder Scope-Wert erzeugt einen lokalen Scope-Lebensraum.

2. Handle-Besitz
   spawn(scope, task) erzeugt einen JoinHandle<T>, der diesem Scope gehoert.

3. Handle-Verbrauch
   join(scope, handle) verbraucht den Handle fuer diesen Scope.
   cancel(scope, handle) kann spaeter als kontrollierter Verbrauch gelten.

4. Exit-Pruefung
   Vor return, abort und end scope darf kein offener Scope-Handle existieren.

5. Escape-Verbot
   Scope-Handles duerfen nicht aus ihrem Scope herausgegeben, in aeussere Variablen geschrieben oder in einen anderen Scope verschoben werden.
```

Diese Regeln gelten identisch fuer REST, gRPC, WebSocket, SSE, Worker-Jobs und interne Parallelisierung.

## Architekturvotum

```text
Scope-Regeln gehoeren in Concurrent.
Schnittstellen-Libs liefern benannte Scope-Kontexte.
Der Verifier prueft nur das gemeinsame Scope-Modell.
```

## V1 WebSocket Runtime-Implementierung (Erledigt 2026-06-03, erweitert 2026-06-11)

Die Go-native WebSocket-Laufzeitumgebung wurde erfolgreich implementiert und in den Compiler integriert. 

### Details der Umsetzung:
1. **Typ-Mapping & Codegen**:
   * Die Freehold-Kanaltypen (`Channel<T>`, `Sender<T>`, `Receiver<T>`) werden nun direkt in native Go-Kanäle (`chan T`, `chan<- T`, `<-chan T`) transpiliert.
   * `WebSocketError` wurde als dedizierter Fehler-Typ im AST und Go-Code registriert.
2. **WebSocket-Client & Server**:
   * Der Client-Handshake (`Connect`) wurde um eine automatische Fallback-Pfadkorrektur erweitert (leere URL-Pfade werden auf `"/"` gesetzt), um RFC-Konformität zu gewährleisten.
   * Der Server-Handshake (`Accept`) führt das Sec-WebSocket-Accept Hashing korrekt durch und startet asynchrone Read/Write-Loops zur bidirektionalen Kommunikation.
3. **Integrationstests**:
     * `27_websocket_demo` verifiziert die einfache Client/Server-Kommunikation.
     * `28_websocket_multi_client_demo` verifiziert mehrere Clients im selben Runtime-Szenario.
     * `29_websocket_go_backend_demo` verifiziert die Freehold-Seite gegen einen kleinen Go-WebSocket-Backend-Prozess.
     * `30_websocket_json_broadcast_demo` verifiziert typed JSON Broadcast mit `Json.parse<Record>`, `Json.stringify`, `@json("clientId")`, Keepalive Ping/Pong, Delivery-Scope-Timeout, Registry/Room-Zuordnung, Backpressure via `channel_try_send`, typed ErrorMessage und Text-JSON-Frame-Policy.
     * `32_websocket_json_broadcast_schema_neg` verifiziert runtime-invalid dynamische JSON-/Schema-Faelle als `Result`-Fehler statt Panics.
     * `33_websocket_room_broadcast_demo` verifiziert, dass Broadcast nur an Clients des Ziel-Rooms/Topics queued wird.

### WebSocket JSON Message Contract

Die aktuelle V1-Demo-Bindung arbeitet auf kompletten Textframes, deren Payload JSON-Strings sind. Fragmentierte und binaere Frames gehoeren unterhalb dieser Binding-Schicht zur Runtime-/Adapter-Policy und werden in der Demo als nicht unterstuetzt modelliert.

```text
Application payload: complete text frame containing JSON text.
Typed envelope: record with kind, clientId and payload fields.
Validation: Json.parse<RecordType>(text) returns Result<RecordType, SchemaError>.
Serialization: Json.stringify(record_value) emits deterministic compact JSON.
Frame policy: text JSON only; binary and fragmented frames are rejected or closed by lower-level adapter policy.
```

### Broadcast, Rooms und Backpressure

Der aktuelle WebSocket-Slice nutzt das allgemeine Concurrent-Modell weiterhin unveraendert. Fachliche WebSocket-Konzepte werden als normale Records und Channels modelliert:

```text
ClientSession
    client_id, room, connection, outgoing sender

ConnectionRegistry
    registrierte Sessions fuer Broadcast-Entscheidungen

Room/Topic Broadcast
    sendet nur an Sessions, deren room/topic zum Ziel passt

Backpressure
    channel_try_send<T> liefert Boolean und erlaubt Drop-/Close-Policy ohne blockierenden Send
```

Die Beispiele halten die deterministischen Log-Checks bewusst auf der fachlichen Ebene: Registry-Zuordnung, Room-Erreichbarkeit, Backpressure-Drop, Close-Status und erfolgreiche typed JSON Roundtrips.

Damit ist die WebSocket-Kopplung für V1 voll funktionsfähig und vollständig durch das Test-Harness abgedeckt.

=== CLOSED ===
