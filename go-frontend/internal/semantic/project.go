package semantic

import (
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
		return nil, fmt.Errorf("module file path mismatch: expected %s, got %s", expectedPath, entryPath)
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
		return nil, nil, err
	}

	imports := make([]*ast.Module, 0, len(project.Modules)-1)
	for name, module := range project.Modules {
		if name != project.Entry.Name {
			imports = append(imports, module)
		}
	}

	return project, ValidateModuleWithImports(project.Entry, imports...), nil
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
			return fmt.Errorf("import cycle: %s", strings.Join(append(stack, moduleName), " -> "))
		}

		imported, ok := p.Modules[moduleName]
		if !ok {
			path := modulePath(p.Root, moduleName)
			if _, err := os.Stat(path); err != nil {
				return fmt.Errorf("imported module not found: %s", moduleName)
			}
			parsed, err := parseModuleFile(path)
			if err != nil {
				return fmt.Errorf("imported module has syntax error: %s: %w", moduleName, err)
			}
			if parsed.Name != moduleName {
				return fmt.Errorf("imported module name mismatch: expected %s, got %s", moduleName, parsed.Name)
			}
			p.Modules[moduleName] = parsed
			p.Files[moduleName] = path
			imported = parsed
		}

		if err := p.resolveImports(imported, append(stack, moduleName)); err != nil {
			return err
		}
	}
	return nil
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
