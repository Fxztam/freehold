package whyml

import (
	"strings"
	"testing"

	"freehold-go-frontend/internal/ast"
	"freehold-go-frontend/internal/lexer"
	"freehold-go-frontend/internal/parser"
	"freehold-go-frontend/internal/token"
)

func parseModule(t *testing.T, source string) *ast.Module {
	t.Helper()

	lex := lexer.New(source)
	var tokens []token.Token
	for {
		tok := lex.Next()
		tokens = append(tokens, tok)
		if tok.Kind == token.EOF {
			break
		}
	}

	p := parser.New(tokens)
	module, err := p.ParseModule()
	if err != nil {
		t.Fatalf("ParseModule() error = %v", err)
	}
	return module
}

func TestWhyMLGeneratorSimple(t *testing.T) {
	module := parseModule(t, `module FlowContractsPos

procedure modify_param(x: Integer, y: Integer)
global Input x, In_Out y
depends y => x
is
    y := x
end modify_param

procedure modify_both(x: Integer, y: Integer)
depends x => (x, y), y => (x, +)
is
    x := x + y
    y := x
end modify_both

function add_one(x: Integer) returns Integer
depends result => x
is
    return x + 1
end add_one

end FlowContractsPos`)

	gen := NewGenerator(module)
	output := gen.Generate()

	// Verify modify_param
	if !strings.Contains(output, "let modify_param (x: int) (y: ref int) : unit") {
		t.Errorf("Expected modify_param declaration not found. Got:\n%s", output)
	}
	if !strings.Contains(output, "y := x") {
		t.Errorf("Expected assignment y := x not found. Got:\n%s", output)
	}

	// Verify modify_both
	if !strings.Contains(output, "let modify_both (x: ref int) (y: ref int) : unit") {
		t.Errorf("Expected modify_both declaration not found. Got:\n%s", output)
	}
	if !strings.Contains(output, "x := (!x + !y)") {
		t.Errorf("Expected assignment x := (!x + !y) not found. Got:\n%s", output)
	}

	// Verify add_one Exception handling
	if !strings.Contains(output, "exception Return int") {
		t.Errorf("Expected Return exception not found. Got:\n%s", output)
	}
	if !strings.Contains(output, "raise (Return ((x + 1)))") {
		t.Errorf("Expected raise Return not found. Got:\n%s", output)
	}
}

func TestWhyMLGeneratorQuantifiersAndArrays(t *testing.T) {
	module := parseModule(t, `module QuantifierTest

type ArrayOfInt is record
    data: Array<Integer, 10>
end record

function all_positive(arr: Array<Integer, 10>, len: Integer) returns Boolean
requires for all i in 0 .. 9 => arr[i] > 0
ensures for some i in 0 .. 9 => arr[i] = 100
is
    return true
end all_positive

end QuantifierTest`)

	gen := NewGenerator(module)
	output := gen.Generate()

	// Verify quantifiers conversion
	if !strings.Contains(output, "forall i: int. 0 <= i <= 9 ->") {
		t.Errorf("Expected forall quantifier translation not found. Got:\n%s", output)
	}
	if !strings.Contains(output, "exists i: int. 0 <= i <= 9 &&") {
		t.Errorf("Expected exists quantifier translation not found. Got:\n%s", output)
	}
}
