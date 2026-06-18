# Freehold Specification: Crypto
**Status:** Baseline cryptographic helper FFI, digest/HMAC helpers, secure random bytes, AES-256-GCM, KeePassXC bridge, and secret-handling rules  
**Audience:** Freehold authors, verifier implementers, FFI authors, backend authors, and application developers handling secrets

This document explains Freehold's current Crypto model.

Crypto support is not new core language syntax. It is a standard FFI module backed by a local Go shim and Go's standard cryptographic packages:

```text
Std.Crypto                         Freehold module surface
freehold.local/cryptoshim           native Go FFI shim
Go crypto/sha256, sha512, hmac      digest and MAC primitives
Go crypto/rand                      operating-system secure random source
Go crypto/aes + cipher.GCM          AES-256-GCM authenticated encryption
keepassxc-cli                       external KeePassXC CLI executable
Windows Credential Manager          local KeePass Manager metadata source
Result<T, CryptoError>              checked fallible boundary
```

The design goal is to make cryptographic boundaries explicit and checked, while keeping secret storage and master-key management outside Freehold source code.

---

## 1. Security Model

The baseline Crypto rules are:

- Digest and HMAC helpers are deterministic `String -> String` functions.
- Random bytes, AES-GCM, and KeePassXC operations return `Result<T, CryptoError>`.
- AES-GCM uses authenticated encryption; AAD must match during decryption.
- Raw secret values should not be logged.
- KeePassXC and Windows Credential Manager integration is read-only from Freehold.
- Master keys are never returned to Freehold.
- The current API has no key derivation, password hashing, signature, certificate, or key-store write operation.

This is a boundary API. It gives Freehold programs access to carefully scoped native crypto helpers without turning Freehold into a general cryptographic framework.

---

## 2. Module Surface

The Crypto surface is declared in `Std.Crypto`:

```freehold
module Std.Crypto

/**
@std
@ffi
Native cryptographic helpers backed by Go's standard crypto packages through
freehold.local/cryptoshim.
*/

error CryptoError

type KeePassXCCredential is record
    username: String
    password: String
    wallet_location: String
end record

@ffi("freehold.local/cryptoshim", "SHA256Hex")
function sha256_hex(text: String) returns String
is
end sha256_hex

@ffi("freehold.local/cryptoshim", "SHA512Hex")
function sha512_hex(text: String) returns String
is
end sha512_hex

@ffi("freehold.local/cryptoshim", "HMACSHA256Hex")
function hmac_sha256_hex(key: String, message: String) returns String
is
end hmac_sha256_hex

@ffi("freehold.local/cryptoshim", "RandomHex")
function random_hex(byte_count: Integer) returns Result<String, CryptoError>
is
end random_hex

@ffi("freehold.local/cryptoshim", "AES256GCMEncryptHex")
function aes256_gcm_encrypt_hex(key_hex: String, plaintext: String, aad: String) returns Result<String, CryptoError>
is
end aes256_gcm_encrypt_hex

@ffi("freehold.local/cryptoshim", "AES256GCMDecryptHex")
function aes256_gcm_decrypt_hex(key_hex: String, envelope_hex: String, aad: String) returns Result<String, CryptoError>
is
end aes256_gcm_decrypt_hex

@ffi("freehold.local/cryptoshim", "KeePassXCCLIPath")
function keepassxc_cli_path() returns Result<String, CryptoError>
is
end keepassxc_cli_path

@ffi("freehold.local/cryptoshim", "KeePassXCVersion")
function keepassxc_version() returns Result<String, CryptoError>
is
end keepassxc_version

@ffi("freehold.local/cryptoshim", "KeePassXCGeneratePassword")
function keepassxc_generate_password(length: Integer) returns Result<String, CryptoError>
is
end keepassxc_generate_password

@ffi("freehold.local/cryptoshim", "KeePassXCListEntries")
function keepassxc_list_entries(db_name: String, max_entries: Integer) returns Result<String, CryptoError>
is
end keepassxc_list_entries

@ffi("freehold.local/cryptoshim", "KeePassXCEntryCredential")
function keepassxc_entry_credential(keyring_name: String, db_file_name: String, title: String) returns Result<KeePassXCCredential, CryptoError>
is
end keepassxc_entry_credential

@ffi("freehold.local/cryptoshim", "KeyringHasKeePassXCMasterKey")
function keyring_has_keepassxc_master_key(label: String) returns Result<Boolean, CryptoError>
is
end keyring_has_keepassxc_master_key

end Std.Crypto
```

The KeyPass-specific functions are documented more deeply in `SPECIFICATION-KEYPASS.md`. This document focuses on the full Crypto surface and its common cryptographic rules.

---

## 3. FFI Boundary

The Freehold declarations map to Go functions in `freehold.local/cryptoshim`:

```text
Freehold @ffi declaration
    -> generated Go wrapper
    -> freehold.local/cryptoshim
    -> Go standard library crypto packages / keepassxc-cli / Windows Credential Manager
```

The local shim module is:

```go
module freehold.local/cryptoshim

go 1.22
```

The generated Go project maps the local module with:

```text
freehold.local/cryptoshim
    requires freehold.local/cryptoshim v0.0.0
    replace  freehold.local/cryptoshim => vendor-go/crypto-shim
```

A Go function returning only `string` maps to a direct Freehold `String`. A Go function returning `(value, error)` maps to `Result<T, CryptoError>`.

Use `String.error_text(result.error)` when diagnostic text is needed.

---

## 4. Digest Helpers

`sha256_hex` and `sha512_hex` compute lowercase hex digests over the UTF-8 bytes of the input string:

```freehold
let sha256: String = sha256_hex("freehold")
call Std.IO.logf("sha256(freehold) = ${}", sha256)

let sha512: String = sha512_hex("freehold")
call Std.IO.logf("sha512(freehold) = ${}", sha512)
```

These helpers are deterministic and cannot fail in the current ABI:

```text
sha256_hex(text: String) returns String
sha512_hex(text: String) returns String
```

Use digest helpers for fingerprints, deterministic checks, cache keys, and artifact comparison. Do not treat a plain hash of a password as password storage.

---

## 5. HMAC-SHA256

Use `hmac_sha256_hex` when a keyed message authentication code is needed:

```freehold
let signature: String = hmac_sha256_hex("secret", "freehold")
call Std.IO.logf("hmac-sha256(secret, freehold) = ${}", signature)
```

The Go shim computes:

```text
HMAC-SHA256(key bytes, message bytes)
```

and returns lowercase hex.

The key parameter is ordinary text in the current ABI. Application code is responsible for retrieving and protecting the key appropriately.

Do not use a plain SHA digest as a substitute for HMAC when authenticity is required.

---

## 6. Secure Random Hex

Use `random_hex` for cryptographically secure random bytes encoded as lowercase hex:

```freehold
let token: Result<String, CryptoError> = random_hex(16)
if token.ok = false then
    call Std.IO.logf("random_hex failed: ${}", String.error_text(token.error))
    return 1
end if
call Std.IO.logf("random token hex = ${}", token.value)
```

The argument is a byte count, not a hex-character count:

```text
random_hex(16) -> 16 random bytes -> 32 hex characters
random_hex(32) -> 32 random bytes -> 64 hex characters
```

The shim bounds the request:

```text
0 <= byte_count <= 4096
```

Negative sizes and oversized requests return `error CryptoError`:

```freehold
let bad_random: Result<String, CryptoError> = random_hex(-1)
if bad_random.ok then
    call Std.IO.log("random_hex accepted a negative size")
    return 1
end if
```

Use `random_hex(32)` to generate an AES-256 key for the current AES-GCM API.

---

## 7. AES-256-GCM Hex ABI

AES-GCM uses a hex-oriented ABI:

```freehold
function aes256_gcm_encrypt_hex(key_hex: String, plaintext: String, aad: String) returns Result<String, CryptoError>
function aes256_gcm_decrypt_hex(key_hex: String, envelope_hex: String, aad: String) returns Result<String, CryptoError>
```

`key_hex` must decode to exactly 32 bytes:

```text
32 bytes = 64 lowercase or uppercase hex characters
```

The encrypt function returns one hex envelope:

```text
nonce || ciphertext || tag
```

The nonce is randomly generated by the shim for each encryption call. The caller stores or transmits only the returned envelope.

---

## 8. AES-GCM Encrypt/Decrypt Pattern

Generate a key and encrypt:

```freehold
let aes_key: Result<String, CryptoError> = random_hex(32)
if aes_key.ok = false then
    call Std.IO.logf("AES-256 key generation failed: ${}", String.error_text(aes_key.error))
    return 1
end if

let encrypted: Result<String, CryptoError> = aes256_gcm_encrypt_hex(aes_key.value, "freehold secret payload", "demo-aad")
if encrypted.ok = false then
    call Std.IO.logf("aes256_gcm_encrypt_hex failed: ${}", String.error_text(encrypted.error))
    return 1
end if
```

Decrypt with the same key and same AAD:

```freehold
let decrypted: Result<String, CryptoError> = aes256_gcm_decrypt_hex(aes_key.value, encrypted.value, "demo-aad")
if decrypted.ok = false then
    call Std.IO.logf("aes256_gcm_decrypt_hex failed: ${}", String.error_text(decrypted.error))
    return 1
end if
```

Then validate expected plaintext when the workflow has a known value:

```freehold
if decrypted.value != "freehold secret payload" then
    call Std.IO.log("aes256_gcm_decrypt_hex returned unexpected plaintext")
    return 1
end if
```

---

## 9. Authenticated Data

`aad` means additional authenticated data. It is authenticated but not encrypted.

The same AAD string must be supplied during decryption:

```freehold
let tampered_aad: Result<String, CryptoError> = aes256_gcm_decrypt_hex(aes_key.value, encrypted.value, "wrong-aad")
if tampered_aad.ok then
    call Std.IO.log("aes256_gcm_decrypt_hex accepted wrong AAD")
    return 1
end if
```

Use AAD for context that should be bound to the ciphertext, for example:

```text
record type name
schema version
tenant/account id
purpose string
protocol or message version
```

Do not put secret data in AAD. AAD is normally stored or transmitted alongside the ciphertext.

---

## 10. KeePassXC Availability

Use `keepassxc_cli_path` before workflows that require KeePassXC:

```freehold
let keepassxc_path: Result<String, CryptoError> = keepassxc_cli_path()
if keepassxc_path.ok = false then
    call Std.IO.logf("keepassxc-cli not available, skipping KeePassXC demo: ${}", String.error_text(keepassxc_path.error))
    return 0
end if
```

Use `keepassxc_version` to inspect the installed CLI:

```freehold
let keepassxc_ver: Result<String, CryptoError> = keepassxc_version()
if keepassxc_ver.ok = false then
    call Std.IO.logf("keepassxc-cli version failed: ${}", String.error_text(keepassxc_ver.error))
    return 1
end if
```

Both functions return `Result<String, CryptoError>` because the executable may be missing or fail.

---

## 11. KeePassXC Password Generation

`keepassxc_generate_password` delegates password generation to `keepassxc-cli generate`:

```freehold
let keepassxc_password: Result<String, CryptoError> = keepassxc_generate_password(24)
if keepassxc_password.ok = false then
    call Std.IO.logf("keepassxc password generation failed: ${}", String.error_text(keepassxc_password.error))
    return 1
end if
```

The shim uses lower, upper, numeric, and special character groups and requires every group.

The length is bounded:

```text
8 <= length <= 256
```

Too-short and oversized lengths return `error CryptoError`:

```freehold
let keepassxc_bad_password: Result<String, CryptoError> = keepassxc_generate_password(4)
if keepassxc_bad_password.ok then
    call Std.IO.log("keepassxc accepted a too-short password length")
    return 1
end if
```

Do not log generated passwords outside controlled demos.

---

## 12. KeePassXC Entry Listing

`keepassxc_list_entries` opens a KeePassXC database through `keepassxc-cli` and returns a formatted text table:

```freehold
let keepassxc_entries: Result<String, CryptoError> = keepassxc_list_entries(keepassxc_demo_db, 200)
if keepassxc_entries.ok = false then
    call Std.IO.logf("keepassxc list entries failed: ${}", String.error_text(keepassxc_entries.error))
    return 1
end if
call Std.IO.logf("${}", keepassxc_entries.value)
```

The list output contains:

```text
TITLE (Target Name)
USERNAME
COMMENT / notes
Total entries
```

It does not return passwords or master keys.

`max_entries` behavior:

```text
max_entries <= 0   -> default 500
max_entries > 1000 -> error CryptoError
```

Use `KEEPASSXC_DEMO_DB` or another non-secret configuration source for the database path when listing entries in demos.

---

## 13. Targeted KeePassXC Credential Lookup

The targeted credential API returns a record:

```freehold
type KeePassXCCredential is record
    username: String
    password: String
    wallet_location: String
end record
```

Example:

```freehold
let oracle_demo_credential: Result<KeePassXCCredential, CryptoError> = keepassxc_entry_credential("OracleAccounts", "./OracleAccounts.dbx", "TEST_DEMO")
if oracle_demo_credential.ok = false then
    call Std.IO.logf("OracleAccounts TEST_DEMO credential lookup failed: ${}", String.error_text(oracle_demo_credential.error))
    return 1
end if
```

The arguments must be non-empty:

```text
keyring_name
db_file_name
title
```

The shim accepts the historical `.dbx` spelling and can resolve it to a local `.kdbx` file when present.

The targeted lookup validates that the returned credential has non-empty:

```text
username
password
wallet_location
```

`wallet_location` is read from a KeePassXC `Wallet_Location` custom field or from supported tag/value forms such as:

```text
Wallet_Location=C:\path\to\wallet
Wallet Location: C:\path\to\wallet
```

---

## 14. Windows Credential Manager Checks

`keyring_has_keepassxc_master_key` checks whether namespaced metadata exists in Windows Credential Manager:

```freehold
let keyring_has: Result<Boolean, CryptoError> = keyring_has_keepassxc_master_key("freehold-demo")
if keyring_has.ok = false then
    call Std.IO.logf("keyring has check failed: ${}", String.error_text(keyring_has.error))
    return 1
end if
```

The checked target uses the internal prefix:

```text
freehold/keepassxc/<label>
```

The label must be non-empty, must not contain NUL, carriage return, or newline characters, and must be at most 160 characters.

This API only reports whether metadata exists. It does not return the master key and it does not write anything.

---

## 15. Error Handling Pattern

Every fallible Crypto boundary uses `Result<T, CryptoError>`:

```freehold
let value: Result<String, CryptoError> = random_hex(16)
if value.ok = false then
    call Std.IO.logf("crypto operation failed: ${}", String.error_text(value.error))
    return 1
end if
```

Then use `.value` only after the `.ok` check:

```freehold
call Std.IO.logf("random token hex = ${}", value.value)
```

Apply this pattern to:

```text
random_hex
aes256_gcm_encrypt_hex
aes256_gcm_decrypt_hex
keepassxc_cli_path
keepassxc_version
keepassxc_generate_password
keepassxc_list_entries
keepassxc_entry_credential
keyring_has_keepassxc_master_key
```

Digest and HMAC helpers return plain `String` because the current Go operations cannot fail through the exposed ABI.

---

## 16. Secret Handling

Do not log:

```text
AES keys
HMAC keys
passwords
generated passwords outside controlled demos
raw KeePassXC credential records
full Oracle connection URLs containing passwords
decrypted secret payloads
master-key material
long-lived bearer tokens
```

Safer logging patterns:

```freehold
call Std.IO.log("AES key generated")
call Std.IO.log("encrypted payload created")
call Std.IO.logf("OracleAccounts TEST_DEMO username = ${}", oracle_demo_credential.value.username)
call Std.IO.log("OracleAccounts TEST_DEMO password and wallet location loaded for DB connect")
```

Avoid:

```freehold
call Std.IO.logf("aes key = ${}", aes_key.value)
call Std.IO.logf("password = ${}", oracle_demo_credential.value.password)
call Std.IO.logf("plaintext = ${}", decrypted.value)
```

The demo prints some generated values to demonstrate behavior. Production-style code should be stricter.

---

## 17. Common Failure Patterns

### 17.1 Treating Byte Count as Hex Length

Problem:

```freehold
let key: Result<String, CryptoError> = random_hex(64)
```

This generates 64 bytes, not a 64-character key. For AES-256-GCM, use `random_hex(32)`.

### 17.2 Invalid AES Key Length

Problem:

```text
key_hex decodes to something other than 32 bytes
```

The AES functions return `error CryptoError`.

### 17.3 Wrong AAD During Decryption

Problem:

```freehold
let plain: Result<String, CryptoError> = aes256_gcm_decrypt_hex(key, envelope, "different-aad")
```

AES-GCM authentication fails when AAD does not match.

### 17.4 Reusing Digests for Authentication

Invalid pattern:

```freehold
let signature: String = sha256_hex(message)
```

Use HMAC when a secret key must authenticate a message.

### 17.5 Not Checking Result

Invalid pattern:

```freehold
let token: Result<String, CryptoError> = random_hex(16)
call Std.IO.log(token.value)
```

Check `.ok` first.

### 17.6 Logging Secrets

Invalid pattern:

```freehold
call Std.IO.logf("generated password = ${}", keepassxc_password.value)
```

This may be acceptable in a controlled demo, but not in application logs.

### 17.7 Expecting Keyring Writes

The current Freehold Crypto/KeyPass surface is read-only for OS keyring and KeePassXC integration. There is no API to store, update, or delete entries.

### 17.8 Missing KeePassXC CLI

Problem:

```text
keepassxc-cli is not installed or not on PATH
```

Check with `keepassxc_cli_path` before KeePassXC-dependent workflows.

---

## 18. Practical Checklist

Before committing Crypto code, check:

- `Std.Crypto` imports expose only the functions the module needs.
- Every `Result<_, CryptoError>` is checked before `.value` is used.
- `random_hex` byte counts are intentional and within `0..4096`.
- AES-256-GCM keys come from `random_hex(32)` or another trusted 32-byte source.
- AES-GCM decryption uses the same AAD that encryption used.
- AAD is non-secret context, not hidden data.
- HMAC is used for keyed authenticity; plain SHA is not used as a signature.
- Passwords, AES keys, HMAC keys, decrypted payloads, and connection URLs are not logged.
- KeePassXC workflows check `keepassxc-cli` availability when appropriate.
- KeePassXC password generation uses lengths in `8..256`.
- KeePassXC list output is treated as metadata, not as credential export.
- Targeted credential lookup validates the expected entry title and metadata.
- OS keyring and KeePassXC integration remain read-only from Freehold.

A good Freehold Crypto program keeps secrets out of source code, checks every fallible native boundary, uses AES-GCM with explicit context, and logs only enough metadata to diagnose the workflow without exposing secret material.
