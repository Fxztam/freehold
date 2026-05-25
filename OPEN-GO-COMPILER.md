# Open: Go Compiler in Freehold

Stand: 2026-05-24

Status: Compiler V1 Start-Slice plus Import-, Cross-Module-Call-, Result-, Abort-, Multi-File-, Runtime-Builtin- und Go-Projekt-Build-Slices implementiert; Modularitaetsvertrag verbindlich; V2/V3-Themen geparkt

Dieses Dokument legt die Leitplanken fuer die naechste Implementierungsphase fest: einen Go-Compiler fuer Freehold, der auf dem bestehenden Parser/AST/Verifier/Spec-Fundament aufsetzt. Wichtigste Vorgabe: Der Compiler darf das Freehold-Modularitaetskonzept nicht aufweichen. Codegen muss Modulgrenzen, Imports, Exposing-Regeln und qualifizierte Namen respektieren.

Die konkrete Abschlussliste vor dem Compilerstart steht in `OPEN-BEFORE-GO-COMPILER.md`: proto Typ-Mapping, Schema-Evolution-Minimalregel, Generics-Codegen-Policy, Result/Abort-Semantik, Runtime-Builtins-Grenze und Syntax-Freeze.

## Implementierter Start-Slice

Der erste Go-Compiler-Slice ist vorhanden:

- `python -m freehold go-codegen <file>` erzeugt Go-Code aus einem Freehold-Modul.
- `--verify <expected.go>` vergleicht normalisiert gegen ein Golden-File und liefert Exit-Code 1 bei Mismatch.
- `--json <file>` schreibt einen JSON-Spiegel mit Modul, Package, Status, Diagnostics und Go-Quelle.
- `generate-go-codegen-artifacts.cmd` erzeugt reproduzierbare `.go`- und `.json`-Artefakte unter `artifacts/go-codegen`.
- `python -m freehold go-codegen-project <entry> --output-dir <dir>` loest den Modulgraphen auf, schreibt pro Freehold-Modul eine Go-Datei und erzeugt `go.mod` plus `build.cmd`.
- `valid_go_codegen`-Manifestfaelle verankern Golden-Vergleiche in den Language-Modulen.
- `valid_go_project_codegen`-Manifestfaelle verankern Multi-File- und Build-File-Golden-Vergleiche fuer importierte Modulgraphen.
- `tests/language_modules/go_codegen_feature_matrix.json` pflegt pro Language-Modul den Go-Codegen-Status `supported`, `rejected` oder `deferred`.
- Runtime-Builtins fuer `Math`, `Std.IO`, `String.*` und `Json.stringify` werden als explizite Go-Stdlib-Imports generiert.
- `verify-parser-conformance.cmd` fuehrt den Go-Codegen-Artefaktcheck als eigenen Gate-Schritt aus.

Aktuell abgedeckter Codegen-Kern: primitive Typ-Aliase, Records, einfache nicht-generische/nicht-async Routinen, Parameter, `let`, Zuweisung, Feldzuweisung, `return`, `check`, `if`, `while`, `case`, Call-Statements, Basis-Literale, praezedenzbewusste Unary/Binary-Ausdruecke, Feldzugriffe, Indexzugriffe, statisch typisierte Array-Literale in `let`, Record-Literale und einfache Calls. Der Import-Slice nutzt `ModuleResolver` fuer dateibasierte Entry-Module, erzeugt deterministische Go-Importpfade fuer benutzte Freehold-Imports und spiegelt Package-/Import-Metadaten in JSON-Artefakten. Der Cross-Module-Call-Slice verifiziert importierte Freehold-Routinen im Modulgraphen und generiert Go-Aufrufe ueber das importierte Package, sowohl fuer `exposing`-Namen als auch fuer qualifizierte Modulnamen. Der Result-Slice bildet `Result<T,E>` als modul-lokalen Go-Struct-Typ ab und generiert `return ok`/`return error` als normale Wert-Returns. Der Abort-Slice bildet `aborts` als expliziten Go-`error`-Rückgabewert ab und propagiert lokale abortende Calls ueber `err`. Der Multi-File-Slice schreibt aufgeloeste Modulgraphen deterministisch nach `go_package_path/module_file.go`, z.B. `App.Main -> app/main/main.go` und `Banking.Proofs -> banking/proofs/proofs.go`; bekannte Runtime-Module werden nicht als Freehold-Stubs emittiert. Der Go-Projekt-Slice erzeugt fuer Projekt-Codegen deterministisch ein `freehold.local`-`go.mod`, ein `build.cmd` mit `go test ./...` und JSON-Metadaten zu Build-Dateien. Die Feature-Matrix deckt alle 24 Language-Module ab und wird im offiziellen Gate validiert. Der Runtime-Builtin-Slice bildet `Math.*` auf Go `math`, `Std.IO.log`/`logf` auf Go `fmt`, `String.concat` auf `+`, `String.substr` auf Slicing, `String.replace`/`String.instr` auf Go `strings`, `String.template` auf `fmt.Sprintf` und `Json.stringify` auf `encoding/json` ab. Record-Felder erhalten JSON-Tags mit Freehold-Feldnamen. Nicht unterstuetzte AST-Formen werden im Codegen-Result als Diagnostics markiert.

## Aktueller Compiler-TODO

Der Compiler-TODO ist nach den abgeschlossenen Start-, Projekt-, Feature-Matrix- und Cross-Module-Call-Slices deutlich kleiner. Dieser Abschnitt ist der aktuelle operative Blick auf das, was fuer den Compiler noch offen ist.

Bereits erledigt:

- Go-Codegen-Grundpfad: `go-codegen`, `go-codegen-project`, JSON-Spiegel, Goldens und Artefakt-Gate.
- Multi-File-/Projekt-Codegen mit `go.mod` und `build.cmd`.
- Importaufloesung, `exposing`, qualifizierte Namen und Cross-Module-Calls auf importierte Freehold-Routinen.
- Primitive Typen, Records, einfache Routinen, Statements und Expressions.
- Result-Wertmodell.
- Abort als Go-`error`-Return fuer abgedeckte V1-Faelle.
- Runtime-Builtins fuer `Math`, `Std.IO`, `String.*`, `String.template`, `Json.stringify` und `Big.*`.
- Feature-Matrix-Gate mit `24/24` Language-Modulen.
- Go-Codegen-Artefakte mit aktuell `56/56` matching.

Direkt offen fuer die naechsten Compiler-Slices:

1. Arrays weiter haerten
    - Eigene Go-Goldens im Array-Modul fehlen noch.
    - Finale Array-Repraesentation sauber entscheiden und absichern.
    - Feature-Matrix: `06_arrays` ist `deferred`, obwohl Arrays schon in anderen Slices vorkommen.

2. Record-/Result-/Abort-Interaktionen ueber Modulgrenzen
    - Cross-Module-Routine-Calls sind vorhanden.
    - Noch zu haerten sind importierte Records, Result-Typen, Abort-Fehler, Signaturtypen, Fehlernamen und Package-Typnamen ueber Modulgrenzen.

3. Result value field access
    - Feature-Matrix: `11_errors_results` fuehrt `Result value field access` als deferred.

4. Abort breiter machen
    - Breitere abort contract implication.
    - Handler-Syntax bleibt offen/geparkt.
    - Feature-Matrix: `21_abort_handling` hat entsprechende deferred items.

5. Dynamische `String.template`-Formate
    - Statische Templates sind implementiert.
    - Dynamische Formatargumente sind noch deferred.
    - Feature-Matrix: `18_string_templates`.

6. Core-/Import-/Whitespace-/Control-Flow-Goldens
    - `01_core`: minimal/empty module Go-Golden-Policy.
    - `02_import`: single-file import declaration codegen policy.
    - `14_comments_whitespace`: optionale Formatter-/Comment-Preservation-Policy.
    - `16_control_flow_edges`: Edge-Goldens und path-aware proof integration.

Bewusst geparkt fuer V2/V3:

- Generics-Codegen, Monomorphisierung, Bounds und Inference.
- Async Runtime, Channels, Scheduler und Scope/JoinHandle-Ausfuehrung.
- gRPC Go server/client bindings.
- REST/WebSocket/SSE Transport-Libs.
- Runtime-Contract-Enforcement.
- path-aware Control-Flow-Proofs.
- Native/Image Builder.

Empfohlene Reihenfolge aus heutiger Sicht:

1. Cross-Module Typ-/Result-/Abort-Signaturen haerten, weil das architektonisch wichtiger ist als kosmetische Goldens.
2. Danach Array-Goldens und kleinere Matrix-Luecken schliessen.
3. Danach weitere Runtime- und Bootstrap-nahe Slices priorisieren.

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
Result<T,E> -> modul-lokaler generierter Result-Struct-Typ
ErrorName -> modul-lokale string-Konstante
abort E -> Go `error`-Return, keine Panic-Semantik
```

Entscheidungen, die vor breitem Codegen finalisiert werden sollten:

- `Array<T, N>` als `[N]T` oder Freehold-eigene Runtime-Struktur?
- `Result<T,E>` V1-Entscheidung: modul-lokaler Struct-Typ je konkret verwendeter Result-Form.
- `abort E` V1-Entscheidung: Go `error`-Return, panic-freier Kontrollfluss.
- Record-Feldnamen: original Freehold names plus Go-exported aliases oder rein package-intern?

## Runtime-/Stdlib-Grenze

Der Compiler braucht eine klare Tabelle, welche Features direkt generiert, ueber Runtime-Packages importiert oder vorerst abgelehnt werden.

Vorlaeufige Einordnung:

| Feature | Compiler V1 |
| --- | --- |
| String builtins | Go `strings`, `fmt.Sprintf` und native String-Operatoren fuer V1-Standardfaelle. |
| Math builtins | Go `math` fuer V1-Standardfaelle. |
| BigInteger/BigFloat | Go `math/big` fuer V1-Standardfaelle. |
| Json.stringify | Go `encoding/json` fuer verifierseitig begrenzte V1-Recordformen. |
| Std.IO | Go `fmt` fuer `log`/`logf` V1-Standardfaelle. |
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
```

Compiler-V1-Abbildung:

```text
Result<Integer, NotFound>
-> type ResultIntegerNotFound struct { Ok bool; Value int64; Error string }

return ok 1
-> return ResultIntegerNotFound{Ok: true, Value: 1}

return error NotFound
-> return ResultIntegerNotFound{Ok: false, Error: NotFound}
```

Abort-V1-Abbildung:

```text
function read(id: Integer) returns Integer
aborts NotFound when id = 0
-> func Read(id int64) (int64, error)

abort E
-> return <zero-value>, errors.New(E)

propagierender Call
-> value, err := Read(id); if err != nil { return <zero-value>, err }
```

Contracts:

- `requires` und `ensures` sind in V1 vor allem verifierseitige Semantik.
- `aborts` beeinflusst die Go-Signatur; `aborts ... when`-Bedingungen bleiben verifierseitig und werden nicht als Runtime-Checks generiert.
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

1. BigNumber-/Runtime-Builtins oder weitere V1-Codegen-Luecken priorisieren.
2. Danach Record-/Result-/Abort-Interaktionen ueber Modulgrenzen haerten.
3. Feature-Matrix bei jedem neuen Go-Codegen-Slice mitpflegen.

## Akzeptanzkriterien fuer Compiler V1 Start

Vor der breiten Implementierung sollte gelten:

- `OPEN-GO-COMPILER.md` ist die Leitplanke fuer Modularitaet und Feature-Grenzen.
- Go-Codegen-Artefakte sind pro Language-Modul reproduzierbar.
- Der Compiler kann ein kleines nicht-generisches Modul mit Record, Routine und `main` uebersetzen.
- Import-/Exposing-Regeln werden nicht umgangen.
- Nicht unterstuetzte Features scheitern mit klaren Diagnostics oder expliziten Not-Implemented-Reports.
