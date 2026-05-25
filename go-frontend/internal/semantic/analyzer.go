package semantic

import (
	"freehold-go-frontend/internal/ast"
	"freehold-go-frontend/internal/diagnostic"
)

type RecordType struct {
	Name   string
	Fields map[string]string
}

type SymbolTable struct {
	Records map[string]RecordType
}

type Analyzer struct {
	symbols     SymbolTable
	diagnostics []*diagnostic.Diagnostic
}

func BuildSymbolTable(module *ast.Module) SymbolTable {
	symbols := SymbolTable{Records: map[string]RecordType{}}
	if module == nil {
		return symbols
	}
	for _, decl := range module.Declarations {
		typeDecl, ok := decl.(ast.TypeDecl)
		if !ok || typeDecl.Base != "record" {
			continue
		}

		fields := map[string]string{}
		for _, field := range typeDecl.Fields {
			fields[field.Name] = field.Type
		}
		symbols.Records[typeDecl.Name] = RecordType{Name: typeDecl.Name, Fields: fields}
	}
	return symbols
}

func ValidateModule(module *ast.Module) []*diagnostic.Diagnostic {
	analyzer := Analyzer{symbols: BuildSymbolTable(module)}
	analyzer.validateModule(module)
	return analyzer.diagnostics
}

func (a *Analyzer) validateModule(module *ast.Module) {
	if module == nil {
		return
	}
	for _, decl := range module.Declarations {
		switch value := decl.(type) {
		case ast.FunctionDecl:
			env := envFromParams(value.Params)
			for _, expr := range value.Requires {
				a.inferExpr(expr, env)
			}
			for _, clause := range value.Aborts {
				if clause.Condition != nil {
					a.inferExpr(clause.Condition, env)
				}
			}
			for _, expr := range value.Ensures {
				a.inferExpr(expr, env)
			}
			a.validateBlock(value.Body, env)
		case ast.ProcedureDecl:
			env := envFromParams(value.Params)
			for _, expr := range value.Requires {
				a.inferExpr(expr, env)
			}
			for _, clause := range value.Aborts {
				if clause.Condition != nil {
					a.inferExpr(clause.Condition, env)
				}
			}
			for _, expr := range value.Ensures {
				a.inferExpr(expr, env)
			}
			a.validateBlock(value.Body, env)
		}
	}
}

func envFromParams(params []ast.Param) map[string]string {
	env := map[string]string{}
	for _, param := range params {
		env[param.Name] = param.Type
	}
	return env
}

func cloneEnv(env map[string]string) map[string]string {
	cloned := map[string]string{}
	for name, typeName := range env {
		cloned[name] = typeName
	}
	return cloned
}

func (a *Analyzer) validateBlock(body []ast.Stmt, env map[string]string) {
	for _, stmt := range body {
		switch value := stmt.(type) {
		case ast.LetStmt:
			a.inferExpr(value.Value, env)
			env[value.Name] = value.Type
		case ast.AssignmentStmt:
			a.inferExpr(value.Target, env)
			a.inferExpr(value.Value, env)
		case ast.ReturnStmt:
			a.inferExpr(value.Value, env)
		case ast.CheckStmt:
			a.inferExpr(value.Condition, env)
		case ast.CallStmt:
			a.inferExpr(value.Call, env)
		case ast.IfStmt:
			a.inferExpr(value.Condition, env)
			a.validateBlock(value.ThenBody, cloneEnv(env))
			a.validateBlock(value.ElseBody, cloneEnv(env))
		case ast.WhileStmt:
			a.inferExpr(value.Condition, env)
			for _, invariant := range value.Invariants {
				a.inferExpr(invariant, env)
			}
			if value.Variant != nil {
				a.inferExpr(value.Variant, env)
			}
			a.validateBlock(value.Body, cloneEnv(env))
		case ast.CaseStmt:
			a.inferExpr(value.Value, env)
			for _, branch := range value.When {
				a.inferExpr(branch.Value, env)
				a.validateBlock(branch.Body, cloneEnv(env))
			}
			a.validateBlock(value.Default, cloneEnv(env))
		case ast.ScopeStmt:
			scopeEnv := cloneEnv(env)
			scopeEnv[value.Name] = "Scope"
			a.validateBlock(value.SpawnBody, cloneEnv(scopeEnv))
			a.validateBlock(value.JoinBody, cloneEnv(scopeEnv))
			a.validateBlock(value.ResultBody, cloneEnv(scopeEnv))
		}
	}
}

func (a *Analyzer) inferExpr(expr ast.Expr, env map[string]string) (string, bool) {
	switch value := expr.(type) {
	case nil:
		return "", false
	case ast.IdentifierExpr:
		typeName, ok := env[value.Name]
		return typeName, ok
	case ast.FieldAccessExpr:
		objectType, ok := a.inferExpr(value.Object, env)
		if !ok {
			return "", false
		}
		record, ok := a.symbols.Records[objectType]
		if !ok {
			a.diagnostics = append(a.diagnostics, diagnostic.FieldAccessRequiresRecord(diagnostic.Location{}, objectType, value.Field))
			return "", false
		}
		fieldType, ok := record.Fields[value.Field]
		if !ok {
			a.diagnostics = append(a.diagnostics, diagnostic.UnknownRecordField(diagnostic.Location{}, record.Name, value.Field))
			return "", false
		}
		return fieldType, true
	case ast.RecordLiteralExpr:
		for _, field := range value.Fields {
			a.inferExpr(field.Value, env)
		}
		return value.Type, true
	case ast.BinaryExpr:
		a.inferExpr(value.Left, env)
		a.inferExpr(value.Right, env)
		return "Boolean", true
	case ast.UnaryExpr:
		a.inferExpr(value.Value, env)
		return "Boolean", true
	case ast.CallExpr:
		for _, arg := range value.Arguments {
			a.inferExpr(arg, env)
		}
		return "", false
	case ast.NamedArgumentExpr:
		return a.inferExpr(value.Value, env)
	case ast.IndexExpr:
		a.inferExpr(value.Array, env)
		a.inferExpr(value.Index, env)
		return "", false
	case ast.ArrayLiteralExpr:
		for _, element := range value.Elements {
			a.inferExpr(element, env)
		}
		return "", false
	case ast.AwaitExpr:
		return a.inferExpr(value.Value, env)
	case ast.OkExpr:
		return a.inferExpr(value.Value, env)
	case ast.NumberExpr:
		return "Integer", true
	case ast.StringExpr:
		return "String", true
	case ast.ErrorExpr:
		return value.Name, true
	}
	return "", false
}
