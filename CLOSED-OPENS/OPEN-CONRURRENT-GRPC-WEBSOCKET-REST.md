# Open: Concurrent Scopes fuer gRPC, WebSocket und REST

Stand: 2026-05-24

Status: V1 Architekturentscheidung abgeschlossen; konkrete Transport-Libs und Bindings fuer V2/V3 geparkt

Dieses Dokument haelt die Entscheidung fest, wie Freehold Scopes fuer gRPC, WebSocket, REST, SSE und aehnliche Schnittstellen modellieren soll. V1 ist als Architekturentscheidung abgeschlossen: Transport-Libs verwenden das gemeinsame Concurrent-Scope-Modell. Konkrete REST/WebSocket/SSE-Libs und gRPC-Bindings bleiben V2/V3.

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
    scope: Concurrent.Scope
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
    scope: Concurrent.Scope
    request: Request
    response: ResponseBuilder
    deadline: Deadline
end record
```

Beispiel WebSocket:

```fh
module WebSocket

type ConnectionScope is record
    scope: Concurrent.Scope
    socket: Connection
    incoming: Receiver<ClientMessage>
    outgoing: Sender<ServerMessage>
end record

type MessageScope is record
    scope: Concurrent.Scope
    connection: ConnectionScope
    message_id: String
end record
```

Dadurch bekommen Programme sprechende fachliche Namen, waehrend der Verifier nur `Concurrent.Scope` und `JoinHandle<T>` verstehen muss.

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

Damit bleibt Freehold klein, konsistent und gut pruefbar. Schnittstellen koennen trotzdem reichhaltige fachliche APIs anbieten.

=== CLOSED ===
