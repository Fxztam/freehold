package semantic

import (
	"path/filepath"
	"testing"
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

func fixtureEntry(t *testing.T, name string) string {
	t.Helper()
	return filepath.Join("..", "..", "..", "tests", "language_modules", "03_import_resolution", "fixtures", "valid", name, "App", "Main.fh")
}
