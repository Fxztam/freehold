package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"freehold-go-frontend/internal/diagnostic"
	"freehold-go-frontend/internal/semantic"
)

type ProjectResult struct {
	EntryFile           string                   `json:"entry_file"`
	EntryModule         string                   `json:"entry_module,omitempty"`
	Modules             []string                 `json:"modules,omitempty"`
	ParseOK             bool                     `json:"parse_ok"`
	SemanticRun         bool                     `json:"semantic_run"`
	SemanticOK          *bool                    `json:"semantic_ok,omitempty"`
	Error               string                   `json:"error,omitempty"`
	SemanticDiagnostics []*diagnostic.Diagnostic `json:"semantic_diagnostics"`
}

func main() {
	outFile := flag.String("out", "", "write JSON result to this file")
	flag.Parse()

	if flag.NArg() != 1 {
		fmt.Println("usage: go-semantic-project [--out <file>] <entry.fh>")
		os.Exit(2)
	}

	entryFile := flag.Arg(0)
	result := run(entryFile)
	if *outFile != "" {
		writeJSON(*outFile, result)
	}

	if result.Error != "" {
		fmt.Println("FAIL", entryFile, "=>", result.Error)
		os.Exit(1)
	}
	if result.SemanticOK != nil && !*result.SemanticOK {
		fmt.Println("FAIL", entryFile, "=>", result.SemanticDiagnostics[0].Error())
		os.Exit(1)
	}

	fmt.Println("OK   ", entryFile)
}

func run(entryFile string) ProjectResult {
	result := ProjectResult{EntryFile: entryFile, SemanticRun: true}
	project, diagnostics, err := semantic.ValidateProject(entryFile)
	if err != nil {
		result.ParseOK = false
		result.Error = err.Error()
		return result
	}

	result.ParseOK = true
	if project != nil {
		result.EntryModule = project.Entry.Name
		result.Modules = project.ModuleNames()
	}
	result.SemanticDiagnostics = diagnostics
	if result.SemanticDiagnostics == nil {
		result.SemanticDiagnostics = []*diagnostic.Diagnostic{}
	}
	semanticOK := len(diagnostics) == 0
	result.SemanticOK = &semanticOK
	if !semanticOK {
		result.Error = diagnostics[0].Error()
	}
	return result
}

func writeJSON(path string, value interface{}) {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile(path, data, 0644); err != nil {
		panic(err)
	}
}
