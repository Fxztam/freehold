// Freehold parser diagnostic catalog.
// Jede neue Fehlerklasse bekommt einen Eintrag und einen stabilen Code.
package diagnostic

import (
	"fmt"
	"strings"

	"freehold-go-frontend/internal/token"
)

type Location struct {
	Line   int `json:"line"`
	Column int `json:"column"`
	Offset int `json:"offset,omitempty"`
}

type Diagnostic struct {
	Severity string   `json:"severity"`
	Phase    string   `json:"phase"`
	Category string   `json:"category"`
	Code     string   `json:"code"`
	Number   int      `json:"number"`
	Name     string   `json:"name"`
	Message  string   `json:"message"`
	Location Location `json:"location"`
	Expected []string `json:"expected,omitempty"`
	Found    string   `json:"found,omitempty"`
	Hint     string   `json:"hint,omitempty"`
}

type Definition struct {
	Severity string
	Phase    string
	Category string
	Code     string
	Number   int
	Name     string
	Message  string
	Hint     string
}

const (
	SyntaxRange    = "FH-SYN-0001..0999"
	SemanticRange  = "FH-SEM-1000..1999"
	TypeRange      = "FH-TYP-2000..2999"
	ContractRange  = "FH-CON-3000..3999"
	BootstrapRange = "FH-BLD-9000..9999"
)

var catalog = map[string]Definition{
	"expected_identifier": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0002",
		Number:   2,
		Name:     "expected_identifier",
		Message:  "Expected an identifier.",
		Hint:     "Use a non-keyword name here.",
	},
	"missing_module_declaration": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0003",
		Number:   3,
		Name:     "missing_module_declaration",
		Message:  "Expected a module declaration.",
		Hint:     "A Freehold file must start with a module declaration.",
	},
	"missing_end": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0004",
		Number:   4,
		Name:     "missing_end",
		Message:  "Expected an end marker.",
		Hint:     "Close the current declaration or block with the matching end clause.",
	},
	"expected_type_annotation_colon": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0005",
		Number:   5,
		Name:     "expected_type_annotation_colon",
		Message:  "Expected ':' for a type annotation.",
		Hint:     "Use ':' in declarations such as 'let x: Integer = 1'; ':=' is used for assignment.",
	},
	"invalid_contract_order": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0006",
		Number:   6,
		Name:     "invalid_contract_order",
		Message:  "Expected requires clauses before ensures clauses.",
		Hint:     "Place all requires clauses before ensures clauses in a contract block.",
	},
	"expected_declaration": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0007",
		Number:   7,
		Name:     "expected_declaration",
		Message:  "Expected a declaration.",
		Hint:     "Use import, type, error, function, or procedure at module level.",
	},
	"missing_case_default": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0008",
		Number:   8,
		Name:     "missing_case_default",
		Message:  "Expected a default case branch.",
		Hint:     "Every case statement must include a default branch.",
	},
	"missing_while_invariant": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0009",
		Number:   9,
		Name:     "missing_while_invariant",
		Message:  "Expected a while invariant.",
		Hint:     "Every while loop must declare at least one invariant before do.",
	},
	"unterminated_block_comment": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0010",
		Number:   10,
		Name:     "unterminated_block_comment",
		Message:  "Unterminated block comment.",
		Hint:     "Close the block comment with */.",
	},
	"expected_statement": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0011",
		Number:   11,
		Name:     "expected_statement",
		Message:  "Expected a statement.",
		Hint:     "Use let, return, check, call, assignment, if, while, or case in a statement block.",
	},
	"expected_assignment_or_call": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0012",
		Number:   12,
		Name:     "expected_assignment_or_call",
		Message:  "Expected assignment or call statement.",
		Hint:     "An identifier-led statement must be an assignment with ':=' or a procedure call.",
	},
	"expected_number": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0013",
		Number:   13,
		Name:     "expected_number",
		Message:  "Expected a number literal.",
		Hint:     "Use an integer or double literal here.",
	},
	"missing_return_type": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0014",
		Number:   14,
		Name:     "missing_return_type",
		Message:  "Expected a function return type.",
		Hint:     "Add a type name after 'returns'.",
	},
	"expected_expression": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0015",
		Number:   15,
		Name:     "expected_expression",
		Message:  "Expected an expression.",
		Hint:     "Use a literal, identifier, call, parenthesized expression, or unary expression here.",
	},
	"unterminated_string": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0016",
		Number:   16,
		Name:     "unterminated_string",
		Message:  "Unterminated string literal.",
		Hint:     "Close the string literal with a double quote.",
	},
	"invalid_number_literal": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0017",
		Number:   17,
		Name:     "invalid_number_literal",
		Message:  "Invalid number literal.",
		Hint:     "Use digits with at most one decimal point and digits on both sides of the decimal point.",
	},
	"missing_parameter_colon": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0018",
		Number:   18,
		Name:     "missing_parameter_colon",
		Message:  "Expected ':' after a parameter name.",
		Hint:     "Write parameters as 'name: Type'.",
	},
	"missing_end_function": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0019",
		Number:   19,
		Name:     "missing_end_function",
		Message:  "Expected 'end' for a function declaration.",
		Hint:     "Close the function body with 'end <function-name>'.",
	},
	"missing_end_procedure": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0020",
		Number:   20,
		Name:     "missing_end_procedure",
		Message:  "Expected 'end' for a procedure declaration.",
		Hint:     "Close the procedure body with 'end <procedure-name>'.",
	},
	"missing_end_if": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0021",
		Number:   21,
		Name:     "missing_end_if",
		Message:  "Expected 'end if'.",
		Hint:     "Close the if statement with 'end if'.",
	},
	"missing_end_while": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0022",
		Number:   22,
		Name:     "missing_end_while",
		Message:  "Expected 'end while'.",
		Hint:     "Close the while statement with 'end while'.",
	},
	"missing_end_case": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0023",
		Number:   23,
		Name:     "missing_end_case",
		Message:  "Expected 'end case'.",
		Hint:     "Close the case statement with 'end case'.",
	},
	"field_access_requires_record": {
		Severity: "error",
		Phase:    "semantic",
		Category: "type",
		Code:     "FH-TYP-2101",
		Number:   2101,
		Name:     "field_access_requires_record",
		Message:  "field access requires record",
		Hint:     "Field access requires the value before the dot to be a record.",
	},
	"unknown_record_field": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1105",
		Number:   1105,
		Name:     "unknown_record_field",
		Message:  "unknown record field",
		Hint:     "A record literal or field access may only use fields declared by the record type.",
	},
	"duplicate_record_literal_field": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1102",
		Number:   1102,
		Name:     "duplicate_record_literal_field",
		Message:  "duplicate record literal field",
		Hint:     "Each record literal field may be assigned at most once.",
	},
	"unknown_record_literal_field": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1103",
		Number:   1103,
		Name:     "unknown_record_literal_field",
		Message:  "unknown record literal field",
		Hint:     "A record literal may only assign fields declared by the record type.",
	},
	"missing_record_literal_field": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1104",
		Number:   1104,
		Name:     "missing_record_literal_field",
		Message:  "missing record literal field",
		Hint:     "A record literal must assign every declared field exactly once.",
	},
	"index_access_requires_array": {
		Severity: "error",
		Phase:    "semantic",
		Category: "type",
		Code:     "FH-TYP-2115",
		Number:   2115,
		Name:     "index_access_requires_array",
		Message:  "index access requires array",
		Hint:     "Index access requires the indexed value to have an Array type.",
	},
	"array_index_requires_integer": {
		Severity: "error",
		Phase:    "semantic",
		Category: "type",
		Code:     "FH-TYP-2116",
		Number:   2116,
		Name:     "array_index_requires_integer",
		Message:  "array index requires Integer",
		Hint:     "Array indices must have type Integer.",
	},
	"imported_module_not_found": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1006",
		Number:   1006,
		Name:     "imported_module_not_found",
		Message:  "imported module not found",
		Hint:     "Imported project modules must exist at the path implied by their module name.",
	},
	"ambiguous_exposed_symbol": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1005",
		Number:   1005,
		Name:     "ambiguous_exposed_symbol",
		Message:  "ambiguous exposed symbol",
		Hint:     "A symbol exposed into the local namespace must come from exactly one imported module.",
	},
	"import_cycle": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1007",
		Number:   1007,
		Name:     "import_cycle",
		Message:  "import cycle",
		Hint:     "Project imports must form an acyclic module graph.",
	},
	"module_file_path_mismatch": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1008",
		Number:   1008,
		Name:     "module_file_path_mismatch",
		Message:  "module file path mismatch",
		Hint:     "A module file path must match its module name, for example App.Main -> App/Main.fh.",
	},
	"imported_module_name_mismatch": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1009",
		Number:   1009,
		Name:     "imported_module_name_mismatch",
		Message:  "imported module name mismatch",
		Hint:     "An imported file must declare the module named by the import.",
	},
	"unknown_exposed_symbol": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1010",
		Number:   1010,
		Name:     "unknown_exposed_symbol",
		Message:  "unknown exposed symbol",
		Hint:     "An import exposing list may only name declarations from the imported module.",
	},
	"imported_module_parse_error": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1011",
		Number:   1011,
		Name:     "imported_module_parse_error",
		Message:  "imported module parse error",
		Hint:     "Imported project modules must parse before project semantics can run.",
	},
	"unknown_routine": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1204",
		Number:   1204,
		Name:     "unknown_routine",
		Message:  "unknown routine",
		Hint:     "Calls must reference a declared function or procedure.",
	},
	"routine_argument_count_mismatch": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1205",
		Number:   1205,
		Name:     "routine_argument_count_mismatch",
		Message:  "wrong routine argument count",
		Hint:     "Pass exactly the parameters declared by the routine signature.",
	},
	"routine_argument_type_mismatch": {
		Severity: "error",
		Phase:    "semantic",
		Category: "type",
		Code:     "FH-TYP-2201",
		Number:   2201,
		Name:     "routine_argument_type_mismatch",
		Message:  "routine argument type mismatch",
		Hint:     "Call arguments must match the declared parameter types.",
	},
	"unknown_type_reference": {
		Severity: "error",
		Phase:    "semantic",
		Category: "type",
		Code:     "FH-TYP-2003",
		Number:   2003,
		Name:     "unknown_type_reference",
		Message:  "unknown type reference",
		Hint:     "Type annotations must reference a built-in or declared type.",
	},
	"duplicate_parameter_name": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1201",
		Number:   1201,
		Name:     "duplicate_parameter_name",
		Message:  "duplicate parameter name",
		Hint:     "Each routine parameter name must be unique.",
	},
	"unknown_assignment_target": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1301",
		Number:   1301,
		Name:     "unknown_assignment_target",
		Message:  "unknown assignment target",
		Hint:     "Assignments must target a declared local variable or field path.",
	},
	"assignment_type_mismatch": {
		Severity: "error",
		Phase:    "semantic",
		Category: "type",
		Code:     "FH-TYP-2301",
		Number:   2301,
		Name:     "assignment_type_mismatch",
		Message:  "assignment type mismatch",
		Hint:     "Assignment values must match the target type.",
	},
	"duplicate_local_name": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1303",
		Number:   1303,
		Name:     "duplicate_local_name",
		Message:  "duplicate local name",
		Hint:     "Each local variable name must be unique in its visible scope.",
	},
	"unknown_variable": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-SEM-1401",
		Number:   1401,
		Name:     "unknown_variable",
		Message:  "unknown variable",
		Hint:     "An expression may only reference variables that are in scope.",
	},
	"expected_token": {
		Severity: "error",
		Phase:    "parse",
		Category: "syntax",
		Code:     "FH-SYN-0999",
		Number:   999,
		Name:     "expected_token",
		Message:  "Expected a different token.",
		Hint:     "Check the syntax around this token.",
	},
	"invalid_global_variable": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3001",
		Number:   3001,
		Name:     "invalid_global_variable",
		Message:  "unknown global variable or service",
		Hint:     "Ensure the global variable is declared as a service or parameter.",
	},
	"duplicate_global": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3002",
		Number:   3002,
		Name:     "duplicate_global",
		Message:  "duplicate global variable",
		Hint:     "Declare each global variable at most once in a routine contract.",
	},
	"transitive_global_missing": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3003",
		Number:   3003,
		Name:     "transitive_global_missing",
		Message:  "transitive global variable accessed by callee must be declared in global contract of caller",
		Hint:     "Add the transitively accessed global to the caller's global contract.",
	},
	"transitive_global_mode_mismatch": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3004",
		Number:   3004,
		Name:     "transitive_global_mode_mismatch",
		Message:  "transitive global variable mode compatibility mismatch",
		Hint:     "Ensure the caller's global mode is compatible with the callee's required mode.",
	},
	"duplicate_dependency_target": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3005",
		Number:   3005,
		Name:     "duplicate_dependency_target",
		Message:  "duplicate dependency target",
		Hint:     "Each dependency target may be specified at most once.",
	},
	"dependency_target_not_allowed": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3006",
		Number:   3006,
		Name:     "dependency_target_not_allowed",
		Message:  "dependency target not allowed or not declared as Output/In_Out",
		Hint:     "Ensure the dependency target is a mutable parameter or global.",
	},
	"dependency_source_not_allowed": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3007",
		Number:   3007,
		Name:     "dependency_source_not_allowed",
		Message:  "dependency source not allowed or not declared as Input/In_Out",
		Hint:     "Ensure the dependency source is a readable parameter or global.",
	},
	"plus_source_not_allowed": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3008",
		Number:   3008,
		Name:     "plus_source_not_allowed",
		Message:  "'+' source is only allowed for parameter/global targets",
		Hint:     "Do not use '+' source for non-parameter/global targets.",
	},
	"undeclared_mutation": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3009",
		Number:   3009,
		Name:     "undeclared_mutation",
		Message:  "target is modified in body but missing from depends clause",
		Hint:     "Add the mutated variable to the depends clause.",
	},
	"unused_target": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3010",
		Number:   3010,
		Name:     "unused_target",
		Message:  "dependency target is not modified in body",
		Hint:     "Ensure the dependency target is mutated in the routine body.",
	},
	"function_missing_result": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3011",
		Number:   3011,
		Name:     "function_missing_result",
		Message:  "function dependency contract must specify 'result'",
		Hint:     "Add a dependency target for 'result' in the depends clause.",
	},
	"dependency_violation": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3012",
		Number:   3012,
		Name:     "dependency_violation",
		Message:  "dependency violation",
		Hint:     "Ensure the variable only depends on declared sources.",
	},
	"aliasing_violation": {
		Severity: "error",
		Phase:    "semantic",
		Category: "semantic",
		Code:     "FH-CON-3013",
		Number:   3013,
		Name:     "aliasing_violation",
		Message:  "aliasing detected in call",
		Hint:     "Avoid passing overlapping mutable references or globals to procedures.",
	},
}

func (d *Diagnostic) Error() string {
	parts := []string{
		fmt.Sprintf("%s: %s", d.Code, d.Message),
		fmt.Sprintf("Location: line %d, column %d", d.Location.Line, d.Location.Column),
	}
	if len(d.Expected) > 0 {
		parts = append(parts, "Expected: "+strings.Join(d.Expected, ", "))
	}
	if d.Found != "" {
		parts = append(parts, "Found: "+d.Found)
	}
	if d.Hint != "" {
		parts = append(parts, "Hint: "+d.Hint)
	}
	return strings.Join(parts, " | ")
}

func ExpectedIdentifier(found token.Token) *Diagnostic {
	return fromCatalog("expected_identifier", found, []string{"identifier"})
}

func ExpectedDeclaration(found token.Token) *Diagnostic {
	if found.Kind == token.Illegal && found.Lexeme == "unterminated block comment" {
		return fromCatalog("unterminated_block_comment", found, []string{"*/"})
	}
	return fromCatalog("expected_declaration", found, []string{"import", "type", "error", "function", "procedure"})
}

func ExpectedStatement(found token.Token) *Diagnostic {
	return fromCatalog("expected_statement", found, []string{"statement"})
}

func ExpectedAssignmentOrCall(found token.Token) *Diagnostic {
	return fromCatalog("expected_assignment_or_call", found, []string{":=", "call"})
}

func ExpectedParameterColon(found token.Token) *Diagnostic {
	return fromCatalog("missing_parameter_colon", found, []string{":"})
}

func MissingReturnType(found token.Token) *Diagnostic {
	return fromCatalog("missing_return_type", found, []string{"type"})
}

func ExpectedExpression(found token.Token) *Diagnostic {
	if diag := illegalTokenDiagnostic(found); diag != nil {
		return diag
	}
	return fromCatalog("expected_expression", found, []string{"expression"})
}

func MissingFunctionEnd(found token.Token) *Diagnostic {
	return fromCatalog("missing_end_function", found, []string{"end"})
}

func MissingProcedureEnd(found token.Token) *Diagnostic {
	return fromCatalog("missing_end_procedure", found, []string{"end"})
}

func MissingIfEnd(found token.Token) *Diagnostic {
	return fromCatalog("missing_end_if", found, []string{"end", "end if"})
}

func MissingWhileEnd(found token.Token) *Diagnostic {
	return fromCatalog("missing_end_while", found, []string{"end", "end while"})
}

func MissingCaseEnd(found token.Token) *Diagnostic {
	return fromCatalog("missing_end_case", found, []string{"end", "end case"})
}

func FieldAccessRequiresRecord(location Location, foundType string, field string) *Diagnostic {
	return fromDefinition("field_access_requires_record", location, foundType, []string{"record before ." + field})
}

func UnknownRecordField(location Location, recordName string, field string) *Diagnostic {
	return fromDefinition("unknown_record_field", location, field, []string{"declared field in " + recordName})
}

func DuplicateRecordLiteralField(location Location, recordName string, field string) *Diagnostic {
	return fromDefinition("duplicate_record_literal_field", location, field, []string{"one assignment for " + recordName + "." + field})
}

func UnknownRecordLiteralField(location Location, recordName string, field string) *Diagnostic {
	return fromDefinition("unknown_record_literal_field", location, field, []string{"declared field in " + recordName})
}

func MissingRecordLiteralField(location Location, recordName string, field string) *Diagnostic {
	return fromDefinition("missing_record_literal_field", location, field, []string{"field assignment in " + recordName + " literal"})
}

func IndexAccessRequiresArray(location Location, foundType string) *Diagnostic {
	return fromDefinition("index_access_requires_array", location, foundType, []string{"Array"})
}

func ArrayIndexRequiresInteger(location Location, foundType string) *Diagnostic {
	return fromDefinition("array_index_requires_integer", location, foundType, []string{"Integer"})
}

func ImportedModuleNotFound(location Location, moduleName string, expectedPath string) *Diagnostic {
	return fromDefinition("imported_module_not_found", location, moduleName, []string{"module file at " + expectedPath})
}

func AmbiguousExposedSymbol(location Location, symbolName string, firstModule string, secondModule string) *Diagnostic {
	return fromDefinition("ambiguous_exposed_symbol", location, symbolName, []string{"unique symbol from either " + firstModule + " or " + secondModule})
}

func ImportCycle(location Location, cycle string) *Diagnostic {
	return fromDefinition("import_cycle", location, cycle, []string{"acyclic import graph"})
}

func ModuleFilePathMismatch(location Location, expectedPath string, actualPath string) *Diagnostic {
	return fromDefinition("module_file_path_mismatch", location, actualPath, []string{expectedPath})
}

func ImportedModuleNameMismatch(location Location, expectedName string, actualName string) *Diagnostic {
	return fromDefinition("imported_module_name_mismatch", location, actualName, []string{expectedName})
}

func UnknownExposedSymbol(location Location, moduleName string, symbolName string) *Diagnostic {
	return fromDefinition("unknown_exposed_symbol", location, symbolName, []string{"declaration in " + moduleName})
}

func ImportedModuleParseError(location Location, moduleName string, cause error) *Diagnostic {
	expected := []string{"parseable module file"}
	if cause != nil {
		expected = append(expected, cause.Error())
	}
	return fromDefinition("imported_module_parse_error", location, moduleName, expected)
}

func UnknownRoutine(location Location, routineName string) *Diagnostic {
	return fromDefinition("unknown_routine", location, routineName, []string{"declared routine"})
}

func RoutineArgumentCountMismatch(location Location, routineName string, expected int, found int) *Diagnostic {
	return fromDefinition("routine_argument_count_mismatch", location, fmt.Sprintf("%d", found), []string{fmt.Sprintf("%d argument(s) for %s", expected, routineName)})
}

func RoutineArgumentTypeMismatch(location Location, routineName string, argumentIndex int, expectedType string, foundType string) *Diagnostic {
	return fromDefinition("routine_argument_type_mismatch", location, foundType, []string{fmt.Sprintf("argument %d as %s for %s", argumentIndex, expectedType, routineName)})
}

func UnknownTypeReference(location Location, typeName string) *Diagnostic {
	return fromDefinition("unknown_type_reference", location, typeName, []string{"known type"})
}

func DuplicateParameterName(location Location, name string) *Diagnostic {
	return fromDefinition("duplicate_parameter_name", location, name, []string{"unique parameter name"})
}

func UnknownAssignmentTarget(location Location, name string) *Diagnostic {
	return fromDefinition("unknown_assignment_target", location, name, []string{"declared local variable"})
}

func AssignmentTypeMismatch(location Location, expectedType string, foundType string) *Diagnostic {
	return fromDefinition("assignment_type_mismatch", location, foundType, []string{expectedType})
}

func DuplicateLocalName(location Location, name string) *Diagnostic {
	return fromDefinition("duplicate_local_name", location, name, []string{"unique local name"})
}

func UnknownVariable(location Location, name string) *Diagnostic {
	return fromDefinition("unknown_variable", location, name, []string{"variable in scope"})
}

func MissingWhileInvariant(found token.Token) *Diagnostic {
	return fromCatalog("missing_while_invariant", found, []string{"invariant"})
}

func MissingCaseDefault(found token.Token) *Diagnostic {
	return fromCatalog("missing_case_default", found, []string{"default"})
}

func ExpectedNumber(found token.Token) *Diagnostic {
	if diag := illegalTokenDiagnostic(found); diag != nil {
		return diag
	}
	return fromCatalog("expected_number", found, []string{"number"})
}

func ExpectedToken(expected token.Kind, found token.Token) *Diagnostic {
	if diag := illegalTokenDiagnostic(found); diag != nil {
		return diag
	}

	name := "expected_token"
	switch expected {
	case token.Module:
		name = "missing_module_declaration"
	case token.End:
		name = "missing_end"
	case token.Colon:
		name = "expected_type_annotation_colon"
	case token.Is:
		if found.Kind == token.Requires {
			name = "invalid_contract_order"
		}
	}
	return fromCatalog(name, found, []string{string(expected)})
}

func illegalTokenDiagnostic(found token.Token) *Diagnostic {
	if found.Kind != token.Illegal {
		return nil
	}

	switch found.Lexeme {
	case "unterminated block comment":
		return fromCatalog("unterminated_block_comment", found, []string{"*/"})
	case "unterminated string":
		return fromCatalog("unterminated_string", found, []string{"\""})
	case "invalid number literal":
		return fromCatalog("invalid_number_literal", found, []string{"number"})
	}

	return nil
}

func fromCatalog(name string, found token.Token, expected []string) *Diagnostic {
	def := catalog[name]
	foundText := string(found.Kind)
	if found.Lexeme != "" {
		foundText = fmt.Sprintf("%s %q", found.Kind, found.Lexeme)
	}
	return &Diagnostic{
		Severity: def.Severity,
		Phase:    def.Phase,
		Category: def.Category,
		Code:     def.Code,
		Number:   def.Number,
		Name:     def.Name,
		Message:  def.Message,
		Location: Location{Line: found.Pos.Line, Column: found.Pos.Column, Offset: found.Pos.Offset},
		Expected: expected,
		Found:    foundText,
		Hint:     def.Hint,
	}
}

func fromDefinition(name string, location Location, found string, expected []string) *Diagnostic {
	def := catalog[name]
	return &Diagnostic{
		Severity: def.Severity,
		Phase:    def.Phase,
		Category: def.Category,
		Code:     def.Code,
		Number:   def.Number,
		Name:     def.Name,
		Message:  def.Message,
		Location: location,
		Expected: expected,
		Found:    found,
		Hint:     def.Hint,
	}
}

func InvalidGlobalVariable(location Location, name string) *Diagnostic {
	return fromDefinition("invalid_global_variable", location, name, []string{"declared service or parameter"})
}

func DuplicateGlobal(location Location, name string) *Diagnostic {
	return fromDefinition("duplicate_global", location, name, []string{"unique global variable"})
}

func TransitiveGlobalMissing(location Location, name string, callee string, caller string) *Diagnostic {
	return fromDefinition("transitive_global_missing", location, name, []string{fmt.Sprintf("transitive global variable '%s' accessed by '%s' must be declared in global contract of '%s'", name, callee, caller)})
}

func TransitiveGlobalModeMismatch(location Location, name string, calleeMode string, caller string, callerMode string) *Diagnostic {
	return fromDefinition("transitive_global_mode_mismatch", location, name, []string{fmt.Sprintf("transitive global variable '%s' with %s mode requires %s mode in '%s'", name, calleeMode, getCompatibleModeDescription(calleeMode), caller)})
}

func getCompatibleModeDescription(mode string) string {
	switch mode {
	case "In_Out":
		return "In_Out"
	case "Output":
		return "Output or In_Out"
	case "Input":
		return "Input or In_Out"
	}
	return "compatible"
}

func DuplicateDependencyTarget(location Location, target string) *Diagnostic {
	return fromDefinition("duplicate_dependency_target", location, target, []string{"unique dependency target"})
}

func DependencyTargetNotAllowed(location Location, target string) *Diagnostic {
	return fromDefinition("dependency_target_not_allowed", location, target, []string{"mutable parameter or global"})
}

func DependencySourceNotAllowed(location Location, source string) *Diagnostic {
	return fromDefinition("dependency_source_not_allowed", location, source, []string{"readable parameter or global"})
}

func PlusSourceNotAllowed(location Location) *Diagnostic {
	return fromDefinition("plus_source_not_allowed", location, "+", []string{"parameter or global target"})
}

func UndeclaredMutation(location Location, target string) *Diagnostic {
	return fromDefinition("undeclared_mutation", location, target, []string{"specified in depends clause"})
}

func UnusedTarget(location Location, target string) *Diagnostic {
	return fromDefinition("unused_target", location, target, []string{"mutated in body"})
}

func FunctionMissingResult(location Location) *Diagnostic {
	return fromDefinition("function_missing_result", location, "result", []string{"result in function depends clause"})
}

func DependencyViolation(location Location, target string, extraSources string) *Diagnostic {
	return fromDefinition("dependency_violation", location, target, []string{fmt.Sprintf("dependency violation: target '%s' depends on undeclared source(s): %s", target, extraSources)})
}

func AliasingViolation(location Location, msg string) *Diagnostic {
	return fromDefinition("aliasing_violation", location, "aliasing", []string{msg})
}
