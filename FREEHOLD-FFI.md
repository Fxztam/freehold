# Freehold FFI fuer Go

Dieses Dokument beschreibt, wie Freehold-Funktionen ueber `@ffi` an Go-Funktionen gebunden werden. Das Oracle-Beispiel mit `freehold.local/oracleshim` ist dabei die Referenz fuer das allgemeine Muster.

## Grundidee

Eine Freehold-Routine kann als native Go-Bindung deklariert werden:

```freehold
@ffi("go/import/path", "ExportedGoFunction")
function name(arg: String) returns String
is
end name
```

Die Routine hat in Freehold einen leeren Body. Der Go-Codegenerator erzeugt daraus einen Wrapper, der Freehold-Werte in Go-Werte uebersetzt, die Go-Funktion aufruft und das Ergebnis wieder in Freehold-Form bringt.

Schema:

```text
Freehold-Modul
    @ffi("go/import/path", "ExportedGoFunction")
        |
        v
generierter Go-Wrapper
        |
        v
Go-Funktion / lokaler Shim / externe Go-Bibliothek
```

## ABI-Regeln

Die FFI-Grenze sollte einfache, stabile Signaturen verwenden.

| Freehold | Go |
| ---------- | ---- |
| `String` | `string` |
| `Integer` | `int64` |
| `Double` | `float64` |
| `Boolean` | `bool` |
| `Result<T, E>` | `(T, error)` |

Bei `Result<T, E>` gilt:

```text
Go: (value, nil)  -> Freehold: ok value
Go: (_, err)      -> Freehold: error E, mit err.Error() als Fehlertext
```

In Freehold wird das Ergebnis so verwendet:

```freehold
let result: Result<String, FileError> = read_text("demo.txt")

if result.ok = false then
    call Std.IO.logf("read failed: ${}", String.error_text(result.error))
    return 1
end if

call Std.IO.logf("content: ${}", result.value)
```

`ok`, `value` und `error` sind semantische Result-Felder. Die aktuelle Go-Repräsentation verwendet einen booleschen `Ok`-Tag, keine numerischen `00`/`01`-Tags.

## Direkte FFI

Direkte FFI ist passend, wenn die Go-Funktion bereits eine einfache Signatur hat.

Beispiel: Go-Standardbibliothek `os.Getenv`.

```freehold
module Std.Env

@ffi("os", "Getenv")
function getenv(name: String) returns String
is
end getenv

end Std.Env
```

Hier braucht Freehold keinen lokalen Shim, weil `os.Getenv(name string) string` direkt zur Freehold-ABI passt.

## Shim-FFI

Ein Shim ist sinnvoll, wenn eine Go-Bibliothek komplexe APIs, Handles, Structs, Interfaces, Contexts oder optionale Parameter nutzt. Der Shim ist ein kleines lokales Go-Modul, das diese Komplexitaet in Freehold-freundliche Funktionen uebersetzt.

Beispielstruktur:

```text
vendor-go/fileshim/
    go.mod
    shim.go

Std/File.fh
```

Go-Shim:

```go
package fileshim

import "os"

func ReadText(path string) (string, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return "", err
    }
    return string(data), nil
}
```

Freehold-Bindung:

```freehold
module Std.File

error FileError

@ffi("freehold.local/fileshim", "ReadText")
function read_text(path: String) returns Result<String, FileError>
is
end read_text

end Std.File
```

Wichtig: Die Go-Funktion muss exportiert sein, also mit einem Grossbuchstaben beginnen (`ReadText`, nicht `readText`).

## Oracle-Referenz

Das Oracle-Modul nutzt genau dieses Shim-Muster.

Freehold:

```freehold
@ffi("freehold.local/oracleshim", "ConnWithCredentials")
function conn_with_credentials(conn_target: String, username: String, password: String) returns Result<String, OracleError>
is
end conn_with_credentials

@ffi("freehold.local/oracleshim", "ConnFromWalletTNS")
function conn_from_wallet_tns(wallet_path: String, username: String, password: String) returns Result<String, OracleError>
is
end conn_from_wallet_tns

@ffi("freehold.local/oracleshim", "QueryScalarWalletTimeout")
function query_scalar_wallet_timeout(conn_str: String, wallet_path: String, query: String, timeout_seconds: Integer) returns Result<String, OracleError>
is
end query_scalar_wallet_timeout
```

Lokales Go-Modul:

```go
module freehold.local/oracleshim

go 1.22

require github.com/sijms/go-ora/v2 v2.9.0

replace github.com/sijms/go-ora/v2 => ../go-ora
```

Go-Funktion im Shim:

```go
func ConnWithCredentials(connTarget string, username string, password string) (string, error)
func ConnFromWalletTNS(walletPath string, username string, password string) (string, error)
func QueryScalarWalletTimeout(connStr string, walletPath string, query string, timeoutSeconds int64) (string, error)
```

`ConnWithCredentials` accepts either a complete `oracle://...` URL, a URL with placeholder credentials, or a `host:port/service` target. It URL-encodes username/password through Go's `net/url` package and returns a connection URL suitable for the wallet routines.

`ConnFromWalletTNS` removes the connection-target environment variable from the Oracle demos: it reads `tnsnames.ora` from the wallet folder, extracts the first `HOST`, `PORT` and `SERVICE_NAME`, then calls the same credential-safe URL builder internally. Demos 44 and 45 obtain the wallet folder from the selected KeePassXC entry's `Wallet_Location` field or `Wallet_Location=...` tag, so demo 44 needs no Oracle connection environment variable and demo 45 only needs `ORACLE_SQL_DIR` for its external SQL files.

Damit entsteht die Zuordnung:

```text
Std.Oracle.fh
    @ffi("freehold.local/oracleshim", "QueryScalarWalletTimeout")
        |
        v
vendor-go/oracle-shim
        |
        v
vendor-go/go-ora
        |
        v
Oracle Database / Oracle Cloud Wallet
```

`freehold.local/oracleshim` ist kein Internet-Modul. Es ist ein lokaler Go-Modulname, der im generierten Go-Projekt per `replace` auf `vendor-go/oracle-shim` gelegt wird.

## Ergebnismengen

Fuer Datenbank-Resultsets gibt es zwei sinnvolle Stufen:

1. Aktuell stabil: Der Shim gibt mehrere Zeilen als formatierten `String` zurueck.
2. Typisiert fuer feste Projektionen: Der Shim gibt `Array<Record, N>` zurueck.
3. Spaeter dynamisch: Cursor-/Iterator-Typen fuer variable Spalten und variable Zeilenzahl.

Das Oracle-Shim nutzt fuer den ersten Schritt eine tab-getrennte Texttabelle:

```go
func QueryRowsWalletTimeout(connStr string, walletPath string, query string, maxRows int64, timeoutSeconds int64) (string, error)
```

Freehold-Bindung:

```freehold
@ffi("freehold.local/oracleshim", "QueryRowsWalletTimeout")
function query_rows_wallet_timeout(conn_str: String, wallet_path: String, query: String, max_rows: Integer, timeout_seconds: Integer) returns Result<String, OracleError>
is
end query_rows_wallet_timeout
```

Anwendung mit Tabelle anlegen, Inserts und Abfrage:

```freehold
let create_table: Result<String, OracleError> = exec_sql_wallet_timeout(wallet_conn, wallet_path, "CREATE TABLE FH_FFI_DEMO (ID NUMBER PRIMARY KEY, NAME VARCHAR2(80), AMOUNT NUMBER)", timeout_seconds)
if create_table.ok = false then
    call Std.IO.logf("create table failed: ${}", String.error_text(create_table.error))
    return 1
end if

let insert_one: Result<String, OracleError> = exec_sql_wallet_timeout(wallet_conn, wallet_path, "INSERT INTO FH_FFI_DEMO (ID, NAME, AMOUNT) VALUES (1, 'Alpha', 125)", timeout_seconds)
if insert_one.ok = false then
    call Std.IO.logf("insert failed: ${}", String.error_text(insert_one.error))
    return 1
end if

let rows: Result<String, OracleError> = query_rows_wallet_timeout(wallet_conn, wallet_path, "SELECT ID, NAME, AMOUNT FROM FH_FFI_DEMO ORDER BY ID", 20, timeout_seconds)
if rows.ok = false then
    call Std.IO.logf("query rows failed: ${}", String.error_text(rows.error))
    return 1
end if

call Std.IO.logf("rows:\n${}", rows.value)
```

Die Ausgabe ist ein einzelner String mit Header und Datenzeilen, z.B.:

```text
ID    NAME    AMOUNT
1     Alpha   125
2     Beta    250
```

Fuer echte Freehold-Iteration kann eine feste SQL-Projektion als Record modelliert werden:

```freehold
type OracleDemoRow is record
    id: Integer
    name: String
    amount: Integer
end record

@ffi("freehold.local/oracleshim", "QueryDemoRowsWalletTimeout")
function query_demo_rows_wallet_timeout(conn_str: String, wallet_path: String, query: String, timeout_seconds: Integer) returns Result<Array<OracleDemoRow, 2>, OracleError>
is
end query_demo_rows_wallet_timeout
```

Der Shim gibt dazu eine strukturell passende Go-Array-Signatur zurueck:

```go
func QueryDemoRowsWalletTimeout(connStr string, walletPath string, query string, timeoutSeconds int64) ([2]struct {
    Id     int64
    Name   string
    Amount int64
}, error)
```

In Freehold wird ueber das feste Array mit `while` und Indexzugriff iteriert:

```freehold
let typed_rows_result: Result<Array<OracleDemoRow, 2>, OracleError> = query_demo_rows_wallet_timeout(wallet_conn, wallet_path, "SELECT ID, NAME, AMOUNT FROM FH_FFI_DEMO ORDER BY ID", timeout_seconds)
if typed_rows_result.ok = false then
    call Std.IO.logf("typed rows failed: ${}", String.error_text(typed_rows_result.error))
    return 1
end if

let typed_rows: Array<OracleDemoRow, 2> = typed_rows_result.value
let row_index: Integer = 0
while row_index < 2
invariant row_index >= 0
invariant row_index <= 2
variant 2 - row_index
do
    let row: OracleDemoRow = typed_rows[row_index]
    let row_text: String = String.template("typed row id=${id}, name=${name}, amount=${amount}", id: row.id, name: row.name, amount: row.amount)
    call Std.IO.log(row_text)
    row_index := row_index + 1
end while
```

Diese Form ist stark typisiert, aber noch bewusst statisch: Spalten und maximale Zeilenzahl sind Teil der FFI-Signatur.

## Go-Modul-Mapping

Wenn ein FFI-Import ein lokales Shim-Modul mit weiteren Abhaengigkeiten braucht, muss der Go-Codegenerator wissen, welche `require`- und `replace`-Eintraege in das generierte `go.mod` gehoeren.

Das Oracle-Mapping ist aktuell im Go-Codegenerator hinterlegt:

```text
freehold.local/oracleshim
    requires freehold.local/oracleshim v0.0.0
    requires github.com/sijms/go-ora/v2 v2.9.0
    replace  freehold.local/oracleshim => vendor-go/oracle-shim
    replace  github.com/sijms/go-ora/v2 => vendor-go/go-ora
```

The SQL-file Oracle demo also uses a small file shim:

```text
freehold.local/fileshim
    requires freehold.local/fileshim v0.0.0
    replace  freehold.local/fileshim => vendor-go/file-shim
```

The Crypto demo uses a local shim around Go's standard crypto packages:

```text
freehold.local/cryptoshim
    requires freehold.local/cryptoshim v0.0.0
    replace  freehold.local/cryptoshim => vendor-go/crypto-shim
```

`Std.Crypto` currently exposes SHA-2, HMAC-SHA256, secure random hex, AES-256-GCM, a small KeePassXC CLI bridge and read-only Windows Credential Manager checks for KeePassXC master-key presence. AES-GCM uses a hex ABI: `key_hex` must encode exactly 32 bytes, encryption returns a hex envelope `nonce || ciphertext || tag`, and decryption requires the same AAD string. The KeePassXC bridge can locate `keepassxc-cli`, read its version, generate passwords, list entries from a KeePassXC database, and read one selected entry credential for a database connection. KeePass Manager profile credentials are read from Windows Credential Manager internally, for example `Profile_OracleAccounts.kdbx@KeePassManagerApp`. The list API returns only title, username and notes; master keys are not returned to Freehold. The targeted credential API returns `KeePassXCCredential { username, password, wallet_location }` for the requested title. `wallet_location` is read from the KeePassXC entry's `Wallet_Location` custom field, or from a tag/value such as `Wallet_Location=C:\path\to\wallet`; callers can build an Oracle wallet connect string without logging the password. The Freehold keyring API is intentionally read-only: no store, update or delete function is exposed.

Example binding for a targeted KeePassXC entry lookup:

```freehold
type KeePassXCCredential is record
    username: String
    password: String
    wallet_location: String
end record

@ffi("freehold.local/cryptoshim", "KeePassXCEntryCredential")
function keepassxc_entry_credential(keyring_name: String, db_file_name: String, title: String) returns Result<KeePassXCCredential, CryptoError>
is
end keepassxc_entry_credential
```

Demo 43 uses:

```freehold
let oracle_demo_credential: Result<KeePassXCCredential, CryptoError> = keepassxc_entry_credential("OracleAccounts", "./OracleAccounts.dbx", "TEST_DEMO")
```

The shim accepts the historical `.dbx` spelling and resolves it to the local `.kdbx` file when present.

Fuer neue lokale Shims sollte ein entsprechendes Mapping ergaenzt werden, damit `freehold build-exe` ohne manuelles Nachbearbeiten des generierten `go.mod` funktioniert.

## Vorgehen fuer neue Go-Routinen

1. Entscheiden, ob direkte FFI reicht oder ein Shim gebraucht wird.
2. Go-Funktion mit einfacher ABI bereitstellen.
3. Fehlerfaelle als `error` zurueckgeben, wenn Freehold `Result<T, E>` verwenden soll.
4. In Freehold einen passenden `error`-Typ deklarieren.
5. Freehold-Routine mit `@ffi("import/path", "GoSymbol")` und leerem Body deklarieren.
6. Bei lokalen Shims ein Go-Modul unter `vendor-go/...` anlegen.
7. Bei lokalen Shims das Go-Modul-Mapping im Codegenerator ergaenzen.
8. Mit `verify` und `build-exe` pruefen.

## Faustregeln

- Direkte FFI fuer einfache Standard-Go-Funktionen wie `os.Getenv`.
- Shim-FFI fuer Datenbanken, Netzwerk, JSON, Crypto, Cloud APIs und Bibliotheken mit komplexen Typen.
- `Result<T, E>` fuer alle Go-Funktionen, die `error` liefern koennen.
- Freehold-FFI-Routinen bleiben leer und werden als vertrauenswuerdige native Bindungen behandelt.
- Verträge solcher Bindungen sind Annahmen: Freehold verifiziert den FFI-Body nicht, sondern nur die Freehold-Signatur und Verwendung.
