# TODO-NEXT: Dringende Prioritäten für die nächste Phase

Dieses Dokument listet die nächsten dringenden Aufgaben für die Weiterentwicklung des Freehold-Compilers und des Verifikation-Backends auf.

---

## ┌── Priorität 1: Portierung der Verifier-Upgrades auf Go-Frontend & FH-Native
Die kürzlich im Python-Referenzcompiler (`freehold/core/verifier.py`) implementierten Verifikations-Upgrades (GNATprove/SPARK Ada Parity) müssen in das Go-Frontend und den selbsthostenden Compiler-Core (`bootstrap/compiler_core_v1/`) portiert werden.

1. **Informationsfluss-Analyse (Taint-Tracking)**
   - *Aufgabe*: Portierung des interprozeduralen Abhängigkeitstrackings (`depends` Kontrakte) zur Absicherung von Modulgrenzen.
2. **Globale Variablen-Propagation**
   - *Aufgabe*: Transitive Prüfung globaler Ressourcen auf dem Call-Stack gegen die deklarierten `global`-Aspekte.
3. **Statisches Anti-Aliasing (Aliasing-Schutz)**
   - *Aufgabe*: Validierung von Prozeduraufrufen zur Laufzeit-Vermeidung überlappender veränderlicher Zeiger (Parameter-Parameter, Parameter-Global, Argument-Global).
4. **Feldspezifisches Dependency-Tracking**
   - *Aufgabe*: Erfassung von qualifizierten Record-Feldpfaden (z. B. `p1.x` -> `p1`) in Depends-Targets und Mutations-Tracking.
5. **Universal WhyML Code-Generator**
   - *Aufgabe*: Portierung der WhyML-Übersetzungsschicht (`WhyMLCodeGen.fh`) für den Export zu Why3.
6. **Quantifizierte Array-Bedingungen**
   - *Aufgabe*: Unterstützung von `for all` / `for some` Ausdrücken, inklusive SMT-LIB v2 Übersetzung.
7. **Concurrency-Verifikation & Channel-Invarianten**
   - *Aufgabe*: Validierung von `with invariant` Bedingungen an Kanälen und Überprüfung von Vorbedingungen beim `spawn`-Aufruf.

---

## ├── Priorität 2: CLI-Komfort & Cross-Platform Härtung
Verbesserung der Developer Experience (DX) und Portabilität beim Kompilieren von Standalone-Executables.

1. **Komfort-CLI-Befehl `freehold build-exe`**
   - *Aufgabe*: Bereitstellung eines direkten CLI-Befehls zur Erstellung nativer Binärdateien aus Freehold-Quellcode (Kapselung des internen `go-codegen-project` Flows).
2. **Cross-Platform Build-Skripte**
   - *Aufgabe*: Erstellung und Pflege von plattformübergreifenden Skripten (z. B. Linux/macOS Shell-Skripte), um den Build-Prozess außerhalb von Windows abzusichern.
3. **Erweiterte Verifikations-Gates**
   - *Status*: Die WebSocket-Smokes `27_websocket_demo`, `28_websocket_multi_client_demo`, `29_websocket_go_backend_demo`, `30_websocket_json_broadcast_demo`, `32_websocket_json_broadcast_schema_neg` und `33_websocket_room_broadcast_demo` sind in den Compiler-/Stage3-Example-Gates registriert.
   - *Naechste Aufgabe*: Den Komfort um gezielte Example-Filter im Runner erweitern, damit neue Runtime-Smokes ohne Vollsuite lokal schneller pruefbar sind.

---

## └── Priorität 3: REST- & Web-Verbindungsbibliotheken (V2/V3)
Ergonomischer Ausbau des Netzwerk-Stacks auf Basis des WebSocket-Erfolgs. Die aktuelle WebSocket-V1-Schicht deckt Verbindung, Multi-Client, Go-Backend, typed JSON Broadcast, Runtime-Schemafehler als `Result`, Room/Topic-Broadcast, Keepalive, Backpressure und Frame-Policy-Smokes ab.

1. **HTTP-REST-Bibliotheken**
   - *Aufgabe*: Bereitstellung standardisierter Modulbibliotheken für klassische HTTP-REST-APIs, die das strukturierte `Concurrent.Scope`-Modell nutzen.
2. **Server-Sent Events (SSE) Client/Server**
   - *Aufgabe*: Integration von SSE-Laufzeitfunktionen analog zur WebSocket- und gRPC-Streaming-Architektur.
