# 04_types

Local type declaration and type reference diagnostics live here.

This section starts after module/import resolution. It covers scalar type aliases,
ranged scalar types, aliases used in Array, Record, Result, and routine return
positions, duplicate type names, built-in type redefinition, and unknown type
references in routine signatures or local declarations.

Initial diagnostics:

```text
VF-N001 duplicate top-level declaration name
VF-N002 reserved keyword cannot be used as name
VF-T001 duplicate type declaration
VF-T002 built-in type cannot be redefined
VF-T003 unknown type reference
VF-T004 invalid range bounds
VF-T005 range requires numeric base type
VF-T006 integer range bounds must be integers
```

Expression-level assignment errors live in later type-focused sections.