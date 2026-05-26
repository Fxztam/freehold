package semantic

import (
	"fmt"
	"sort"
	"strings"

	"freehold-go-frontend/internal/ast"
	"freehold-go-frontend/internal/diagnostic"
	"freehold-go-frontend/internal/token"
)

type RecordType struct {
	Name          string
	QualifiedName string
	Fields        map[string]string
}

type RoutineType struct {
	Name          string
	QualifiedName string
	Params        []ast.Param
	ReturnType    string
}

type SymbolTable struct {
	Records  map[string]RecordType
	Routines map[string]RoutineType
	Types    map[string]bool
}

type Analyzer struct {
	symbols     SymbolTable
	diagnostics []*diagnostic.Diagnostic
}

func BuildSymbolTable(module *ast.Module) SymbolTable {
	symbols := SymbolTable{Records: map[string]RecordType{}, Routines: map[string]RoutineType{}, Types: builtinTypes()}
	if module == nil {
		return symbols
	}
	for _, decl := range module.Declarations {
		switch value := decl.(type) {
		case ast.TypeDecl:
			symbols.Types[value.Name] = true
			if value.Base != "record" {
				continue
			}

			fields := map[string]string{}
			for _, field := range value.Fields {
				fields[field.Name] = field.Type
			}
			record := RecordType{Name: value.Name, QualifiedName: qualifiedName(module, value.Name), Fields: fields}
			symbols.Records[value.Name] = record
			symbols.Records[record.QualifiedName] = record
			symbols.Types[record.QualifiedName] = true
		case ast.ErrorDecl:
			symbols.Types[value.Name] = true
			symbols.Types[qualifiedName(module, value.Name)] = true
		case ast.FunctionDecl:
			routine := RoutineType{Name: value.Name, QualifiedName: qualifiedName(module, value.Name), Params: value.Params, ReturnType: value.ReturnType}
			symbols.Routines[value.Name] = routine
			symbols.Routines[routine.QualifiedName] = routine
		case ast.ProcedureDecl:
			routine := RoutineType{Name: value.Name, QualifiedName: qualifiedName(module, value.Name), Params: value.Params}
			symbols.Routines[value.Name] = routine
			symbols.Routines[routine.QualifiedName] = routine
		}
	}
	return symbols
}

func qualifiedName(module *ast.Module, name string) string {
	if module == nil || module.Name == "" {
		return name
	}
	return module.Name + "." + name
}

func BuildSymbolTableWithImports(module *ast.Module, importedModules ...*ast.Module) SymbolTable {
	importedByName := map[string]*ast.Module{}
	for _, imported := range importedModules {
		if imported != nil {
			importedByName[imported.Name] = imported
		}
	}
	return buildSymbolTableWithImports(module, importedByName, map[string]bool{})
}

func buildSymbolTableWithImports(module *ast.Module, importedByName map[string]*ast.Module, stack map[string]bool) SymbolTable {
	symbols := BuildSymbolTable(module)
	if module == nil || stack[module.Name] {
		return symbols
	}

	stack[module.Name] = true
	defer delete(stack, module.Name)

	for _, decl := range module.Declarations {
		importDecl, ok := decl.(ast.ImportDecl)
		if !ok {
			continue
		}

		imported := importedByName[importDecl.Module]
		if imported == nil {
			continue
		}

		importedSymbols := buildSymbolTableWithImports(imported, importedByName, stack)
		for _, exposed := range importDecl.Exposing {
			record, ok := importedSymbols.Records[exposed]
			if ok {
				addRecordWithDependencies(&symbols, importedSymbols, record, map[string]bool{})
			}
			if importedSymbols.Types[exposed] {
				addType(&symbols, exposed)
				addType(&symbols, qualifiedName(imported, exposed))
			}
			routine, ok := importedSymbols.Routines[exposed]
			if ok {
				addRoutine(&symbols, routine)
			}
		}
	}

	return symbols
}

func addRoutine(target *SymbolTable, routine RoutineType) {
	if _, exists := target.Routines[routine.Name]; !exists {
		target.Routines[routine.Name] = routine
	}
	if routine.QualifiedName != "" {
		target.Routines[routine.QualifiedName] = routine
	}
}

func addType(target *SymbolTable, name string) {
	if name != "" {
		target.Types[name] = true
	}
}

func addRecordWithDependencies(target *SymbolTable, source SymbolTable, record RecordType, seen map[string]bool) {
	seenName := record.QualifiedName
	if seenName == "" {
		seenName = record.Name
	}
	if seen[seenName] {
		return
	}
	seen[seenName] = true

	record = resolveRecordFieldTypes(source, record)

	if _, exists := target.Records[record.Name]; !exists {
		target.Records[record.Name] = record
	}
	addType(target, record.Name)
	if record.QualifiedName != "" {
		target.Records[record.QualifiedName] = record
		addType(target, record.QualifiedName)
	}

	for _, fieldType := range record.Fields {
		dependency, ok := source.Records[fieldType]
		if ok {
			addRecordWithDependencies(target, source, dependency, seen)
		}
	}
}

func resolveRecordFieldTypes(source SymbolTable, record RecordType) RecordType {
	fields := map[string]string{}
	for fieldName, fieldType := range record.Fields {
		resolved := fieldType
		dependency, ok := source.Records[fieldType]
		if ok && dependency.QualifiedName != "" {
			resolved = dependency.QualifiedName
		}
		fields[fieldName] = resolved
	}
	record.Fields = fields
	return record
}

func ValidateModule(module *ast.Module) []*diagnostic.Diagnostic {
	analyzer := Analyzer{symbols: BuildSymbolTable(module)}
	analyzer.validateModule(module)
	return analyzer.diagnostics
}

func ValidateModuleWithImports(module *ast.Module, importedModules ...*ast.Module) []*diagnostic.Diagnostic {
	analyzer := Analyzer{symbols: BuildSymbolTableWithImports(module, importedModules...)}
	analyzer.validateModule(module)
	return analyzer.diagnostics
}

func (a *Analyzer) validateModule(module *ast.Module) {
	if module == nil {
		return
	}
	for _, decl := range module.Declarations {
		switch value := decl.(type) {
		case ast.TypeDecl:
			if value.Base == "record" {
				for _, field := range value.Fields {
					a.validateTypeReference(field.Type, locationFromPosition(field.Pos))
				}
			} else {
				a.validateTypeReference(value.Base, locationFromPosition(value.Pos))
			}
		case ast.FunctionDecl:
			a.validateRoutineSignature(value.Params, value.ReturnType, locationFromPosition(value.Pos))
			env := a.envFromParams(value.Params)
			for _, expr := range value.Requires {
				a.inferExpr(expr, env)
			}
			for _, clause := range value.Aborts {
				if clause.Condition != nil {
					a.inferExpr(clause.Condition, env)
				}
			}
			ensuresEnv := contractEnv(env, value.ReturnType)
			for _, expr := range value.Ensures {
				a.inferExpr(expr, ensuresEnv)
			}
			a.validateBlock(value.Body, env)
		case ast.ProcedureDecl:
			a.validateRoutineSignature(value.Params, "", locationFromPosition(value.Pos))
			env := a.envFromParams(value.Params)
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

func (a *Analyzer) envFromParams(params []ast.Param) map[string]string {
	env := map[string]string{}
	for _, param := range params {
		env[param.Name] = param.Type
	}
	return env
}

func contractEnv(env map[string]string, returnType string) map[string]string {
	contract := cloneEnv(env)
	if returnType == "" {
		return contract
	}
	contract["result"] = returnType
	if okType, errorType, ok := resultTypes(returnType); ok {
		contract["value"] = okType
		contract["error"] = errorType
	}
	return contract
}

func resultTypes(typeName string) (string, string, bool) {
	typeName = strings.TrimSpace(typeName)
	if !strings.HasPrefix(typeName, "Result<") || !strings.HasSuffix(typeName, ">") {
		return "", "", false
	}
	parts := splitTopLevel(typeName[len("Result<") : len(typeName)-1])
	if len(parts) != 2 {
		return "", "", false
	}
	return parts[0], parts[1], true
}

func (a *Analyzer) validateRoutineSignature(params []ast.Param, returnType string, returnLocation diagnostic.Location) {
	seen := map[string]token.Position{}
	for _, param := range params {
		if firstPos, exists := seen[param.Name]; exists {
			location := locationFromPosition(param.Pos)
			if location.Line == 0 {
				location = locationFromPosition(firstPos)
			}
			a.diagnostics = append(a.diagnostics, diagnostic.DuplicateParameterName(location, param.Name))
		} else {
			seen[param.Name] = param.Pos
		}
		a.validateTypeReference(param.Type, locationFromPosition(param.Pos))
	}
	if returnType != "" {
		a.validateTypeReference(returnType, returnLocation)
	}
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
			a.validateTypeReference(value.Type, locationFromPosition(value.Pos))
			valueType, valueOK := a.inferExpr(value.Value, env)
			if _, exists := env[value.Name]; exists {
				a.diagnostics = append(a.diagnostics, diagnostic.DuplicateLocalName(locationFromPosition(value.Pos), value.Name))
			}
			if valueOK && a.knownType(value.Type) && !sameType(value.Type, valueType) {
				a.diagnostics = append(a.diagnostics, diagnostic.AssignmentTypeMismatch(locationFromPosition(value.Pos), value.Type, valueType))
			}
			env[value.Name] = value.Type
		case ast.AssignmentStmt:
			targetType, targetOK := a.inferAssignmentTarget(value.Target, env)
			valueType, valueOK := a.inferExpr(value.Value, env)
			if targetOK && valueOK && a.knownType(targetType) && !sameType(targetType, valueType) {
				a.diagnostics = append(a.diagnostics, diagnostic.AssignmentTypeMismatch(locationFromPosition(value.Pos), targetType, valueType))
			}
		case ast.ReturnStmt:
			a.inferExpr(value.Value, env)
		case ast.CheckStmt:
			a.inferExpr(value.Condition, env)
		case ast.CallStmt:
			if call, ok := value.Call.(ast.CallExpr); ok {
				a.validateCall(call, env, locationFromPosition(value.Pos))
			} else {
				a.inferExpr(value.Call, env)
			}
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
		if value.Name == "true" || value.Name == "false" || value.Name == "success" || value.Name == "failure" {
			return "Boolean", true
		}
		typeName, ok := env[value.Name]
		if !ok {
			a.diagnostics = append(a.diagnostics, diagnostic.UnknownVariable(locationFromPosition(value.Pos), value.Name))
		}
		return typeName, ok
	case ast.FieldAccessExpr:
		objectType, ok := a.inferExpr(value.Object, env)
		if !ok {
			return "", false
		}
		record, ok := a.symbols.Records[objectType]
		if !ok {
			a.diagnostics = append(a.diagnostics, diagnostic.FieldAccessRequiresRecord(locationFromPosition(value.Pos), objectType, value.Field))
			return "", false
		}
		fieldType, ok := record.Fields[value.Field]
		if !ok {
			a.diagnostics = append(a.diagnostics, diagnostic.UnknownRecordField(locationFromPosition(value.Pos), record.Name, value.Field))
			return "", false
		}
		return fieldType, true
	case ast.RecordLiteralExpr:
		a.validateRecordLiteral(value, env)
		return value.Type, true
	case ast.BinaryExpr:
		leftType, leftOK := a.inferExpr(value.Left, env)
		rightType, rightOK := a.inferExpr(value.Right, env)
		if isBooleanOperator(value.Op) || isComparisonOperator(value.Op) {
			return "Boolean", true
		}
		if leftOK && rightOK && (leftType == "Double" || rightType == "Double") {
			return "Double", true
		}
		if leftOK && rightOK {
			return leftType, true
		}
		return "", false
	case ast.UnaryExpr:
		valueType, ok := a.inferExpr(value.Value, env)
		if value.Op == "not" {
			return "Boolean", true
		}
		return valueType, ok
	case ast.CallExpr:
		return a.validateCall(value, env, locationFromPosition(value.Pos))
	case ast.NamedArgumentExpr:
		return a.inferExpr(value.Value, env)
	case ast.IndexExpr:
		arrayType, ok := a.inferExpr(value.Array, env)
		indexType, indexOK := a.inferExpr(value.Index, env)
		if indexOK && !sameType("Integer", indexType) {
			a.diagnostics = append(a.diagnostics, diagnostic.ArrayIndexRequiresInteger(locationFromExpr(value.Index), indexType))
		}
		if !ok {
			return "", false
		}
		elementType, elementOK := arrayElementType(arrayType)
		if !elementOK {
			a.diagnostics = append(a.diagnostics, diagnostic.IndexAccessRequiresArray(locationFromPosition(value.Pos), arrayType))
			return "", false
		}
		return elementType, true
	case ast.ArrayLiteralExpr:
		if len(value.Elements) == 0 {
			return "Array<Empty, 0>", true
		}
		elementType, elementOK := a.inferExpr(value.Elements[0], env)
		for _, element := range value.Elements {
			a.inferExpr(element, env)
		}
		if !elementOK {
			return "", false
		}
		return fmt.Sprintf("Array<%s, %d>", elementType, len(value.Elements)), true
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

func (a *Analyzer) inferAssignmentTarget(expr ast.Expr, env map[string]string) (string, bool) {
	switch value := expr.(type) {
	case ast.IdentifierExpr:
		typeName, ok := env[value.Name]
		if !ok {
			a.diagnostics = append(a.diagnostics, diagnostic.UnknownAssignmentTarget(locationFromPosition(value.Pos), value.Name))
		}
		return typeName, ok
	default:
		return a.inferExpr(expr, env)
	}
}

func (a *Analyzer) validateTypeReference(typeName string, location diagnostic.Location) {
	if typeName == "" || a.knownType(typeName) {
		return
	}
	a.diagnostics = append(a.diagnostics, diagnostic.UnknownTypeReference(location, typeName))
}

func (a *Analyzer) knownType(typeName string) bool {
	typeName = strings.TrimSpace(typeName)
	if typeName == "" {
		return true
	}
	if a.symbols.Types[typeName] {
		return true
	}
	if _, ok := a.symbols.Records[typeName]; ok {
		return true
	}
	if elementType, ok := arrayElementType(typeName); ok {
		return a.knownType(elementType)
	}
	if strings.HasPrefix(typeName, "Result<") && strings.HasSuffix(typeName, ">") {
		parts := splitTopLevel(typeName[len("Result<") : len(typeName)-1])
		if len(parts) != 2 {
			return false
		}
		return a.knownType(parts[0]) && a.knownType(parts[1])
	}
	return false
}

func builtinTypes() map[string]bool {
	return map[string]bool{
		"Boolean":    true,
		"BigFloat":   true,
		"BigInteger": true,
		"Double":     true,
		"Executor":   true,
		"Integer":    true,
		"Scope":      true,
		"String":     true,
	}
}

func splitTopLevel(value string) []string {
	var parts []string
	start := 0
	depth := 0
	for index, char := range value {
		switch char {
		case '<':
			depth++
		case '>':
			depth--
		case ',':
			if depth == 0 {
				parts = append(parts, strings.TrimSpace(value[start:index]))
				start = index + 1
			}
		}
	}
	parts = append(parts, strings.TrimSpace(value[start:]))
	return parts
}

func (a *Analyzer) validateRecordLiteral(literal ast.RecordLiteralExpr, env map[string]string) {
	record, ok := a.symbols.Records[literal.Type]
	if !ok {
		for _, field := range literal.Fields {
			a.inferExpr(field.Value, env)
		}
		return
	}

	seen := map[string]token.Position{}
	for _, field := range literal.Fields {
		if firstPos, exists := seen[field.Name]; exists {
			location := locationFromPosition(field.Pos)
			if location.Line == 0 {
				location = locationFromPosition(firstPos)
			}
			a.diagnostics = append(a.diagnostics, diagnostic.DuplicateRecordLiteralField(location, record.Name, field.Name))
		} else {
			seen[field.Name] = field.Pos
		}
		if _, exists := record.Fields[field.Name]; !exists {
			a.diagnostics = append(a.diagnostics, diagnostic.UnknownRecordLiteralField(locationFromPosition(field.Pos), record.Name, field.Name))
		}
		a.inferExpr(field.Value, env)
	}

	var missing []string
	for fieldName := range record.Fields {
		if _, exists := seen[fieldName]; !exists {
			missing = append(missing, fieldName)
		}
	}
	sort.Strings(missing)
	for _, fieldName := range missing {
		a.diagnostics = append(a.diagnostics, diagnostic.MissingRecordLiteralField(locationFromPosition(literal.Pos), record.Name, fieldName))
	}
}

func (a *Analyzer) validateCall(call ast.CallExpr, env map[string]string, location diagnostic.Location) (string, bool) {
	argTypes := make([]string, len(call.Arguments))
	argOK := make([]bool, len(call.Arguments))
	for index, arg := range call.Arguments {
		argTypes[index], argOK[index] = a.inferExpr(arg, env)
	}

	name, ok := callName(call.Callee)
	if !ok {
		return "", false
	}
	routine, ok := a.symbols.Routines[name]
	if !ok {
		if !isQualifiedCallName(name) {
			a.diagnostics = append(a.diagnostics, diagnostic.UnknownRoutine(location, name))
		}
		return "", false
	}
	if len(call.Arguments) != len(routine.Params) {
		a.diagnostics = append(a.diagnostics, diagnostic.RoutineArgumentCountMismatch(location, routine.Name, len(routine.Params), len(call.Arguments)))
		return routine.ReturnType, routine.ReturnType != ""
	}
	for index, param := range routine.Params {
		if !argOK[index] {
			continue
		}
		if !sameType(param.Type, argTypes[index]) {
			a.diagnostics = append(a.diagnostics, diagnostic.RoutineArgumentTypeMismatch(locationFromExpr(call.Arguments[index]), routine.Name, index+1, param.Type, argTypes[index]))
		}
	}
	return routine.ReturnType, routine.ReturnType != ""
}

func sameType(expected string, found string) bool {
	return expected == found
}

func locationFromExpr(expr ast.Expr) diagnostic.Location {
	switch value := expr.(type) {
	case ast.IdentifierExpr:
		return locationFromPosition(value.Pos)
	case ast.FieldAccessExpr:
		return locationFromPosition(value.Pos)
	case ast.IndexExpr:
		return locationFromPosition(value.Pos)
	case ast.ArrayLiteralExpr:
		return locationFromPosition(value.Pos)
	case ast.CallExpr:
		return locationFromPosition(value.Pos)
	case ast.AwaitExpr:
		return locationFromPosition(value.Pos)
	case ast.NamedArgumentExpr:
		return locationFromPosition(value.Pos)
	case ast.RecordLiteralExpr:
		return locationFromPosition(value.Pos)
	case ast.BinaryExpr:
		return locationFromPosition(value.Pos)
	case ast.UnaryExpr:
		return locationFromPosition(value.Pos)
	case ast.OkExpr:
		return locationFromPosition(value.Pos)
	case ast.NumberExpr:
		return locationFromPosition(value.Pos)
	case ast.StringExpr:
		return locationFromPosition(value.Pos)
	case ast.ErrorExpr:
		return locationFromPosition(value.Pos)
	}
	return diagnostic.Location{}
}

func callName(expr ast.Expr) (string, bool) {
	switch value := expr.(type) {
	case ast.IdentifierExpr:
		return value.Name, true
	case ast.FieldAccessExpr:
		objectName, ok := callName(value.Object)
		if !ok {
			return "", false
		}
		return objectName + "." + value.Field, true
	}
	return "", false
}

func isQualifiedCallName(name string) bool {
	for _, char := range name {
		if char == '.' {
			return true
		}
	}
	return false
}

func isBooleanOperator(op string) bool {
	return op == "and" || op == "or"
}

func isComparisonOperator(op string) bool {
	switch op {
	case "=", "!=", "<", "<=", ">", ">=":
		return true
	}
	return false
}

func arrayElementType(typeName string) (string, bool) {
	const prefix = "Array<"
	if len(typeName) <= len(prefix) || typeName[:len(prefix)] != prefix || typeName[len(typeName)-1] != '>' {
		return "", false
	}
	inner := typeName[len(prefix) : len(typeName)-1]
	depth := 0
	for index, char := range inner {
		switch char {
		case '<':
			depth++
		case '>':
			depth--
		case ',':
			if depth == 0 {
				return inner[:index], true
			}
		}
	}
	return "", false
}

func locationFromPosition(pos token.Position) diagnostic.Location {
	return diagnostic.Location{Line: pos.Line, Column: pos.Column, Offset: pos.Offset}
}
