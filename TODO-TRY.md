# Entwurf: Benanntes und geschachteltes Try-Konstrukt für Freehold
**Erstellungsdatum:** 14. Juni 2026

Dieses Dokument hält den aktuellen Diskussions- und Entwurfsstand für die Syntax und Semantik einer strukturierten Abort-Fehlerbehandlung mittels benannter `try ... end try`-Blöcke in Freehold fest.

---

## 1. Motivation und Design-Entscheidung

Bisher verhalten sich `abort <ErrorName>`-Anweisungen in Freehold wie nicht abfangbare Abstürze, die den Prozess oder Task-Scheduler direkt terminieren. Für hochsichere transaktionale und volatile Anwendungen (z. B. Netzwerk, Datenbanken) ist die Möglichkeit einer lokalen, kontrollierten Fehlerbehandlung unerlässlich.

### Warum `try <id> ... end try <id>`?
* **Robuste Syntax:** Das explizite Benennen der Blöcke verhindert visuelle oder logische Zuordnungsfehler bei der Verschachtelung. Der Parser kann so Mismatches sofort abfangen (z. B. `FH-PARSE-0001: end try name mismatch`).
* **Konsistenz:** Es fügt sich nahtlos in das bestehende Freehold-Design ein, das bereits Namens-Symmetrien bei Modulen, Routinen und Scopes (`scope name do ... end scope`) erzwingt.
* **Separation of Concerns:** Es vermeidet Konflikte mit der bestehenden `scope`-Syntax, die exklusiv für das Structured-Concurrency-Ressourcenmanagement (`spawn`/`join`/`result`) reserviert bleibt.

---

## 2. Syntax-Spezifikation (Code-Beispiel)

```fh
error ConnectionError
error DBError
error SchemaError

type User is record
    id: Integer
    active: Boolean
end record

function sync_and_load_user(id: Integer) returns User
is
    try db_transaction
        -- Äußerer Schutzblock für Datenbank-Interaktionen
        
        try api_call
            -- Innerer Schutzblock für volatile API-Aufrufe
            if id < 0 then
                abort ConnectionError
            end if
            
            return User { id: id, active: true }

        on ConnectionError do
            -- Behandle den Fehler lokal im inneren Block (Fallback)
            if id = -42 then
                abort DBError -- Eskaliert den Fehler an den äußeren Block
            end if
            return User { id: 0, active: false }
        end try api_call

    on DBError, SchemaError do
        -- Fängt Fehler auf der Transaktions-Ebene ab
        return User { id: -1, active: false }
    end try db_transaction
end sync_and_load_user
```

---

## 3. Semantische Analyse & Compiler-Pfad

### A. Parser & AST (`freehold.lark`)
Die Grammatik wird um ein neues Block-Statement erweitert:
* `try_stmt: "try" IDENTIFIER block "on" handler_list "end" "try" IDENTIFIER`
* `handler_list: handler_clause ("," handler_clause)*`
* `handler_clause: "on" qualified_name_list "do" block`

*Validator-Kriterium im Parser:*
Ein Syntax-Mismatch wird sofort geworfen, wenn das öffnende `IDENTIFIER` nach `try` ungleich dem schließenden `IDENTIFIER` nach `end try` ist.

### B. Control-Flow-Analyzer (Verifier)
* **Stack-basierte Registrierung:** Tritt der Compiler in einen `try <name>`-Block ein, schiebt er die deklarierten Handler (z. B. `ConnectionError`) auf einen lokalen Ausnahme-Stack.
* **Pfad-Rettung (normal_return_possible):** Wird innerhalb eines try-Blocks ein `abort X` ausgelöst, das von einem aktiven Handler abgedeckt wird, gilt dieser Pfad **nicht** mehr als unkontrollierter Abbruch. Die Funktion behält an dieser Stelle ihre Rückgabegarantie, da der Handler einen definitiven Return-Wert oder Ersatzwert bereitstellen muss.
* **SMT-Integration:** Unter dem Handler-Block `on ConnectionError do` gilt für den SMT-Solver die logische Pfadbedingung, unter der der Abort ausgelöst wurde (z. B. `id < 0`). Dies erlaubt mathematisch präzise Kontrollfluss-Verifikationen innerhalb der Recovery-Routinen.

### C. IR-Lowering & Go-Codegen-Abbildung
Im Backend-Codegen (Go-Code) wird dieses Konstrukt flachgeklopft und auf Go's systemeigene `panic`- und `recover`-Mechanismen abgebildet:

```go
func SyncAndLoadUser(ctx context.Context, id int64) (User, error) {
    // Äußerer Try-Block (db_transaction)
    var result User
    func() {
        defer func() {
            if r := recover(); r != nil {
                if isDBErrorOrSchemaError(r) {
                    // Ausführung der on DBError, SchemaError Klausel
                    result = User{Id: -1, Active: false}
                } else {
                    panic(r) // Weiterschleifen anderer Ausnahmen / Aborts
                }
            }
        }()

        // Innerer Try-Block (api_call)
        func() {
            defer func() {
                if r := recover(); r != nil {
                    if isConnectionError(r) {
                        // Ausführung der on ConnectionError Klausel
                        if id == -42 {
                            panic(FreeholdAbort{Kind: "DBError"}) // Eskalation
                        }
                        result = User{Id: 0, Active: false}
                    } else {
                        panic(r)
                    }
                }
            }()

            if id < 0 {
                panic(FreeholdAbort{Kind: "ConnectionError"})
            }
            result = User{Id: id, Active: true}
        }()
    }()
    return result, nil
}
```

---

## 4. Todo-Liste für die Implementierung

- [ ] **Phase 1: Grammatik & Parser**
  - [ ] Neuen Block `try_stmt` in `freehold.lark` integrieren.
  - [ ] AST-Node `TryStmt(name, body, handlers, end_name, pos)` implementieren.
  - [ ] Syntax-Check auf Identität von `name` und `end_name` im Parser verankern.
- [ ] **Phase 2: Semantischer Verifier**
  - [ ] Abort-Stack-Logik in `verifier.py` integrieren.
  - [ ] Erreichbarkeits- und Implikationsprüfung für Handlers im `ControlFlowAnalyzer` implementieren (SMT-Check).
- [ ] **Phase 3: Codegen & Tests**
  - [ ] Go-Codegen-Templates für panic/recover-Kapselung in `go_codegen.py` anbinden.
  - [ ] Positive und negative Testfälle in `tests/language_modules/` schreiben.
