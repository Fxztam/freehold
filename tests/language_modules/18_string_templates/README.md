# 18_string_templates

String templates use `${}` placeholders in ordinary String values.

First stage:

```text
String.template("id=${}", id) -> String
Std.IO.logf("id=${}", id) -> output
```

Rules:

```text
`${}` and `${ }` are positional placeholders.
`${name}` placeholders bind named values.
Each placeholder requires exactly one following value.
Template values may be String, Integer, Boolean, or Double.
The first template argument may be a String literal or a runtime String expression.
The old `{}` placeholder form is rejected.
```
