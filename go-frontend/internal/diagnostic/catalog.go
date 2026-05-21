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

func MissingWhileInvariant(found token.Token) *Diagnostic {
	return fromCatalog("missing_while_invariant", found, []string{"invariant"})
}

func MissingCaseDefault(found token.Token) *Diagnostic {
	return fromCatalog("missing_case_default", found, []string{"default"})
}

func ExpectedNumber(found token.Token) *Diagnostic {
	return fromCatalog("expected_number", found, []string{"number"})
}

func ExpectedToken(expected token.Kind, found token.Token) *Diagnostic {
	if found.Kind == token.Illegal && found.Lexeme == "unterminated block comment" {
		return fromCatalog("unterminated_block_comment", found, []string{"*/"})
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
