# Freehold – Test Suite (pos/neg Split)

Jede Kategorie ist in zwei Dateien aufgeteilt:

| Suffix    | Inhalt                                              | Erwartetes Ergebnis      |
|-----------|-----------------------------------------------------|--------------------------|
| `_pos.fh` | Ausschließlich gültiger Code                        | Kompiliert **fehlerfrei** |
| `_neg.fh` | Ungültiger Code – ein Fehlerfall **pro Modul**      | Jedes Modul **scheitert** mit annotiertem Fehlertyp |

## Dateiübersicht

| Kategorie          | _pos.fh               | _neg.fh               | PASS | FAIL |
|--------------------|-----------------------|-----------------------|:----:|:----:|
| Lexer              | test-01-lex_pos.fh    | test-01-lex_neg.fh    | 4    | 4    |
| Modul              | test-02-mod_pos.fh    | test-02-mod_neg.fh    | 3    | 2    |
| Import             | test-03-imp_pos.fh    | test-03-imp_neg.fh    | 3    | 4    |
| Typen/Range/Proto  | test-04-types_pos.fh  | test-04-types_neg.fh  | 8    | 7    |
| Generics           | test-05-generics_pos.fh | test-05-generics_neg.fh | 7  | 3  |
| Funktionen         | test-06-functions_pos.fh | test-06-functions_neg.fh | 7 | 4 |
| Prozeduren         | test-07-procedures_pos.fh | test-07-procedures_neg.fh | 4 | 3 |
| Service/RPC        | test-08-service_pos.fh | test-08-service_neg.fh | 3   | 4   |
| requires           | test-09-requires_pos.fh | test-09-requires_neg.fh | 9  | 4  |
| ensures            | test-10-ensures_pos.fh | test-10-ensures_neg.fh | 9   | 4   |
| aborts             | test-11-aborts_pos.fh | test-11-aborts_neg.fh | 6    | 4   |
| Result<T,E>        | test-12-result_pos.fh | test-12-result_neg.fh | 6    | 4   |
| let & Mutation     | test-13-let-mut_pos.fh | test-13-let-mut_neg.fh | 9  | 6   |
| Kontrollfluss      | test-14-control_pos.fh | test-14-control_neg.fh | 9  | 7   |
| scope/async        | test-15-scope_pos.fh  | test-15-scope_neg.fh  | 6    | 3   |
| Ausdrücke          | test-16-expressions_pos.fh | test-16-expressions_neg.fh | 14 | 6 |
| Stdlib & Args      | test-17-stdlib_pos.fh | test-17-stdlib_neg.fh | 16   | 6   |
| **Gesamt**         |                       |                       | **123** | **75** |

## Struktur der _neg.fh Dateien

Jeder Fehlerfall ist ein eigenständiges Modul:

```fh
-- ──────────────────────────────────────────────────────────
-- [FAIL TYPE] REQ-06: requires-Ausdruck mit falschem Typ
-- ──────────────────────────────────────────────────────────
module Test.REQ.06

function bad_req(n: Integer) returns Integer
requires n = "x"         -- Integer = String → FAIL TYPE
is
    return n
end bad_req

end Test.REQ.06
```

Der Test-Runner prüft jedes Modul unabhängig:
- `_pos.fh` → alle Module müssen **kompilieren**
- `_neg.fh` → jedes Modul muss mit dem annotierten Fehlertyp **scheitern**

## Fehlertyp-Kürzel

| Kürzel  | Bedeutung                                      |
|---------|------------------------------------------------|
| `SYN`   | Parser-/Syntaxfehler                           |
| `TYPE`  | Typprüfer-Fehler                               |
| `PRE`   | `requires`-Verletzung                          |
| `POST`  | `ensures`-Verletzung                           |
| `ABORT` | `aborts`/`abort`-Verletzung                    |
| `SEM`   | Semantikfehler (Scope, Duplikat, Shadowing …)  |
| `EDGE`  | Grenzfall                                      |

## Empfohlene Testreihenfolge

```
Phase 1  Lexer + Parser:    01-lex  → 02-mod → 03-imp
Phase 2  Typsystem:         04-types → 05-generics → 06-functions
Phase 3  Contract-System:   09-requires → 10-ensures → 11-aborts
Phase 4  Fehlerbehandlung:  12-result → 13-let-mut
Phase 5  Kontrollfluss:     14-control → 15-scope
Phase 6  Ausdrücke/Stdlib:  16-expressions → 17-stdlib
Phase 7  Services:          07-procedures → 08-service
```

## Abhängigkeiten

`test-support.fh` definiert alle gemeinsamen Typen und muss zuerst kompiliert werden:
- Typen: `Point`, `Box`, `Labeled`
- Error-Typen: `NotFound`, `InvalidInput`, `Overflow`
- Konstruktoren: `make_point`, `make_box`, `make_labeled`
