# TODO Open Std

Stand: 2026-06-11

Dieses Dokument sammelt die offene Standardbibliothek-Roadmap fuer Freehold. Es trennt den aktuellen belegten Stand von der Zielstruktur fuer kuenftige `Std.*`-Module.

## Ziel-Namespace

Die Standardbibliothek soll langfristig unter `Std.*` gebuendelt werden. Fuer Transport- und Verbindungs-APIs ist die Zielrichtung:

```text
Std.Concurrent
Std.Json
Std.Connect.Common
Std.Connect.Http
Std.Connect.Rest
Std.Connect.WebSocket
Std.Connect.Sse
Std.Connect.Grpc
```

`Std.Connect.*` ist dabei die fachliche Transportfamilie. Gemeinsame Lebenszeit-, Task- und Channel-Regeln bleiben in `Std.Concurrent`; JSON-Serialisierung und Schema-Parsing bleiben in `Std.Json`.

Namespace-Policy: Neue Standardbibliotheksmodule werden als echte Modulpfade umgesetzt, nicht als Alias auf alte Top-Level-Namen. Das heisst: Eine API `Std.Connect.WebSocket` liegt als Datei `Std/Connect/WebSocket.fh` vor, wird unter diesem Modulnamen importiert und bekommt im Go-Projekt einen passenden Paketpfad. Alte Top-Level-Namen wie `WebSocket` sind nur noch Legacy und sollen nicht in neuen Beispielen verwendet werden.

## Aktueller Stand

| Bereich | Aktueller Name/Ort | Stand |
| --- | --- | --- |
| Console IO | `Std.IO` | Modul existiert als Runtime-Binding fuer `log`, `logf` und einfache typisierte Log-Varianten. Python-Runtime und Go-Codegen binden die relevanten Faelle auf Host-Ausgabe. |
| Datei IO | `File` | Bootstrap-Modul existiert mit `read_to_string(path)` und `write_string(path, content)`. Im nativen Go-Codegen ist `File.write_string` inklusive automatischer Parent-Directory-Erzeugung dokumentiert; `File.read_to_string` wird fuer dynamische Compiler-Ingestion genutzt. |
| System IO | `System` | Bootstrap-Modul existiert mit `args()`, `run_command(command)` und `get_env(name)`. Aktuell eher Compiler-/Bootstrap-nahe Host-Flaeche als ausgearbeitete Std-API. |
| JSON | `Json` | `Json.stringify(record)`, typed `Json.parse<Record>(text)`, `@json("externalName")`, compile-time Literal-Schema-Diagnostik und runtime `Result`-Fehler fuer dynamische Faelle sind implementiert und in WebSocket-/Language-Module-Slices abgedeckt. |
| Concurrency | Sprache/Runtime-Helfer | Async/await, strukturierte Scopes, `Scope`, `JoinHandle<T>`, `Channel<T>`, `Sender<T>`, `Receiver<T>`, `channel`, `channel_sender`, `channel_receiver`, `channel_send`, `channel_receive` und `channel_try_send` sind als aktuelle Oberflaechen belegt. Das Ziel ist eine konsolidierte `Std.Concurrent`-API. |
| gRPC | IDL/Go-Projekt-Slice | Parser/AST/Semantik, Proto3-Codegen und unary Go-Server-Bindings sind fuer den aktuellen Slice implementiert. Streaming, Client-Bindings, Deadlines, Metadaten und Auth bleiben V3/offen. |
| WebSocket | `Std.Connect.WebSocket` | Go-native WebSocket-Runtime und Compiler-Beispiele 27/28/29/30 sind auf den echten Modulpfad `Std.Connect.WebSocket` migriert. Der Kontextschnitt umfasst `ConnectionScope`, `MessageScope`, `TextMessage`, `FramePolicy`, `CloseStatus`, `new_connection_scope`, `new_message_scope`, `receive_text`, `send_text`, `try_send_text` und `close_with_status`. Beispiele 32/33 bleiben JSON-/Room-Modell-Slices ohne eigenes WebSocket-Modul. |
| HTTP/REST | `Std.Connect.Common`, `Std.Connect.Http`, `Std.Connect.Rest` | V1-Typoberflaeche ist als echte Modulpfade angelegt. `Common` enthaelt `Endpoint`, `Header`, `Headers`, `Timeout`, `Deadline`, `Body` und `ConnectError`. `Http` enthaelt `Client`, `Server`, `Request`, `Response`, `ResponseBuilder`, `RequestScope`, `ServerHandle`, `RequestContext`, `MiddlewareContext`, `StreamResponse`, `SseEvent`, `SseStream`, Builder fuer Text-/JSON-Requests und Responses, die Go-native Client-Runtime fuer `send`, `get` und `post_json`, die Go-native Server-Runtime fuer `serve`, `accept_request`, `respond` und `stop_server`, eine datengetriebene Middleware-Onion, die Go-native Streaming-Runtime fuer `respond_stream` und `open_stream` sowie die Go-native SSE-Runtime fuer `respond_sse` und `open_sse`. `Rest` baut darauf mit `ResourceRoute`, `ResourceRequest`, `ResourceResponse`, `ProblemDetails` und typed JSON-Mapping auf. Beispiel 34 verifiziert den typed Contract-Slice; Beispiel 35 echte GET-/POST-/404-Roundtrips gegen ein Go-Backend; Beispiel 36 einen nativen Freehold-HTTP-Server; Beispiel 37 eine Logging+Auth-Middleware-Onion; Beispiel 38 natives chunked HTTP-Streaming ueber Channels; Beispiel 39 native SSE ueber Channels. |
| SSE | `Std.Connect.Http` (`respond_sse`/`open_sse`) | Native SSE ist als HTTP-Streaming-Spezialisierung auf `Std.Connect.Http` umgesetzt: `SseEvent`/`SseStream` plus `respond_sse`/`open_sse` liefern `text/event-stream`-Events (`event:`/`data:`-Frames) ueber einen `Channel<SseEvent>`. Beispiel 39 verifiziert den End-to-End-Roundtrip. Ein eigenes `Std.Connect.Sse`-Modul bleibt optional. |

## Namensbereinigung

Kurzfristig existieren historisch gewachsene Namen nebeneinander:

```text
Std.IO
File
System
Json
WebSocket
Scope / JoinHandle / Channel helper
```

Die Zielstruktur sollte diese Oberflaechen nicht brutal umbenennen, sondern kompatibel einordnen:

```text
Std.IO                 bleibt Console-/Log-Ausgabe oder wird als Alias stabilisiert
Std.IO.File            moegliche Einordnung fuer Datei-IO, falls IO als Obergruppe gewuenscht ist
Std.File               Alternative, falls Datei-IO nicht unter Console/IO haengen soll
Std.System             Host-/Prozess-/Env-Funktionen
Std.Json               kanonischer Ort fuer Json.stringify/Json.parse
Std.Concurrent         kanonischer Ort fuer Scope/Task/Channel
Std.Connect.*          kanonischer Ort fuer Transportprotokolle; echte Modulpfade, keine Alias-Policy
```

Offene Entscheidung: `File` sollte entweder nach `Std.IO.File` oder `Std.File` migriert werden. Da `Std.IO` heute bereits Console-Logging bedeutet, ist `Std.File` semantisch sauberer; `Std.IO.File` passt besser, wenn `IO` als allgemeiner Ein-/Ausgabe-Namespace verstanden werden soll. Bis zur Entscheidung sollten bestehende `File.read_to_string`/`File.write_string`-Aufrufe als kompatible Altoberflaeche erhalten bleiben.

## Std.Concurrent

Ziel:

```fh
import Std.Concurrent

let request_scope: Std.Concurrent.Scope = Std.Concurrent.scope()
let handle: Std.Concurrent.JoinHandle<Response> =
    Std.Concurrent.spawn<Response>(request_scope, load_response())
let response: Response = await Std.Concurrent.join<Response>(request_scope, handle)
```

Zu dokumentieren/implementieren:

- Moduldatei/API fuer `Std.Concurrent` mit `Scope`, `JoinHandle<T>`, `Channel<T>`, `Sender<T>`, `Receiver<T>`.
- Kanonische Namen fuer `scope`, `spawn`, `join`, `cancel`, `channel`, `sender`, `receiver`, `send`, `receive`, `try_send`.
- Kompatibilitaetsstrategie fuer aktuelle Helper-Namen wie `channel_send<T>` und `scope_spawn<T>`.
- Verifier-Regeln bleiben transportunabhaengig: kein offener JoinHandle am Scope-Ende, kein Handle-Escape, Channel-Invarianten bei Send/Receive.
- Cancellation/Deadline als Runtime-/API-Slice nach V1.

## Std.Json

Ziel:

```fh
import Std.Json

let text: String = Std.Json.stringify(person)
let parsed: Result<Person, Std.Json.SchemaError> = Std.Json.parse<Person>(text)
```

Aktueller belegter Stand:

- Deterministisches kompaktes JSON fuer Record-Werte.
- Record-Feldreihenfolge folgt der Record-Deklaration.
- `@json("externalName")` wird fuer externe Feldnamen verwendet.
- Typed parse nutzt den Record-Typ als Schema.
- Literal-JSON kann compile-time schema-geprueft werden.
- Dynamisches JSON liefert runtime `Result`-Fehler statt Panics.
- `null`, optionale Felder, dynamisches `Json.Value` und breite Value-Accessor-APIs bleiben offen.

Offen:

- Namespace-Migration von `Json.*` nach `Std.Json.*` oder Alias-Strategie.
- `Std.Json.SchemaError`, `ParseError`, spaeter `Value/Object/Array` modellieren.
- Duplicate-Key-Validierung fuer strict parse beibehalten: Token-Scan vor Go-Decode, nicht nur Map-Unmarshal.
- Nicht-nullable Default explizit in der Std-Dokumentation festhalten.

## Std.IO, Std.File und Std.System

Aktuell vorhanden:

```fh
module Std.IO

procedure log(message: String)
procedure log_int(number: Integer)
procedure log_bool(flag: Boolean)
procedure log_double(number: Double)
procedure logf(template: String, item: String)
procedure logf_int(template: String, number: Integer)
```

Die Python-Runtime bietet derzeit `log(value)` und variadisches `logf(template, *values)`; Tests decken `Std.IO.log`/`Std.IO.logf` fuer einfache skalare Faelle und negative Typfaelle ab. Go-Codegen bildet die V1-Standardfaelle auf `fmt` ab.

Aktuell vorhanden fuer Datei/System:

```fh
module File
function read_to_string(path: String) returns Result<String, String>
function write_string(path: String, content: String) returns Result<Boolean, String>

module System
function args() returns Array<String, 10>
function run_command(command: String) returns Integer
function get_env(name: String) returns String
```

Offen:

- Entscheidung `Std.File` vs. `Std.IO.File`.
- Einheitliche Fehlerrecords statt `String`-Fehler fuer Datei-IO.
- Read/write Bytes, append, exists, remove, rename, mkdirs, list_dir.
- Pfadmodell und deterministische Testbarkeit.
- `Std.System` fuer Args, Env und Prozessaufrufe als bewusst hostgebundene API dokumentieren.

## Std.Connect.Common

Gemeinsame Transporttypen, die nicht HTTP-, REST-, WebSocket-, SSE- oder gRPC-spezifisch sind:

```text
Endpoint / Uri / Authority / Path / Query
Header / Headers
Method / StatusCode
Deadline / Timeout
CancellationToken
Peer / LocalAddress / RemoteAddress
TlsConfig
AuthContext
ConnectError
Body / Bytes / Text
```

Aktueller belegter Stand:

- Echter Modulpfad `Std.Connect.Common` ist angelegt.
- V1-Typen: `Endpoint`, `Header`, `Headers`, `Timeout`, `Deadline`, `Body`, `ConnectError`.
- V1-Builder: `new_endpoint`, `localhost_http`, `new_header`, `empty_headers`, `json_headers`, `with_request_id`, `empty_body`, `text_body`, `json_body`, `timeout_millis`, `no_deadline`.

Offen:

- Fehlerhierarchie und `Result<T, E>`-Konvention fuer Transportfehler.
- Timeout/Cancellation-Anschluss an `Std.Concurrent`.
- Gemeinsame Header-/Metadata-Struktur fuer HTTP und gRPC.
- Text/Binary-Grenze fuer WebSocket/SSE/HTTP-Body klaeren.

## Std.Connect.Http

Zielbereich fuer generische HTTP-Bausteine:

```text
Request
Response
RequestScope
ResponseBuilder
Client
Server
Handler
Middleware
```

Aktueller belegter Stand:

- Echter Modulpfad `Std.Connect.Http` ist angelegt.
- V1-Typen: `Client`, `Server`, `Request`, `Response`, `ResponseBuilder`, `RequestScope`.
- `RequestScope.runtime_scope` buendelt den allgemeinen `Scope`; das Feld heisst wie bei WebSocket bewusst nicht `scope`.
- V1-Builder und Client-Helfer: `new_client`, `new_server`, `new_request`, `text_request`, `json_request`, `new_response_builder`, `new_request_scope`, `with_status`, `with_body`, `build_response`, `text_response`, `json_response`, `not_found`, `get`, `post_json`.
- `send(client, request)` ist im Go-Codegen fuer `Std.Connect.Http` als native Client-Runtime umgesetzt. Die Runtime baut URLs aus `Endpoint` und `Request`, setzt JSON-/Auth-/Request-ID-Header, fuehrt `net/http`-Requests mit Timeout aus und gibt `Result<Response, ConnectError>` zurueck.
- Server-Handler-Slice: `serve(endpoint)`, `accept_request(server)`, `respond(request_context, response)` und `stop_server(server)` sind im Go-Codegen als native `net`/`net/http`-Server-Runtime umgesetzt. `serve` bindet einen TCP-Listener, `accept_request` liest eine eingehende Anfrage in eine `Request` (inkl. Headers/Body), `respond` schreibt die `Response` zurueck und schliesst die Verbindung. Neue Typen `ServerHandle` und `RequestContext` tragen die Runtime-Identitaet.
- Middleware-Slice: `MiddlewareContext` plus `new_middleware_context`, `context_with_trace`, `context_short_circuit` und `with_trace_header` modellieren eine datengetriebene Onion-Pipeline (Freehold hat keine First-Class-Funktionen). Eine Schicht kann den Request annotieren, kurzschliessen (Short-Circuit mit eigener Response) und Spuren sammeln; die Anwendung verdrahtet die Schichten in Onion-Reihenfolge um den Handler.
- `34_http_rest_contract_demo` prueft HTTP-Endpoint, RequestScope, JSON-Headers und Response-Mapping.
- `35_http_client_go_backend_demo` prueft echte GET-/POST-/404-Roundtrips gegen ein Go-Backend und validiert Response-JSON via `Json.parse<Record>`.
- `36_http_server_demo` startet einen nativen Freehold-HTTP-Server und bedient GET-/POST-Requests des nativen HTTP-Clients im selben Prozess (Port 8106).
- `37_http_middleware_demo` baut eine Logging+Auth-Onion auf dem nativen Server; ein autorisierter Request durchlaeuft alle Schichten inkl. Handler, ein anonymer Request wird von der Auth-Schicht mit 401 kurzgeschlossen (Port 8107).
- Streaming-Slice: `StreamResponse` plus `respond_stream(request_context, status_code, content_type, chunk_count, chunks)` und `open_stream(client, request)` setzen HTTP/1.1 `Transfer-Encoding: chunked` im Go-Codegen um. Der Server sendet Chunks ueber einen `Receiver<String>`, der Client liest sie ueber `StreamResponse.chunks` (`Receiver<String>`) wieder ein. Die Chunk-Anzahl wird ueber den `X-Chunk-Count`-Header transportiert, da der Channel keine Close-Detektion an der Freehold-Oberflaeche hat.
- `38_http_streaming_demo` sendet drei Chunks ueber einen `Channel<String>` per `respond_stream` als chunked Body; der native Client liest sie via `open_stream` ueber einen `Receiver<String>` ein und setzt sie wieder zusammen (Port 8108).
- SSE-Slice: `SseEvent`/`SseStream` plus `new_sse_event`, `respond_sse(request_context, event_count, events)` und `open_sse(client, request)` setzen `text/event-stream` im Go-Codegen um. Der Server schreibt `event:`/`data:`-Frames aus einem `Receiver<SseEvent>`, der Client parst sie via `open_sse` und reicht sie ueber `SseStream.events` (`Receiver<SseEvent>`) weiter. Die Event-Anzahl wird wie beim Streaming ueber den `X-Event-Count`-Header transportiert.
- `39_http_sse_demo` sendet drei `SseEvent`-Werte ueber einen `Channel<SseEvent>` per `respond_sse`; der native Client liest sie via `open_sse` ueber einen `Receiver<SseEvent>` ein und loggt Event-Typ und Daten (Port 8109).

Offen:

- Backpressure und dynamische Chunk-/Event-Anzahl (Channel-Close-Detektion) erst nach stabilem `Std.Concurrent`.
- Erweiterte Header-/Status-/Body-Policies ueber den aktuellen V1-Client hinaus.

## Std.Connect.Rest

REST baut auf `Std.Connect.Http` auf und soll keine eigene Scope-Mechanik besitzen.

Aktueller belegter Stand:

- Echter Modulpfad `Std.Connect.Rest` ist angelegt.
- V1-Typen: `ResourceRoute`, `ResourceRequest`, `ResourceResponse`, `ProblemDetails`, `RestError`.
- V1-Builder/Mapper: `route`, `get_resource`, `post_resource`, `ok_json`, `created_json`, `problem`, `problem_json`, `missing_resource`, `to_http_response`, `new_resource_scope`.
- `new_resource_scope` delegiert auf `Std.Connect.Http.new_request_scope`; REST besitzt keine eigene Lebenszeitmechanik.
- `34_http_rest_contract_demo` prueft typed GET, POST, `ProblemDetails` und `Json.parse`/`Json.stringify` fuer REST-Payloads.
- Native REST-Client-Aufrufe koennen auf `Std.Connect.Http.get`/`post_json` aufsetzen; eine eigene REST-Netzwerk-Runtime ist bewusst nicht eingefuehrt.

Offen:

- Validation- und Contract-Integration fuer Request-Records.
- OpenAPI/Schema-Emission als spaeterer Tooling-Slice pruefen.

## Std.Connect.WebSocket

Aktueller belegter Stand:

- Native Go-WebSocket-Runtime fuer Compiler-Beispiele.
- Echter Modulpfad `Std.Connect.WebSocket` ist aktiv; Beispiele 27/28/29/30 importieren diesen Namen.
- Textframe-basierte JSON-Policy fuer V1-Demos.
- Typed JSON Broadcast mit `Json.parse<Record>`/`Json.stringify`.
- Multi-Client, Rooms/Topics, Keepalive, Backpressure via `channel_try_send`, typed ErrorMessage und Schema-Negativfaelle.
- `Std/Connect/WebSocket.fh` enthaelt jetzt eine stdlib-nahe Kontextoberflaeche: `ConnectionScope`, `MessageScope`, `TextMessage`, `BinaryMessage`, `FramePolicy`, `CloseStatus`, `new_connection_scope`, `new_message_scope`, `default_frame_policy`, `receive_text`, `send_text`, `try_send_text`, `close_with_status`.
- `ConnectionScope.runtime_scope` und `MessageScope.runtime_scope` buendeln den allgemeinen `Scope`; das Feld heisst bewusst nicht `scope`, weil `scope` ein reserviertes Freehold-Wort ist.
- `30_websocket_json_broadcast_demo` nutzt `ConnectionScope`/`MessageScope` aktiv fuer Keepalive, Empfang, Versand, Broadcast und Close-Status.

Ziel-API:

```text
Connection
ConnectionScope
MessageScope
TextMessage
BinaryMessage
CloseStatus
Client
Server
accept / connect / receive / send / close
```

Offen:

- Historischen Top-Level-Namen `WebSocket` als Legacy behandeln und spaeter entfernen, sobald keine alten Beispiele/Goldens mehr darauf zeigen.
- Fragmentierung und Binary-Frames als explizite Runtime-Policy.
- Close-Code-/Error-Modell.
- Backpressure-Strategien aus `try_send_text` weiter zu benannten Policies ausbauen.
- Cancellation/Deadline-Anbindung an `Std.Concurrent`.

## Std.Connect.Sse

SSE ist noch nicht implementiert.

Zielbereich:

```text
Event
EventId
EventStream
SseResponse
send_event
heartbeat
reconnect_delay
```

Offen:

- Server-Sent-Events als HTTP-Streaming-Spezialisierung auf `Std.Connect.Http` modellieren.
- Backpressure und Client-Disconnect ueber `Std.Concurrent` klaeren.
- JSON-Event-Payloads ueber `Std.Json` typisieren.

## Std.Connect.Grpc

Aktueller belegter Stand:

- gRPC-IDL ist fuer V1 in Parser/AST/Semantik vorhanden.
- Proto3-Codegen und unary Go-Server-Bindings sind implementiert.
- Combined gRPC/async/channel-Beispiele sichern IR- und Go-Projektoberflaechen.

Ziel-API:

```text
Service
UnaryCall
ServerStream
ClientStream
BidirectionalStream
RequestScope
Metadata
Status
StatusCode
```

Offen:

- Client-Bindings.
- Streaming V3: server, client und bidirectional streaming.
- Deadlines, Cancellation, Metadata und Auth.
- Status-Code-/Error-Mapping.
- Einordnung der IDL-Generierung in `Std.Connect.Grpc` ohne die Sprache mit Transport-Scope-Sonderregeln zu belasten.

## Naechste Schnitte

1. Entscheidung treffen: `File` wird `Std.File` oder `Std.IO.File`; Altname bleibt vorerst Alias.
2. `Json`-API als `Std.Json` dokumentieren und Alias-/Migration festlegen.
3. `Std.Concurrent` als kanonische Moduloberflaeche fuer bestehende Scope-/Channel-Helfer spezifizieren.
4. `Std.Connect.Common` mit gemeinsamen Fehler-, Header-, Endpoint-, Deadline- und Cancellation-Typen beginnen.
5. Historisches `WebSocket`-Top-Level-Modul nach Abschluss der Golden-/Artifact-Migration entfernen.
6. HTTP/REST/SSE als echte Module unter `Std.Connect.Common` und `Std.Concurrent` aufbauen.
7. gRPC V3 Streaming als echtes Modul `Std.Connect.Grpc` anbinden und die vorhandene IDL-/Proto-Basis weiterverwenden.