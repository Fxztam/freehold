from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any

@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    line: int
    column: int
    found: str
    expected: str
    hint: str
    phase: str = "syntax"

    def format(self) -> str:
        return (
            f"{self.code}: {self.message}\n"
            f"Phase: {self.phase}\n"
            f"Location: line {self.line}, column {self.column}\n"
            f"Found: {self.found}\n"
            f"Expected: {self.expected}\n"
            f"Hint:\n{self.hint.rstrip()}"
        )

CORE_MODULE_HINT = """A Freehold file must include a module name and end with the same name.

Example:
    module Hello

    procedure main()
    is
        check true
    end main

    end Hello
"""

MODULE_END_HINT = """Every module must end with its qualified module name.

Example:
    module Demo
    ...
    end Demo
"""

MODULE_END_NAME_HINT = """The module end declaration must repeat the exact module name.

Example:
    module MissingEnd
    ...
    end MissingEnd
"""

COMMENT_NESTED_HINT = """Block comments cannot be nested.

Close the first block comment before starting another one, or use line comments inside the block text.
"""

COMMENT_UNTERMINATED_HINT = """A block comment must end with `*/`.

Add the closing marker before the next Freehold declaration or before the end of the file.
"""

IMPORT_SELF_HINT = """A module cannot import itself.

Example:
    module App.Main
    import Banking.Proofs
    end App.Main
"""

IMPORT_DUPLICATE_HINT = """Each imported module may appear only once.

Example:
    import Banking.Types
    import Banking.Proofs
"""

IMPORT_DUPLICATE_EXPOSING_HINT = """Each exposed symbol may appear only once in an import exposing list.

Example:
    import Banking.Proofs exposing balance_never_negative, transfer_preserves_total
"""

IMPORT_AMBIGUOUS_EXPOSING_HINT = """A symbol exposed into the local namespace must come from exactly one imported module.

Use qualified imports when two modules intentionally export the same name.

Example:
    import Domestic.Orders
    import Partner.Orders
    call Domestic.Orders.load_order(1)
"""

IMPORT_NAME_HINT = """An import declaration must name the module to import.

Example:
    import Banking.Proofs
"""

IMPORT_EXPOSING_HINT = """An exposing clause must list at least one symbol.

Example:
    import Banking.Proofs exposing balance_never_negative
"""

MODULE_NOT_FOUND_HINT = """The imported module must exist under the module search root.

Example path:
    Banking.Proofs -> Banking/Proofs.fh
"""

IMPORTED_MODULE_NAME_HINT = """The imported file must declare the module name used by the import.

Example:
    import Banking.Proofs

The imported file should start with:
    module Banking.Proofs
"""

IMPORTED_MODULE_SYNTAX_HINT = """The imported module must parse before it can be used.

Open the imported `.fh` file and fix the syntax error there first.
"""

EXPOSED_SYMBOL_HINT = """Every symbol listed in an exposing clause must be declared by the imported module.

Example:
    import Banking.Proofs exposing balance_never_negative
"""

CYCLIC_IMPORT_HINT = """Imports must not form a cycle.

Move shared definitions into a third module and import that module from both sides.
"""

TYPE_DUPLICATE_HINT = """Each type name may be declared only once in a module.

Use a new name or remove the duplicate declaration.
"""

DECLARATION_DUPLICATE_HINT = """Each top-level declaration name may be used only once in a module.

Top-level declarations include types, records, errors, functions, and procedures.
"""

RESERVED_NAME_HINT = """Reserved Freehold words cannot be used as user-defined names.

Examples of reserved words:
    module, import, type, record, function, procedure, let, return, if, while
"""

TYPE_BUILTIN_HINT = """Built-in Freehold types cannot be redefined.

Built-in types:
    Integer, Boolean, Double, String
"""

TYPE_UNKNOWN_HINT = """A type reference must name a built-in type or a type declared earlier in the module.

Example:
    type Money is Integer range 0..1000000

    function balance() returns Money
    is
        return 0
    end balance
"""

TYPE_RANGE_BOUNDS_HINT = """A range lower bound must be less than or equal to its upper bound.

Example:
    type Percent is Integer range 0..100
"""

TYPE_RANGE_NUMERIC_HINT = """Only Integer and Double based types may declare ranges.

Examples:
    type Percent is Integer range 0..100
    type Temperature is Double range -273.15..10000.0
"""

TYPE_INTEGER_RANGE_HINT = """Integer ranges must use integer bounds.

Example:
    type Count is Integer range 0..100
"""

TYPE_VALUE_OUT_OF_RANGE_HINT = """A constant value assigned to a range subtype must lie within the declared bounds.

Example:
    type Percent is Integer range 0..100
    let x: Percent = 50 -- OK
    let y: Percent = 150 -- Error: 150 out of range
"""

FORMAL_VERIFICATION_HINT = """The SMT solver could not prove that the verification condition holds under the given preconditions and path conditions.

To satisfy the verifier:
- Add requires clauses to restrict inputs
- Add loop invariants to carry properties
- Check for overflow or potential violations
"""

GENERIC_DUPLICATE_PARAM_HINT = """A generic declaration may list each type parameter only once.

Example:
    type Box<T> is record
        value: T
    end record
"""

GENERIC_MISSING_ARGUMENT_HINT = """A generic type must be used with the number of type arguments declared by its template.

Example:
    type Box<T> is record
        value: T
    end record

    let value: Box<Integer> = Box<Integer> { value: 1 }
"""

GENERIC_TOO_MANY_ARGUMENTS_HINT = """A generic type instantiation must provide exactly the declared number of type arguments.

Check the generic declaration and remove or add type arguments as needed.
"""

GENERIC_NON_GENERIC_ARGUMENTS_HINT = """Only generic type declarations may be used with type arguments.

Example:
    Box<Integer> is valid only if Box was declared with a type parameter such as Box<T>.
"""

GENERIC_ROUTINE_MISSING_ARGUMENT_HINT = """A generic function call must provide the number of type arguments declared by the function.

Example:
    function identity<T>(x: T) returns T
    is
        return x
    end identity

    let item: Integer = identity<Integer>(1)
"""

GENERIC_ROUTINE_ARITY_HINT = """A generic function call must provide exactly the declared number of type arguments.

Check the function declaration and add or remove type arguments as needed.
"""

GENERIC_NON_GENERIC_ROUTINE_HINT = """Only generic functions may be called with type arguments.

Remove the type argument list or add type parameters to the function declaration.
"""

RECORD_DUPLICATE_FIELD_HINT = """A record type may declare each field name only once.

Example:
    type Account is record
        id: Integer
        active: Boolean
    end record
"""

RECORD_UNKNOWN_TYPE_HINT = """A record literal must use a declared record type.

Declare the record type before constructing a record literal.
"""

RECORD_UNKNOWN_FIELD_HINT = """A record literal or field access may only use fields declared by the record type.

Check the record type declaration for the available field names.
"""

RECORD_MISSING_FIELD_HINT = """A record literal must provide every field declared by the record type.

Example:
    Account { id: 1, active: true }
"""

RECORD_DUPLICATE_LITERAL_FIELD_HINT = """A record literal may assign each field only once.

Remove the duplicate field initializer.
"""

RECORD_FIELD_ACCESS_HINT = """Field access requires the value before the dot to be a record.

Example:
    account.id
"""

RECORD_UNKNOWN_VARIABLE_HINT = """A field path must start with a known local record variable.

Declare the variable before reading or assigning its fields.
"""

ARRAY_SCALAR_LITERAL_HINT = """Array literals may contain scalar values only.

Nested array literals are not supported by the current Array type.
"""

ARRAY_MIXED_TYPES_HINT = """All values in an array literal must have the same base type.

Example:
    [1, 2, 3]
"""

ARRAY_LENGTH_HINT = """An array literal must match the fixed size declared by its Array type.

Example:
    let xs: Array<Integer, 3> = [1, 2, 3]
"""

ARRAY_ELEMENT_TYPE_HINT = """Array literal elements must match the declared element type.

Example:
    let xs: Array<Integer, 3> = [1, 2, 3]
"""

ARRAY_UNKNOWN_HINT = """Array indexing must start with a known local array variable.

Declare the array before reading from it.
"""

ARRAY_INDEX_TARGET_HINT = """Index access requires an Array value before the brackets.

Example:
    xs[0]
"""

ARRAY_INDEX_TYPE_HINT = """Array indexes must be Integer expressions.

Example:
    xs[0]
"""

ARRAY_BOUNDS_HINT = """Static array indexes must be within the fixed array bounds.

For Array<T, 3>, valid indexes are 0, 1, and 2.
"""

ROUTINE_END_NAME_HINT = """A routine must end with the same name used in its declaration.

Example:
    function total() returns Integer
    is
        return 0
    end total
"""

ROUTINE_DUPLICATE_PARAM_HINT = """Each routine parameter name may appear only once in the parameter list.

Use distinct names for every parameter.
"""

ROUTINE_MISSING_RETURN_HINT = """Every function must guarantee a return statement.

Add a return statement on all paths through the function body.
"""

ROUTINE_PROCEDURE_RETURN_HINT = """Procedures do not return values.

Use a function when a routine needs to produce a value.
"""

ROUTINE_UNKNOWN_HINT = """A call must name a declared routine.

Declare the function or procedure before calling it.
"""

ROUTINE_CALL_KIND_HINT = """The `call` statement can only invoke procedures.

Use a function call expression when reading a function result.
"""

ROUTINE_FUNCTION_CALL_KIND_HINT = """A routine used in an expression must be a function.

Use a `call` statement for procedures, or change the routine to return a value.
"""

ROUTINE_ARGUMENT_COUNT_HINT = """A routine call must pass exactly the parameters declared by the routine.

Check the routine declaration and update the argument list.
"""

ROUTINE_ARGUMENT_TYPE_HINT = """Routine arguments must match the declared parameter types.

Check the parameter declaration for the expected type.
"""

ROUTINE_RETURN_TYPE_HINT = """A function return expression must match the declared return type.

Check the function's `returns` clause and the returned expression.
"""

STRING_ARGUMENT_COUNT_HINT = """A String built-in call must pass exactly the arguments required by that function.

Examples:
    String.concat(left, right)
    String.substr(text, start, length)
    String.replace(text, old, new)
    String.instr(text, needle)
"""

STRING_ARGUMENT_TYPE_HINT = """String built-in arguments must match the expected type for their position.

Check the String function signature and pass String or Integer values as required.
"""

TEMPLATE_ARGUMENT_COUNT_HINT = """A string template must provide exactly one value for each placeholder.

Examples:
    String.template("id=${}", id)
    String.template("id=${id}", id: id)
    Std.IO.logf("id=${}, active=${}", id, active)
"""

TEMPLATE_PLACEHOLDER_HINT = """Freehold string templates use `${}` or `${name}` placeholders.

Use `${}` for positional values or `${name}` with named bindings. The older `{}` form is intentionally not accepted.
"""

TEMPLATE_BINDING_HINT = """Named string templates require exact bindings.

Every `${name}` placeholder must have a matching `name: value` binding, every binding must be used, and each binding name may appear only once.

Example:
    String.template("name=${name}", name: user_name)
"""

TEMPLATE_VALUE_TYPE_HINT = """String template values must be scalar display values.

Supported value types:
    String, Integer, Boolean, Double
"""

MATH_ARGUMENT_COUNT_HINT = """A Math built-in call must pass exactly the arguments required by that function.

Examples:
    Math.sin(value)
    Math.sqrt(value)
    Math.pow(base, exponent)
    Math.min(left, right)
"""

MATH_ARGUMENT_TYPE_HINT = """Math built-in arguments must be numeric expressions.

Pass Integer or Double values to Math functions.
"""

BIG_ARGUMENT_COUNT_HINT = """A Big built-in call must pass exactly the arguments required by that function.

Examples:
    Big.int(text)
    Big.addInt(left, right)
    Big.float(text, precisionBits)
    Big.format(value, digits)
"""

BIG_ARGUMENT_TYPE_HINT = """Big built-in arguments must match the exact arbitrary-precision type expected by the operation.

Use BigInteger values for Big.*Int operations and BigFloat values for Big.*Float operations.
Convert explicitly with Big.fromInteger or Big.floatFromInteger.
"""

JSON_ARGUMENT_COUNT_HINT = """Json.stringify accepts exactly one value.

Example:
    let text: String = Json.stringify(person)
"""

JSON_PARSE_ARGUMENT_COUNT_HINT = """Json.parse accepts exactly one JSON text value.

Example:
    let parsed: Result<Person, SchemaError> = Json.parse<Person>(text)
"""

JSON_PARSE_TYPE_ARGUMENT_HINT = """Json.parse is a generic JSON-to-record builtin.

Pass exactly one record type argument and one String value.

Example:
    Json.parse<Person>(text)
"""

JSON_PARSE_TARGET_TYPE_HINT = """Json.parse V2 decodes JSON into a Freehold record type.

Records are the canonical schema source. Use a record type as the type argument.
"""

JSON_FIELD_NAME_HINT = """@json field names define the external JSON object key for a Freehold record field.

Use a non-empty string literal, and make every external JSON field name unique within the record.
Record constructors still use the Freehold field name.
"""

JSON_PARSE_LITERAL_SCHEMA_HINT = """Json.parse<Record>(...) validates literal JSON text at compile time.

For string literals, the JSON object must match the target Freehold record schema exactly:
all required fields present, no unknown fields, and matching JSON-compatible field types.
Use a dynamic String value when invalid input should be handled only as a runtime Result failure.
"""

JSON_ARGUMENT_TYPE_HINT = """Json.stringify V1 accepts a record value as its top-level argument.

Construct a record with TypeName { field: value } and pass that record value.
"""

JSON_SERIALIZABLE_TYPE_HINT = """Json.stringify V1 serializes record fields whose values are JSON-compatible Freehold values.

Supported field value types:
    String, Integer, Boolean, Double, records, and arrays of supported values

Convert BigInteger, BigFloat, Result, and other unsupported values explicitly before serializing.
"""

GRPC_PROTO_DUPLICATE_HINT = """Each gRPC/protobuf field id must be unique inside one record.

Use stable positive numbers and never reuse a number for a different field.
"""

GRPC_PROTO_INVALID_HINT = """A protobuf field id must be a positive integer.

Use `proto 1`, `proto 2`, and so on for fields that are used in gRPC messages.
"""

GRPC_PROTO_MISSING_HINT = """Records used as gRPC request or response messages must assign stable proto ids to every field.

Example:
    id: String proto 1
"""

GRPC_RPC_TYPE_HINT = """Unary gRPC V1 rpc request and response types must name declared record messages.

Declare the record before the service and use that record type in the rpc signature.
"""

GRPC_RPC_DUPLICATE_HINT = """Each rpc name may appear only once inside a service.

Rename the duplicate rpc or merge the declarations.
"""

GRPC_PROTO_UNSUPPORTED_TYPE_HINT = """gRPC/protobuf message fields must use protobuf-compatible Freehold types.

Supported V1 field value types:
    String, Integer, Boolean, Double, records, and arrays of supported values

Convert or wrap BigInteger, BigFloat, Result, and other unsupported values before exposing them through gRPC.
"""

STATEMENT_UNKNOWN_ASSIGNMENT_HINT = """Assignment requires an existing local variable.

Declare the variable with `let` before assigning to it.
"""

STATEMENT_ASSIGNMENT_TYPE_HINT = """The expression on the right side of an assignment must match the target type.

Check the target declaration and the assigned expression.
"""

STATEMENT_BOOLEAN_HINT = """This statement position requires a Boolean expression.

Use a comparison or Boolean expression such as `amount > 0` or `ready = true`.
"""

STATEMENT_WHILE_VARIANT_HINT = """A while variant must be an Integer expression.

Variants are used as numeric progress measures for loop termination reasoning.
"""

STATEMENT_CASE_TYPE_HINT = """Each case branch value must have the same base type as the case expression.

Use branch values that match the expression after `case`.
"""

STATEMENT_CASE_DUPLICATE_HINT = """Each literal case branch value may appear only once.

Remove the duplicate branch or merge its body into the first branch.
"""

STATEMENT_LET_OPERATOR_HINT = """A `let` statement declares a new local variable and uses `=`.

Use `:=` only when assigning to an existing variable.

Examples:
    let amount: Integer = 1
    amount := 2
"""

STATEMENT_WHILE_INVARIANT_SYNTAX_HINT = """Every `while` loop must declare at least one invariant before `do`.

Example:
    while amount > 0
        invariant amount >= 0
    do
        amount := amount - 1
    end while
"""

STATEMENT_CASE_DEFAULT_SYNTAX_HINT = """Every `case` statement must include a `default` branch before `end case`.

Example:
    case choice is
        when 1 =>
            check true
        default =>
            check false = false
    end case
"""

CONTRACT_BOOLEAN_HINT = """Contract clauses must be Boolean expressions.

Use a comparison or Boolean expression after `requires` or `ensures`.
"""

CONTRACT_RESULT_CONTEXT_HINT = """Result contract expressions are only available in `ensures` clauses of Result-returning functions.

Use `success`, `failure`, `value`, or `error` only when the function returns `Result<T, E>`.
"""

ABORT_UNKNOWN_HINT = """An abort path must name an error declared in the module.

Declare the error before using it in an `aborts` clause or `abort` statement.
"""

ABORT_NOT_DECLARED_HINT = """An `abort ErrorName` statement must be declared by the enclosing routine.

Add a matching `aborts ErrorName` clause to the routine contract.
"""

ABORT_DUPLICATE_HINT = """Each routine may declare a given abort error at most once.

Use one `aborts ErrorName` clause per controlled abort path.
"""

ABORT_PROPAGATION_HINT = """A call to an aborting routine must keep the abort visible.

Add a matching `aborts ErrorName` clause to the caller, or handle the abort once handler syntax exists.
"""

ABORT_CONDITION_COVERAGE_HINT = """A conditional abort contract only covers abort sites reached under the same condition.

Move the `abort ErrorName` under a matching `if` guard, change the `aborts ErrorName when ...` condition, or remove the condition if every path may abort with that error.
"""

ABORT_MAIN_REQUIRES_HINT = """`main` has no ordinary Freehold caller, so `requires` cannot express a call-site obligation there.

Use an explicit top-level `aborts ErrorName when condition` path, or introduce a future environment-assumption construct instead of `requires`.
"""

ABORT_UNREACHABLE_HINT = """Statements after a guaranteed exit cannot execute.

Remove the unreachable statement or move it before the `return`/`abort` path. This check is intentionally simple: a previous `return`, `abort`, or branch shape that exits on all paths ends the current block.
"""

EXPRESSION_UNKNOWN_VARIABLE_HINT = """An expression may only reference variables that are in scope.

Declare the variable with `let` or as a routine parameter before using it.
"""

EXPRESSION_COMPARE_HINT = """Equality comparisons require both sides to have the same base type.

Compare values of matching types, or convert the value before comparing it.
"""

EXPRESSION_BOOLEAN_OPERATOR_HINT = """Boolean operators require Boolean operands on both sides.

Use comparisons to produce Boolean values before combining them with `and` or `or`.
"""

EXPRESSION_COMPARISON_OPERATOR_HINT = """Ordering comparisons require numeric operands.

Use `<`, `<=`, `>`, and `>=` with Integer or Double expressions.
"""

EXPRESSION_ARITHMETIC_HINT = """Arithmetic operators require numeric operands.

Use Integer or Double expressions with `+`, `-`, `*`, and `/`.
"""

EXPRESSION_UNARY_NOT_HINT = """The unary `not` operator requires a Boolean operand.

Example:
    not ready
"""

EXPRESSION_UNARY_NEGATIVE_HINT = """The unary `-` operator requires a numeric operand.

Example:
    -amount
"""

ASYNC_AWAIT_CONTEXT_HINT = """`await` may only be used inside an async routine.

Example:
    async function load() returns Integer
    is
        return await fetch()
    end load
"""

ASYNC_AWAITABLE_HINT = """`await` requires an awaitable expression.

In V1a, async function calls are awaitable:
    let item: Integer = await fetch()

Do not use `await` on plain scalar values or synchronous function calls.
"""

CHANNEL_ARGUMENT_COUNT_HINT = """A Channel built-in call must pass exactly the arguments required by that function.

Examples:
    channel<Integer>(capacity)
    channel_sender<Integer>(channel)
    channel_receiver<Integer>(channel)
    channel_send<Integer>(sender, value)
    channel_receive<Integer>(receiver)
"""

CHANNEL_ARGUMENT_TYPE_HINT = """Channel built-in arguments must match the channel element type.

Use Sender<T> with values of T, Receiver<T> for receive, and Channel<T> when splitting endpoints.
"""

SCOPE_HANDLE_ESCAPE_HINT = """A JoinHandle spawned inside a Scope is local to that Scope.

Join the handle inside the Scope before returning, storing it somewhere longer-lived, or passing it outside the scope boundary.
"""

SCOPE_HANDLE_JOIN_HINT = """Every JoinHandle spawned inside a Scope must be joined before leaving that Scope.

Use scope_join<T>(scope, handle) and await the result before returning from the routine or ending the scope block.
"""

ERROR_UNKNOWN_RESULT_TYPE_HINT = """The error type in `Result<T, E>` must name a declared error.

Declare the error before using it in a Result type.

Example:
    error NotFound
    function load() returns Result<Integer, NotFound>
"""

ERROR_UNKNOWN_RETURN_HINT = """A `return error` statement must return a declared error.

Declare the error before returning it.
"""

ERROR_WRONG_RETURN_HINT = """A Result function may only return the error declared in its `Result<T, E>` type.

Return the declared error type or change the function's Result type.
"""

ERROR_RESULT_RETURN_FORM_HINT = """A Result function must return either `ok <expr>` or `error <Name>`.

Plain return expressions are only valid for non-Result functions.
"""

ERROR_PLAIN_RETURN_FORM_HINT = """A non-Result function must return a plain expression.

Use `returns Result<T, E>` when the function should return `ok` or `error`.
"""

ERROR_OK_TYPE_HINT = """A Result `ok` return value must match the Result's success type.

Check the first type argument in `Result<T, E>` and the expression after `ok`.
"""

ERROR_NESTED_RESULT_HINT = """Nested Result payloads are forbidden in V1.

Use a non-Result success value such as Integer, a record, or Array<T, N>, and keep the error side as a declared error.
"""

def _token_value(token: Any) -> str:
    if token is None:
        return "EOF"
    value = getattr(token, "value", None)
    if value is not None:
        return repr(str(value))
    return repr(str(token))

def _line(exc: Exception) -> int:
    return int(getattr(exc, "line", 1) or 1)

def _column(exc: Exception) -> int:
    return int(getattr(exc, "column", 1) or 1)

def _expected(exc: Exception) -> set[str]:
    expected = getattr(exc, "expected", None)
    if expected is None:
        return set()
    try:
        return set(str(x) for x in expected)
    except TypeError:
        return {str(expected)}

def _source_position_from_message(message: str) -> tuple[int, int]:
    match = re.search(r"line (\d+):(\d+):", message)
    if not match:
        return 1, 1
    return int(match.group(1)), int(match.group(2))

def _line_ending_with(source: str, pattern: str) -> tuple[int, int] | None:
    regex = re.compile(pattern)
    for line_number, text in enumerate(source.splitlines(), start=1):
        match = regex.match(text.strip())
        if match:
            return line_number, len(text.rstrip()) + 1
    return None

def diagnose_parse_error(source: str, exc: Exception) -> Diagnostic:
    stripped = source.strip()
    expected = _expected(exc)
    line = _line(exc)
    column = _column(exc)
    found = _token_value(getattr(exc, "token", None))

    if not stripped:
        return Diagnostic("VF-C001", "expected module declaration", 1, 1, "end of file", '"module"', CORE_MODULE_HINT)

    # Strip comments and whitespace from start to find the first real code block
    import re
    code_only = source
    while True:
        prev_len = len(code_only)
        code_only = code_only.lstrip()
        if code_only.startswith("--"):
            code_only = re.sub(r"^--[^\n]*\n?", "", code_only)
        elif code_only.startswith("/*"):
            end_idx = code_only.find("*/")
            if end_idx != -1:
                code_only = code_only[end_idx+2:]
        if len(code_only) == prev_len:
            break

    stripped_code = code_only.strip()
    first_word = stripped_code.split(maxsplit=1)[0] if stripped_code else ""
    if not stripped_code.startswith("module"):
        return Diagnostic("VF-C002", "unexpected top-level input; expected module declaration", line, column, repr(first_word), '"module"', CORE_MODULE_HINT)

    if stripped == "module":
        return Diagnostic("VF-C003", "expected module name after 'module'", 1, 7, "EOF", "module name",
                          "Write a qualified module name after the module keyword.\n\nExample:\n    module MyApp.Main")

    for line_number, text in enumerate(source.splitlines(), start=1):
        let_assignment_match = re.search(r"\blet\s+[A-Za-z_][A-Za-z0-9_]*(?:\s*:\s*[A-Za-z_][A-Za-z0-9_]*)?\s*:=", text)
        if let_assignment_match:
            operator_column = text.index(":=", let_assignment_match.start()) + 1
            return Diagnostic("VF-ST007", "let declaration uses assignment operator", line_number, operator_column, '":="', '"=" in let declaration', STATEMENT_LET_OPERATOR_HINT)

    missing_import_name = _line_ending_with(source, r"^import$")
    if missing_import_name:
        return Diagnostic("VF-I004", "expected module name after 'import'", missing_import_name[0], missing_import_name[1], "end of line", "module name", IMPORT_NAME_HINT)

    missing_exposing_symbol = _line_ending_with(source, r"^import\s+[A-Za-z_][A-Za-z0-9_.]*\s+exposing$")
    if missing_exposing_symbol:
        return Diagnostic("VF-I005", "expected symbol name after 'exposing'", missing_exposing_symbol[0], missing_exposing_symbol[1], "end of line", "symbol name", IMPORT_EXPOSING_HINT)

    if type(exc).__name__ in {"UnexpectedEOF", "UnexpectedToken"} and ("END" in expected or "$END" in expected or "MODULE_END" in expected):
        return Diagnostic("VF-C004", "expected module end declaration", line, column, found, '"end <Module.Name>"', MODULE_END_HINT)

    if "procedure" in stripped and "NAME" in expected:
        return Diagnostic("VF-P001", "expected procedure name", line, column, found, "procedure name",
                          "Procedure declarations require a name.\n\nExample:\n    procedure main()\n    is\n        check true\n    end main")

    if "LPAR" in expected or "'('" in expected:
        return Diagnostic("VF-P002", "expected parameter list after procedure name", line, column, found, '"("',
                          "Procedure declarations must include parentheses, even when there are no parameters.\n\nExample:\n    procedure main()")

    if "IS" in expected:
        return Diagnostic("VF-P003", "expected 'is' to start declaration body", line, column, found, '"is"',
                          "A procedure or function body starts with 'is'.\n\nExample:\n    procedure main()\n    is\n        check true\n    end main")

    if "INVARIANT" in expected and found == "'do'":
        return Diagnostic("VF-ST008", "while loop requires invariant", line, column, found, '"invariant" before "do"', STATEMENT_WHILE_INVARIANT_SYNTAX_HINT)

    if "DEFAULT" in expected and found == "'end'":
        return Diagnostic("VF-ST009", "case statement requires default branch", line, column, found, '"default =>" before "end case"', STATEMENT_CASE_DEFAULT_SYNTAX_HINT)

    return Diagnostic("VF-C999", f"syntax error ({type(exc).__name__})", line, column, found,
                      ", ".join(sorted(expected)) if expected else "valid Freehold syntax",
                      "The parser could not match this input to the Freehold grammar.\nAdd a targeted diagnostic rule for this syntax case.")

def diagnose_exception(source: str, exc: Exception) -> Diagnostic:
    if type(exc).__name__ in {"UnexpectedToken", "UnexpectedCharacters", "UnexpectedEOF"}:
        return diagnose_parse_error(source, exc)
    message = str(exc)
    nested_comment_match = re.search(r"nested block comments are not allowed", message)
    if nested_comment_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-CM001", "nested block comment", line, column, '"/*" inside block comment', "non-nested block comment", COMMENT_NESTED_HINT)
    unterminated_comment_match = re.search(r"unterminated block comment", message)
    if unterminated_comment_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-CM002", "unterminated block comment", line, column, '"/*"', '"*/"', COMMENT_UNTERMINATED_HINT)
    module_end_match = re.search(r"module end name mismatch: expected ([A-Za-z_][A-Za-z0-9_.]*), got ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if module_end_match:
        line, column = _source_position_from_message(message)
        expected_name, found_name = module_end_match.groups()
        return Diagnostic("VF-C005", "module end name mismatch", line, column, found_name, expected_name, MODULE_END_NAME_HINT, phase="semantic")
    self_import_match = re.search(r"module cannot import itself: ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if self_import_match:
        line, column = _source_position_from_message(message)
        module_name = self_import_match.group(1)
        return Diagnostic("VF-I001", "module cannot import itself", line, column, module_name, "different module name", IMPORT_SELF_HINT, phase="semantic")
    duplicate_import_match = re.search(r"duplicate import: ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if duplicate_import_match:
        line, column = _source_position_from_message(message)
        module_name = duplicate_import_match.group(1)
        return Diagnostic("VF-I002", "duplicate import declaration", line, column, module_name, "unique imported module", IMPORT_DUPLICATE_HINT, phase="semantic")
    duplicate_exposing_match = re.search(r"duplicate exposing symbol ([A-Za-z_][A-Za-z0-9_]*) in import ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if duplicate_exposing_match:
        line, column = _source_position_from_message(message)
        symbol_name, module_name = duplicate_exposing_match.groups()
        return Diagnostic("VF-I003", "duplicate exposing symbol", line, column, symbol_name, f"unique symbol in import {module_name}", IMPORT_DUPLICATE_EXPOSING_HINT, phase="semantic")
    ambiguous_exposing_match = re.search(r"ambiguous exposed symbol ([A-Za-z_][A-Za-z0-9_]*): ([A-Za-z_][A-Za-z0-9_.]*) and ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if ambiguous_exposing_match:
        line, column = _source_position_from_message(message)
        symbol_name, first_module, second_module = ambiguous_exposing_match.groups()
        return Diagnostic("VF-I006", "ambiguous exposed symbol", line, column, symbol_name, f"unique symbol from either {first_module} or {second_module}", IMPORT_AMBIGUOUS_EXPOSING_HINT, phase="semantic")
    module_not_found_match = re.search(r"imported module not found: ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if module_not_found_match:
        line, column = _source_position_from_message(message)
        module_name = module_not_found_match.group(1)
        return Diagnostic("VF-M001", "imported module not found", line, column, module_name, "existing module file", MODULE_NOT_FOUND_HINT, phase="resolution")
    imported_name_match = re.search(r"imported module name mismatch: expected ([A-Za-z_][A-Za-z0-9_.]*), got ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if imported_name_match:
        line, column = _source_position_from_message(message)
        expected_name, found_name = imported_name_match.groups()
        return Diagnostic("VF-M002", "imported module name mismatch", line, column, found_name, expected_name, IMPORTED_MODULE_NAME_HINT, phase="resolution")
    imported_syntax_match = re.search(r"imported module has syntax error: ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if imported_syntax_match:
        line, column = _source_position_from_message(message)
        module_name = imported_syntax_match.group(1)
        return Diagnostic("VF-M003", "imported module has syntax error", line, column, module_name, "parsable imported module", IMPORTED_MODULE_SYNTAX_HINT, phase="resolution")
    exposed_symbol_match = re.search(r"exposed symbol not found: ([A-Za-z_][A-Za-z0-9_]*) in import ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if exposed_symbol_match:
        line, column = _source_position_from_message(message)
        symbol_name, module_name = exposed_symbol_match.groups()
        return Diagnostic("VF-M004", "exposed symbol not found", line, column, symbol_name, f"declared symbol in {module_name}", EXPOSED_SYMBOL_HINT, phase="resolution")
    cyclic_import_match = re.search(r"cyclic import: (.+)", message)
    if cyclic_import_match:
        line, column = _source_position_from_message(message)
        cycle = cyclic_import_match.group(1)
        return Diagnostic("VF-M005", "cyclic import", line, column, cycle, "acyclic import graph", CYCLIC_IMPORT_HINT, phase="resolution")
    builtin_duplicate_match = re.search(r"built-in type name already defined: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if builtin_duplicate_match:
        line, column = _source_position_from_message(message)
        type_name = builtin_duplicate_match.group(1)
        return Diagnostic("VF-T002", "built-in type cannot be redefined", line, column, type_name, "new type name", TYPE_BUILTIN_HINT, phase="semantic")
    declaration_duplicate_match = re.search(r"declaration name already defined: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if declaration_duplicate_match:
        line, column = _source_position_from_message(message)
        declaration_name = declaration_duplicate_match.group(1)
        return Diagnostic("VF-N001", "duplicate top-level declaration name", line, column, declaration_name, "unique declaration name", DECLARATION_DUPLICATE_HINT, phase="semantic")
    reserved_name_match = re.search(r"reserved keyword cannot be used as name: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if reserved_name_match:
        line, column = _source_position_from_message(message)
        name = reserved_name_match.group(1)
        return Diagnostic("VF-N002", "reserved keyword cannot be used as name", line, column, name, "non-keyword identifier", RESERVED_NAME_HINT, phase="semantic")
    type_duplicate_match = re.search(r"type already defined: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if type_duplicate_match:
        line, column = _source_position_from_message(message)
        type_name = type_duplicate_match.group(1)
        return Diagnostic("VF-T001", "duplicate type declaration", line, column, type_name, "unique type name", TYPE_DUPLICATE_HINT, phase="semantic")
    unknown_type_match = re.search(r"unknown type: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_type_match:
        line, column = _source_position_from_message(message)
        type_name = unknown_type_match.group(1)
        return Diagnostic("VF-T003", "unknown type reference", line, column, type_name, "declared type", TYPE_UNKNOWN_HINT, phase="semantic")
    duplicate_type_param_match = re.search(r"duplicate type parameter: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if duplicate_type_param_match:
        line, column = _source_position_from_message(message)
        param_name = duplicate_type_param_match.group(1)
        return Diagnostic("VF-GEN002", "duplicate type parameter", line, column, param_name, "unique type parameter", GENERIC_DUPLICATE_PARAM_HINT, phase="semantic")
    generic_missing_match = re.search(r"generic type requires (\d+) type argument\(s\): ([A-Za-z_][A-Za-z0-9_]*)", message)
    if generic_missing_match:
        line, column = _source_position_from_message(message)
        expected_count, type_name = generic_missing_match.groups()
        return Diagnostic("VF-GEN010", "missing type argument", line, column, type_name, f"{expected_count} type argument(s)", GENERIC_MISSING_ARGUMENT_HINT, phase="semantic")
    generic_arity_match = re.search(r"generic type ([A-Za-z_][A-Za-z0-9_]*) expects (\d+) type argument\(s\), got (\d+)", message)
    if generic_arity_match:
        line, column = _source_position_from_message(message)
        type_name, expected_count, actual_count = generic_arity_match.groups()
        code = "VF-GEN010" if actual_count == "0" else "VF-GEN011"
        message_text = "missing type argument" if actual_count == "0" else "too many type arguments"
        return Diagnostic(code, message_text, line, column, f"{type_name}<{actual_count}>", f"{expected_count} type argument(s)", GENERIC_TOO_MANY_ARGUMENTS_HINT, phase="semantic")
    non_generic_args_match = re.search(r"non-generic type used with type arguments: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if non_generic_args_match:
        line, column = _source_position_from_message(message)
        type_name = non_generic_args_match.group(1)
        return Diagnostic("VF-GEN012", "non-generic type used with type arguments", line, column, type_name, "generic type declaration", GENERIC_NON_GENERIC_ARGUMENTS_HINT, phase="semantic")
    generic_routine_missing_match = re.search(r"generic routine requires (\d+) type argument\(s\): ([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)", message)
    if generic_routine_missing_match:
        line, column = _source_position_from_message(message)
        expected_count, routine_name = generic_routine_missing_match.groups()
        if routine_name == "Json.parse":
            return Diagnostic("VF-J005", "missing Json parse type argument", line, column, "type argument list", f"{expected_count} record type argument(s) for {routine_name}", JSON_PARSE_TYPE_ARGUMENT_HINT, phase="semantic")
        return Diagnostic("VF-GEN030", "missing routine type argument", line, column, routine_name, f"{expected_count} type argument(s)", GENERIC_ROUTINE_MISSING_ARGUMENT_HINT, phase="semantic")
    generic_routine_arity_match = re.search(r"generic routine ([A-Za-z_][A-Za-z0-9_]*) expects (\d+) type argument\(s\), got (\d+)", message)
    if generic_routine_arity_match:
        line, column = _source_position_from_message(message)
        routine_name, expected_count, actual_count = generic_routine_arity_match.groups()
        return Diagnostic("VF-GEN031", "wrong routine type argument count", line, column, f"{routine_name}<{actual_count}>", f"{expected_count} type argument(s)", GENERIC_ROUTINE_ARITY_HINT, phase="semantic")
    non_generic_routine_match = re.search(r"non-generic routine used with type arguments: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if non_generic_routine_match:
        line, column = _source_position_from_message(message)
        routine_name = non_generic_routine_match.group(1)
        return Diagnostic("VF-GEN032", "non-generic routine used with type arguments", line, column, routine_name, "generic function declaration", GENERIC_NON_GENERIC_ROUTINE_HINT, phase="semantic")
    invalid_range_match = re.search(r"invalid range bounds: (.+)", message)
    if invalid_range_match:
        line, column = _source_position_from_message(message)
        bounds = invalid_range_match.group(1)
        return Diagnostic("VF-T004", "invalid range bounds", line, column, bounds, "lower bound <= upper bound", TYPE_RANGE_BOUNDS_HINT, phase="semantic")
    range_numeric_match = re.search(r"range requires numeric base type: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if range_numeric_match:
        line, column = _source_position_from_message(message)
        base_type = range_numeric_match.group(1)
        return Diagnostic("VF-T005", "range requires numeric base type", line, column, base_type, "Integer or Double", TYPE_RANGE_NUMERIC_HINT, phase="semantic")
    integer_range_match = re.search(r"integer range bounds must be integers", message)
    if integer_range_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-T006", "integer range bounds must be integers", line, column, "fractional bound", "integer bounds", TYPE_INTEGER_RANGE_HINT, phase="semantic")
    json_parse_literal_match = re.search(r"Json\.parse literal does not match ([A-Za-z_][A-Za-z0-9_]*(?:<.+>)?): (.+)", message)
    if json_parse_literal_match:
        line, column = _source_position_from_message(message)
        record_name, details = json_parse_literal_match.groups()
        return Diagnostic("VF-J009", "Json parse literal schema mismatch", line, column, details, f"JSON matching {record_name}", JSON_PARSE_LITERAL_SCHEMA_HINT, phase="semantic")
    out_of_range_match = re.search(r"^line \d+:\d+: value (-?\d+(?:\.\d+)?) out of range for type ([A-Za-z_][A-Za-z0-9_]*) \((-?\d+(?:\.\d+)?)\.\.(-?\d+(?:\.\d+)?)\)$", message)
    if out_of_range_match:
        line, column = _source_position_from_message(message)
        val, type_name, min_val, max_val = out_of_range_match.groups()
        return Diagnostic("VF-T007", "value out of range", line, column, val, f"{min_val}..{max_val}", TYPE_VALUE_OUT_OF_RANGE_HINT, phase="semantic")
    verification_match = re.search(r"verification failed: (.+)", message)
    if verification_match:
        line, column = _source_position_from_message(message)
        details = verification_match.group(1)
        return Diagnostic("VF-V001", "formal verification failed", line, column, details, "proven verification conditions", FORMAL_VERIFICATION_HINT, phase="semantic")
    duplicate_record_field_match = re.search(r"duplicate record field: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if duplicate_record_field_match:
        line, column = _source_position_from_message(message)
        field_name = duplicate_record_field_match.group(1)
        return Diagnostic("VF-R001", "duplicate record field", line, column, field_name, "unique field name", RECORD_DUPLICATE_FIELD_HINT, phase="semantic")
    duplicate_json_field_match = re.search(r"duplicate @json field name: (.+)", message)
    if duplicate_json_field_match:
        line, column = _source_position_from_message(message)
        field_name = duplicate_json_field_match.group(1)
        return Diagnostic("VF-J007", "duplicate Json field name", line, column, field_name, "unique @json field name", JSON_FIELD_NAME_HINT, phase="semantic")
    invalid_json_field_match = re.search(r"invalid @json field name: (.+)", message)
    if invalid_json_field_match:
        line, column = _source_position_from_message(message)
        field_name = invalid_json_field_match.group(1)
        return Diagnostic("VF-J008", "invalid Json field name", line, column, field_name, "non-empty @json field name", JSON_FIELD_NAME_HINT, phase="semantic")
    unknown_record_type_match = re.search(r"unknown record type: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_record_type_match:
        line, column = _source_position_from_message(message)
        record_name = unknown_record_type_match.group(1)
        return Diagnostic("VF-R002", "unknown record type", line, column, record_name, "declared record type", RECORD_UNKNOWN_TYPE_HINT, phase="semantic")
    duplicate_literal_field_match = re.search(r"duplicate record literal field: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if duplicate_literal_field_match:
        line, column = _source_position_from_message(message)
        field_name = duplicate_literal_field_match.group(1)
        return Diagnostic("VF-R003", "duplicate record literal field", line, column, field_name, "unique literal field", RECORD_DUPLICATE_LITERAL_FIELD_HINT, phase="semantic")
    unknown_literal_field_match = re.search(r"unknown field for ([A-Za-z_][A-Za-z0-9_]*): ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_literal_field_match:
        line, column = _source_position_from_message(message)
        record_name, field_name = unknown_literal_field_match.groups()
        return Diagnostic("VF-R004", "unknown record literal field", line, column, field_name, f"declared field in {record_name}", RECORD_UNKNOWN_FIELD_HINT, phase="semantic")
    duplicate_proto_match = re.search(r"duplicate proto field id: (\d+)", message)
    if duplicate_proto_match:
        line, column = _source_position_from_message(message)
        proto_id = duplicate_proto_match.group(1)
        return Diagnostic("VF-GRPC001", "duplicate proto field id", line, column, proto_id, "unique proto field id in record", GRPC_PROTO_DUPLICATE_HINT, phase="semantic")
    invalid_proto_match = re.search(r"invalid proto field id: (\d+)", message)
    if invalid_proto_match:
        line, column = _source_position_from_message(message)
        proto_id = invalid_proto_match.group(1)
        return Diagnostic("VF-GRPC002", "invalid proto field id", line, column, proto_id, "positive proto field id", GRPC_PROTO_INVALID_HINT, phase="semantic")
    missing_proto_match = re.search(r"missing proto field id in grpc message: ([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)", message)
    if missing_proto_match:
        line, column = _source_position_from_message(message)
        field_name = missing_proto_match.group(1)
        return Diagnostic("VF-GRPC003", "missing proto field id in grpc message", line, column, field_name, "field: Type proto N", GRPC_PROTO_MISSING_HINT, phase="semantic")
    unknown_rpc_match = re.search(r"unknown rpc (request|response) type: ([A-Za-z_][A-Za-z0-9_<> ,]*)", message)
    if unknown_rpc_match:
        line, column = _source_position_from_message(message)
        role, type_name = unknown_rpc_match.groups()
        return Diagnostic("VF-GRPC004", "unknown rpc type", line, column, f"{role} {type_name}", "declared record message type", GRPC_RPC_TYPE_HINT, phase="semantic")
    duplicate_rpc_match = re.search(r"duplicate rpc name: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if duplicate_rpc_match:
        line, column = _source_position_from_message(message)
        rpc_name = duplicate_rpc_match.group(1)
        return Diagnostic("VF-GRPC005", "duplicate rpc name", line, column, rpc_name, "unique rpc name in service", GRPC_RPC_DUPLICATE_HINT, phase="semantic")
    unsupported_grpc_type_match = re.search(r"unsupported grpc proto field type: ([A-Za-z_][A-Za-z0-9_<> ,]*)", message)
    if unsupported_grpc_type_match:
        line, column = _source_position_from_message(message)
        type_name = unsupported_grpc_type_match.group(1)
        return Diagnostic("VF-GRPC006", "unsupported grpc proto field type", line, column, type_name, "String, Integer, Boolean, Double, record, or Array of supported values", GRPC_PROTO_UNSUPPORTED_TYPE_HINT, phase="semantic")
    missing_record_field_match = re.search(r"missing record field\(s\) for ([A-Za-z_][A-Za-z0-9_]*): (.+)", message)
    if missing_record_field_match:
        line, column = _source_position_from_message(message)
        record_name, field_names = missing_record_field_match.groups()
        return Diagnostic("VF-R005", "missing record literal field", line, column, field_names, f"all fields for {record_name}", RECORD_MISSING_FIELD_HINT, phase="semantic")
    field_access_record_match = re.search(r"field access requires record before \.([A-Za-z_][A-Za-z0-9_]*), got (.+)", message)
    if field_access_record_match:
        line, column = _source_position_from_message(message)
        field_name, found_type = field_access_record_match.groups()
        return Diagnostic("VF-R006", "field access requires record", line, column, found_type, f"record before .{field_name}", RECORD_FIELD_ACCESS_HINT, phase="semantic")
    unknown_field_access_match = re.search(r"unknown field ([A-Za-z_][A-Za-z0-9_]*) for record ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if unknown_field_access_match:
        line, column = _source_position_from_message(message)
        field_name, record_name = unknown_field_access_match.groups()
        return Diagnostic("VF-R007", "unknown record field", line, column, field_name, f"declared field in {record_name}", RECORD_UNKNOWN_FIELD_HINT, phase="semantic")
    unknown_record_variable_match = re.search(r"unknown record variable: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_record_variable_match:
        line, column = _source_position_from_message(message)
        variable_name = unknown_record_variable_match.group(1)
        return Diagnostic("VF-R008", "unknown record variable", line, column, variable_name, "declared record variable", RECORD_UNKNOWN_VARIABLE_HINT, phase="semantic")
    array_scalar_match = re.search(r"array literal elements must be scalar", message)
    if array_scalar_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-A001", "array literal elements must be scalar", line, column, "nested array literal", "scalar element", ARRAY_SCALAR_LITERAL_HINT, phase="semantic")
    array_mixed_match = re.search(r"array literal has mixed element types", message)
    if array_mixed_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-A002", "array literal has mixed element types", line, column, "mixed element types", "same element type", ARRAY_MIXED_TYPES_HINT, phase="semantic")
    array_length_match = re.search(r"array length mismatch: expected (\d+), got (\d+)", message)
    if array_length_match:
        line, column = _source_position_from_message(message)
        expected_size, found_size = array_length_match.groups()
        return Diagnostic("VF-A003", "array length mismatch", line, column, found_size, expected_size, ARRAY_LENGTH_HINT, phase="semantic")
    array_element_match = re.search(r"array element type mismatch", message)
    if array_element_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-A004", "array element type mismatch", line, column, "literal element type", "declared array element type", ARRAY_ELEMENT_TYPE_HINT, phase="semantic")
    unknown_array_match = re.search(r"unknown array: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_array_match:
        line, column = _source_position_from_message(message)
        array_name = unknown_array_match.group(1)
        return Diagnostic("VF-A005", "unknown array", line, column, array_name, "declared array variable", ARRAY_UNKNOWN_HINT, phase="semantic")
    array_target_match = re.search(r"index access requires Array, got (.+)", message)
    if array_target_match:
        line, column = _source_position_from_message(message)
        found_type = array_target_match.group(1)
        return Diagnostic("VF-A006", "index access requires Array", line, column, found_type, "Array", ARRAY_INDEX_TARGET_HINT, phase="semantic")
    array_index_type_match = re.search(r"array index must be Integer, got (.+)", message)
    if array_index_type_match:
        line, column = _source_position_from_message(message)
        found_type = array_index_type_match.group(1)
        return Diagnostic("VF-A007", "array index must be Integer", line, column, found_type, "Integer", ARRAY_INDEX_TYPE_HINT, phase="semantic")
    array_bounds_match = re.search(r"array index out of bounds: (-?\d+) for size (\d+)", message)
    if array_bounds_match:
        line, column = _source_position_from_message(message)
        index_value, size = array_bounds_match.groups()
        return Diagnostic("VF-A008", "array index out of bounds", line, column, index_value, f"0 <= index < {size}", ARRAY_BOUNDS_HINT, phase="semantic")
    routine_end_match = re.search(r"(function|procedure) end name mismatch: expected ([A-Za-z_][A-Za-z0-9_]*), got ([A-Za-z_][A-Za-z0-9_]*)", message)
    if routine_end_match:
        line, column = _source_position_from_message(message)
        kind, expected_name, found_name = routine_end_match.groups()
        return Diagnostic("VF-U001", f"{kind} end name mismatch", line, column, found_name, expected_name, ROUTINE_END_NAME_HINT, phase="semantic")
    duplicate_parameter_match = re.search(r"duplicate parameter name: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if duplicate_parameter_match:
        line, column = _source_position_from_message(message)
        parameter_name = duplicate_parameter_match.group(1)
        return Diagnostic("VF-U002", "duplicate parameter name", line, column, parameter_name, "unique parameter name", ROUTINE_DUPLICATE_PARAM_HINT, phase="semantic")
    missing_return_match = re.search(r"function ([A-Za-z_][A-Za-z0-9_]*) has no guaranteed return", message)
    if missing_return_match:
        line, column = _source_position_from_message(message)
        function_name = missing_return_match.group(1)
        return Diagnostic("VF-U003", "function has no guaranteed return", line, column, function_name, "return statement on all paths", ROUTINE_MISSING_RETURN_HINT, phase="semantic")
    procedure_return_match = re.search(r"procedure cannot return a value", message)
    if procedure_return_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-U004", "procedure cannot return a value", line, column, "return value", "no return value", ROUTINE_PROCEDURE_RETURN_HINT, phase="semantic")
    unknown_routine_match = re.search(r"unknown routine: ([A-Za-z_][A-Za-z0-9_.]*)", message)
    if unknown_routine_match:
        line, column = _source_position_from_message(message)
        routine_name = unknown_routine_match.group(1)
        return Diagnostic("VF-U005", "unknown routine", line, column, routine_name, "declared routine", ROUTINE_UNKNOWN_HINT, phase="semantic")
    call_requires_procedure_match = re.search(r"call requires procedure", message)
    if call_requires_procedure_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-U006", "call requires procedure", line, column, "function", "procedure", ROUTINE_CALL_KIND_HINT, phase="semantic")
    function_call_requires_function_match = re.search(r"function call requires function", message)
    if function_call_requires_function_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-U010", "function call requires function", line, column, "procedure", "function", ROUTINE_FUNCTION_CALL_KIND_HINT, phase="semantic")
    argument_count_match = re.search(r"routine ([A-Za-z_][A-Za-z0-9_.]*) expects (\d+) argument\(s\), got (\d+)", message)
    if argument_count_match:
        line, column = _source_position_from_message(message)
        routine_name, expected_count, found_count = argument_count_match.groups()
        return Diagnostic("VF-U007", "wrong routine argument count", line, column, found_count, f"{expected_count} argument(s) for {routine_name}", ROUTINE_ARGUMENT_COUNT_HINT, phase="semantic")
    argument_type_match = re.search(r"routine argument (\d+) type mismatch for ([A-Za-z_][A-Za-z0-9_.]*): expected ([A-Za-z_][A-Za-z0-9_]*), got (.+)", message)
    if argument_type_match:
        line, column = _source_position_from_message(message)
        argument_index, routine_name, expected_type, found_type = argument_type_match.groups()
        return Diagnostic("VF-U008", "routine argument type mismatch", line, column, found_type, f"argument {argument_index} as {expected_type} for {routine_name}", ROUTINE_ARGUMENT_TYPE_HINT, phase="semantic")
    return_type_match = re.search(r"function return type mismatch: expected (.+), got (.+)", message)
    if return_type_match:
        line, column = _source_position_from_message(message)
        expected_type, found_type = return_type_match.groups()
        return Diagnostic("VF-U009", "function return type mismatch", line, column, found_type, expected_type, ROUTINE_RETURN_TYPE_HINT, phase="semantic")
    string_arg_count_match = re.search(r"(String\.[A-Za-z_][A-Za-z0-9_]*) expects (\d+) arguments", message)
    if string_arg_count_match:
        line, column = _source_position_from_message(message)
        function_name, expected_count = string_arg_count_match.groups()
        return Diagnostic("VF-S001", "wrong String argument count", line, column, "argument list", f"{expected_count} argument(s) for {function_name}", STRING_ARGUMENT_COUNT_HINT, phase="semantic")
    string_arg_type_match = re.search(r"(String\.[A-Za-z_][A-Za-z0-9_]*) argument (\d+) expected ([A-Za-z_][A-Za-z0-9_]*), got (.+)", message)
    if string_arg_type_match:
        line, column = _source_position_from_message(message)
        function_name, argument_index, expected_type, found_type = string_arg_type_match.groups()
        return Diagnostic("VF-S002", "String argument type mismatch", line, column, found_type, f"argument {argument_index} as {expected_type} for {function_name}", STRING_ARGUMENT_TYPE_HINT, phase="semantic")
    template_count_match = re.search(r"(String\.template|Std\.IO\.logf) placeholder count mismatch: expected (\d+), got (\d+)", message)
    if template_count_match:
        line, column = _source_position_from_message(message)
        function_name, expected_count, found_count = template_count_match.groups()
        return Diagnostic("VF-TPL001", "string template placeholder count mismatch", line, column, found_count, f"{expected_count} template value(s) for {function_name}", TEMPLATE_ARGUMENT_COUNT_HINT, phase="semantic")
    template_old_placeholder_match = re.search(r"(String\.template|Std\.IO\.logf) template placeholder must use \$\{\} instead of \{\}", message)
    if template_old_placeholder_match:
        line, column = _source_position_from_message(message)
        function_name = template_old_placeholder_match.group(1)
        return Diagnostic("VF-TPL002", "old template placeholder rejected", line, column, "{}", f"${{}} placeholder for {function_name}", TEMPLATE_PLACEHOLDER_HINT, phase="semantic")
    template_invalid_named_match = re.search(r"(String\.template|Std\.IO\.logf) invalid named template placeholder: (\$\{[^}]+\})", message)
    if template_invalid_named_match:
        line, column = _source_position_from_message(message)
        function_name, placeholder = template_invalid_named_match.groups()
        return Diagnostic("VF-TPL003", "invalid named string template placeholder", line, column, placeholder, f"${{name}} placeholder for {function_name}", TEMPLATE_PLACEHOLDER_HINT, phase="semantic")
    template_brace_match = re.search(r"(String\.template|Std\.IO\.logf) invalid template brace: ([{}])", message)
    if template_brace_match:
        line, column = _source_position_from_message(message)
        function_name, brace = template_brace_match.groups()
        return Diagnostic("VF-TPL004", "invalid string template brace", line, column, brace, f"${{}} placeholder for {function_name}", TEMPLATE_PLACEHOLDER_HINT, phase="semantic")
    template_value_type_match = re.search(r"(String\.template|Std\.IO\.logf) template value ([A-Za-z_][A-Za-z0-9_]*|\d+) expected String, Integer, Boolean, or Double, got (.+)", message)
    if template_value_type_match:
        line, column = _source_position_from_message(message)
        function_name, argument_index, found_type = template_value_type_match.groups()
        return Diagnostic("VF-TPL005", "string template value type mismatch", line, column, found_type, f"scalar template value {argument_index} for {function_name}", TEMPLATE_VALUE_TYPE_HINT, phase="semantic")
    template_duplicate_binding_match = re.search(r"(String\.template|Std\.IO\.logf) duplicate template binding: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if template_duplicate_binding_match:
        line, column = _source_position_from_message(message)
        function_name, binding_name = template_duplicate_binding_match.groups()
        return Diagnostic("VF-TPL006", "duplicate string template binding", line, column, binding_name, f"unique binding name for {function_name}", TEMPLATE_BINDING_HINT, phase="semantic")
    template_missing_binding_match = re.search(r"(String\.template|Std\.IO\.logf) missing template binding: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if template_missing_binding_match:
        line, column = _source_position_from_message(message)
        function_name, binding_name = template_missing_binding_match.groups()
        return Diagnostic("VF-TPL007", "missing string template binding", line, column, binding_name, f"binding for {function_name}", TEMPLATE_BINDING_HINT, phase="semantic")
    template_unused_binding_match = re.search(r"(String\.template|Std\.IO\.logf) unused template binding: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if template_unused_binding_match:
        line, column = _source_position_from_message(message)
        function_name, binding_name = template_unused_binding_match.groups()
        return Diagnostic("VF-TPL008", "unused string template binding", line, column, binding_name, f"placeholder in {function_name}", TEMPLATE_BINDING_HINT, phase="semantic")
    template_mixed_match = re.search(r"(String\.template|Std\.IO\.logf) cannot mix positional and named template (?:arguments|placeholders)", message)
    if template_mixed_match:
        line, column = _source_position_from_message(message)
        function_name = template_mixed_match.group(1)
        return Diagnostic("VF-TPL009", "mixed string template modes", line, column, "mixed positional/named template", f"one template mode for {function_name}", TEMPLATE_BINDING_HINT, phase="semantic")
    math_arg_count_match = re.search(r"(Math\.[A-Za-z_][A-Za-z0-9_]*) expects (\d+) arguments", message)
    if math_arg_count_match:
        line, column = _source_position_from_message(message)
        function_name, expected_count = math_arg_count_match.groups()
        return Diagnostic("VF-MA001", "wrong Math argument count", line, column, "argument list", f"{expected_count} argument(s) for {function_name}", MATH_ARGUMENT_COUNT_HINT, phase="semantic")
    math_arg_type_match = re.search(r"(Math\.[A-Za-z_][A-Za-z0-9_]*) argument (\d+) expected numeric, got (.+)", message)
    if math_arg_type_match:
        line, column = _source_position_from_message(message)
        function_name, argument_index, found_type = math_arg_type_match.groups()
        return Diagnostic("VF-MA002", "Math argument type mismatch", line, column, found_type, f"numeric argument {argument_index} for {function_name}", MATH_ARGUMENT_TYPE_HINT, phase="semantic")
    big_arg_count_match = re.search(r"(Big\.[A-Za-z_][A-Za-z0-9_]*) expects (\d+) arguments", message)
    if big_arg_count_match:
        line, column = _source_position_from_message(message)
        function_name, expected_count = big_arg_count_match.groups()
        return Diagnostic("VF-BI001", "wrong Big argument count", line, column, "argument list", f"{expected_count} argument(s) for {function_name}", BIG_ARGUMENT_COUNT_HINT, phase="semantic")
    big_arg_type_match = re.search(r"(Big\.[A-Za-z_][A-Za-z0-9_]*) argument (\d+) expected ([A-Za-z_][A-Za-z0-9_]*), got (.+)", message)
    if big_arg_type_match:
        line, column = _source_position_from_message(message)
        function_name, argument_index, expected_type, found_type = big_arg_type_match.groups()
        return Diagnostic("VF-BI002", "Big argument type mismatch", line, column, found_type, f"argument {argument_index} as {expected_type} for {function_name}", BIG_ARGUMENT_TYPE_HINT, phase="semantic")
    json_arg_count_match = re.search(r"(Json\.stringify) expects (\d+) arguments", message)
    if json_arg_count_match:
        line, column = _source_position_from_message(message)
        function_name, expected_count = json_arg_count_match.groups()
        return Diagnostic("VF-J001", "wrong Json argument count", line, column, "argument list", f"{expected_count} argument(s) for {function_name}", JSON_ARGUMENT_COUNT_HINT, phase="semantic")
    json_parse_arg_count_match = re.search(r"(Json\.parse) expects (\d+) arguments", message)
    if json_parse_arg_count_match:
        line, column = _source_position_from_message(message)
        function_name, expected_count = json_parse_arg_count_match.groups()
        return Diagnostic("VF-J004", "wrong Json parse argument count", line, column, "argument list", f"{expected_count} argument(s) for {function_name}", JSON_PARSE_ARGUMENT_COUNT_HINT, phase="semantic")
    json_parse_type_arg_match = re.search(r"generic routine requires (\d+) type argument\(s\): (Json\.parse)", message)
    if json_parse_type_arg_match:
        line, column = _source_position_from_message(message)
        expected_count, function_name = json_parse_type_arg_match.groups()
        return Diagnostic("VF-J005", "missing Json parse type argument", line, column, "type argument list", f"{expected_count} record type argument(s) for {function_name}", JSON_PARSE_TYPE_ARGUMENT_HINT, phase="semantic")
    json_parse_target_type_match = re.search(r"(Json\.parse) type argument expected record, got (.+)", message)
    if json_parse_target_type_match:
        line, column = _source_position_from_message(message)
        function_name, found_type = json_parse_target_type_match.groups()
        return Diagnostic("VF-J006", "Json parse target type mismatch", line, column, found_type, f"record type argument for {function_name}", JSON_PARSE_TARGET_TYPE_HINT, phase="semantic")
    json_arg_type_match = re.search(r"(Json\.stringify) argument (\d+) expected record, got (.+)", message)
    if json_arg_type_match:
        line, column = _source_position_from_message(message)
        function_name, argument_index, found_type = json_arg_type_match.groups()
        return Diagnostic("VF-J002", "Json argument type mismatch", line, column, found_type, f"record argument {argument_index} for {function_name}", JSON_ARGUMENT_TYPE_HINT, phase="semantic")
    json_serializable_type_match = re.search(r"(Json\.stringify) cannot serialize (.+) at (.+)", message)
    if json_serializable_type_match:
        line, column = _source_position_from_message(message)
        function_name, found_type, path = json_serializable_type_match.groups()
        return Diagnostic("VF-J003", "Json value type not serializable", line, column, f"{path}: {found_type}", f"JSON-serializable value for {function_name}", JSON_SERIALIZABLE_TYPE_HINT, phase="semantic")
    unknown_assignment_match = re.search(r"unknown assignment target: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_assignment_match:
        line, column = _source_position_from_message(message)
        target_name = unknown_assignment_match.group(1)
        return Diagnostic("VF-ST001", "unknown assignment target", line, column, target_name, "declared local variable", STATEMENT_UNKNOWN_ASSIGNMENT_HINT, phase="semantic")
    assignment_type_match = re.search(r"cannot assign (.+) to (.+)", message)
    if assignment_type_match:
        line, column = _source_position_from_message(message)
        found_type, expected_type = assignment_type_match.groups()
        return Diagnostic("VF-ST002", "assignment type mismatch", line, column, found_type, expected_type, STATEMENT_ASSIGNMENT_TYPE_HINT, phase="semantic")
    statement_boolean_match = re.search(r"(check|if condition|while condition|while invariant) requires Boolean, got (.+)", message)
    if statement_boolean_match:
        line, column = _source_position_from_message(message)
        statement_name, found_type = statement_boolean_match.groups()
        return Diagnostic("VF-ST003", f"{statement_name} requires Boolean", line, column, found_type, "Boolean", STATEMENT_BOOLEAN_HINT, phase="semantic")
    while_variant_match = re.search(r"while variant must be Integer, got (.+)", message)
    if while_variant_match:
        line, column = _source_position_from_message(message)
        found_type = while_variant_match.group(1)
        return Diagnostic("VF-ST004", "while variant must be Integer", line, column, found_type, "Integer", STATEMENT_WHILE_VARIANT_HINT, phase="semantic")
    case_type_match = re.search(r"case branch type (.+) does not match case expression (.+)", message)
    if case_type_match:
        line, column = _source_position_from_message(message)
        branch_type, case_type = case_type_match.groups()
        return Diagnostic("VF-ST005", "case branch type mismatch", line, column, branch_type, case_type, STATEMENT_CASE_TYPE_HINT, phase="semantic")
    duplicate_case_match = re.search(r"duplicate case branch value", message)
    if duplicate_case_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-ST006", "duplicate case branch value", line, column, "duplicate branch value", "unique case branch value", STATEMENT_CASE_DUPLICATE_HINT, phase="semantic")
    contract_boolean_match = re.search(r"contract (requires|ensures) requires Boolean, got (.+)", message)
    if contract_boolean_match:
        line, column = _source_position_from_message(message)
        contract_name, found_type = contract_boolean_match.groups()
        return Diagnostic("VF-CT001", f"{contract_name} clause requires Boolean", line, column, found_type, "Boolean", CONTRACT_BOOLEAN_HINT, phase="semantic")
    contract_result_context_match = re.search(r"Result contract expression ([A-Za-z_][A-Za-z0-9_]*) is only available in Result ensures", message)
    if contract_result_context_match:
        line, column = _source_position_from_message(message)
        expression_name = contract_result_context_match.group(1)
        return Diagnostic("VF-CT002", "Result contract expression outside Result ensures", line, column, expression_name, "Result ensures context", CONTRACT_RESULT_CONTEXT_HINT, phase="semantic")
    unknown_abort_match = re.search(r"unknown abort error: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_abort_match:
        line, column = _source_position_from_message(message)
        error_name = unknown_abort_match.group(1)
        return Diagnostic("VF-ABT001", "unknown abort error", line, column, error_name, "declared error", ABORT_UNKNOWN_HINT, phase="semantic")
    abort_not_declared_match = re.search(r"abort not declared by routine: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if abort_not_declared_match:
        line, column = _source_position_from_message(message)
        error_name = abort_not_declared_match.group(1)
        return Diagnostic("VF-ABT002", "abort not declared by routine", line, column, f"abort {error_name}", f"aborts {error_name}", ABORT_NOT_DECLARED_HINT, phase="semantic")
    duplicate_abort_match = re.search(r"duplicate abort declaration: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if duplicate_abort_match:
        line, column = _source_position_from_message(message)
        error_name = duplicate_abort_match.group(1)
        return Diagnostic("VF-ABT003", "duplicate abort declaration", line, column, error_name, "unique abort declaration", ABORT_DUPLICATE_HINT, phase="semantic")
    abort_propagation_match = re.search(r"caller does not handle or propagate abort: ([A-Za-z_][A-Za-z0-9_.]*) may abort ([A-Za-z_][A-Za-z0-9_]*)", message)
    if abort_propagation_match:
        line, column = _source_position_from_message(message)
        routine_name, error_name = abort_propagation_match.groups()
        return Diagnostic("VF-ABT005", "caller does not handle or propagate abort", line, column, f"call {routine_name} may abort {error_name}", f"caller declares aborts {error_name} or handles {error_name}", ABORT_PROPAGATION_HINT, phase="semantic")
    abort_condition_coverage_match = re.search(r"abort condition not covered by abort contract: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if abort_condition_coverage_match:
        line, column = _source_position_from_message(message)
        error_name = abort_condition_coverage_match.group(1)
        return Diagnostic("VF-ABT006", "abort condition not covered by abort contract", line, column, f"abort {error_name}", f"path implies aborts {error_name} condition", ABORT_CONDITION_COVERAGE_HINT, phase="semantic")
    main_requires_match = re.search(r"main requires clause is not allowed", message)
    if main_requires_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-ABT009", "main requires clause is not allowed", line, column, "requires", "explicit top-level aborts clause or environment assumption", ABORT_MAIN_REQUIRES_HINT, phase="semantic")
    abort_unreachable_match = re.search(r"unreachable statement after guaranteed exit", message)
    if abort_unreachable_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-ABT010", "unreachable statement after guaranteed exit", line, column, "statement after guaranteed exit", "reachable statement", ABORT_UNREACHABLE_HINT, phase="semantic")
    unknown_variable_match = re.search(r"unknown variable: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_variable_match:
        line, column = _source_position_from_message(message)
        variable_name = unknown_variable_match.group(1)
        return Diagnostic("VF-E001", "unknown variable", line, column, variable_name, "variable in scope", EXPRESSION_UNKNOWN_VARIABLE_HINT, phase="semantic")
    compare_match = re.search(r"cannot compare (.+) with (.+)", message)
    if compare_match:
        line, column = _source_position_from_message(message)
        left_type, right_type = compare_match.groups()
        return Diagnostic("VF-E002", "comparison type mismatch", line, column, f"{left_type} with {right_type}", "matching operand types", EXPRESSION_COMPARE_HINT, phase="semantic")
    boolean_operator_match = re.search(r"boolean operator (and|or) requires Boolean operands, got (.+) and (.+)", message)
    if boolean_operator_match:
        line, column = _source_position_from_message(message)
        operator, left_type, right_type = boolean_operator_match.groups()
        return Diagnostic("VF-E003", "Boolean operator operand mismatch", line, column, f"{left_type} and {right_type}", f"Boolean operands for {operator}", EXPRESSION_BOOLEAN_OPERATOR_HINT, phase="semantic")
    comparison_operator_match = re.search(r"comparison operator (<=|>=|<|>) requires numeric operands, got (.+) and (.+)", message)
    if comparison_operator_match:
        line, column = _source_position_from_message(message)
        operator, left_type, right_type = comparison_operator_match.groups()
        return Diagnostic("VF-E004", "ordering comparison requires numeric operands", line, column, f"{left_type} and {right_type}", f"numeric operands for {operator}", EXPRESSION_COMPARISON_OPERATOR_HINT, phase="semantic")
    arithmetic_match = re.search(r"arithmetic operator ([+\-*/]) requires numeric operands, got (.+) and (.+)", message)
    if arithmetic_match:
        line, column = _source_position_from_message(message)
        operator, left_type, right_type = arithmetic_match.groups()
        return Diagnostic("VF-E005", "arithmetic requires numeric operands", line, column, f"{left_type} and {right_type}", f"numeric operands for {operator}", EXPRESSION_ARITHMETIC_HINT, phase="semantic")
    unary_not_match = re.search(r"unary not requires Boolean, got (.+)", message)
    if unary_not_match:
        line, column = _source_position_from_message(message)
        found_type = unary_not_match.group(1)
        return Diagnostic("VF-E006", "unary not requires Boolean", line, column, found_type, "Boolean", EXPRESSION_UNARY_NOT_HINT, phase="semantic")
    unary_negative_match = re.search(r"unary - requires numeric operand, got (.+)", message)
    if unary_negative_match:
        line, column = _source_position_from_message(message)
        found_type = unary_negative_match.group(1)
        return Diagnostic("VF-E007", "unary negative requires numeric operand", line, column, found_type, "Integer or Double", EXPRESSION_UNARY_NEGATIVE_HINT, phase="semantic")
    await_context_match = re.search(r"await is only allowed inside async (?:function|functions|routine|routines)", message)
    if await_context_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-ASY001", "await outside async routine", line, column, "await", "async routine context", ASYNC_AWAIT_CONTEXT_HINT, phase="semantic")
    awaitable_match = re.search(r"await requires an awaitable expression, got (.+)", message)
    if awaitable_match:
        line, column = _source_position_from_message(message)
        found_type = awaitable_match.group(1)
        return Diagnostic("VF-ASY002", "await requires awaitable expression", line, column, found_type, "awaitable expression", ASYNC_AWAITABLE_HINT, phase="semantic")
    channel_arg_count_match = re.search(r"(channel|channel_sender|channel_receiver|channel_send|channel_try_send|channel_receive) expects (\d+) arguments", message)
    if channel_arg_count_match:
        line, column = _source_position_from_message(message)
        function_name, expected_count = channel_arg_count_match.groups()
        return Diagnostic("VF-CH001", "wrong Channel argument count", line, column, "argument list", f"{expected_count} argument(s) for {function_name}", CHANNEL_ARGUMENT_COUNT_HINT, phase="semantic")
    channel_arg_type_match = re.search(r"(channel|channel_sender|channel_receiver|channel_send|channel_try_send|channel_receive) argument (\d+) expected (.+), got (.+)", message)
    if channel_arg_type_match:
        line, column = _source_position_from_message(message)
        function_name, argument_index, expected_type, found_type = channel_arg_type_match.groups()
        return Diagnostic("VF-CH002", "Channel argument type mismatch", line, column, found_type, f"argument {argument_index} as {expected_type} for {function_name}", CHANNEL_ARGUMENT_TYPE_HINT, phase="semantic")
    scope_handle_escape_match = re.search(r"scope JoinHandle cannot escape its scope: ([A-Za-z_][A-Za-z0-9_]*) from ([A-Za-z_][A-Za-z0-9_]*)", message)
    if scope_handle_escape_match:
        line, column = _source_position_from_message(message)
        handle_name, scope_name = scope_handle_escape_match.groups()
        return Diagnostic("VF-SC001", "scope JoinHandle cannot escape", line, column, handle_name, f"scope-local JoinHandle joined inside {scope_name}", SCOPE_HANDLE_ESCAPE_HINT, phase="semantic")
    scope_handle_unjoined_match = re.search(r"scope JoinHandle must be joined before leaving scope: ([A-Za-z_][A-Za-z0-9_]*) from ([A-Za-z_][A-Za-z0-9_]*)", message)
    if scope_handle_unjoined_match:
        line, column = _source_position_from_message(message)
        handle_name, scope_name = scope_handle_unjoined_match.groups()
        return Diagnostic("VF-SC002", "scope JoinHandle must be joined", line, column, handle_name, f"scope_join before leaving {scope_name}", SCOPE_HANDLE_JOIN_HINT, phase="semantic")
    unknown_result_error_type_match = re.search(r"unknown result error type: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_result_error_type_match:
        line, column = _source_position_from_message(message)
        error_name = unknown_result_error_type_match.group(1)
        return Diagnostic("VF-ER001", "unknown result error type", line, column, error_name, "declared error", ERROR_UNKNOWN_RESULT_TYPE_HINT, phase="semantic")
    unknown_error_return_match = re.search(r"unknown error: ([A-Za-z_][A-Za-z0-9_]*)", message)
    if unknown_error_return_match:
        line, column = _source_position_from_message(message)
        error_name = unknown_error_return_match.group(1)
        return Diagnostic("VF-ER002", "unknown returned error", line, column, error_name, "declared error", ERROR_UNKNOWN_RETURN_HINT, phase="semantic")
    wrong_result_error_match = re.search(r"Function returns (Result<[^>]+>), cannot return error ([A-Za-z_][A-Za-z0-9_]*)", message)
    if wrong_result_error_match:
        line, column = _source_position_from_message(message)
        result_type, error_name = wrong_result_error_match.groups()
        return Diagnostic("VF-ER003", "wrong Result error return", line, column, error_name, result_type, ERROR_WRONG_RETURN_HINT, phase="semantic")
    result_return_form_match = re.search(r"Result function must return ok or error", message)
    if result_return_form_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-ER004", "Result function must return ok or error", line, column, "plain return", "ok or error return", ERROR_RESULT_RETURN_FORM_HINT, phase="semantic")
    plain_return_form_match = re.search(r"plain function must return expression", message)
    if plain_return_form_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-ER005", "plain function cannot return ok or error", line, column, "ok/error return", "plain expression return", ERROR_PLAIN_RETURN_FORM_HINT, phase="semantic")
    result_ok_type_match = re.search(r"Result ok type mismatch: expected (.+), got (.+)", message)
    if result_ok_type_match:
        line, column = _source_position_from_message(message)
        expected_type, found_type = result_ok_type_match.groups()
        return Diagnostic("VF-ER006", "Result ok type mismatch", line, column, found_type, expected_type, ERROR_OK_TYPE_HINT, phase="semantic")
    nested_result_match = re.search(r"nested Result payloads are forbidden in v1", message)
    if nested_result_match:
        line, column = _source_position_from_message(message)
        return Diagnostic("VF-ER007", "nested Result payloads are forbidden in v1", line, column, "Result payload", "non-Result value type", ERROR_NESTED_RESULT_HINT, phase="semantic")
    return Diagnostic("VF-S999", f"semantic error ({type(exc).__name__})", _line(exc), _column(exc), repr(str(exc)),
                      "valid Freehold semantics",
                      "The parser accepted the input, but semantic analysis rejected it.\nAdd a targeted semantic diagnostic rule.",
                      phase="semantic")
