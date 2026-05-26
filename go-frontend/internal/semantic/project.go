package semantic

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"freehold-go-frontend/internal/ast"
	"freehold-go-frontend/internal/diagnostic"
	"freehold-go-frontend/internal/lexer"
	"freehold-go-frontend/internal/parser"
	"freehold-go-frontend/internal/token"
)

type Project struct {
	Root    string
	Entry   *ast.Module
	Modules map[string]*ast.Module
	Files   map[string]string
}

type ProjectLoadError struct {
	Diagnostic *diagnostic.Diagnostic
}

func (e *ProjectLoadError) Error() string {
	if e == nil || e.Diagnostic == nil {
		return "project load error"
	}
	return e.Diagnostic.Error()
}

var runtimeModules = map[string]bool{
	"Json":   true,
	"Math":   true,
	"Std.IO": true,
	"String": true,
}

func LoadProject(entryFile string) (*Project, error) {
	entryPath, err := filepath.Abs(entryFile)
	if err != nil {
		return nil, err
	}

	entryModule, err := parseModuleFile(entryPath)
	if err != nil {
		return nil, err
	}

	root, err := inferProjectRoot(entryPath, entryModule.Name)
	if err != nil {
		return nil, err
	}

	expectedPath := modulePath(root, entryModule.Name)
	if !samePath(expectedPath, entryPath) {
		return nil, projectDiagnostic(diagnostic.ModuleFilePathMismatch(locationFromPosition(entryModule.Pos), expectedPath, entryPath))
	}

	project := &Project{
		Root:    root,
		Entry:   entryModule,
		Modules: map[string]*ast.Module{entryModule.Name: entryModule},
		Files:   map[string]string{entryModule.Name: entryPath},
	}
	if err := project.resolveImports(entryModule, []string{entryModule.Name}); err != nil {
		return nil, err
	}
	return project, nil
}

func ValidateProject(entryFile string) (*Project, []*diagnostic.Diagnostic, error) {
	project, err := LoadProject(entryFile)
	if err != nil {
		var loadErr *ProjectLoadError
		if errors.As(err, &loadErr) {
			return nil, []*diagnostic.Diagnostic{loadErr.Diagnostic}, nil
		}
		return nil, nil, err
	}

	imports := make([]*ast.Module, 0, len(project.Modules)-1)
	for name, module := range project.Modules {
		if name != project.Entry.Name {
			imports = append(imports, module)
		}
	}

	if diagnostics := project.ambiguousExposedDiagnostics(project.Entry); len(diagnostics) > 0 {
		return project, diagnostics, nil
	}

	diagnostics := project.qualifiedCallDiagnostics(project.Entry)
	diagnostics = append(diagnostics, ValidateModuleWithImports(project.Entry, imports...)...)
	return project, diagnostics, nil
}

func (p *Project) ModuleNames() []string {
	names := make([]string, 0, len(p.Modules))
	for name := range p.Modules {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func (p *Project) resolveImports(module *ast.Module, stack []string) error {
	for _, decl := range module.Declarations {
		importDecl, ok := decl.(ast.ImportDecl)
		if !ok {
			continue
		}

		moduleName := importDecl.Module
		if runtimeModules[moduleName] {
			continue
		}
		if contains(stack, moduleName) {
			cycle := strings.Join(append(stack, moduleName), " -> ")
			return projectDiagnostic(diagnostic.ImportCycle(locationFromPosition(importDecl.Pos), cycle))
		}

		imported, ok := p.Modules[moduleName]
		if !ok {
			path := modulePath(p.Root, moduleName)
			if _, err := os.Stat(path); err != nil {
				return projectDiagnostic(diagnostic.ImportedModuleNotFound(locationFromPosition(importDecl.Pos), moduleName, path))
			}
			parsed, err := parseModuleFile(path)
			if err != nil {
				return projectDiagnostic(diagnostic.ImportedModuleParseError(locationFromPosition(importDecl.Pos), moduleName, err))
			}
			if parsed.Name != moduleName {
				return projectDiagnostic(diagnostic.ImportedModuleNameMismatch(locationFromPosition(parsed.Pos), moduleName, parsed.Name))
			}
			p.Modules[moduleName] = parsed
			p.Files[moduleName] = path
			imported = parsed
		}

		if missing := missingExposedSymbols(imported, importDecl.Exposing); len(missing) > 0 {
			return projectDiagnostic(diagnostic.UnknownExposedSymbol(locationFromPosition(importDecl.Pos), moduleName, missing[0]))
		}

		if err := p.resolveImports(imported, append(stack, moduleName)); err != nil {
			return err
		}
	}
	return nil
}

func projectDiagnostic(diag *diagnostic.Diagnostic) error {
	return &ProjectLoadError{Diagnostic: diag}
}

func missingExposedSymbols(module *ast.Module, exposing []string) []string {
	if module == nil || len(exposing) == 0 {
		return nil
	}
	declared := map[string]bool{}
	for _, decl := range module.Declarations {
		switch value := decl.(type) {
		case ast.TypeDecl:
			declared[value.Name] = true
		case ast.FunctionDecl:
			declared[value.Name] = true
		case ast.ProcedureDecl:
			declared[value.Name] = true
		case ast.ErrorDecl:
			declared[value.Name] = true
		}
	}

	var missing []string
	for _, name := range exposing {
		if !declared[name] {
			missing = append(missing, name)
		}
	}
	return missing
}

func (p *Project) ambiguousExposedDiagnostics(module *ast.Module) []*diagnostic.Diagnostic {
	if p == nil || module == nil {
		return nil
	}
	seen := map[string]string{}
	for _, decl := range module.Declarations {
		importDecl, ok := decl.(ast.ImportDecl)
		if !ok || runtimeModules[importDecl.Module] {
			continue
		}
		for _, exposed := range importDecl.Exposing {
			if firstModule, exists := seen[exposed]; exists && firstModule != importDecl.Module {
				return []*diagnostic.Diagnostic{
					diagnostic.AmbiguousExposedSymbol(locationFromPosition(importDecl.Pos), exposed, firstModule, importDecl.Module),
				}
			}
			seen[exposed] = importDecl.Module
		}
	}
	return nil
}

func (p *Project) qualifiedCallDiagnostics(module *ast.Module) []*diagnostic.Diagnostic {
	if p == nil || module == nil {
		return nil
	}
	directImports := map[string]bool{module.Name: true}
	for _, decl := range module.Declarations {
		importDecl, ok := decl.(ast.ImportDecl)
		if ok && !runtimeModules[importDecl.Module] {
			directImports[importDecl.Module] = true
		}
	}

	var diagnostics []*diagnostic.Diagnostic
	forEachCall(module, func(call ast.CallExpr) {
		name, ok := callName(call.Callee)
		if !ok || !isQualifiedCallName(name) || hasRuntimePrefix(name) {
			return
		}
		moduleName, ok := p.qualifiedCallModule(name)
		if !ok || !directImports[moduleName] || !moduleHasRoutine(p.Modules[moduleName], name) {
			diagnostics = append(diagnostics, diagnostic.UnknownRoutine(locationFromPosition(call.Pos), name))
		}
	})
	return diagnostics
}

func (p *Project) qualifiedCallModule(name string) (string, bool) {
	var matched string
	for moduleName := range p.Modules {
		if name == moduleName || strings.HasPrefix(name, moduleName+".") {
			if len(moduleName) > len(matched) {
				matched = moduleName
			}
		}
	}
	return matched, matched != ""
}

func moduleHasRoutine(module *ast.Module, qualifiedRoutine string) bool {
	if module == nil {
		return false
	}
	_, ok := BuildSymbolTable(module).Routines[qualifiedRoutine]
	return ok
}

func hasRuntimePrefix(name string) bool {
	for moduleName := range runtimeModules {
		if name == moduleName || strings.HasPrefix(name, moduleName+".") {
			return true
		}
	}
	return false
}

func forEachCall(module *ast.Module, visit func(ast.CallExpr)) {
	for _, decl := range module.Declarations {
		switch value := decl.(type) {
		case ast.FunctionDecl:
			for _, expr := range value.Requires {
				walkExprCalls(expr, visit)
			}
			for _, clause := range value.Aborts {
				walkExprCalls(clause.Condition, visit)
			}
			for _, expr := range value.Ensures {
				walkExprCalls(expr, visit)
			}
			walkStmtCalls(value.Body, visit)
		case ast.ProcedureDecl:
			for _, expr := range value.Requires {
				walkExprCalls(expr, visit)
			}
			for _, clause := range value.Aborts {
				walkExprCalls(clause.Condition, visit)
			}
			for _, expr := range value.Ensures {
				walkExprCalls(expr, visit)
			}
			walkStmtCalls(value.Body, visit)
		}
	}
}

func walkStmtCalls(stmts []ast.Stmt, visit func(ast.CallExpr)) {
	for _, stmt := range stmts {
		switch value := stmt.(type) {
		case ast.LetStmt:
			walkExprCalls(value.Value, visit)
		case ast.AssignmentStmt:
			walkExprCalls(value.Target, visit)
			walkExprCalls(value.Value, visit)
		case ast.ReturnStmt:
			walkExprCalls(value.Value, visit)
		case ast.CheckStmt:
			walkExprCalls(value.Condition, visit)
		case ast.CallStmt:
			walkExprCalls(value.Call, visit)
		case ast.IfStmt:
			walkExprCalls(value.Condition, visit)
			walkStmtCalls(value.ThenBody, visit)
			walkStmtCalls(value.ElseBody, visit)
		case ast.WhileStmt:
			walkExprCalls(value.Condition, visit)
			for _, invariant := range value.Invariants {
				walkExprCalls(invariant, visit)
			}
			walkExprCalls(value.Variant, visit)
			walkStmtCalls(value.Body, visit)
		case ast.CaseStmt:
			walkExprCalls(value.Value, visit)
			for _, branch := range value.When {
				walkExprCalls(branch.Value, visit)
				walkStmtCalls(branch.Body, visit)
			}
			walkStmtCalls(value.Default, visit)
		case ast.ScopeStmt:
			walkStmtCalls(value.SpawnBody, visit)
			walkStmtCalls(value.JoinBody, visit)
			walkStmtCalls(value.ResultBody, visit)
		}
	}
}

func walkExprCalls(expr ast.Expr, visit func(ast.CallExpr)) {
	switch value := expr.(type) {
	case nil:
		return
	case ast.CallExpr:
		visit(value)
		for _, arg := range value.Arguments {
			walkExprCalls(arg, visit)
		}
	case ast.FieldAccessExpr:
		walkExprCalls(value.Object, visit)
	case ast.RecordLiteralExpr:
		for _, field := range value.Fields {
			walkExprCalls(field.Value, visit)
		}
	case ast.BinaryExpr:
		walkExprCalls(value.Left, visit)
		walkExprCalls(value.Right, visit)
	case ast.UnaryExpr:
		walkExprCalls(value.Value, visit)
	case ast.NamedArgumentExpr:
		walkExprCalls(value.Value, visit)
	case ast.IndexExpr:
		walkExprCalls(value.Array, visit)
		walkExprCalls(value.Index, visit)
	case ast.ArrayLiteralExpr:
		for _, element := range value.Elements {
			walkExprCalls(element, visit)
		}
	case ast.AwaitExpr:
		walkExprCalls(value.Value, visit)
	case ast.OkExpr:
		walkExprCalls(value.Value, visit)
	}
}

func parseModuleFile(path string) (*ast.Module, error) {
	source, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	lex := lexer.New(string(source))
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
		return nil, err
	}
	return module, nil
}

func inferProjectRoot(entryPath string, moduleName string) (string, error) {
	parts := strings.Split(moduleName, ".")
	if len(parts) == 0 || parts[0] == "" {
		return "", fmt.Errorf("invalid module name: %s", moduleName)
	}

	root := filepath.Dir(entryPath)
	for range parts[1:] {
		root = filepath.Dir(root)
	}
	return root, nil
}

func modulePath(root string, moduleName string) string {
	parts := strings.Split(moduleName, ".")
	parts[len(parts)-1] += ".fh"
	return filepath.Join(append([]string{root}, parts...)...)
}

func samePath(left string, right string) bool {
	leftClean, leftErr := filepath.Abs(left)
	rightClean, rightErr := filepath.Abs(right)
	if leftErr != nil || rightErr != nil {
		return filepath.Clean(left) == filepath.Clean(right)
	}
	return strings.EqualFold(filepath.Clean(leftClean), filepath.Clean(rightClean))
}

func contains(values []string, value string) bool {
	for _, item := range values {
		if item == value {
			return true
		}
	}
	return false
}
