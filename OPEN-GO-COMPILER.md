# Open: Go Compiler in Freehold

Stand: 2026-05-24

Status: Compiler V1 Start-Slice implementiert; Modularitaetsvertrag verbindlich; V2/V3-Themen geparkt

Dieses Dokument legt die Leitplanken fuer die naechste Implementierungsphase fest: einen Go-Compiler fuer Freehold, der auf dem bestehenden Parser/AST/Verifier/Spec-Fundament aufsetzt. Wichtigste Vorgabe: Der Compiler darf das Freehold-Modularitaetskonzept nicht aufweichen. Codegen muss Modulgrenzen, Imports, Exposing-Regeln und qualifizierte Namen respektieren.

Die konkrete Abschlussliste vor dem Compilerstart steht in `OPEN-BEFORE-GO-COMPILER.md`: proto Typ-Mapping, Schema-Evolution-Minimalregel, Generics-Codegen-Policy, Result/Abort-Semantik, Runtime-Builtins-Grenze und Syntax-Freeze.

## Implementierter Start-Slice

Der erste Go-Compiler-Slice ist vorhanden:

- `python -m freehold go-codegen <file>` erzeugt Go-Code aus einem Freehold-Modul.
- `--verify <expected.go>` vergleicht normalisiert gegen ein Golden-File und liefert Exit-Code 1 bei Mismatch.
- `--json <file>` schreibt einen JSON-Spiegel mit Modul, Package, Status, Diagnostics und Go-Quelle.
- `generate-go-codegen-artifacts.cmd` erzeugt reproduzierbare `.go`- und `.json`-Artefakte unter `artifacts/go-codegen`.
- `valid_go_codegen`-Manifestfaelle verankern Golden-Vergleiche in den Language-Modulen.
- `verify-parser-conformance.cmd` fuehrt den Go-Codegen-Artefaktcheck als eigenen Gate-Schritt aus.

Aktuell abgedeckter Codegen-Kern: primitive Typ-Aliase, Records, einfache nicht-generische/nicht-async Routinen, Parameter, `let`, Zuweisung, Feldzuweisung, `return`, `check`, `if`, `while`, `case`, Call-Statements, Basis-Literale, Unary/Binary-Ausdruecke, Feldzugriffe, Indexzugriffe, Record-Literale und einfache Calls. Nicht unterstuetzte AST-Formen werden im Result als Diagnostics markiert.

## Ziel

Compiler V1 soll Freehold-Programme aus dem stabilisierten V1-Sprachkern nach Go uebersetzen. Er soll klein beginnen, aber von Anfang an so strukturiert sein, dass spaetere Features wie gRPC-Bindings, Runtime-Ausfuehrung, Generics-Monomorphisierung und Transport-Libs ohne Architekturbruch hinzukommen koennen.

Compiler V1 ist kein Anlass, Sprachsyntax neu zu formen. Die aktuelle Syntax fuer Core, Records, Arrays, Routinen, Contracts, Result, Abort, Generics V1b, Concurrency V1 und gRPC IDL V1 gilt fuer den Compilerstart als eingefroren.

## Modularitaetsvertrag

Der Go-Compiler muss Freeholds Modularitaetsmodell weitestgehend einhalten. Diese Regeln gelten fuer Compiler V1 als verbindlich:

1. Freehold-`module X.Y.Z` bleibt die primaere Compilation Unit.
2. Freehold-Modulnamen werden deterministisch auf Go-Packages und Ausgabepfade abgebildet.
3. `import` und `exposing` bleiben die offiziellen Modulgrenzen.
4. Codegen darf keine impliziten globalen Symbole ueber Modulgrenzen hinweg einfuehren.
5. Imports werden vor Codegen aufgeloest; der Compiler scannt nicht ungefragt beliebige Nachbarmodule.
6. Exposing-Listen definieren, welche fremden Symbole unqualifiziert sichtbar sind.
7. Qualifizierte Referenzen erhalten die Quellmodul-Grenze, statt in globale Namen flachgezogen zu werden.
8. Generierter Go-Code darf keine versteckten Cross-Module-Abhaengigkeiten erzeugen.
9. Runtime- und Stdlib-Abhaengigkeiten werden als explizite Imports generierter oder bereitgestellter Go-Packages sichtbar.
10. Builtins duerfen nicht als magische Sonderfaelle quer durch den Compiler verteilt werden; sie brauchen eine klare Runtime-/Stdlib-Zuordnung.
11. gRPC `.proto package` leitet sich in V1 aus dem Freehold-Modulnamen ab, solange keine explizite Proto-Package-Syntax existiert.
12. Jedes Language-Modul bleibt unabhaengig testbar; Go-Codegen-Artefakte sollen pro Modul/Fall vergleichbar werden.

Nicht erlaubt fuer Compiler V1:

```text
Alle Freehold-Module in ein einziges Go-Package kippen.
Alle Symbole in einen globalen Namensraum flatten.
Import-/Exposing-Regeln beim Codegen ignorieren.
Runtime-Aufrufe als unsichtbare Compiler-Magie einbauen.
```

## Compilation Units und Go-Packages

Vorlaeufige Abbildung:

```text
Freehold module Billing.Invoice
-> Go package billing_invoice oder billing/invoice, noch final festzulegen

Freehold module GrpcIdl.UnaryServiceProtoFields
-> proto package grpcidl.unaryserviceprotofields
```

Die konkrete Go-Package-Pfadkonvention muss vor der ersten Codegen-Implementierung final entschieden werden. Wichtig ist weniger die Schreibweise als die Stabilitaet:

- gleicher Freehold-Modulname erzeugt immer denselben Go-Package-Pfad
- zwei verschiedene Freehold-Module kollidieren nicht
- qualifizierte Freehold-Aufrufe bleiben eindeutig aufloesbar
- generierte Dateien koennen pro Modul isoliert gebaut und getestet werden

## Compiler V1 Scope

Compiler V1 sollte mit einem konservativen Feature-Set starten:

| Bereich | Compiler V1 Policy |
| --- | --- |
| Module/Imports | Muss Modulgrenzen und `exposing` respektieren. |
| Primitive Typen | `Integer`, `Boolean`, `Double`, `String` nach Go-Grundtypen. |
| Records | Go structs, Feldnamen stabil aus Freehold-Feldern. |
| Arrays | Statische/Freehold-Arrays als einfache Go-Repräsentation, genaue Form noch festzulegen. |
| Routines | Funktionen/Prozeduren als Go-Funktionen innerhalb des Modulpackages. |
| Calls | Nur aufgeloeste unqualifizierte und qualifizierte Calls. |
| Statements | Core Statements zuerst: `let`, assignment, `if`, `while`, `case`, `return`, `check`. |
| Contracts | V1 verifierseitig; Runtime-Enforcement geparkt. |
| Result | Wertmodell abbilden, `return error E` bleibt normaler Return. |
| Abort | Abnormaler Exit; konkrete Go-Abbildung fuer V1 explizit entscheiden. |
| Generics | V1b im AST/Verifier erlaubt; Go-Codegen zunaechst ablehnen oder nur konkretisierte Builtins behandeln. |
| Concurrency | Statische Typ-/Lifetime-Regeln sind vorhanden; echte Runtime-Ausfuehrung geparkt. |
| gRPC IDL | `.proto`-Codegen ist eigener Pfad; Go-gRPC-Bindings geparkt. |

## Typ-Mapping Freehold -> Go

Vorlaeufiges Mapping fuer Compiler V1:

```text
Integer  -> int64
Boolean  -> bool
Double   -> float64
String   -> string
Record   -> struct
Array<T> -> noch festzulegen, vermutlich []T oder fixed-size representation je nach Freehold-Arrayform
Result<T,E> -> generierter Result-Typ oder Runtime-Generic, noch festzulegen
ErrorName -> symbolischer Fehlerwert oder typed error wrapper, noch festzulegen
```

Entscheidungen, die vor breitem Codegen finalisiert werden sollten:

- `Array<T, N>` als `[N]T` oder Freehold-eigene Runtime-Struktur?
- `Result<T,E>` als generischer Go-Typ, monomorphisierte Structs oder Runtime-Wrapper?
- `abort E` als Go `error` return, panic-freier Kontrollfluss oder spezielle Runtime-Struktur?
- Record-Feldnamen: original Freehold names plus Go-exported aliases oder rein package-intern?

## Runtime-/Stdlib-Grenze

Der Compiler braucht eine klare Tabelle, welche Features direkt generiert, ueber Runtime-Packages importiert oder vorerst abgelehnt werden.

Vorlaeufige Einordnung:

| Feature | Compiler V1 |
| --- | --- |
| String builtins | Go stdlib oder Freehold runtime package. |
| Math builtins | Go `math` oder Runtime-Wrapper. |
| BigInteger/BigFloat | Runtime package oder vorerst abgelehnt, je nach Ziel-Slice. |
| Json.stringify | Runtime package; V1 stringify semantics bereits verifierseitig begrenzt. |
| Std.IO | Runtime package/stub fuer erste CLI-Ausfuehrung. |
| Channel/Scope/JoinHandle | Typen koennen existieren; echte Runtime-Ausfuehrung geparkt. |
| gRPC IDL | `.proto`-Generator vorhanden; Go-Bindings spaeter. |

Regel: Runtime-Abhaengigkeiten werden als explizite Go-Imports sichtbar. Der Compiler soll nicht so tun, als waeren sie globale magische Funktionen.

## Result und Abort Policy

Diese Semantik muss fuer den Compilerstart stabil bleiben:

```text
return ok value
    normaler Return eines Result<T,E>-Werts

return error E
    normaler Return eines Result<T,E>-Werts mit Fehlerpayload
    kein abort, kein panic, kein abnormaler Control Flow

abort E
    abnormaler Exit gemaess Abort-Regeln
    muss spaeter eine eigene Go-Abbildung bekommen
```

Contracts:

- `requires`, `ensures`, `aborts` sind in V1 vor allem verifierseitige Semantik.
- Runtime-Contract-Enforcement ist nicht Teil des ersten Go-Compiler-Slice.
- Der Compiler darf Contracts nicht stillschweigend falsch interpretieren.

## Generics Policy

Generics V1b sind im Sprachmodell vorhanden, aber Go-Codegen soll sie nicht nebenbei improvisieren.

Compiler V1 darf deshalb:

- generische User-Records und generische User-Routines zunaechst mit klarer Diagnostic/Not-Implemented-Policy ablehnen
- eingebaute generische Typformen wie `Array<T>` und `Result<T,E>` gezielt behandeln
- konkrete nicht-generische Programme zuerst stabil uebersetzen

Compiler V1 soll nicht:

- halbfertige Monomorphisierung in mehreren Codepfaden verstreuen
- generische IDL-Typen direkt als Protobuf Messages ausgeben
- Inference oder Bounds einfuehren

Generics V2/V3:

- Monomorphisierte Codegen-Artefakte
- Bounds
- Type Inference
- qualifizierte generische Calls
- generische IDL-Monomorphisierung vor `.proto`-Generation

## gRPC und Proto Policy

Der vorhandene gRPC-V1-Pfad bleibt getrennt vom allgemeinen Go-Compiler:

```text
Freehold gRPC IDL -> proto3 file
```

Go-gRPC-Bindings sind der naechste Transport-Slice, aber nicht Voraussetzung fuer den ersten allgemeinen Go-Codegen.

Compiler V1 muss dennoch die Modulpolitik respektieren:

- Proto package aus Freehold-Modulname ableiten
- Service/Message-Namen nicht global flatten
- spaetere generated Go packages fuer gRPC eindeutig neben Freehold-Go-Packages fuehren

Geparkt fuer V2/V3:

- Go server/client stubs
- `implements Service.Rpc`
- gRPC Status-Code Mapping
- streaming
- deadlines/cancellation/metadata/auth
- schema evolution wie `reserved proto`

## Deferred fuer Compiler V1

Diese Themen werden fuer den Compilerstart bewusst nicht geloest:

- echte async Runtime-Ausfuehrung
- Scheduler, Work-Stealing, Blocking-Pool, CancellationToken
- Channel-Laufzeitverhalten, Close/Backpressure/select
- gRPC Go-Bindings und Transportserver
- REST/WebSocket/SSE Transport-Libs
- Runtime-Contract-Enforcement
- path-aware control-flow proofs
- Generics Bounds/Inference/volle Monomorphisierung
- Native/Image Builder

## Empfohlene naechste Schritte

1. Go-Package-Pfadkonvention fuer Freehold-Module festlegen.
2. Compiler-Artefaktstruktur definieren, z.B. `artifacts/go-codegen/<module>/...`.
3. Minimalen Codegen fuer ein einzelnes Modul ohne Imports bauen.
4. Danach Import-/Exposing-Aufloesung in Codegen integrieren.
5. Feature-Matrix pro Language-Modul pflegen: supported, rejected, deferred.
6. Erst danach Runtime-/Stdlib-Packages systematisch anbinden.

## Akzeptanzkriterien fuer Compiler V1 Start

Vor der breiten Implementierung sollte gelten:

- `OPEN-GO-COMPILER.md` ist die Leitplanke fuer Modularitaet und Feature-Grenzen.
- Go-Codegen-Artefakte sind pro Language-Modul reproduzierbar.
- Der Compiler kann ein kleines nicht-generisches Modul mit Record, Routine und `main` uebersetzen.
- Import-/Exposing-Regeln werden nicht umgangen.
- Nicht unterstuetzte Features scheitern mit klaren Diagnostics oder expliziten Not-Implemented-Reports.
