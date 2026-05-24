# Open: Before Go Compiler

Stand: 2026-05-24

Status: Vorbereitende Abschlussliste vor Go-Compiler V1; V1-Policies festzurren, V2/V3-Themen parken

Dieses Dokument sammelt die Punkte, die vor dem Start des Go-Compiler-Basis-Codegens abgeschlossen oder bewusst entschieden sein sollen. Ziel ist nicht, neue Sprachfeatures einzubauen, sondern die Compilergrundlage stabil zu machen: Syntax einfrieren, Typ- und Runtime-Policies festhalten, und spaetere Transport-/Runtime-Themen sauber aus V1 herausnehmen.

## Muss vor Go-Compiler V1 feststehen

### Source-Level Syntax einfrieren

Fuer den Compilerstart gilt die bestehende Syntax als eingefroren fuer Compiler V1:

- Core Statements und Expressions
- Records
- Arrays
- Routines
- Contracts
- Result
- Abort
- Generics V1b
- Concurrency V1
- gRPC IDL V1

Regel: Der Compiler soll auf einer stabilen Sprache bauen. Neue Syntaxaenderungen gehoeren danach in eigene V2/V3-Phasen und duerfen den ersten Go-Codegen nicht wieder verschieben.

### gRPC / Proto Typ-Mapping finalisieren

Das V1-Mapping ist als feste Policy zu behandeln:

| Freehold Type | proto3 Type | Policy |
| --- | --- | --- |
| `String` | `string` | V1 fest. |
| `Boolean` | `bool` | V1 fest. |
| `Integer` | `int64` | V1 fest; bewusst nicht `sint64`. |
| `Double` | `double` | V1 fest. |
| Record | message reference | V1 fest, wenn alle Felder protofaehig sind. |
| `Array<T>` | `repeated <T>` | V1 fest, sofern `T` protofaehig ist. |

Entscheidung: `Integer -> int64` bleibt fuer V1 die erwartbare, einfache Abbildung. `sint64` wird nicht automatisch verwendet.

Tests vor Compilerstart:

- positiver Test fuer alle skalaren Mappings
- positiver Test fuer Record-Referenz
- positiver Test fuer `Array<T>` / `repeated`
- negativer Test fuer nicht protofaehige Typen

### Schema-Evolution Minimalregel

`proto N` ist V1 vorhanden. Fuer Compiler V1 reicht die Minimalregel:

```text
proto IDs muessen positiv sein.
proto IDs muessen je Record eindeutig sein.
proto IDs muessen fuer alle gRPC-Record-Felder vollstaendig angegeben sein.
```

`reserved proto ...` wird fuer V1 nicht implementiert.

Geparkt fuer V2:

- `reserved proto`
- Reservierung geloeschter Feldnummern
- Reservierung geloeschter Feldnamen
- Compatibility-Checks zwischen Versionen

### gRPC Go-Binding noch nicht starten

Der aktuelle V1-Stand ist:

```text
Freehold gRPC IDL -> proto3 output
```

Go-gRPC-Server/Client-Stubs sind kein Teil des Compiler-Basis-Codegens. Sie sollen nach dem allgemeinen Go-Codegen als eigener Block auf dem vorhandenen `.proto`-Output aufbauen.

Geparkt bis nach Basis-Codegen:

- Go server stubs
- Go client stubs
- Service-Implementierungsbindung
- gRPC Status/Error Mapping
- Deadlines, cancellation, metadata, auth
- Streaming

### Generics-Codegen-Policy

Generics V1b bleiben im AST und Verifier erlaubt. Fuer den ersten Go-Codegen gilt aber:

```text
Generische User-Konstrukte werden im Go-Codegen zunaechst abgelehnt,
sofern keine explizite Monomorphisierung implementiert ist.
```

V1 Compiler Policy:

- generische User-Records wie `Box<Integer>` im Codegen zunaechst mit sauberem Not-Implemented/Diagnostic-Pfad ablehnen
- generische User-Funktionen wie `identity<Integer>` im Codegen zunaechst ablehnen
- einfache konkretisierte Builtins gezielt behandeln, insbesondere `Array<T>` und `Result<T,E>`
- keine halbfertige Monomorphisierung nebenbei einbauen

Spaetere Optionen:

- volle Monomorphisierung
- Go-Generics fuer geeignete Runtime-Typen
- Bounds
- Type Inference
- qualifizierte generische Calls

### Control-Flow / Abort / Result Semantik einfrieren

Diese Semantik ist fuer Compiler V1 verbindlich:

```text
return error E
    normaler Result-Return
    kein Go-panic
    kein abort
    kein abnormaler Control Flow

abort E
    abnormaler Exit gemaess Freehold-Abort-Regeln
    braucht eine eigene Go-Abbildung in einer spaeteren Runtime-/Compiler-Phase

requires / ensures / aborts
    fuer Go V1 primaer verifierseitig behandeln
    Runtime-Erzwingung ist nicht Teil des ersten Compiler-Slice
```

Regel: Der Go-Compiler darf Result und Abort nicht zusammenwerfen. `return error E` bleibt ein normaler Wertfluss; `abort E` bleibt abnormaler Kontrollfluss.

### Runtime-Builtins-Grenze

Vor Go-Codegen muss klar sein, was direkt generiert wird, was Runtime-Aufruf ist, was gestubbt wird und was V1 ablehnt.

| Bereich | Go Compiler V1 Policy |
| --- | --- |
| Freehold Core | supported fuer den ersten Basis-Slice. |
| Records | supported als Go structs. |
| Arrays | supported/stub je nach finaler Array-Repr. |
| Result | supported/stub ueber klare Runtime- oder generierte Repr. |
| String | supported ueber Go stdlib oder Freehold runtime package. |
| Math | supported/stub ueber Go `math` oder Runtime-Wrapper. |
| Json | stub oder runtime package; keine implizite Compiler-Magie. |
| BigInteger/BigFloat | rejected oder runtime package; V1-Entscheidung vor Implementierung treffen. |
| Std.IO | stub/runtime package fuer erste CLI-Ausfuehrung. |
| Channel | rejected/stub fuer Runtime; statische Typen koennen bestehen. |
| Scope/JoinHandle | rejected/stub fuer Runtime; echte Ausfuehrung geparkt. |
| gRPC IDL | supported nur als `.proto`-Output, nicht als Go-Binding. |

Regel: Runtime-Builtins werden als explizite Go-Imports oder klare Compiler-Reports sichtbar. Keine versteckten globalen Sonderfunktionen.

## Kann warten

Diese Punkte sind nicht Teil des Go-Compiler-Basisstarts:

- gRPC Streaming
- REST/WebSocket/SSE Transport-Libs
- Scheduler-Qualitaet
- echte async Runtime
- Cancellation/Deadline
- Generics Bounds/Inference
- path-aware Control Flow
- gRPC Error/Status-Mapping
- `reserved proto`

## Vor-Go-Compiler Akzeptanzkriterien

Vor dem Start der breiten Go-Compiler-Implementierung sollte gelten:

- `OPEN-GO-COMPILER.md` definiert Modularitaet und Compiler-V1-Scope.
- `OPEN-BEFORE-GO-COMPILER.md` definiert die Abschlussliste vor Codegen.
- gRPC/proto Typ-Mapping ist dokumentiert und durch Tests abgedeckt.
- Schema-Evolution V1 ist bewusst minimal: positiv, eindeutig, vollstaendig.
- Generics-Codegen hat eine klare Ablehnungs-/Not-Implemented-Policy.
- Result und Abort sind fuer Go-Codegen semantisch getrennt.
- Runtime-Builtins haben eine supported/stub/rejected-Einordnung.
- Source-Level Syntax ist fuer Compiler V1 eingefroren.
