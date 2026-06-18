# Freehold Test Generation Task

Read:

- All the SPECIFICATIONS

Task:

Generate a first Freehold module test package.

Requirements:

Create:

1. Module demonstrations
2. Positive tests
3. Negative tests

Do not invent syntax.

Use only documented module syntax.

Every generated file must contain:

- Purpose
- Referenced specification section
- Expected result

---

Generate

## Demonstrations

module_demo_01.fh
module_demo_02.fh
module_demo_03.fh
..

---

## Positive Tests

module_positive_01.fh
module_positive_02.fh
module_positive_03.fh
module_positive_04.fh
module_positive_05.fh

Expected:

Parser Success
Verifier Success
Runtime Success

---

## Negative Tests

module_negative_01.fh
module_negative_02.fh
module_negative_03.fh
module_negative_04.fh
module_negative_05.fh

Possible failure categories:

- Missing module name
- Wrong end label
- Duplicate module declaration
- Invalid import
- Invalid module structure

Expected:

Parser Failure
or
Verifier Failure

---

Output Format

For each generated file provide:

Filename:
Purpose:
Referenced Specification:
Expected Result:
Source Code:

Summary

Test Demos with positive / negative Tests and expected outputs for

Modules
Procedures
Functions
Records
Contracts

---

## Generated Test Directory Layout

Each test module (e.g. `01_Module`) follows this folder convention:

```
Test/01_Module/
├── module_demo_01.fh          # Demonstrations – valid, illustrative examples
├── module_demo_02.fh
├── module_demo_03.fh
├── valid/                     # Positive tests – must pass parser, verifier, and runtime
│   ├── module_positive_01.fh
│   ├── module_positive_02.fh
│   ├── module_positive_03.fh
│   ├── module_positive_04.fh
│   └── module_positive_05.fh
├── invalid/                   # Negative tests – must trigger a parser or verifier failure
│   ├── module_negative_01.fh
│   ├── module_negative_02.fh
│   ├── module_negative_03.fh
│   ├── module_negative_04.fh
│   └── module_negative_05.fh
├── expected_positive_outputs/ # Expected success snapshots for demos and positive tests
│   ├── module_demo_01.expected
│   ├── module_demo_02.expected
│   ├── module_demo_03.expected
│   ├── module_positive_01.expected
│   ├── module_positive_02.expected
│   ├── module_positive_03.expected
│   ├── module_positive_04.expected
│   └── module_positive_05.expected
└── expected_negative_errors/  # Expected failure snapshots for negative tests
    ├── module_negative_01.expected
    ├── module_negative_02.expected
    ├── module_negative_03.expected
    ├── module_negative_04.expected
    └── module_negative_05.expected
```

- **Demos** live at the top level of the module folder and show idiomatic usage.
- **`valid/`** holds positive tests; every `.expected` file records `parser_result: success`, `verifier_result: success`, and where applicable `runtime_result: success`.
- **`invalid/`** holds negative tests; every `.expected` file records the failing phase (`parser` or `verifier`), the `failure_category`, and an `error_hint`.
- **`expected_positive_outputs/`** and **`expected_negative_errors/`** are the reference snapshots consumed by the test runner to assert compiler behaviour.
If
While
Arrays
Strings
Result
