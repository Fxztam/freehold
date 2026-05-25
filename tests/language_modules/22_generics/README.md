# 22_generics

This module covers parser and verifier support for generic records, generic routines, generic instantiation, and generic arity diagnostics.

Go codegen V1 policy:

```text
frontend-valid generic records and routines are intentionally unsupported by Go codegen V1
the expected codegen diagnostic is FH-GOCODEGEN-0001
invalid generic fixtures are also run through the Go codegen entry point
the expected outcome for invalid fixtures is the same semantic diagnostic before any Go output is accepted
```
