package semantic

import (
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

func TestValidateModuleAcceptsNestedRecordFieldAccess(t *testing.T) {
	module := parseModule(t, `module NestedRecordFieldAccess

type Address is record
    city_id: Integer
end record

type Customer is record
    id: Integer
    address: Address
end record

procedure main()
is
    let address: Address = Address { city_id: 7 }
    let customer: Customer = Customer { id: 1, address: address }
    check customer.address.city_id = 7
end main

end NestedRecordFieldAccess`)

	diagnostics := ValidateModule(module)
	if len(diagnostics) != 0 {
		t.Fatalf("ValidateModule() diagnostics = %#v, want none", diagnostics)
	}
}

func TestValidateModuleRejectsFieldAccessOnScalar(t *testing.T) {
	module := parseModule(t, `module FieldAccessOnScalar

procedure main()
is
    let amount: Integer = 1
    check amount.id = 1
end main

end FieldAccessOnScalar`)

	diagnostics := ValidateModule(module)
	if len(diagnostics) != 1 {
		t.Fatalf("ValidateModule() diagnostics count = %d, want 1", len(diagnostics))
	}
	diag := diagnostics[0]
	if diag.Code != "FH-TYP-2101" || diag.Name != "field_access_requires_record" {
		t.Fatalf("diagnostic = %s/%s, want FH-TYP-2101/field_access_requires_record", diag.Code, diag.Name)
	}
	if diag.Found != "Integer" {
		t.Fatalf("diagnostic Found = %q, want Integer", diag.Found)
	}
	if len(diag.Expected) != 1 || diag.Expected[0] != "record before .id" {
		t.Fatalf("diagnostic Expected = %#v, want record before .id", diag.Expected)
	}
}

func TestValidateModuleRejectsUnknownRecordField(t *testing.T) {
	module := parseModule(t, `module UnknownFieldAccess

type Account is record
    id: Integer
end record

procedure main()
is
    let account: Account = Account { id: 1 }
    check account.active
end main

end UnknownFieldAccess`)

	diagnostics := ValidateModule(module)
	if len(diagnostics) != 1 {
		t.Fatalf("ValidateModule() diagnostics count = %d, want 1", len(diagnostics))
	}
	diag := diagnostics[0]
	if diag.Code != "FH-SEM-1105" || diag.Name != "unknown_record_field" {
		t.Fatalf("diagnostic = %s/%s, want FH-SEM-1105/unknown_record_field", diag.Code, diag.Name)
	}
	if diag.Found != "active" {
		t.Fatalf("diagnostic Found = %q, want active", diag.Found)
	}
	if len(diag.Expected) != 1 || diag.Expected[0] != "declared field in Account" {
		t.Fatalf("diagnostic Expected = %#v, want declared field in Account", diag.Expected)
	}
}

func TestBuildSymbolTableRecordsFields(t *testing.T) {
	module := parseModule(t, `module Records

type Address is record
    city_id: Integer
end record

type Customer is record
    address: Address
end record

end Records`)

	symbols := BuildSymbolTable(module)
	address, ok := symbols.Records["Address"]
	if !ok {
		t.Fatal("Address record missing from symbol table")
	}
	if address.Fields["city_id"] != "Integer" {
		t.Fatalf("Address.city_id type = %q, want Integer", address.Fields["city_id"])
	}
	customer := symbols.Records["Customer"]
	if customer.Fields["address"] != "Address" {
		t.Fatalf("Customer.address type = %q, want Address", customer.Fields["address"])
	}
}
