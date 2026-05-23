# Open: gRPC und IDL in Freehold

Stand: 2026-05-23

Status: offen, Design-Diskussion

Dieses Dokument haelt die erste Diskussion zur Aufnahme von gRPC in Freehold fest. Ziel ist noch keine Implementierung, sondern eine klare strategische Richtung fuer Records, Services, Contracts, Fehlerabbildung und spaeteren Codegen.

## Ausgangsfrage

Kann man eine Datenstruktur `record` fuer gRPC definieren?

## Kurzantwort

Ja. Ein Freehold-`record` kann sehr gut eine gRPC/Protobuf-Message beschreiben. Freehold sollte gRPC aber nicht direkt mit normalen Records vermischen, sondern eine IDL-Schicht definieren, in der Records als Messages verwendet werden koennen.

Der wichtigste Designpunkt ist: Protobuf braucht stabile Field Numbers. Daher braucht Freehold fuer gRPC-kompatible Records eine explizite oder eindeutig ableitbare Field-ID-Regel.

## Record als gRPC Message

Ein Freehold-Record kann als Protobuf-Message interpretiert werden:

```fh
type UserRequest is record
    id: String
end

type UserReply is record
    name: String
    active: Boolean
end
```

Moegliche Protobuf-Ausgabe:

```proto
message UserRequest {
  string id = 1;
}

message UserReply {
  string name = 1;
  bool active = 2;
}
```

Diese implizite Nummerierung ist bequem, aber fuer Schema-Evolution riskant. Sobald Felder geloescht, verschoben oder umbenannt werden, koennen alte und neue Clients inkompatibel werden.

## Field Numbers

Fuer gRPC/Protobuf sollte Freehold stabile Field IDs unterstuetzen.

Verworfene bzw. nachrangige Syntax-Variante:

```fh
type UserRequest is record
    id @1: String
end

type UserReply is record
    name @1: String
    active @2: Boolean
end
```

Bevorzugte Syntax-Variante:

```fh
type UserRequest is record
    id: String proto 1
end
```

Designentscheidung: Freehold bevorzugt `field: Type proto N` fuer Protobuf/gRPC Field IDs.

Gruende:

- Die normale Record-Syntax `field: Type` bleibt erhalten.
- `proto N` liest sich als gezielte IDL-/Codegen-Annotation und nicht als neue allgemeine Feldnamensyntax.
- Die Zahl gilt klar fuer Protobuf/gRPC und nicht automatisch fuer jede moegliche Field-ID-Semantik in Freehold.
- Spaetere IDL-Attribute koennen neben `proto N` stehen, ohne die Feldstruktur umzubauen.

Beispiel:

```fh
type UserReply is record
    name: String proto 1
    active: Boolean proto 2
end
```

Regel:

```text
proto field ids are optional for normal records,
required for records used as gRPC/protobuf messages.
```

Erwartete spaetere Diagnostics:

- duplicate proto field id
- missing proto field id in grpc message
- invalid proto field id
- reserved proto field id used
- proto field id changed incompatibly

Eine explizite Field-ID-Syntax ist langfristig besser als reine Reihenfolge. Sie macht Protobuf-Versionierung, Compatibility-Diagnostics und Codegen robuster.

## Service als gRPC Service

Ein gRPC-Service ist nicht nur ein Record, sondern ein Set von Remote-Routinen. Freehold koennte dafuer eine eigene `service`-Deklaration bekommen.

Moegliche Freehold-Syntax:

```fh
service UserService is
    rpc GetUser(request: UserRequest): UserReply
end
```

Moegliche Protobuf-Ausgabe:

```proto
service UserService {
  rpc GetUser (UserRequest) returns (UserReply);
}
```

## Streaming

gRPC kennt mehrere Call-Formen:

- unary
- server streaming
- client streaming
- bidirectional streaming

Streaming sollte nicht in V1 erzwungen werden. Es kann spaeter ergaenzt werden:

```fh
service LogService is
    rpc WatchLogs(request: LogRequest): stream LogEvent
    rpc Upload(stream Chunk): UploadResult
    rpc Chat(stream ChatMessage): stream ChatMessage
end
```

### Ausgangsfrage zu Streaming

Wie kann man das Streaming fuer gRPC aus Freehold vorbereiten?

### Kurzantwort zu Streaming

Freehold sollte Streaming frueh syntaktisch und im internen Modell vorbereiten, aber nicht sofort voll ausfuehren. Streaming ist nicht nur ein anderer Rueckgabetyp, sondern ein anderes Ausfuehrungsmodell mit Cancellation, Deadlines, Backpressure, Message-Contracts und Abschluss-Semantik.

### `stream T` als reservierte Typform

Freehold sollte eine Typform `stream T` fuer RPC-Positionen reservieren:

```fh
stream LogEvent
```

Damit koennen Service-Signaturen spaeter alle vier gRPC-Arten ausdruecken:

```fh
service LogService is
        rpc GetUser(request: UserRequest): UserReply
        rpc WatchLogs(request: LogRequest): stream LogEvent
        rpc Upload(stream Chunk): UploadResult
        rpc Chat(stream ChatMessage): stream ChatMessage
end
```

Zuordnung:

```text
Unary:
    rpc GetUser(request: UserRequest): UserReply

Server streaming:
    rpc WatchLogs(request: LogRequest): stream LogEvent

Client streaming:
    rpc Upload(stream Chunk): UploadResult

Bidirectional streaming:
    rpc Chat(stream ChatMessage): stream ChatMessage
```

Empfehlung: `stream T` zunaechst nur in `rpc`-Request- und Response-Positionen erlauben, nicht in beliebigen Variablen, Records oder normalen Funktionen. So bleibt V1 klein und die spaetere Stream-Semantik wird nicht versehentlich Teil der Kernsprache.

### Interne Streaming-Modellierung

Streaming sollte intern nicht nur aus dem Typtext abgeleitet werden. Besser ist ein explizites RPC-Modell:

```text
RpcDecl
    name
    request_type
    response_type
    client_streaming: Boolean
    server_streaming: Boolean
```

Damit kann die `.proto`-Generation direkt und stabil abbilden:

```proto
rpc WatchLogs (LogRequest) returns (stream LogEvent);
rpc Upload (stream Chunk) returns (UploadResult);
rpc Chat (stream ChatMessage) returns (stream ChatMessage);
```

Auch Go-Codegen wird dadurch einfacher, weil gRPC-Go fuer die vier Formen verschiedene Server-Methodensignaturen verwendet.

### Stream-Contracts vorbereiten

Normale `requires` und `ensures` reichen fuer unary Calls. Bei Streams braucht Freehold spaeter mehrere Contract-Ebenen:

```text
per-message contract
completion contract
abort/cancel contract
backpressure policy
ordering policy
```

Moegliche spaetere Syntax-Idee:

```fh
service LogService is
        rpc WatchLogs(request: LogRequest): stream LogEvent
        requires request.topic <> ""
        ensures each event in result satisfies event.level >= 0
        aborts PermissionDenied when not_allowed(request.topic)
end
```

Weitere moegliche Contract-Formen:

```fh
ensures eventually result completes
ensures count(result) <= 1000
```

Diese Formen sollen nicht Teil von gRPC/IDL V1 sein. Sie sollten aber als spaetere Analyse- und Runtime-Contract-Richtung vorgemerkt werden.

### Cancellation, Deadline und Abort

gRPC-Streaming hat Cancellation. Cancellation ist nicht dasselbe wie ein Freehold-`abort`.

Empfohlene Trennung:

```text
abort
    fachlicher Fehler: NotFound, PermissionDenied, InvalidArgument

cancel
    Transport-, Client- oder Deadline-Ereignis

deadline
    Zeitlimit des RPC

close
    normaler Stream-Abschluss
```

Moegliche spaetere Policy-Syntax:

```fh
policy WatchLogs is
        deadline 30s
        cancel on client_disconnect
        max_messages 1000
end
```

Empfehlung: `cancel` und `deadline` nicht sofort in die Kernsprache ziehen. Fuer den Anfang reicht es, sie als gRPC/IDL-Policy vorzusehen.

## Contracts als gRPC Semantik

Freehold-Contracts passen sehr gut zu gRPC-Services. `requires`, `ensures` und `aborts` koennen aus IDL eine semantisch reichere Schnittstellenbeschreibung machen.

Beispiel:

```fh
error NotFound
error PermissionDenied

service UserService is
    rpc GetUser(request: UserRequest): UserReply
    requires request.id <> ""
    aborts NotFound when user_missing(request.id)
    aborts PermissionDenied when not_allowed(request.id)
end
```

Daraus koennten spaeter erzeugt werden:

- `.proto`-Dateien
- Server-Interfaces
- Client-Stubs
- Runtime-Validation
- Error-Mapping auf gRPC Status Codes
- Dokumentation

## Fehler-Mapping

Freehold-`error` passt gut zu gRPC Status Codes.

Moegliche Syntax-Variante:

```fh
error NotFound maps grpc NOT_FOUND
error PermissionDenied maps grpc PERMISSION_DENIED
error InvalidArgument maps grpc INVALID_ARGUMENT
```

Alternative Syntax-Variante:

```fh
error NotFound @grpc_status(NOT_FOUND)
```

Offene Designfrage: Soll das Mapping Teil der normalen Error-Deklaration sein, eine Annotation, oder eine separate IDL-Mapping-Datei?

## Empfohlene Richtung

Freehold-Records koennen gRPC-Messages sein, sollten aber ueber eine explizite IDL-Absicht und stabile Field IDs verfuegen.

Beispiel fuer die bevorzugte Zielsyntax:

```fh
type UserRequest is record
    id: String proto 1
end

type UserReply is record
    name: String proto 1
    active: Boolean proto 2
end

service UserService is
    rpc GetUser(request: UserRequest): UserReply
end
```

Damit waere Freehold zugleich:

```text
Sprache
+ IDL
+ Contracts
+ Codegen-Quelle
```

## Roadmap

### gRPC/IDL V1

- record field numbers
- gRPC-kompatibles Scalar-Mapping
- service declarations
- unary `rpc`
- `.proto`-Generation
- basic error/status mapping

### gRPC/IDL V2

- streaming
- metadata
- deadlines
- auth annotations
- client stub generation
- server stub generation

### gRPC/IDL V3

- runtime contract enforcement
- compatibility/versioning rules
- schema evolution diagnostics
- reserved field numbers and reserved field names
- generated documentation

## Offene Fragen

1. Sollen Field IDs fuer alle Records erlaubt sein oder nur fuer `grpc`/`proto`-markierte Records?
2. Soll die gRPC-Absicht explizit am Typ stehen, zum Beispiel `type UserRequest is grpc record`, oder reicht Field-ID-Syntax?
3. Soll `service` Teil der Kernsprache werden oder ein IDL-Modul oberhalb der Kernsprache?
4. Wie werden Freehold-`error`-Deklarationen stabil auf gRPC Status Codes gemappt?
5. Wie werden Contracts zwischen generierter Runtime-Validation, Dokumentation und statischer Analyse aufgeteilt?
6. Welche Schema-Evolution-Regeln sollen sofort diagnostiziert werden?

## Nicht Teil des ersten Slice

- Streaming
- Auth
- Deadlines
- komplexes Metadata-Modell
- volle Runtime-Contract-Enforcement
- Native-Code- oder Image-Builder-Integration

Der erste Slice sollte klein bleiben: Records mit Field IDs, unary Services und `.proto`-Generation.