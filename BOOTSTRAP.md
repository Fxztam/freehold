# Freehold Bootstrap

Stand: 2026-05-29

Status: Self-Hosting und Bootstrap-Parität wurden erfolgreich über identische SHA256-Hashes der Stage-1 und Stage-2 Compiler-Kerne verifiziert. Der Go-Codegen und die Toolchain sind voll integriert.

Dieses Dokument beschreibt den kontrollierten Pfad von einem extern implementierten Stage0-Compiler zu einem Freehold-Compilerkern. Die zentrale Architekturentscheidung ist festgelegt: FH-IR ist das kanonische Vergleichsformat zwischen Stage 1 und Stage 2.

## Festgelegte Bootstrap-Entscheidung

Das verbindliche Bootstrap-Vergleichsartefakt ist deterministisches, kanonisches FH-IR.

```text
Stage 0 Compiler
    kompiliert Freehold-Compilerquellen
    -> compiler.stage1.fhirb

Stage 1 Compiler/Runner
    fuehrt oder benutzt compiler.stage1.fhirb
    kompiliert dieselben Freehold-Compilerquellen erneut
    -> compiler.stage2.fhirb

Bootstrap-Gate
    sha256(compiler.stage1.fhirb) == sha256(compiler.stage2.fhirb)
```

Native Binaries, LLVM IR oder Go-Code koennen zusaetzlich erzeugt und geprueft werden. Sie sind aber nicht der primaere Bootstrap-Vertrauensanker. Der Bootstrap beweist zuerst, dass der Compilerzustand reproduziert wird. Native Artefakte sind danach abgeleitete Produkte.

## FH-IR Rolle

FH-IR ist die stabile semantische Mitte der Pipeline.

```text
Freehold Source
    -> typed AST
    -> FH-CIR
    -> FH-LIR
    -> FH-IR Interpreter
    -> optional LLVM IR
    -> optional native binary
```

Empfohlene Schichtung:

- FH-CIR: canonical IR, typed, module-level, gut vergleichbar.
- FH-LIR: lowered IR, block/register-orientiert, interpreterfreundlich.
- LLVM IR: Backend-Ausgabe, nicht primaeres Stage-Vergleichsformat.

Das Bootstrap-Vergleichsprofil fuer FH-IR muss deterministisch sein:

- stabile Modulreihenfolge
- stabile Symbol-IDs
- stabile Reihenfolge von Typen, Records, Feldern, Routinen, Blocks und Instruktionen
- keine Host-Pfade im Vergleichsartefakt
- keine Zeitstempel
- keine Debug-Information im Vergleichsartefakt oder Debug-Information nur als separate optionale Section
- keine Hash-/Map-Iteration fuer semantische Ausgabe
- normalisierte String-, Integer-, BigInteger- und Float-Repraesentationen
- explizite IR-Schema-Version
- explizites Bootstrap-Profil
- deterministische Standardbibliothek und Runtime-Builtin-Tabelle

## Warum der Go-Pfad trotz Python-FH-IR sinnvoll bleibt

Die Frage ist berechtigt: Wenn Python mittelfristig bereits kanonisches FH-IR erzeugen kann, warum wurde dann ueberhaupt ein Go-Pfad aufgebaut?

Die kurze Antwort lautet: Python-FH-IR und Go-Pfad loesen zwei verschiedene Probleme.

Python-FH-IR liefert den Referenz- und Vergleichsanker:

```text
Freehold Source
    -> Python Compiler
    -> FH-IR
```

Das ist sehr wertvoll, weil es die Sprache semantisch fixiert und ein deterministisches Bootstrap-Vergleichsartefakt bereitstellt. Es ist aber noch kein Bootstrap im engeren Sinn, sondern weiterhin ein Python-Compiler.

Der Go-Pfad loest das naechste Problem:

```text
Freehold Source
    -> Go Compilerpfad
    -> FH-IR / Go Source / EXE
```

Damit entsteht ein zweiter, unabhaengiger Compilerpfad, der naeher an einer nativen Toolchain liegt und spaeter den Python-Compiler teilweise oder ganz ersetzen kann.

Die Rollen sind deshalb unterschiedlich:

- Python: Referenzcompiler, Sprachdefinition, schnelle Iteration, kanonisches FH-IR.
- Go: Stage-2-Bruecke, nativer Compilerpfad, spaeter ersetzbarer Python-Nachfolger.
- Freehold selbst: langfristiges Self-Hosting-Ziel.

Nur Python->FH-IR wuerde bedeuten:

```text
Freehold ist korrekt, weil der Python-Compiler es sagt.
```

Das ist praktisch, aber noch kein Bootstrap-Vertrauensmodell. Der eigentliche Gewinn entsteht erst mit einem zweiten Pfad:

```text
Python Compiler -> FH-IR A
Go Compiler     -> FH-IR A
```

Wenn beide unabhaengigen Pfade dasselbe kanonische FH-IR erzeugen, wird die Sprachbedeutung deutlich staerker abgesichert, als wenn nur ein einzelner Python-Compiler als Wahrheit dient.

Deshalb war der Go-Pfad kein Umweg, sondern der Beginn von Stage 2:

```text
Stage 1:
    Freehold Source
        -> Python
        -> FH-IR

Stage 2:
    Freehold Source
        -> Go
        -> FH-IR

Bootstrap-Gate:
    Python FH-IR == Go FH-IR
```

Erst danach wird der Go-Pfad selbst wieder zum Trampolin:

```text
Freehold Source
    -> Go Compiler
    -> Go Source / EXE
    -> spaeter Freehold Compilerkern
```

Und noch spaeter:

```text
Freehold Compiler Source
    -> Stage-2 Compiler
    -> neuer Compiler
```

Warum nicht direkt von Python aus nach Self-Hosting bootstrappen? Weil dafuer in Freehold selbst noch mehrere Compiler-relevante Bausteine fehlen oder noch nicht robust genug sind, zum Beispiel:

- Datei- und Tooling-I/O fuer Compilerwerkzeuge
- reichere Collections/Tabellenmodelle
- robuste Diagnostic- und Metadaten-Ausgabe
- kanonischer FH-IR-Serializer und Validator
- spaeter breitere Lowering- und Runtime-Abdeckung

Go ist dafuer eine sehr praktische Zwischenstufe, weil es sofort eine stabile native Toolchain, gute Bibliotheken und eine einfache EXE-Auslieferung bietet.

Die strategische Reihenfolge bleibt deshalb:

1. Python erzeugt kanonisches FH-IR.
2. Go erzeugt dasselbe kanonische FH-IR.
3. Beide Pfade werden gegeneinander validiert.
4. Danach wird der Go-Pfad weiter in Richtung nativer Bootstrap-Compiler gehaertet.
5. Erst spaeter wird ein echter Freehold-Compiler in Freehold selbst realistisch.

Die Existenz des Go-Pfads ist also kein Widerspruch zu Python-FH-IR, sondern die notwendige zweite Haelfte der Bootstrap-Strategie.

Stage 1 sollte mindestens erzeugen:

```text
compiler.stage1.fhirb
compiler.stage1.manifest.json
compiler.stage1.sha256
```

Stage 2 sollte mindestens erzeugen:

```text
compiler.stage2.fhirb
compiler.stage2.manifest.json
compiler.stage2.sha256
```

Das Manifest ist kanonisch zu serialisieren und enthaelt nur deterministische Felder, zum Beispiel:

```json
{
  "schema": "fh-bootstrap-manifest-v1",
  "languageVersion": "freehold-v1",
  "irSchema": "fhir-v1",
  "compilerMode": "bootstrap-canonical",
  "sourceRootHash": "...",
  "stdLibHash": "...",
  "artifact": "compiler.stage1.fhirb",
  "artifactSha256": "..."
}
```

## FH-IR Interpreter

Der FH-IR Interpreter ist der erste Ausfuehrungspfad fuer FH-IR.

Prioritaet des Interpreters:

1. deterministische Semantik
2. klare Diagnostics und Contract-Verletzungen
3. einfacher Bootstrap-Betrieb
4. erst spaeter Performance

Der Interpreter sollte eine typed block/register IR ausfuehren und Contracts als echte Instruktionen behandeln:

```text
contract_requires %cond, routine_id, contract_id
contract_ensures  %cond, routine_id, contract_id
contract_check    %cond, source_span_id
```

`Result<T,E>` bleibt ein normales Wertmodell. `abort E` bleibt ein Kontrollfluss-Effekt und wird nicht mit Result vermischt.

Ein erster FH-IR-Interpreter-Slice sollte klein bleiben:

- Integer
- Boolean
- String
- Records
- fixed Arrays
- Result
- function/procedure calls
- if/while/case als Blocks
- requires/ensures/check
- deterministic Std.IO output buffer

Danach ausbauen:

- abort propagation
- BigInteger/BigFloat
- Json.stringify
- String.template
- modules/imports/linking
- async/scope/channel spaeter
- gRPC spaeter

## LLVM und Native Code

LLVM ist ein Backend-Ziel, nicht das primaere Bootstrap-Vergleichsformat.

```text
FH-LIR
    -> LLVM lowering
    -> LLVM IR
    -> object/native binary
```

Der verpflichtende Bootstrap-Vergleich bleibt:

```text
compiler.stage1.fhirb == compiler.stage2.fhirb
```

Optionale Zusatzvergleiche:

```text
normalized stage1.ll == normalized stage2.ll
normalized/native stage1 binary == normalized/native stage2 binary
```

Die Bootstrap-Regel lautet:

```text
FH-IR reproduziert sich selbst.
```

Erst wenn Stage 1 und Stage 2 dasselbe kanonische FH-IR erzeugen, ist der Bootstrap-Gate bestanden.

## Grundantwort

Ja: Aus dem Go-Code, wie er jetzt bereits generiert wird, kann spaeter ein Freehold-Bootstrap entstehen.

Aber: Mit dem heutigen Stand geht das noch nicht vollstaendig. Der aktuelle Go-Codegen kann bereits echte Freehold-Module in baubare Go-Projekte uebersetzen, deckt aber noch nicht genug Sprache, Runtime und Compiler-Infrastruktur ab, um den Freehold-Compiler selbst vollstaendig in Freehold zu schreiben und zu bauen.

Der heutige Stand ist deshalb am besten als Bootstrap-Fundament zu verstehen:

- stabiler Stage0-Codegen nach Go
- reproduzierbare Go-Artefakte
- Modulgraph- und Projekt-Codegen
- kontrollierte Feature-Matrix
- klare Grenze zwischen unterstuetzten V1-Features und geparkten V2/V3-Themen

## Heutige Bootstrap-Faehigkeiten

Der aktuelle Go-Codegen kann bereits wichtige Bausteine liefern, die fuer Bootstrapping notwendig sind:

- Freehold-Module nach Go uebersetzen.
- Mehrere Freehold-Module als Go-Projekt ausgeben.
- `go.mod` und `build.cmd` fuer generierte Projekte erzeugen.
- Imports, `exposing`, qualifizierte Namen und Cross-Module-Routine-Calls respektieren.
- Deterministische Package-Pfade und Import-Aliase fuer Freehold-Module generieren.
- Primitive Typen, Records, einfache Routinen, Statements und Expressions abbilden.
- `Result<T,E>` als Go-Wertmodell generieren.
- `aborts` fuer abgedeckte V1-Faelle als explizite Go-`error`-Returns abbilden.
- Runtime-Builtins fuer `Math`, `Std.IO`, `String.*`, `String.template`, `Json.stringify` und erste `Big.*`-Faelle auf Go-Stdlib-/Runtime-Funktionen abbilden.
- Go-Codegen-Goldens, Artefakte und Feature-Matrix im Gate pruefen.
- Generierte Go-Projekte mit `go test ./...` bauen.

Das ist genau die Art Fundament, auf dem ein Bootstrap-Pfad entstehen kann.

## Was fuer echtes Bootstrapping noch fehlt

Ein echter Bootstrap bedeutet nicht nur, Freehold nach Go zu uebersetzen. Er bedeutet, dass ein relevanter Compilerkern in Freehold selbst geschrieben und mit dem vorhandenen Compiler nach Go oder FH-IR uebersetzt werden kann.

Dafuer fehlen noch mehrere Schichten.

## 1. Compilerkern in Freehold ausdruecken

Der Compiler selbst muss spaeter in Freehold geschrieben werden koennen. Dafuer braucht Freehold genug Sprachmittel, um mindestens diese Teile sauber auszudruecken:

- AST-Modelle
- Token-/Parser- oder IR-Eingabemodelle
- Diagnostics
- Symboltabellen
- Typinformationen
- Modulgraphen
- Verifier-Regeln
- IR- und Codegen-Regeln
- Artefakt- und JSON-Metadaten

Aktuell existiert diese Compilerlogik noch ueberwiegend in Python- und Go-Werkzeugen. Bootstrap beginnt erst dann wirklich, wenn ein kleiner, aber echter Compilerkern als Freehold-Quellcode vorliegt.

## 2. Mehr Codegen- und IR-Abdeckung

Der heutige Codegen deckt den V1-Kern gut ab, aber ein Compilerprogramm braucht voraussichtlich mehr als diesen Kern.

Besonders wichtig sind:

- BigNumber-/Runtime-Builtins fuer `BigInteger` und `BigFloat`.
- robuste Array-Goldens und finale Array-Repraesentation.
- importierte Records ueber Modulgrenzen.
- importierte Result-Typen ueber Modulgrenzen.
- importierte Abort-Fehler und Fehlertypen ueber Modulgrenzen.
- stabile Package-Typnamen fuer Cross-Module-Signaturen.
- Result-value- und Result-array-value-Contract-Zugriffe.
- breitere Abort-Semantik und eventuell spaetere Handler-Syntax.
- dynamische oder mindestens klar begrenzte String-Template-Formen.
- ausreichend Datei-/CLI-/Diagnostic-Ausgabe fuer Compilerwerkzeuge.
- kanonisches FH-IR-Schema und Serializer.
- FH-IR Validator und Interpreter.

Der naechste strategisch sinnvolle Schritt fuer Bootstrap ist deshalb nicht sofort Self-Hosting, sondern das Schliessen dieser V1-Luecken und das Aufbauen der FH-IR-Schicht.

## 3. Runtime-Layer stabilisieren

Ein bootstrappender Compiler braucht eine verlaessliche Runtime-Grenze. Alle Freehold-Builtins, die der Compilerkern verwendet, muessen stabil nach Go, FH-IR und spaeter LLVM abbildbar sein.

Bereits vorhanden:

- `String.concat`
- `String.substr`
- `String.replace`
- `String.instr`
- `String.template` fuer statische und erste dynamische Formen
- `Math.*` fuer V1-Standardfaelle
- `Std.IO.log` und `Std.IO.logf`
- `Json.stringify` fuer verifierseitig begrenzte Recordformen
- erste `Big.*` Runtime-Builtins

Wahrscheinlich noch notwendig:

- vollstaendigere `Big.*` Runtime oder Go-/FH-IR-Mapping
- Collections oder ausreichend starke Array-/Record-Muster
- Dateizugriff
- CLI-Argumente
- strukturierte Diagnostic-Ausgabe
- kontrollierte Fehlerausgabe
- eventuell Pfad-/String-Helfer fuer Modulnamen und Dateinamen

Die Regel bleibt: Runtime-Abhaengigkeiten muessen sichtbar und explizit sein. Bootstrap darf keine versteckten globalen Compiler-Magien einfuehren.

## 4. Parser- und Grammar-Strategie

Der Bootstrap muss nicht sofort bedeuten, dass Freehold seinen Parser komplett selbst baut.

Es gibt zwei sinnvolle Pfade:

1. Pragmatischer Stage0-Pfad
   - Freehold schreibt zuerst AST-/Verifier-/IR-/Codegen-nahe Compilerteile.
   - Parser/Grammar-Erzeugung bleibt zunaechst extern oder generiert.
   - Der Freehold-Compilerkern arbeitet auf einer stabilen AST- oder IR-Eingabe.

2. Voller Self-Hosting-Pfad
   - Freehold implementiert spaeter auch Parser, Grammar-Verarbeitung oder Parsergenerator-nahe Logik selbst.
   - Dieser Pfad ist deutlich spaeter und gehoert nicht in den ersten Bootstrap-Slice.

Empfehlung: Zuerst den pragmatischen Stage0-Pfad gehen. Ein stabiler AST-/IR-Eingang ist fuer Bootstrap ausreichend und vermeidet, dass Parserbau den Compiler-Bootstrap blockiert.

## 5. Deterministische Stage-Vergleiche

Bootstrapping braucht reproduzierbare Stufen und klare Vergleichskriterien.

Vorgeschlagene Stufen:

```text
Stage0
    Der heutige externe Freehold-Compiler/Go-Codegen erzeugt FH-IR und/oder Go-Code.

Stage1
    Ein in Freehold geschriebener Compilerkern wird mit Stage0 zu FH-IR kompiliert.
    Der Stage1-Compiler/Runner erzeugt selbst wieder FH-IR-Artefakte.

Stage2
    Der Stage1-Compiler kompiliert den Freehold-Compilerkern erneut.
    Die erzeugten FH-IR-Outputs werden mit Stage1-FH-IR verglichen.
```

Verpflichtendes Vergleichskriterium:

- bytegleiches kanonisches FH-IR, gemessen ueber `sha256(compiler.stage1.fhirb) == sha256(compiler.stage2.fhirb)`.

Optionale Zusatzvergleiche:

- normalisierte Go-Ausgabe
- normalisierte LLVM-IR-Ausgabe
- bytegleiche JSON-Metadaten
- gleiche Diagnostics
- gleiche Artefaktliste
- funktionale Gleichheit ueber Goldens und Tests
- normalisierte oder reproduzierbare native Binaries

Fuer den Anfang bleibt funktionale Gleichheit ueber Goldens nuetzlich. Der eigentliche Bootstrap-Gate zielt aber auf bytegleiches kanonisches FH-IR.

## Realistischer Bootstrap-Fahrplan

### Phase A: Compiler V1 weiter vervollstaendigen

Ziel: Genug Sprache und Runtime abdecken, damit ein kleiner Compilerkern in Freehold realistisch schreibbar wird.

Prioritaeten:

1. FH-IR-Schema, Canonicalizer und Serializer entwerfen.
2. FH-IR Validator und Interpreter fuer den V1-Kern bauen.
3. BigNumber-/Runtime-Builtins verbreitern.
4. Arrays und finale Array-Repraesentation haerten.
5. Cross-Module Records, Results und Aborts in Signaturen haerten.
6. breitere Abort-Abdeckung.
7. benoetigte CLI-/Datei-/Diagnostic-Runtime klaeren.

### Phase B: Mini-Compilerkern in Freehold schreiben

Ziel: Nicht den ganzen Compiler portieren, sondern einen kleinen, testbaren Compilerkern schaffen.

Moegliche Startinhalte:

- einfache AST-Datentypen
- kleine Symboltabellen
- einfache Typnamen- und Modulnamen-Helfer
- IR-Namensbildung
- Go-Namensbildung
- Go-Package-Pfadbildung
- Codegen fuer eine kleine Teilmenge
- Diagnostic-Strukturen

Dieser Kern soll bewusst klein bleiben. Er muss noch nicht den gesamten Freehold-Compiler ersetzen.

### Phase C: Stage0-Go-Codegen und Stage0-FH-IR verwenden

Ziel: Der heutige Compiler uebersetzt den Freehold-Compilerkern in ein baubares oder interpretierbares Stage1-Artefakt.

Akzeptanzkriterien:

- erzeugtes Go-Projekt baut mit `go test ./...`, falls Go als Runner genutzt wird
- `compiler.stage1.fhirb` wird deterministisch erzeugt
- Artefakte sind reproduzierbar
- Diagnostics sind stabil
- generierter Compiler kann erste Mini-Fixtures verarbeiten

### Phase D: Stage1 gegen Fixtures laufen lassen

Ziel: Der mit Stage0 gebaute Freehold-Compilerkern erzeugt selbst FH-IR, Go-Code oder JSON-Artefakte.

Akzeptanzkriterien:

- Stage1 verarbeitet dieselben Mini-Fixtures wie Stage0 fuer den gewaehlten Teilbereich.
- Stage1-Ausgaben stimmen normalisiert mit erwarteten Goldens ueberein.
- Abweichungen werden als Diagnostics sichtbar, nicht stillschweigend verschluckt.

### Phase E: Stage2-FH-IR-Vergleich

Ziel: Der Stage1-Compiler kompiliert den Freehold-Compilerkern erneut.

Akzeptanzkriterien:

- Stage2 baut oder interpretiert erfolgreich.
- `compiler.stage1.fhirb` und `compiler.stage2.fhirb` sind bytegleich.
- Manifest-Hashes stimmen.
- Unterschiede sind erklaert und reproduzierbar.

### Phase F: Schrittweise Abloesung externer Compilerlogik

Ziel: Python-/Go-Compilerlogik wird nicht abrupt ersetzt, sondern Modul fuer Modul durch Freehold-Compilerlogik ergaenzt oder abgeloest.

Moegliche Reihenfolge:

1. Namensbildung und Package-Pfadbildung.
2. Diagnostic-Modelle.
3. einfache AST-Transformationen.
4. FH-IR-Emission fuer Kern-Statements.
5. Go-Codegen fuer Kern-Statements.
6. Modulgraph-nahe Logik.
7. Verifier-Teilregeln.
8. Parser-/Grammar-nahe Logik erst deutlich spaeter.

## Nicht-Ziele fuer den ersten Bootstrap-Slice

Diese Dinge sollen den ersten Bootstrap-Slice nicht blockieren:

- kompletter Parser in Freehold
- komplette Grammar-Verarbeitung in Freehold
- vollstaendige Monomorphisierung von Generics
- Async Runtime und Channel-Ausfuehrung
- gRPC Go server/client bindings
- REST/WebSocket/SSE Transport-Libs
- Native/Image Builder
- LLVM als primaeres Stage-Vergleichsformat
- vollstaendige native bytegleiche Stage1/Stage2-Reproduktion ab Tag eins

## Risiken

Wichtige Risiken fuer den Bootstrap-Pfad:

- Zu frueher Versuch, den ganzen Compiler auf einmal in Freehold zu schreiben.
- Unklare Runtime-Grenze fuer Builtins.
- Cross-Module-Typnamen, die im Go-Code, FH-IR oder LLVM-Code kollidieren oder nicht importierbar sind.
- Nicht-deterministische Artefaktreihenfolge.
- Zu breite Generics-Anforderungen vor stabiler V1-Codegen-Basis.
- Parser-Self-Hosting als Blocker fuer den ersten Bootstrap.
- Verwechslung von Native-Binary-Reproduktion mit dem primaeren FH-IR-Bootstrap-Gate.

Gegenmassnahmen:

- kleine Stage0/Stage1-Slices
- Feature-Matrix weiter pflegen
- alle neuen Bootstrap-Faelle als Goldens ablegen
- generierte Go-Projekte weiterhin bauen
- FH-IR-Goldens und Hash-Gates einfuehren
- Runtime-Abhaengigkeiten explizit halten
- Parser/Grammar erst spaeter self-hosten

## Kurzfazit

Der jetzige Go-Codegen ist ein Stage0-Kandidat fuer Freehold-Bootstrapping. Er uebersetzt bereits echte Freehold-Module nach baubarem Go, respektiert Modulgrenzen und besitzt reproduzierbare Artefakte.

Noch ist er kein kompletter Bootstrap-Compiler. Dafuer fehlen weitere V1-Codegen-Abdeckung, Runtime-Schichten, FH-IR-Schichten und ein erster Compilerkern in Freehold selbst.

Der richtige naechste Schritt ist deshalb nicht sofort Self-Hosting, sondern die offenen V1-Luecken und die FH-IR-Basis so zu schliessen, dass ein kleiner Compilerkern in Freehold bequem, deterministisch und testbar ausdrueckbar wird.

Die strategische Regel bleibt:

```text
FH-IR reproduziert sich selbst.
```