package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"freehold-go-frontend/internal/lexer"
	"freehold-go-frontend/internal/parser"
	"freehold-go-frontend/internal/token"
)

type ParseResult struct {
	SourceFile string      `json:"source_file"`
	ModuleName string      `json:"module_name"`
	CaseKind   string      `json:"case_kind"`
	ParseOK    bool        `json:"parse_ok"`
	AST        interface{} `json:"ast,omitempty"`
	Error      string      `json:"error,omitempty"`
}

func main() {
	stopAfterFirst := flag.Bool("stop-after-first", false, "stop after the first parsed test case")
	outRoot := flag.String("out", "", "write JSON results under this directory instead of next to the language module tests")
	flag.Parse()

	if flag.NArg() < 1 {
		fmt.Println("usage: freehold-parse-language-modules [--out <output-dir>] <path-to-language_modules>")
		os.Exit(2)
	}

	root := flag.Arg(0)

	moduleDirs, err := os.ReadDir(root)
	if err != nil {
		panic(err)
	}

	total := 0
	okCount := 0
	failCount := 0

	for _, entry := range moduleDirs {
		if !entry.IsDir() {
			continue
		}

		moduleName := entry.Name()
		if !looksLikeNumberedModule(moduleName) {
			continue
		}

		modulePath := filepath.Join(root, moduleName)

		caseDirs := []string{
			"valid",
			"invalid_syntax",
			"invalid_semantics",
		}

		for _, caseKind := range caseDirs {
			casePath := filepath.Join(modulePath, caseKind)

			if !dirExists(casePath) {
				continue
			}

			files, err := filepath.Glob(filepath.Join(casePath, "*.fh"))
			if err != nil {
				fmt.Println("Glob error:", err)
				continue
			}

			outDir := outputDir(*outRoot, modulePath, moduleName, caseKind)
			if err := os.MkdirAll(outDir, 0755); err != nil {
				panic(err)
			}

			for _, file := range files {
				total++

				result := parseFile(file, moduleName, caseKind)

				base := strings.TrimSuffix(filepath.Base(file), filepath.Ext(file))
				outFile := filepath.Join(outDir, base+".json")

				writeJSON(outFile, result)

				if result.ParseOK {
					okCount++
					fmt.Println("OK   ", moduleName, caseKind, filepath.Base(file))
				} else {
					failCount++
					fmt.Println("FAIL ", moduleName, caseKind, filepath.Base(file), "=>", result.Error)
				}

				fmt.Println("WRITE", outFile)

				if *stopAfterFirst {
					fmt.Println()
					fmt.Println("--stop-after-first: Testlauf nach erstem Parsing beendet.")
					printSummary(total, okCount, failCount)
					return
				}
			}
		}
	}

	printSummary(total, okCount, failCount)
}

func outputDir(outRoot string, modulePath string, moduleName string, caseKind string) string {
	if outRoot != "" {
		return filepath.Join(outRoot, moduleName, caseKind)
	}

	return filepath.Join(modulePath, "go-generated-ast", caseKind)
}

func parseFile(file string, moduleName string, caseKind string) (result ParseResult) {
	result = ParseResult{
		SourceFile: file,
		ModuleName: moduleName,
		CaseKind:   caseKind,
	}

	defer func() {
		if r := recover(); r != nil {
			result.ParseOK = false
			result.Error = fmt.Sprint(r)
		}
	}()

	sourceBytes, err := os.ReadFile(file)
	if err != nil {
		result.ParseOK = false
		result.Error = err.Error()
		return result
	}

	source := string(sourceBytes)

	l := lexer.New(source)

	var toks []token.Token
	for {
		tok := l.Next()
		toks = append(toks, tok)

		if tok.Kind == token.EOF {
			break
		}
	}

	p := parser.New(toks)

	mod, err := p.ParseModule()
	if err != nil {
		result.ParseOK = false
		result.Error = err.Error()
		return result
	}

	result.ParseOK = true
	result.AST = mod

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

func printSummary(total int, okCount int, failCount int) {
	fmt.Println()
	fmt.Println("Summary")
	fmt.Println("-------")
	fmt.Println("Total:", total)
	fmt.Println("OK:   ", okCount)
	fmt.Println("FAIL: ", failCount)
}

func looksLikeNumberedModule(name string) bool {
	return len(name) >= 3 &&
		name[0] >= '0' &&
		name[0] <= '9' &&
		name[1] >= '0' &&
		name[1] <= '9' &&
		name[2] == '_'
}

func dirExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}
