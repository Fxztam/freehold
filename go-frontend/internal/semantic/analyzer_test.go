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
	if diag.Location.Line != 6 || diag.Location.Column != 11 {
		t.Fatalf("diagnostic Location = line %d, column %d, want line 6, column 11", diag.Location.Line, diag.Location.Column)
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
	if diag.Location.Line != 10 || diag.Location.Column != 11 {
		t.Fatalf("diagnostic Location = line %d, column %d, want line 10, column 11", diag.Location.Line, diag.Location.Column)
	}
	if len(diag.Expected) != 1 || diag.Expected[0] != "declared field in Account" {
		t.Fatalf("diagnostic Expected = %#v, want declared field in Account", diag.Expected)
	}
}

func TestValidateModuleRejectsUnknownRoutine(t *testing.T) {
	module := parseModule(t, `module UnknownRoutineCall

procedure main()
is
    call missing()
end main

end UnknownRoutineCall`)

	diagnostics := ValidateModule(module)
	if len(diagnostics) != 1 {
		t.Fatalf("ValidateModule() diagnostics count = %d, want 1", len(diagnostics))
	}
	diag := diagnostics[0]
	if diag.Code != "FH-SEM-1204" || diag.Name != "unknown_routine" {
		t.Fatalf("diagnostic = %s/%s, want FH-SEM-1204/unknown_routine", diag.Code, diag.Name)
	}
	if diag.Found != "missing" {
		t.Fatalf("diagnostic Found = %q, want missing", diag.Found)
	}
	if diag.Location.Line != 5 || diag.Location.Column != 5 {
		t.Fatalf("diagnostic Location = line %d, column %d, want line 5, column 5", diag.Location.Line, diag.Location.Column)
	}
}

func TestValidateModuleRejectsRoutineArgumentCountMismatch(t *testing.T) {
	module := parseModule(t, `module WrongArgumentCount

function add(left: Integer, right: Integer) returns Integer
is
    return left + right
end add

procedure main()
is
    check add(1) = 1
end main

end WrongArgumentCount`)

	diagnostics := ValidateModule(module)
	if len(diagnostics) != 1 {
		t.Fatalf("ValidateModule() diagnostics count = %d, want 1", len(diagnostics))
	}
	diag := diagnostics[0]
	if diag.Code != "FH-SEM-1205" || diag.Name != "routine_argument_count_mismatch" {
		t.Fatalf("diagnostic = %s/%s, want FH-SEM-1205/routine_argument_count_mismatch", diag.Code, diag.Name)
	}
	if diag.Found != "1" {
		t.Fatalf("diagnostic Found = %q, want 1", diag.Found)
	}
	if len(diag.Expected) != 1 || diag.Expected[0] != "2 argument(s) for add" {
		t.Fatalf("diagnostic Expected = %#v, want 2 argument(s) for add", diag.Expected)
	}
	if diag.Location.Line != 10 || diag.Location.Column != 11 {
		t.Fatalf("diagnostic Location = line %d, column %d, want line 10, column 11", diag.Location.Line, diag.Location.Column)
	}
}

func TestValidateModuleRejectsRoutineArgumentTypeMismatch(t *testing.T) {
	module := parseModule(t, `module WrongArgumentType

function negate(flag: Boolean) returns Boolean
is
    return not flag
end negate

procedure main()
is
    check negate(1)
end main

end WrongArgumentType`)

	diagnostics := ValidateModule(module)
	if len(diagnostics) != 1 {
		t.Fatalf("ValidateModule() diagnostics count = %d, want 1", len(diagnostics))
	}
	diag := diagnostics[0]
	if diag.Code != "FH-TYP-2201" || diag.Name != "routine_argument_type_mismatch" {
		t.Fatalf("diagnostic = %s/%s, want FH-TYP-2201/routine_argument_type_mismatch", diag.Code, diag.Name)
	}
	if diag.Found != "Integer" {
		t.Fatalf("diagnostic Found = %q, want Integer", diag.Found)
	}
	if len(diag.Expected) != 1 || diag.Expected[0] != "argument 1 as Boolean for negate" {
		t.Fatalf("diagnostic Expected = %#v, want argument 1 as Boolean for negate", diag.Expected)
	}
	if diag.Location.Line != 10 || diag.Location.Column != 18 {
		t.Fatalf("diagnostic Location = line %d, column %d, want line 10, column 18", diag.Location.Line, diag.Location.Column)
	}
}

func TestValidateModuleWithImportsAcceptsImportedNestedRecordFieldAccess(t *testing.T) {
	typesModule := parseModule(t, `module Domain.Types

type Address is record
    city_id: Integer
end record

type Customer is record
    id: Integer
    address: Address
end record

function make_address(city_id: Integer) returns Address
is
    return Address { city_id: city_id }
end make_address

function make_customer(id: Integer, address: Address) returns Customer
is
    return Customer { id: id, address: address }
end make_customer

end Domain.Types`)

	shipmentsModule := parseModule(t, `module Domain.Shipments

import Domain.Types exposing Address, Customer, make_address, make_customer

type Shipment is record
    customer: Customer
    destination: Address
end record

function make_shipment(id: Integer, city_id: Integer) returns Shipment
is
    let destination: Address = make_address(city_id)
    let customer: Customer = make_customer(id, destination)
    return Shipment { customer: customer, destination: destination }
end make_shipment

end Domain.Shipments`)

	appModule := parseModule(t, `module App.Main

import Domain.Shipments exposing Shipment, make_shipment

type Address is record
    label: String
end record

procedure main()
is
    let shipment: Shipment = make_shipment(1001, 42)
    check shipment.customer.id = 1001
	check make_shipment(1001, 42).customer.address.city_id = 42
    check shipment.customer.address.city_id = shipment.destination.city_id
end main

end App.Main`)

	diagnostics := ValidateModuleWithImports(appModule, typesModule, shipmentsModule)
	if len(diagnostics) != 0 {
		t.Fatalf("ValidateModuleWithImports() diagnostics = %#v, want none", diagnostics)
	}
}

func TestValidateModuleWithImportsRejectsImportedRoutineArgumentTypeMismatch(t *testing.T) {
	domainModule := parseModule(t, `module Domain.Math

function negate(flag: Boolean) returns Boolean
is
    return not flag
end negate

end Domain.Math`)

	appModule := parseModule(t, `module App.Main

import Domain.Math exposing negate

procedure main()
is
    check negate(1)
end main

end App.Main`)

	diagnostics := ValidateModuleWithImports(appModule, domainModule)
	if len(diagnostics) != 1 {
		t.Fatalf("ValidateModuleWithImports() diagnostics count = %d, want 1", len(diagnostics))
	}
	diag := diagnostics[0]
	if diag.Code != "FH-TYP-2201" || diag.Name != "routine_argument_type_mismatch" {
		t.Fatalf("diagnostic = %s/%s, want FH-TYP-2201/routine_argument_type_mismatch", diag.Code, diag.Name)
	}
	if diag.Found != "Integer" {
		t.Fatalf("diagnostic Found = %q, want Integer", diag.Found)
	}
}

func TestValidateModuleWithImportsRejectsUnknownFieldOnImportedRecord(t *testing.T) {
	domainModule := parseModule(t, `module Domain.Types

type Account is record
    id: Integer
end record

end Domain.Types`)

	appModule := parseModule(t, `module App.Main

import Domain.Types exposing Account

procedure main()
is
    let account: Account = Account { id: 1 }
    check account.active
end main

end App.Main`)

	diagnostics := ValidateModuleWithImports(appModule, domainModule)
	if len(diagnostics) != 1 {
		t.Fatalf("ValidateModuleWithImports() diagnostics count = %d, want 1", len(diagnostics))
	}
	diag := diagnostics[0]
	if diag.Code != "FH-SEM-1105" || diag.Name != "unknown_record_field" {
		t.Fatalf("diagnostic = %s/%s, want FH-SEM-1105/unknown_record_field", diag.Code, diag.Name)
	}
	if diag.Found != "active" {
		t.Fatalf("diagnostic Found = %q, want active", diag.Found)
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

func TestBuildSymbolTableWithImportsIncludesTransitiveRecordDependencies(t *testing.T) {
	typesModule := parseModule(t, `module Domain.Types

type Address is record
    city_id: Integer
end record

type Customer is record
    address: Address
end record

end Domain.Types`)

	shipmentsModule := parseModule(t, `module Domain.Shipments

import Domain.Types exposing Address, Customer

type Shipment is record
    customer: Customer
end record

end Domain.Shipments`)

	appModule := parseModule(t, `module App.Main

import Domain.Shipments exposing Shipment

type Address is record
    label: String
end record

end App.Main`)

	symbols := BuildSymbolTableWithImports(appModule, typesModule, shipmentsModule)
	if _, ok := symbols.Records["Shipment"]; !ok {
		t.Fatal("Shipment record missing from import-aware symbol table")
	}
	if _, ok := symbols.Records["Customer"]; !ok {
		t.Fatal("Customer dependency missing from import-aware symbol table")
	}
	if _, ok := symbols.Records["Address"]; !ok {
		t.Fatal("local Address record missing from import-aware symbol table")
	}
	if _, ok := symbols.Records["Domain.Types.Address"]; !ok {
		t.Fatal("qualified Address transitive dependency missing from import-aware symbol table")
	}
}
