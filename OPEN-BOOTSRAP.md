# Open: Freehold Bootstrap

Stand: 2026-05-24

Status: Bootstrap ist strategisch moeglich, aber noch nicht self-hosting-faehig. Der aktuelle Go-Codegen ist ein belastbarer Stage0-Kandidat, kein vollstaendiger Bootstrap-Compiler.

Dieses Dokument beschreibt, wie Freehold spaeter aus dem bereits vorhandenen Go-Codegen heraus gebootstrapped werden kann. Ziel ist nicht, sofort einen kompletten Compiler in Freehold zu schreiben, sondern einen kontrollierten Pfad von einem extern implementierten Stage0-Compiler zu einem Freehold-Compilerkern zu definieren.

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
- Runtime-Builtins fuer `Math`, `Std.IO`, `String.*`, `String.template` und `Json.stringify` auf Go-Stdlib-Funktionen abbilden.
- Go-Codegen-Goldens, Artefakte und Feature-Matrix im Gate pruefen.
- Generierte Go-Projekte mit `go test ./...` bauen.

Das ist genau die Art Fundament, auf dem ein Bootstrap-Pfad entstehen kann.

## Was fuer echtes Bootstrapping noch fehlt

Ein echter Bootstrap bedeutet nicht nur, Freehold nach Go zu uebersetzen. Er bedeutet, dass ein relevanter Compilerkern in Freehold selbst geschrieben und mit dem vorhandenen Compiler nach Go uebersetzt werden kann.

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
- Go-Codegen-Regeln
- Artefakt- und JSON-Metadaten

Aktuell existiert diese Compilerlogik noch ueberwiegend in Python- und Go-Werkzeugen. Bootstrap beginnt erst dann wirklich, wenn ein kleiner, aber echter Compilerkern als Freehold-Quellcode vorliegt.

## 2. Mehr Codegen-Abdeckung

Der heutige Codegen deckt den V1-Kern gut ab, aber ein Compilerprogramm braucht voraussichtlich mehr als diesen Kern.

Besonders wichtig sind:

- BigNumber-/Runtime-Builtins fuer `BigInteger` und `BigFloat`.
- robustere Array-Goldens und finale Array-Repraesentation.
- importierte Records ueber Modulgrenzen.
- importierte Result-Typen ueber Modulgrenzen.
- importierte Abort-Fehler und Fehlertypen ueber Modulgrenzen.
- stabile Package-Typnamen fuer Cross-Module-Signaturen.
- `Result` value field access.
- breitere Abort-Semantik und eventuell spaetere Handler-Syntax.
- dynamische oder mindestens klar begrenzte String-Template-Formen.
- ausreichend Datei-/CLI-/Diagnostic-Ausgabe fuer Compilerwerkzeuge.

Der naechste strategisch sinnvolle Schritt fuer Bootstrap ist deshalb nicht sofort Self-Hosting, sondern das Schliessen dieser V1-Luecken.

## 3. Runtime-Layer stabilisieren

Ein bootstrappender Compiler braucht eine verlaessliche Runtime-Grenze. Alle Freehold-Builtins, die der Compilerkern verwendet, muessen stabil nach Go abbildbar sein.

Bereits vorhanden:

- `String.concat`
- `String.substr`
- `String.replace`
- `String.instr`
- `String.template` fuer statische Formen
- `Math.*` fuer V1-Standardfaelle
- `Std.IO.log` und `Std.IO.logf`
- `Json.stringify` fuer verifierseitig begrenzte Recordformen

Wahrscheinlich noch notwendig:

- `Big.*` Runtime oder Go-Mapping
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
   - Freehold schreibt zuerst AST-/Verifier-/Codegen-nahe Compilerteile.
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
    Der heutige externe Freehold-Compiler/Go-Codegen erzeugt Go-Code.

Stage1
    Ein in Freehold geschriebener Compilerkern wird mit Stage0 nach Go kompiliert.
    Der daraus entstehende Go-Compiler erzeugt selbst wieder Go-Code oder Artefakte.

Stage2
    Der Stage1-Compiler kompiliert den Freehold-Compilerkern erneut.
    Die erzeugten Outputs werden mit Stage1-Outputs verglichen.
```

Vergleichsmoeglichkeiten:

- bytegleiche Go-Ausgabe, falls Formatierung und Reihenfolge streng deterministisch sind
- normalisierte Go-Ausgabe
- bytegleiche JSON-Metadaten
- gleiche Diagnostics
- gleiche Artefaktliste
- funktionale Gleichheit ueber Goldens und Tests

Fuer den Anfang reicht funktionale Gleichheit ueber Goldens. Spaeter sollte normalisierte oder bytegleiche Ausgabe angestrebt werden.

## Realistischer Bootstrap-Fahrplan

### Phase A: Compiler V1 weiter vervollstaendigen

Ziel: Genug Sprache und Runtime abdecken, damit ein kleiner Compilerkern in Freehold realistisch schreibbar wird.

Prioritaeten:

1. BigNumber-/Runtime-Builtins.
2. Arrays und finale Array-Repraesentation haerten.
3. Cross-Module Records, Results und Aborts in Signaturen haerten.
4. Result value field access.
5. breitere Abort-Abdeckung.
6. benoetigte CLI-/Datei-/Diagnostic-Runtime klaeren.

### Phase B: Mini-Compilerkern in Freehold schreiben

Ziel: Nicht den ganzen Compiler portieren, sondern einen kleinen, testbaren Compilerkern schaffen.

Moegliche Startinhalte:

- einfache AST-Datentypen
- kleine Symboltabellen
- einfache Typnamen- und Modulnamen-Helfer
- Go-Namensbildung
- Go-Package-Pfadbildung
- Codegen fuer eine kleine Teilmenge
- Diagnostic-Strukturen

Dieser Kern soll bewusst klein bleiben. Er muss noch nicht den gesamten Freehold-Compiler ersetzen.

### Phase C: Stage0-Go-Codegen verwenden

Ziel: Der heutige Compiler uebersetzt den Freehold-Compilerkern nach Go.

Akzeptanzkriterien:

- erzeugtes Go-Projekt baut mit `go test ./...`
- Artefakte sind reproduzierbar
- Diagnostics sind stabil
- generierter Compiler kann erste Mini-Fixtures verarbeiten

### Phase D: Stage1 gegen Fixtures laufen lassen

Ziel: Der mit Stage0 gebaute Freehold-Compilerkern erzeugt selbst Go-Code oder JSON-Artefakte.

Akzeptanzkriterien:

- Stage1 verarbeitet dieselben Mini-Fixtures wie Stage0 fuer den gewaehlten Teilbereich.
- Stage1-Ausgaben stimmen normalisiert mit erwarteten Goldens ueberein.
- Abweichungen werden als Diagnostics sichtbar, nicht stillschweigend verschluckt.

### Phase E: Stage2-Vergleich

Ziel: Der Stage1-Compiler kompiliert den Freehold-Compilerkern erneut.

Akzeptanzkriterien:

- Stage2 baut erfolgreich.
- Stage1- und Stage2-Ausgaben sind normalisiert gleich oder funktional gleich.
- Unterschiede sind erklaert und reproduzierbar.

### Phase F: Schrittweise Ablösung externer Compilerlogik

Ziel: Python-/Go-Compilerlogik wird nicht abrupt ersetzt, sondern Modul fuer Modul durch Freehold-Compilerlogik ergaenzt oder abgeloest.

Moegliche Reihenfolge:

1. Namensbildung und Package-Pfadbildung.
2. Diagnostic-Modelle.
3. einfache AST-Transformationen.
4. Go-Codegen fuer Kern-Statements.
5. Modulgraph-nahe Logik.
6. Verifier-Teilregeln.
7. Parser-/Grammar-nahe Logik erst deutlich spaeter.

## Nicht-Ziele fuer den ersten Bootstrap-Slice

Diese Dinge sollen den ersten Bootstrap-Slice nicht blockieren:

- kompletter Parser in Freehold
- komplette Grammar-Verarbeitung in Freehold
- vollstaendige Monomorphisierung von Generics
- Async Runtime und Channel-Ausfuehrung
- gRPC Go server/client bindings
- REST/WebSocket/SSE Transport-Libs
- Native/Image Builder
- vollstaendige bytegleiche Stage1/Stage2-Reproduktion ab Tag eins

## Risiken

Wichtige Risiken fuer den Bootstrap-Pfad:

- Zu frueher Versuch, den ganzen Compiler auf einmal in Freehold zu schreiben.
- Unklare Runtime-Grenze fuer Builtins.
- Cross-Module-Typnamen, die im Go-Code kollidieren oder nicht importierbar sind.
- Nicht-deterministische Artefaktreihenfolge.
- Zu breite Generics-Anforderungen vor stabiler V1-Codegen-Basis.
- Parser-Self-Hosting als Blocker fuer den ersten Bootstrap.

Gegenmassnahmen:

- kleine Stage0/Stage1-Slices
- Feature-Matrix weiter pflegen
- alle neuen Bootstrap-Faelle als Goldens ablegen
- generierte Go-Projekte weiterhin bauen
- Runtime-Abhaengigkeiten explizit halten
- Parser/Grammar erst spaeter self-hosten

## Kurzfazit

Der jetzige Go-Codegen ist genau ein Stage0-Kandidat fuer Freehold-Bootstrapping. Er uebersetzt bereits echte Freehold-Module nach baubarem Go, respektiert Modulgrenzen und besitzt reproduzierbare Artefakte.

Noch ist er kein kompletter Bootstrap-Compiler. Dafuer fehlen weitere V1-Codegen-Abdeckung, Runtime-Schichten und ein erster Compilerkern in Freehold selbst.

Der richtige naechste Schritt ist deshalb nicht sofort Self-Hosting, sondern die offenen V1-Luecken so zu schliessen, dass ein kleiner Compilerkern in Freehold bequem und testbar ausdrueckbar wird.