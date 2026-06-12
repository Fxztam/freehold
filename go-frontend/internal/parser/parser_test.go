package parser

import (
	"testing"

	"freehold-go-frontend/internal/ast"
	"freehold-go-frontend/internal/lexer"
	"freehold-go-frontend/internal/token"
)

func parseModuleForTest(t *testing.T, source string) *ast.Module {
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

	parser := New(tokens)
	module, err := parser.ParseModule()
	if err != nil {
		t.Fatalf("ParseModule() error = %v", err)
	}
	return module
}

func TestParseResultKeywordFieldAccess(t *testing.T) {
	module := parseModuleForTest(t, `module ResultKeywordFields

error LookupFailed

function load() returns Result<String, LookupFailed>
is
    return ok "value"
end load

procedure main()
is
    let result: Result<String, LookupFailed> = load()
    check result.ok
    check result.value = "value"
    check result.error = ""
end main

end ResultKeywordFields`)

	if len(module.Declarations) != 3 {
		t.Fatalf("declaration count = %d, want 3", len(module.Declarations))
	}
	procedure, ok := module.Declarations[2].(ast.ProcedureDecl)
	if !ok {
		t.Fatalf("third declaration = %T, want ast.ProcedureDecl", module.Declarations[2])
	}
	fields := []string{"ok", "value", "error"}
	for index, field := range fields {
		stmt, ok := procedure.Body[index+1].(ast.CheckStmt)
		if !ok {
			t.Fatalf("body[%d] = %T, want ast.CheckStmt", index+1, procedure.Body[index+1])
		}
		access, ok := leftmostFieldAccess(stmt.Condition)
		if !ok {
			t.Fatalf("body[%d] condition = %T, want or contain ast.FieldAccessExpr", index+1, stmt.Condition)
		}
		if access.Field != field {
			t.Fatalf("body[%d] field = %q, want %q", index+1, access.Field, field)
		}
	}
}

func TestParseAnnotations(t *testing.T) {
	module := parseModuleForTest(t, `module AnnotationSyntax

type Person is record
    first_name: String @json("firstName")
end record

@ffi("freehold.local/shim", "Lookup")
function lookup() returns Result<Person, LookupFailed>
is
end lookup

error LookupFailed

end AnnotationSyntax`)

	if len(module.Declarations) != 3 {
		t.Fatalf("declaration count = %d, want 3", len(module.Declarations))
	}
	if _, ok := module.Declarations[0].(ast.TypeDecl); !ok {
		t.Fatalf("first declaration = %T, want ast.TypeDecl", module.Declarations[0])
	}
	if _, ok := module.Declarations[1].(ast.FunctionDecl); !ok {
		t.Fatalf("second declaration = %T, want ast.FunctionDecl", module.Declarations[1])
	}
}

func leftmostFieldAccess(expr ast.Expr) (ast.FieldAccessExpr, bool) {
	switch typed := expr.(type) {
	case ast.FieldAccessExpr:
		return typed, true
	case ast.BinaryExpr:
		return leftmostFieldAccess(typed.Left)
	default:
		return ast.FieldAccessExpr{}, false
	}
}
