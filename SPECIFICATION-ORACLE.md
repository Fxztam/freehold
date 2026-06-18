# Freehold Specification: Oracle
**Status:** Baseline Oracle Database FFI, Oracle Cloud wallet connections, KeePassXC credential flow, SQL-file execution, and typed demo rows  
**Audience:** Freehold authors, FFI authors, backend authors, database integration developers, and verifier implementers

This document explains Freehold's current Oracle integration.

Oracle support is not new core syntax. It is a standard FFI module backed by a local Go shim and the vendored `go-ora` driver:

```text
Std.Oracle                      Freehold module surface
freehold.local/oracleshim        native Go FFI shim
github.com/sijms/go-ora/v2       vendored Oracle driver
Oracle wallet folder             downloaded Oracle Cloud wallet
KeePassXC / KeyPass              credential source for username/password/wallet path
Result<T, OracleError>           checked database error boundary
```

The design goal is to keep Oracle database access explicit, typed at the Freehold boundary where possible, and safe with respect to secrets.

---

## 1. Module Surface

The Oracle surface is declared in `Std.Oracle`:

```freehold
module Std.Oracle

/**
@std
@ffi
Native Oracle database bindings backed by the vendored go-ora driver through
freehold.local/oracleshim.
*/

type OracleDemoRow is record
    id: Integer
    name: String
    amount: Integer
end record

error OracleError

@ffi("freehold.local/oracleshim", "ConnWithCredentials")
function conn_with_credentials(conn_target: String, username: String, password: String) returns Result<String, OracleError>
is
end conn_with_credentials

@ffi("freehold.local/oracleshim", "ConnFromWalletTNS")
function conn_from_wallet_tns(wallet_path: String, username: String, password: String) returns Result<String, OracleError>
is
end conn_from_wallet_tns

@ffi("freehold.local/oracleshim", "PingWalletTimeout")
function ping_wallet_timeout(conn_str: String, wallet_path: String, timeout_seconds: Integer) returns String
is
end ping_wallet_timeout

@ffi("freehold.local/oracleshim", "QueryScalarWalletTimeout")
function query_scalar_wallet_timeout(conn_str: String, wallet_path: String, query: String, timeout_seconds: Integer) returns Result<String, OracleError>
is
end query_scalar_wallet_timeout

@ffi("freehold.local/oracleshim", "QueryRowsWalletTimeout")
function query_rows_wallet_timeout(conn_str: String, wallet_path: String, query: String, max_rows: Integer, timeout_seconds: Integer) returns Result<String, OracleError>
is
end query_rows_wallet_timeout

@ffi("freehold.local/oracleshim", "QueryDemoRowsWalletTimeout")
function query_demo_rows_wallet_timeout(conn_str: String, wallet_path: String, query: String, timeout_seconds: Integer) returns Result<Array<OracleDemoRow, 2>, OracleError>
is
end query_demo_rows_wallet_timeout

@ffi("freehold.local/oracleshim", "ExecWalletTimeout")
function exec_sql_wallet_timeout(conn_str: String, wallet_path: String, statement: String, timeout_seconds: Integer) returns Result<String, OracleError>
is
end exec_sql_wallet_timeout

end Std.Oracle
```

Most operations return `Result<T, OracleError>`. `ping_wallet_timeout` is the exception: it returns an empty string on success and an error text on failure.

---

## 2. FFI Boundary

The Oracle module uses Freehold's Go FFI pattern:

```text
Freehold @ffi declaration
    -> generated Go wrapper
    -> freehold.local/oracleshim
    -> github.com/sijms/go-ora/v2
    -> Oracle Database / Oracle Cloud Wallet
```

The local Go module is:

```go
module freehold.local/oracleshim

go 1.22

require github.com/sijms/go-ora/v2 v2.9.0

replace github.com/sijms/go-ora/v2 => ../go-ora
```

The generated Go project maps the local shim with `require` and `replace` entries:

```text
freehold.local/oracleshim
    requires freehold.local/oracleshim v0.0.0
    requires github.com/sijms/go-ora/v2 v2.9.0
    replace  freehold.local/oracleshim => vendor-go/oracle-shim
    replace  github.com/sijms/go-ora/v2 => vendor-go/go-ora
```

`freehold.local/oracleshim` is a local module name. It is not downloaded from the network.

---

## 3. Connection URL With Credentials

Use `conn_with_credentials` when the connection target is known and username/password are supplied separately:

```freehold
let conn_result: Result<String, OracleError> = conn_with_credentials("adb.example.oraclecloud.com:1522/service", username, password)
if conn_result.ok = false then
    call Std.IO.logf("Oracle connection URL build failed: ${}", String.error_text(conn_result.error))
    return 1
end if
```

The shim accepts:

```text
host:port/service
oracle://host:port/service
oracle://USER:PASS@host:port/service
```

It trims the username, rejects empty connection target, username, or password, and URL-encodes username/password into the URL userinfo.

Do not log the returned connection URL because it contains credentials.

---

## 4. Wallet Connection From tnsnames.ora

The preferred Oracle Cloud wallet pattern is `conn_from_wallet_tns`:

```freehold
let wallet_conn_result: Result<String, OracleError> = conn_from_wallet_tns(wallet_path, username, password)
if wallet_conn_result.ok = false then
    call Std.IO.logf("Oracle connection URL build from tnsnames.ora failed: ${}", String.error_text(wallet_conn_result.error))
    return 1
end if
let wallet_conn: String = wallet_conn_result.value
```

The shim reads:

```text
<wallet_path>/tnsnames.ora
```

It extracts the first:

```text
HOST
PORT
SERVICE_NAME
```

Then it builds an `oracle://user:password@host:port/service` URL.

This removes the need for an `ORACLE_CLOUD_CONN` environment variable in the newer demos. The wallet location comes from KeePassXC `Wallet_Location` metadata.

---

## 5. Wallet DSN Options

Wallet operations call the Go driver with an augmented DSN:

```text
SSL=enable
SSL Verify=false
WALLET=<url-escaped wallet path>
CONNECT TIMEOUT=<seconds>
TIMEOUT=<seconds>
```

Conceptually:

```text
oracle://user:password@host:port/service?SSL=enable&SSL Verify=false&WALLET=C%3A%2Fwallet&CONNECT TIMEOUT=10&TIMEOUT=10
```

If the base connection string already has query parameters, wallet parameters are appended with `&` instead of `?`.

Timeout options are added when `timeout_seconds` is greater than zero.

---

## 6. KeePassXC Credential Pattern

Oracle demos 44 and 45 load username, password, and wallet location through the KeyPass/KeePassXC bridge:

```freehold
let oracle_credentials: Result<KeePassXCCredential, CryptoError> = keepassxc_entry_credential("OracleAccounts", "./OracleAccounts.dbx", "TEST_DEMO")
if oracle_credentials.ok = false then
    call Std.IO.logf("Oracle TEST_DEMO credential lookup failed: ${}", String.error_text(oracle_credentials.error))
    return 1
end if

call Std.IO.logf("Oracle credentials loaded from KeePassXC for username = ${}", oracle_credentials.value.username)
let wallet_path: String = oracle_credentials.value.wallet_location
call Std.IO.log("Oracle wallet location loaded from KeePassXC")
```

Then build the wallet connection:

```freehold
let wallet_conn_result: Result<String, OracleError> = conn_from_wallet_tns(wallet_path, oracle_credentials.value.username, oracle_credentials.value.password)
```

The password is used for the connection URL but is not logged.

---

## 7. Environment Variable Pattern

Older demos use environment variables:

```freehold
let wallet_conn: String = getenv("ORACLE_CLOUD_CONN")
if wallet_conn = "" then
    call Std.IO.log("ORACLE_CLOUD_CONN is missing")
    return 1
end if

let wallet_path: String = getenv("ORACLE_WALLET_PATH")
if wallet_path = "" then
    call Std.IO.log("ORACLE_WALLET_PATH is missing")
    return 1
end if
```

This is useful for controlled deployment environments. For local developer credentials, prefer the KeePassXC pattern so passwords are not stored in source code or shell history.

The SQL-file demo still uses an environment variable for a non-secret path:

```freehold
let sql_dir: String = getenv("ORACLE_SQL_DIR")
if sql_dir = "" then
    call Std.IO.log("ORACLE_SQL_DIR is missing")
    return 1
end if
```

---

## 8. Ping

Use `ping_wallet_timeout` before executing queries:

```freehold
let wallet_ping: String = ping_wallet_timeout(wallet_conn, wallet_path, timeout_seconds)
if wallet_ping != "" then
    call Std.IO.logf("Oracle wallet ping failed: ${}", wallet_ping)
    return 1
end if
call Std.IO.log("Oracle wallet ping succeeded")
```

`ping_wallet_timeout` returns:

```text
""               success
error text        failure
```

This plain-string shape is historical and convenient for a simple health check. Query and exec operations use `Result<T, OracleError>`.

---

## 9. Scalar Query

Use `query_scalar_wallet_timeout` to read the first column of the first row as a string:

```freehold
let wallet_scalar: Result<String, OracleError> = query_scalar_wallet_timeout(wallet_conn, wallet_path, "SELECT systimestamp FROM dual", timeout_seconds)
if wallet_scalar.ok = false then
    call Std.IO.logf("Oracle wallet query_scalar failed: ${}", String.error_text(wallet_scalar.error))
    return 1
end if
call Std.IO.logf("Oracle wallet database time = ${}", wallet_scalar.value)
```

In the SQL-file demo, the query is loaded from a file:

```sql
SELECT systimestamp FROM dual
```

---

## 10. Executing SQL Statements

Use `exec_sql_wallet_timeout` for DDL, DML, and PL/SQL blocks that do not return rows:

```freehold
let create_table: Result<String, OracleError> = exec_sql_wallet_timeout(wallet_conn, wallet_path, "CREATE TABLE FH_FFI_DEMO (ID NUMBER PRIMARY KEY, NAME VARCHAR2(80), AMOUNT NUMBER)", timeout_seconds)
if create_table.ok = false then
    call Std.IO.logf("Oracle demo create table failed: ${}", String.error_text(create_table.error))
    return 1
end if
```

The result value is the affected row count as a string when the driver reports it.

A robust drop-table pattern handles a missing table:

```freehold
let drop_table: Result<String, OracleError> = exec_sql_wallet_timeout(wallet_conn, wallet_path, "BEGIN EXECUTE IMMEDIATE 'DROP TABLE FH_FFI_DEMO'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;", timeout_seconds)
```

For larger SQL or PL/SQL, prefer SQL files.

---

## 11. SQL Files

The SQL-file demo keeps SQL and PL/SQL in `.sql` files and loads them at runtime:

```freehold
import File exposing read_to_string

function sql_path(sql_dir: String, file_name: String) returns String
is
    return String.concat(String.concat(sql_dir, "/"), file_name)
end sql_path
```

Read and execute a file:

```freehold
function run_exec_file(wallet_conn: String, wallet_path: String, sql_dir: String, file_name: String, label: String, timeout_seconds: Integer) returns Boolean
is
    let path: String = sql_path(sql_dir, file_name)
    let loaded: Result<String, String> = read_to_string(path)
    if not loaded.ok then
        call Std.IO.logf("read SQL file failed: ${}", loaded.error)
        return false
    end if

    let executed: Result<String, OracleError> = exec_sql_wallet_timeout(wallet_conn, wallet_path, loaded.value, timeout_seconds)
    if not executed.ok then
        call Std.IO.logf("execute SQL file failed: ${}", String.error_text(executed.error))
        return false
    end if

    call Std.IO.logf("executed SQL file: ${}", label)
    return true
end run_exec_file
```

Example SQL files:

```sql
CREATE TABLE FH_FFI_DEMO_SQL (
    ID NUMBER PRIMARY KEY,
    NAME VARCHAR2(80),
    AMOUNT NUMBER
)
```

```sql
INSERT INTO FH_FFI_DEMO_SQL (ID, NAME, AMOUNT)
VALUES (1, 'Alpha', 125)
```

```sql
SELECT ID, NAME, AMOUNT
FROM FH_FFI_DEMO_SQL
ORDER BY ID
```

---

## 12. Row Query as Text Table

Use `query_rows_wallet_timeout` for a flexible, FFI-friendly result set:

```freehold
let rows: Result<String, OracleError> = query_rows_wallet_timeout(wallet_conn, wallet_path, "SELECT ID, NAME, AMOUNT FROM FH_FFI_DEMO ORDER BY ID", 20, timeout_seconds)
if rows.ok = false then
    call Std.IO.logf("Oracle demo query rows failed: ${}", String.error_text(rows.error))
    return 1
end if
call Std.IO.logf("Oracle demo rows:\n${}", rows.value)
```

The shim returns a tab-separated table string with a header row:

```text
ID	NAME	AMOUNT
1	Alpha	125
2	Beta	250
```

`max_rows` limits the number of data rows when greater than zero.

Cells are formatted as strings. `NULL` is rendered as `NULL`; embedded newlines, carriage returns, and tabs are replaced with spaces.

---

## 13. Typed Fixed Projection

For code that wants typed Freehold iteration, define a fixed record projection:

```freehold
type OracleDemoRow is record
    id: Integer
    name: String
    amount: Integer
end record
```

The FFI binding returns a fixed-size array:

```freehold
function query_demo_rows_wallet_timeout(conn_str: String, wallet_path: String, query: String, timeout_seconds: Integer) returns Result<Array<OracleDemoRow, 2>, OracleError>
```

Use it like this:

```freehold
let typed_rows_result: Result<Array<OracleDemoRow, 2>, OracleError> = query_demo_rows_wallet_timeout(wallet_conn, wallet_path, "SELECT ID, NAME, AMOUNT FROM FH_FFI_DEMO ORDER BY ID", timeout_seconds)
if typed_rows_result.ok = false then
    call Std.IO.logf("Oracle demo typed rows failed: ${}", String.error_text(typed_rows_result.error))
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

This is strongly typed but deliberately static: columns and row count are part of the FFI signature.

---

## 14. Type Conversion Rules

The current typed demo projection expects:

```text
ID      -> Integer
NAME    -> String
AMOUNT  -> Integer
```

The shim converts Oracle numeric cells to `int64` for `Integer`. It accepts common numeric representations from the driver, including integer and float values and numeric strings. `NULL` is rejected for integer fields.

Text table queries are less strict: every cell is formatted as text.

---

## 15. Secret Handling

Oracle connection URLs contain credentials. Treat them as secret values.

Do not log:

```text
wallet_conn
password
full oracle:// URL
raw KeePassXC credential object
```

Safe pattern:

```freehold
call Std.IO.logf("Oracle credentials loaded from KeePassXC for username = ${}", oracle_credentials.value.username)
call Std.IO.log("Oracle wallet location loaded from KeePassXC")
```

Avoid:

```freehold
call Std.IO.logf("wallet_conn = ${}", wallet_conn)
call Std.IO.logf("password = ${}", oracle_credentials.value.password)
```

---

## 16. Error Handling Pattern

Use `Result` checks at every fallible boundary:

```freehold
let result: Result<String, OracleError> = query_scalar_wallet_timeout(wallet_conn, wallet_path, query, timeout_seconds)
if result.ok = false then
    call Std.IO.logf("Oracle query failed: ${}", String.error_text(result.error))
    return 1
end if
```

Do the same for `CryptoError` when loading KeePassXC credentials and for `String` file errors when loading SQL files.

A typical full chain has three checked boundaries:

```text
KeePassXC credential lookup       Result<KeePassXCCredential, CryptoError>
Oracle connection URL build       Result<String, OracleError>
Oracle query/exec operation       Result<String, OracleError>
```

---

## 17. Common Failure Patterns

### 17.1 Missing Wallet Path

Problem:

```text
wallet_path = ""
```

`conn_from_wallet_tns` returns `error OracleError` because the wallet path must not be empty.

### 17.2 Missing tnsnames.ora

Problem:

```text
<wallet_path>/tnsnames.ora does not exist
```

The connection URL build fails before any database connection attempt.

### 17.3 Incomplete TNS Data

Problem:

```text
tnsnames.ora has no HOST, PORT, or SERVICE_NAME entry
```

The shim extracts the first occurrence of each required field. Missing fields cause `error OracleError`.

### 17.4 Logging Connection URLs

Invalid:

```freehold
call Std.IO.log(wallet_conn)
```

The connection URL includes username and password.

### 17.5 Not Checking Result

Invalid:

```freehold
let rows: Result<String, OracleError> = query_rows_wallet_timeout(wallet_conn, wallet_path, query, 20, timeout_seconds)
call Std.IO.log(rows.value)
```

Check `.ok` first.

### 17.6 Using Typed Projection for the Wrong SQL Shape

Invalid pattern:

```freehold
let typed_rows_result: Result<Array<OracleDemoRow, 2>, OracleError> = query_demo_rows_wallet_timeout(wallet_conn, wallet_path, "SELECT NAME FROM FH_FFI_DEMO", timeout_seconds)
```

`OracleDemoRow` expects `ID`, `NAME`, and `AMOUNT` in that fixed projection.

### 17.7 Inline Large SQL Blocks

Inline SQL strings are fine for tiny examples. For larger SQL or PL/SQL, use `.sql` files loaded with `File.read_to_string`.

---

## 18. Practical Checklist

Before committing Oracle code, check:

- Oracle support is imported from `Std.Oracle`.
- Secrets are loaded through KeePassXC or controlled environment variables.
- `Wallet_Location` points to a folder containing `tnsnames.ora`.
- `conn_from_wallet_tns` result is checked before using the connection string.
- The connection string is never logged.
- `ping_wallet_timeout` is used before query/exec workflows.
- Every `Result<_, OracleError>` is checked before `.value` is used.
- SQL file paths such as `ORACLE_SQL_DIR` are validated before reading.
- SQL-file reads check `Result<String, String>`.
- `max_rows` is set intentionally for text-table queries.
- Typed row APIs are used only for fixed projections that match the declared record.
- Timeout values are explicit and nonzero for network/database work.
- Error logs include operation context but not credentials.

A good Freehold Oracle program keeps credentials outside source code, builds wallet connections through a checked FFI boundary, and uses either text-table results for flexible queries or fixed `Array<Record,N>` results for typed projections.
