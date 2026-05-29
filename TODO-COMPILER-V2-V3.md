# TODO Compiler V2/V3: Priorisierte Roadmap & GNATprove-Alignment

> [!IMPORTANT]
> **Grammar & Parser Source of Truth:**
> - `freehold/grammar/freehold.lark` ist die exakt auszuführende Parser-Grammatik (Lark) und die primäre Source of Truth für den Parser.
> - `freehold/core/grammar_inline.py` (enthält `FREEHOLD_GRAMMAR`) enthält die exakt gespiegelte Inline-Variante der Lark-Grammatik und muss bei jeder Grammatikänderung absolut synchron gehalten werden.
> - Die verschiedenen EBNF-Dateien in `freehold/grammar/freehold*.ebnf` dienen primär der Spezifikation, Dokumentation oder Visualisierung und dürfen **nicht** mit der aktiven Lark-Grammatik verwechselt werden.

Dieses Dokument definiert die priorisierte Roadmap für die Weiterentwicklung des Freehold-Compilers und der Verifikations-Engine in den Phasen V2 und V3. Die Themen sind nach ihrer Wichtigkeit für die Sprach-Sicherheit, Code-Generierung und Schnittstellen-Integration geordnet.

---

## Priorität 1: Formale Verifikation & Typsystem-Erweiterungen (Sicherheit)

Diese Features erweitern das mathematische Beweissystem von Freehold auf Basis des **SPARK Ada / GNATprove** Vorbilds.

1. **Statische Subtyp-Wertebereiche (Ada-Subtypes)**
   - *Ziel*: Automatische statische Generierung von SMT-Beweisen für Wertebereichs-Invarianten (z. B. `type My_Range is Integer range 1 .. 10`).
   - *Details*: 
     - Generierung von Pfad-Annahmen (Assertions) für Variablen dieses Typs im SMT-Pfad (z. B. `(assert (>= x 1))` und `(assert (<= x 10))`).
     - Generierung von Verification Conditions (VCs) bei jeder Zuweisung (`:=`) oder Bindung (`let`).
2. **Generics-Inferenz & Typ-Constraints (Bounds)**
   - *Ziel*: Automatische Auflösung generischer Argumente bei Funktionsaufrufen (`my_func(5)` statt `my_func<Integer>(5)`).
   - *Details*: Einschränkung generischer Typen über formale Constraints (z. B. `T is Comparable`).
3. **Abort-Implikationsprüfung & Pfadsensitive Kontrollfluss-Analyse**
   - *Ziel*: Formale Verifikation von Abort-Bedingungen.
   - *Details*: Mathematischer Nachweis im SMT-Solver, dass bestimmte Fehlermeldungen/Aborts unter definierten Vorbedingungen (`requires`) unmöglich ausgelöst werden können (Ausschluss von Laufzeit-Abstürzen).

---

## Priorität 2: Concurrency & Runtime-Scheduler (Performance)

Diese Features erwecken die asynchrone Sprachdefinition von Freehold auf Runtime-Ebene zum Leben.

1. **Asynchroner Runtime-Executor**
   - *Ziel*: Implementierung eines physischen Task-Schedulers und Thread-Pools für die Ausführung von nebenläufigen Programmen in Go.
   - *Details*: Entwicklung effizienter Work-Stealing-Algorithmen zur Lastverteilung asynchroner Scopes.
2. **Cancellation Tokens, Deadlines & Timeouts**
   - *Ziel*: Sicheres Abbrechen asynchroner Operationen und Propagation von Timeouts über asynchrone Call-Chains hinweg.
3. **Scheduler-Optimierung & Tuning**
   - *Ziel*: Priorisierung und Ressourcen-Tuning der Concurrent-Scopes unter Last.

---

## Priorität 3: Go-Backend & Transpiler-Optimierung (Codegen)

Diese Features optimieren die Codequalität und Performance des generierten Go-Codes.

1. **Generics-Monomorphisierung**
   - *Ziel*: Vollständige Transpilierung von generischen Freehold-Typen und -Funktionen in spezifische, nicht-generische Go-Funktionen zur Kompilierungszeit.
   - *Details*: Vermeidet Performance-Einbußen durch dynamische Typ-Interface-Boxen in Go.
2. **Qualifizierte generische Aufrufe**
   - *Ziel*: Voller Support für den Zugriff auf geschachtelte generische Members und komplexe Typ-Kompositionen im Go-Frontend.

---

## Priorität 4: Netzwerk- & Schnittstellen-Bindings (Integration)

Diese Features ermöglichen die native Interoperabilität von Freehold in verteilten Systemen.

1. **gRPC-Client-Bindings & Streaming**
   - *Ziel*: Generierung von Client-Stubs zur Kommunikation mit externen gRPC-Services.
   - *Details*: Unterstützung für bidirektionales, serverseitiges und clientseitiges gRPC-Streaming.
2. **Custom Error- & Metadata-Mapping**
   - *Ziel*: Flexible, deklarative Abbildung von Freehold-Aborts auf gRPC-Header und spezifische Status-Codes.
3. **REST- & WebSocket-Verbindungsbibliotheken**
   - *Ziel*: Bereitstellung standardisierter Modulbibliotheken für Web-Verbindungen (SSE, WebSockets und klassische HTTP-REST-APIs).
