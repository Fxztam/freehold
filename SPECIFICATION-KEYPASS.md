# Freehold Specification: KeyPass
**Status:** Baseline KeePassXC/keyring bridge, credential lookup, password generation, and secret-handling rules  
**Audience:** Freehold authors, verifier implementers, FFI authors, backend authors, and application developers handling credentials

This document explains Freehold's KeyPass model: a small, read-only bridge from Freehold to KeePassXC and the local operating-system keyring.

The current implementation is exposed through `Std.Crypto` and a Go FFI shim:

```text
Std.Crypto                         Freehold module surface
freehold.local/cryptoshim           native Go shim
keepassxc-cli                       external KeePassXC CLI executable
Windows Credential Manager          local profile/master-key metadata source
KeePassXCCredential                 selected credential record
Result<T, CryptoError>              checked error boundary
```

The design goal is to let Freehold programs use credentials without committing passwords, wallet locations, API tokens, or database connection secrets into source code.

---

## 1. Security Model

KeyPass support is intentionally conservative.

The baseline rules are:

- Freehold reads credentials through `Std.Crypto`.
- KeePassXC database access is performed by `keepassxc-cli`.
- KeePass Manager profile credentials are read from Windows Credential Manager by the shim.
- Master keys are not returned to Freehold.
- The keyring API is read-only.
- No store, update, delete, or overwrite function is exposed.
- All fallible operations return `Result<T, CryptoError>`.
- Application code must check `.ok` before using `.value`.

This is a boundary API, not a new core language feature.

---

## 2. Module Surface

The KeyPass-related surface lives in `Std.Crypto`:

```freehold
import Std.Crypto exposing CryptoError, KeePassXCCredential, keepassxc_cli_path, keepassxc_entry_credential, keepassxc_generate_password, keepassxc_list_entries, keepassxc_version, keyring_has_keepassxc_master_key
```

The module declares a dedicated error:

```freehold
error CryptoError
```

The targeted credential record is:

```freehold
type KeePassXCCredential is record
    username: String
    password: String
    wallet_location: String
end record
```

`username` and `password` come from the selected KeePassXC entry.  
`wallet_location` comes from the entry's `Wallet_Location` field or a supported tag form.

---

## 3. FFI Boundary

The Freehold functions are FFI declarations backed by `freehold.local/cryptoshim`:

```freehold
@ffi("freehold.local/cryptoshim", "KeePassXCEntryCredential")
function keepassxc_entry_credential(keyring_name: String, db_file_name: String, title: String) returns Result<KeePassXCCredential, CryptoError>
is
end keepassxc_entry_credential
```

The Go-side shape is:

```go
func KeePassXCEntryCredential(keyringName string, dbFileName string, title string) (KeePassXCCredential, error)
```

A Go `nil` error maps to `ok value`.  
A Go error maps to `error CryptoError` with diagnostic text available through `String.error_text(result.error)`.

---

## 4. Checking KeePassXC Availability

Use `keepassxc_cli_path` to check whether `keepassxc-cli` is available on `PATH`:

```freehold
let keepassxc_path: Result<String, CryptoError> = keepassxc_cli_path()
if keepassxc_path.ok = false then
    call Std.IO.logf("keepassxc-cli not available: ${}", String.error_text(keepassxc_path.error))
    return 1
end if
```

Use `keepassxc_version` to read the CLI version:

```freehold
let keepassxc_ver: Result<String, CryptoError> = keepassxc_version()
if keepassxc_ver.ok = false then
    call Std.IO.logf("keepassxc-cli version failed: ${}", String.error_text(keepassxc_ver.error))
    return 1
end if
```

These checks should run before a workflow depends on a KeePassXC database.

---

## 5. Generating Passwords

Use `keepassxc_generate_password` to ask KeePassXC to generate a password:

```freehold
let generated: Result<String, CryptoError> = keepassxc_generate_password(24)
if generated.ok = false then
    call Std.IO.logf("password generation failed: ${}", String.error_text(generated.error))
    return 1
end if
```

The baseline native shim bounds password length:

```text
minimum length: 8
maximum length: 256
```

Invalid:

```freehold
let too_short: Result<String, CryptoError> = keepassxc_generate_password(4)
```

This returns an error result.

Do not log generated passwords in production code. A demo may log one to prove the FFI path, but application code should treat the value as secret material.

---

## 6. Listing Entries

Use `keepassxc_list_entries` to list database entries:

```freehold
let entries: Result<String, CryptoError> = keepassxc_list_entries("OracleAccounts.kdbx", 200)
if entries.ok = false then
    call Std.IO.logf("KeePassXC list entries failed: ${}", String.error_text(entries.error))
    return 1
end if
```

The list API returns a formatted text table containing only:

```text
title
username
notes
```

The list API does not return passwords or master keys.

`max_entries` defaults internally when less than or equal to zero and is capped by the shim. Values above the current upper bound are rejected.

---

## 7. Targeted Credential Lookup

Use `keepassxc_entry_credential` to read one selected credential:

```freehold
let oracle_credentials: Result<KeePassXCCredential, CryptoError> = keepassxc_entry_credential("OracleAccounts", "./OracleAccounts.dbx", "TEST_DEMO")
if oracle_credentials.ok = false then
    call Std.IO.logf("credential lookup failed: ${}", String.error_text(oracle_credentials.error))
    return 1
end if
```

The arguments are:

```text
keyring_name   KeePass Manager profile/keyring name
db_file_name   KeePassXC database file path
title          entry title to read
```

The returned value is:

```freehold
let username: String = oracle_credentials.value.username
let password: String = oracle_credentials.value.password
let wallet_path: String = oracle_credentials.value.wallet_location
```

The shim validates that `username`, `password`, and `wallet_location` are not empty.

---

## 8. Database File Resolution

The current shim accepts the historical `.dbx` spelling and resolves it to `.kdbx` when a matching database exists.

Example:

```freehold
keepassxc_entry_credential("OracleAccounts", "./OracleAccounts.dbx", "TEST_DEMO")
```

The shim looks for the requested path and then for the `.kdbx` alternative:

```text
./OracleAccounts.dbx
./OracleAccounts.kdbx
```

If no database file is found, the operation returns `error CryptoError`.

---

## 9. Keyring/Profile Lookup

The targeted credential API reads KeePass Manager profile data from Windows Credential Manager.

For a keyring name such as:

```text
OracleAccounts
```

The profile is looked up with names derived from the keyring name and database path. The profile contains the data needed by the shim to open the KeePassXC database, such as the master password and optional key file path.

Master-key material is passed internally to `keepassxc-cli` over stdin. It is not returned to Freehold code.

---

## 10. Master-Key Presence Check

Use `keyring_has_keepassxc_master_key` for a read-only existence check:

```freehold
let keyring_has: Result<Boolean, CryptoError> = keyring_has_keepassxc_master_key("freehold-demo")
if keyring_has.ok = false then
    call Std.IO.logf("keyring has-check failed: ${}", String.error_text(keyring_has.error))
    return 1
end if
```

The shim uses a namespaced Windows Credential Manager target:

```text
freehold/keepassxc/<label>
```

The label must be non-empty, must not contain NUL or newline characters, and must not exceed the shim's length limit.

This function reports presence only. It does not return the credential payload.

---

## 11. Wallet Location

`wallet_location` is intended for database-wallet workflows such as Oracle Autonomous Database.

The shim reads it from either:

```text
Wallet_Location custom field
WalletLocation custom field
Wallet_Location=... tag
Wallet_Location:... tag
Wallet Location=... tag
Wallet Location:... tag
```

Freehold receives the normalized location as:

```freehold
oracle_credentials.value.wallet_location
```

Use it as a path input to wallet-aware FFI routines. Do not log full paths if your deployment treats them as sensitive operational metadata.

---

## 12. Oracle Wallet Pattern

The current Oracle demos use KeePassXC to avoid committing database credentials.

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

Build a connection string with the Oracle FFI helper:

```freehold
let wallet_conn_result: Result<String, OracleError> = conn_from_wallet_tns(wallet_path, oracle_credentials.value.username, oracle_credentials.value.password)
if wallet_conn_result.ok = false then
    call Std.IO.logf("Oracle connection URL build from tnsnames.ora failed: ${}", String.error_text(wallet_conn_result.error))
    return 1
end if
```

The password is used to build a connection URL but is not logged.

---

## 13. Environment Variables vs KeyPass

Older demos use environment variables for secrets:

```freehold
let wallet_conn: String = getenv("ORACLE_CLOUD_CONN")
let wallet_path: String = getenv("ORACLE_WALLET_PATH")
```

This is acceptable for local experiments and CI-controlled environments, but for local developer credentials the KeyPass pattern is preferred:

```freehold
let oracle_credentials: Result<KeePassXCCredential, CryptoError> = keepassxc_entry_credential("OracleAccounts", "./OracleAccounts.dbx", "TEST_DEMO")
```

Use environment variables for non-secret paths and configuration when appropriate, for example:

```freehold
let sql_dir: String = getenv("ORACLE_SQL_DIR")
```

Do not commit connection strings containing passwords.

---

## 14. Logging Rules

Safe to log:

```text
operation succeeded
operation failed with non-secret error text
username when the application policy allows it
entry title
whether a keyring record exists
```

Do not log:

```text
password
master password
raw connection URL containing password
full token value
AES key
decrypted secret payload
credential JSON from the keyring
```

Preferred pattern:

```freehold
call Std.IO.logf("Oracle credentials loaded from KeePassXC for username = ${}", oracle_credentials.value.username)
call Std.IO.log("Oracle password loaded for DB connect")
```

Avoid:

```freehold
call Std.IO.logf("password = ${}", oracle_credentials.value.password)
```

---

## 15. Error Handling Pattern

Every KeyPass FFI operation that can fail returns `Result<T, CryptoError>`.

Use this pattern consistently:

```freehold
let credential: Result<KeePassXCCredential, CryptoError> = keepassxc_entry_credential("OracleAccounts", "./OracleAccounts.dbx", "TEST_DEMO")
if credential.ok = false then
    call Std.IO.logf("credential lookup failed: ${}", String.error_text(credential.error))
    return 1
end if
```

Then validate any domain-specific expectations:

```freehold
if credential.value.wallet_location = "" then
    call Std.IO.log("credential has empty Wallet_Location")
    return 1
end if
```

The shim already rejects empty username, password, and wallet location for targeted credential lookup, but application-level checks are still useful at boundaries.

---

## 16. Common Failure Patterns

### 16.1 Missing `keepassxc-cli`

Problem:

```text
keepassxc-cli is not installed or not on PATH
```

Check with:

```freehold
let path: Result<String, CryptoError> = keepassxc_cli_path()
```

### 16.2 Logging Passwords

Invalid pattern:

```freehold
call Std.IO.logf("password = ${}", credential.value.password)
```

Passwords may be used, but they should not be printed.

### 16.3 Not Checking `Result`

Invalid pattern:

```freehold
let credential: Result<KeePassXCCredential, CryptoError> = keepassxc_entry_credential("OracleAccounts", "./OracleAccounts.dbx", "TEST_DEMO")
let password: String = credential.value.password
```

Check `.ok` first.

### 16.4 Empty Lookup Arguments

Invalid:

```freehold
let credential: Result<KeePassXCCredential, CryptoError> = keepassxc_entry_credential("", "", "")
```

`keyring_name`, `db_file_name`, and `title` must be non-empty.

### 16.5 Missing Wallet Location

Problem:

```text
KeePassXC entry exists, but no Wallet_Location field or tag is present
```

The targeted credential lookup returns `error CryptoError` because the Oracle wallet pattern requires this metadata.

### 16.6 Using KeyPass as a Write API

The current Freehold keyring API is read-only. There is no `store`, `update`, or `delete` operation.

### 16.7 Treating List Output as Secret Data

`keepassxc_list_entries` returns a non-secret listing of title, username, and notes. It is not a bulk credential export API.

---

## 17. Practical Checklist

Before committing KeyPass code, check:

- Secrets are not hard-coded in `.fh` source files.
- `keepassxc-cli` availability is checked for workflows that require it.
- KeyPass calls return `Result<T, CryptoError>` and `.ok` is checked.
- Passwords and connection URLs containing passwords are not logged.
- `keyring_name`, `db_file_name`, and `title` are non-empty.
- KeePassXC database files use `.kdbx`; `.dbx` is accepted only as a compatibility spelling.
- `Wallet_Location` is present when an Oracle wallet workflow needs it.
- The Freehold program uses returned credentials only for immediate boundary calls.
- Master-key material is never expected in Freehold code.
- Environment variables are used for non-secret configuration or controlled deployment inputs.
- Read-only semantics are preserved: no code path attempts to store, update, or delete keyring entries.

A good Freehold KeyPass program keeps secret storage outside source code, reads credentials through an explicit checked boundary, and uses secrets only long enough to call the next trusted transport or database layer.
