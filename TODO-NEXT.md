# TODO-NEXT: Dringende Prioritäten für die nächste Phase

Dieses Dokument listet die nächsten dringenden Aufgaben für die Weiterentwicklung des Freehold-Compilers und des Verifikation-Backends auf.

---

## ┌── Priorität 0: Bereinigung & Konsolidierung der Framing-Meilensteine (Aktuelle Baustelle)
Die kürzlich im Python-Referenzcompiler vorgenommenen Framing-, Modifies- und Aliasing-Verbesserungen sind vollständig verifiziert. Folgende Aufräum- und Feinschliff-Themen stehen an:

1. **Arbeitsbaum-Cleanup**
   - Untracked temporäre Archive und Protokolle (`.zip`, `run_log.txt`, `stage3_examples_log.txt`, etc.) sicher löschen oder in `.gitignore` verschieben.
   - Die verifizierten Änderungen strukturiert in Git committen.
2. **Modernisierung der GNATprove-Äquivalenztests**
   - Die verbleibenden älteren Testfälle in `freehold_gnatprove_equivalence_tests_v2` (z. B. in `01_contract_overflow` bis `09_record_updates`) von alter Freehold-Syntax (z. B. `record` statt `type ... is record`, `do` statt `is`, `:=` in `let`) auf die aktuelle Parser-Spezifikation migrieren, um die GNATprove-Äquivalenzprüfung (`run_expected.py`) wieder auf 100% Erfolg zu heben.
3. **Morgige Kernaufgabe: Task-Verifikation & Concurrency-Garantien (Sicherheits-Standard)**
   - *Aufgabe*: Analyse und Einplanung des [memories/repo/task_verification_proposal.md](memories/repo/task_verification_proposal.md) zur Einführung von `task` als vertraglich prüfbare Einheit im Verifier.
   - *Inhalte & Concurrency-Regeln*:
     1. **Die 6 statischen Verifikationsregeln**: Vollständiges Awaiting/Detaching von Handles, strikte Kanaltypisierung, Flussrichtungs-Validierung (`send` / `receive` vs. `Sender`/`Receiver`), Preconditions an der `spawn`-Grenze und Postconditions nach dem `await` (integriert in Z3).
     2. **Shared-Mutable-State-Verhinderung**: Statische Fehlerprüfung, wenn mutable State an mehrere gestartete Tasks übergeben wird. Fehlermeldung:
        `Compile error: shared mutable state passed to multiple spawned tasks`
     3. **Prioritär gesteuertes Scheduling (`priority`)**: Integration von `spawn ... with priority X` im Parser und Codegen (Mapping auf das $O(\log N)$-prioritized Insertion-Verfahren des Runtimeschedulers).
     4. **Prozessordrosselung & Begrenzungen (`limit` / `parallel`)**: Unterstützung von `parallel (limit = N) do ... end parallel`-Regionen. Statische "No-Blocking"-Garantie im Verifier (keine unbegrenzten blockierenden Kanal-Ops in limitierten Pools).
     5. **Paralleles Rendezvous (`await all`)**: Syntaktische Abbildung von `await all [t1, t2]` im Parser, inklusive monomorphtypisierter Array-Ergebniszusammenführung.
     6. **Physisches Core-Mapping & M:N Thread-Pool**: Go-Runtime-Optimierung auf Basis von `runtime.NumCPU()`, Work-Stealing-Scheduling pro Kern sowie beweisbar race-freie Ausführung der asynchronen Co-Routinen.

---

## ├── Priorität 1: Portierung der Verifier-Upgrades auf Go-Frontend & FH-Native
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
