# Done: Go Compiler

Stand: 2026-05-24

## Feature-Matrix-Slice

Commit: `a7fa3d2 Add Go codegen feature matrix`

Umgesetzt:

- Neue Go-Codegen-Feature-Matrix: `tests/language_modules/go_codegen_feature_matrix.json`
- Neuer Validator: `tools/verify_go_feature_matrix.py`
- Neuer Wrapper: `verify-go-feature-matrix.cmd`
- Offizieller Gate erweitert: `verify-parser-conformance.cmd` laeuft jetzt mit `[7/14] Verify Go feature matrix`.

Matrix-Stand:

- `24/24` Language-Module abgedeckt
- `supported`: 13
- `rejected`: 3
- `deferred`: 8

Verifiziert:

- `verify-go-feature-matrix.cmd`: gruen
- `py_compile` fuer den Validator: gruen
- `git diff --check`: gruen
- `verify-parser-conformance.cmd`: passed
- Go-Codegen-Artefakte: `49/49`
- Parser-Status: `319/319`
- AST Shape: `274/274`
- Semantic AST: `274/274`
- Arbeitsbaum nach Commit: sauber

## Cross-Module-Call-Semantik-Slice

Commit: `bc112a4 Add cross-module routine call semantics`

Umgesetzt:

- Import-aware Verifikation fuer Freehold-Modulgraphen in `freehold/core/module_resolver.py`.
- `freehold/core/verifier.py` loest importierte Routinen ueber `exposing` unqualifiziert auf, z.B. `balance_never_negative()`.
- `freehold/core/verifier.py` loest importierte Routinen auch qualifiziert ueber Modulnamen auf, z.B. `Banking.Proofs.balance_never_negative()`.
- Lokale Routinen behalten Vorrang vor exposed Importen.
- Go-Codegen nutzt die bestehende Package-Import-Mechanik und erzeugt fuer importierte Freehold-Routinen Aufrufe wie `banking_proofs.BalanceNeverNegative()`.
- `03_import_resolution` deckt jetzt exposed und qualifizierte Cross-Module-Routine-Calls inklusive Projekt-Codegen-Goldens ab.
- Go-Codegen-Feature-Matrix und Statusdokumente sind nachgezogen; Cross-Module-Calls sind nicht mehr deferred.

Verifiziert:

- `python -m py_compile` fuer Verifier/Resolver/Go-Codegen: gruen
- `python -m freehold test-language --module 03_import_resolution`: `12/12`
- `python -m freehold test-language --module 15_qualified_names_calls`: `15/15`
- Temporaere `go-codegen-project` Builds fuer exposed und qualifizierten Cross-Module-Call: gruen
- `generate-go-codegen-artifacts.cmd`: `51/51`
- `verify-go-feature-matrix.cmd`: gruen, `24/24` Matrix-Eintraege
- `verify-parser-conformance.cmd`: passed
- Arbeitsbaum nach Commit: nur `DONE-COMPILER.md` ungetrackt

Naechster Block laut aktualisierter Liste:

- BigNumber-/Runtime-Builtins oder weitere V1-Codegen-Luecken priorisieren.
- Danach Record-/Result-/Abort-Interaktionen ueber Modulgrenzen haerten.