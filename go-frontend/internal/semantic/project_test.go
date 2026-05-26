package semantic

import (
	"os"
	"path/filepath"
	"testing"

	"freehold-go-frontend/internal/diagnostic"
)

func TestLoadProjectResolvesImportedModules(t *testing.T) {
	entry := fixtureEntry(t, "import_nested_record_field_access")

	project, err := LoadProject(entry)
	if err != nil {
		t.Fatalf("LoadProject() error = %v", err)
	}

	wantModules := []string{"App.Main", "Domain.Shipments", "Domain.Types"}
	gotModules := project.ModuleNames()
	if len(gotModules) != len(wantModules) {
		t.Fatalf("ModuleNames() = %#v, want %#v", gotModules, wantModules)
	}
	for index, want := range wantModules {
		if gotModules[index] != want {
			t.Fatalf("ModuleNames()[%d] = %q, want %q", index, gotModules[index], want)
		}
	}
}

func TestValidateProjectAcceptsImportedNestedRecordFieldAccess(t *testing.T) {
	entry := fixtureEntry(t, "import_nested_record_field_access")

	_, diagnostics, err := ValidateProject(entry)
	if err != nil {
		t.Fatalf("ValidateProject() error = %v", err)
	}
	if len(diagnostics) != 0 {
		t.Fatalf("ValidateProject() diagnostics = %#v, want none", diagnostics)
	}
}

func TestValidateProjectRejectsMissingImportedModule(t *testing.T) {
	root := t.TempDir()
	entry := writeProjectFile(t, root, "App", "Main.fh", `module App.Main

import Domain.Missing exposing Account

procedure main()
is
    check true
end main

end App.Main`)

	_, diagnostics, err := ValidateProject(entry)
	assertProjectDiagnostic(t, diagnostics, err, "FH-SEM-1006", "imported_module_not_found", "Domain.Missing")
}

func TestValidateProjectRejectsImportCycle(t *testing.T) {
	root := t.TempDir()
	entry := writeProjectFile(t, root, "App", "Main.fh", `module App.Main

import Domain.A exposing ping

procedure main()
is
    call ping()
end main

end App.Main`)
	writeProjectFile(t, root, "Domain", "A.fh", `module Domain.A

import Domain.B exposing pong

procedure ping()
is
    call pong()
end ping

end Domain.A`)
	writeProjectFile(t, root, "Domain", "B.fh", `module Domain.B

import Domain.A exposing ping

procedure pong()
is
    call ping()
end pong

end Domain.B`)

	_, diagnostics, err := ValidateProject(entry)
	assertProjectDiagnostic(t, diagnostics, err, "FH-SEM-1007", "import_cycle", "App.Main -> Domain.A -> Domain.B -> Domain.A")
}

func TestValidateProjectRejectsEntryModulePathMismatch(t *testing.T) {
	root := t.TempDir()
	entry := writeProjectFile(t, root, "App", "Main.fh", `module App.Other

procedure main()
is
    check true
end main

end App.Other`)

	_, diagnostics, err := ValidateProject(entry)
	assertProjectDiagnostic(t, diagnostics, err, "FH-SEM-1008", "module_file_path_mismatch", entry)
}

func TestValidateProjectRejectsImportedModuleNameMismatch(t *testing.T) {
	root := t.TempDir()
	entry := writeProjectFile(t, root, "App", "Main.fh", `module App.Main

import Domain.Types exposing Account

procedure main()
is
    check true
end main

end App.Main`)
	writeProjectFile(t, root, "Domain", "Types.fh", `module Domain.Other

type Account is record
    id: Integer
end record

end Domain.Other`)

	_, diagnostics, err := ValidateProject(entry)
	assertProjectDiagnostic(t, diagnostics, err, "FH-SEM-1009", "imported_module_name_mismatch", "Domain.Other")
}

func TestValidateProjectRejectsImportedModuleParseError(t *testing.T) {
	root := t.TempDir()
	entry := writeProjectFile(t, root, "App", "Main.fh", `module App.Main

import Domain.Types

procedure main()
is
    check true
end main

end App.Main`)
	writeProjectFile(t, root, "Domain", "Types.fh", `module Domain.Types

procedure broken

end Domain.Types`)

	_, diagnostics, err := ValidateProject(entry)
	assertProjectDiagnostic(t, diagnostics, err, "FH-SEM-1011", "imported_module_parse_error", "Domain.Types")
}

func TestValidateProjectRejectsUnknownExposedSymbol(t *testing.T) {
	root := t.TempDir()
	entry := writeProjectFile(t, root, "App", "Main.fh", `module App.Main

import Domain.Types exposing Missing

procedure main()
is
    check true
end main

end App.Main`)
	writeProjectFile(t, root, "Domain", "Types.fh", `module Domain.Types

type Account is record
    id: Integer
end record

end Domain.Types`)

	_, diagnostics, err := ValidateProject(entry)
	assertProjectDiagnostic(t, diagnostics, err, "FH-SEM-1010", "unknown_exposed_symbol", "Missing")
}

func TestValidateProjectRejectsAmbiguousExposedSymbol(t *testing.T) {
	root := t.TempDir()
	entry := writeProjectFile(t, root, "App", "Main.fh", `module App.Main

import Domestic.Orders exposing load_order
import Partner.Orders exposing load_order

procedure main()
is
    call load_order()
end main

end App.Main`)
	writeProjectFile(t, root, "Domestic", "Orders.fh", `module Domestic.Orders

procedure load_order()
is
end load_order

end Domestic.Orders`)
	writeProjectFile(t, root, "Partner", "Orders.fh", `module Partner.Orders

procedure load_order()
is
end load_order

end Partner.Orders`)

	_, diagnostics, err := ValidateProject(entry)
	assertProjectDiagnostic(t, diagnostics, err, "FH-SEM-1005", "ambiguous_exposed_symbol", "load_order")
}

func TestValidateProjectRejectsRoutineHiddenByImportExposing(t *testing.T) {
	root := t.TempDir()
	entry := writeProjectFile(t, root, "App", "Main.fh", `module App.Main

import Domain.Math

procedure main()
is
    call negate(true)
end main

end App.Main`)
	writeProjectFile(t, root, "Domain", "Math.fh", `module Domain.Math

procedure negate(flag: Boolean)
is
end negate

end Domain.Math`)

	_, diagnostics, err := ValidateProject(entry)
	assertProjectDiagnostic(t, diagnostics, err, "FH-SEM-1204", "unknown_routine", "negate")
}

func TestValidateProjectRejectsWrongQualifiedModuleRoutine(t *testing.T) {
	root := t.TempDir()
	entry := writeProjectFile(t, root, "App", "Main.fh", `module App.Main

import Domestic.Orders

procedure main()
is
    call Partner.Orders.load_order()
end main

end App.Main`)
	writeProjectFile(t, root, "Domestic", "Orders.fh", `module Domestic.Orders

procedure load_order()
is
end load_order

end Domestic.Orders`)

	_, diagnostics, err := ValidateProject(entry)
	assertProjectDiagnostic(t, diagnostics, err, "FH-SEM-1204", "unknown_routine", "Partner.Orders.load_order")
}

func fixtureEntry(t *testing.T, name string) string {
	t.Helper()
	return filepath.Join("..", "..", "..", "tests", "language_modules", "03_import_resolution", "fixtures", "valid", name, "App", "Main.fh")
}

func writeProjectFile(t *testing.T, root string, dir string, name string, source string) string {
	t.Helper()
	path := filepath.Join(root, dir, name)
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		t.Fatalf("MkdirAll() error = %v", err)
	}
	if err := os.WriteFile(path, []byte(source), 0644); err != nil {
		t.Fatalf("WriteFile() error = %v", err)
	}
	return path
}

func assertProjectDiagnostic(t *testing.T, diagnostics []*diagnostic.Diagnostic, err error, code string, name string, found string) {
	t.Helper()
	if err != nil {
		t.Fatalf("ValidateProject() error = %v", err)
	}
	if len(diagnostics) != 1 {
		t.Fatalf("ValidateProject() diagnostics count = %d, want 1: %#v", len(diagnostics), diagnostics)
	}
	diag := diagnostics[0]
	if diag.Code != code || diag.Name != name {
		t.Fatalf("diagnostic = %s/%s, want %s/%s", diag.Code, diag.Name, code, name)
	}
	if diag.Found != found {
		t.Fatalf("diagnostic Found = %q, want %q", diag.Found, found)
	}
}
