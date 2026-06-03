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
	GlobalSpecs   []ast.GlobalSpec
	DependsSpecs  []ast.DependsSpec
}

type SymbolTable struct {
	Records   map[string]RecordType
	Routines  map[string]RoutineType
	Types     map[string]bool
	Errors    map[string]bool
	TypeBases map[string]string
	Services  map[string]bool
}

type Analyzer struct {
	symbols     SymbolTable
	diagnostics []*diagnostic.Diagnostic
}

func BuildSymbolTable(module *ast.Module) SymbolTable {
	symbols := SymbolTable{
		Records:   map[string]RecordType{},
		Routines:  map[string]RoutineType{},
		Types:     builtinTypes(),
		Errors:    map[string]bool{},
		TypeBases: map[string]string{},
		Services:  map[string]bool{},
	}
	for name := range symbols.Types {
		symbols.TypeBases[name] = name
	}
	if module == nil {
		return symbols
	}
	for _, decl := range module.Declarations {
		switch value := decl.(type) {
		case ast.TypeDecl:
			symbols.Types[value.Name] = true
			symbols.TypeBases[value.Name] = value.Base
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
			symbols.Errors[value.Name] = true
			symbols.Errors[qualifiedName(module, value.Name)] = true
		case ast.ServiceDecl:
			symbols.Services[value.Name] = true
			symbols.Services[qualifiedName(module, value.Name)] = true
			symbols.Types[value.Name] = true
			symbols.Types[qualifiedName(module, value.Name)] = true
		case ast.FunctionDecl:
			routine := RoutineType{
				Name:          value.Name,
				QualifiedName: qualifiedName(module, value.Name),
				Params:        value.Params,
				ReturnType:    value.ReturnType,
				GlobalSpecs:   value.GlobalSpecs,
				DependsSpecs:  value.DependsSpecs,
			}
			symbols.Routines[value.Name] = routine
			symbols.Routines[routine.QualifiedName] = routine
		case ast.ProcedureDecl:
			routine := RoutineType{
				Name:          value.Name,
				QualifiedName: qualifiedName(module, value.Name),
				Params:        value.Params,
				GlobalSpecs:   value.GlobalSpecs,
				DependsSpecs:  value.DependsSpecs,
			}
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
				if base, ok := importedSymbols.TypeBases[exposed]; ok {
					addTypeBase(&symbols, exposed, base)
					addTypeBase(&symbols, qualifiedName(imported, exposed), base)
				}
			}
			if importedSymbols.Errors[exposed] {
				addError(&symbols, exposed)
				addError(&symbols, qualifiedName(imported, exposed))
			}
			if importedSymbols.Services[exposed] {
				addService(&symbols, exposed)
				addService(&symbols, qualifiedName(imported, exposed))
			}
			routine, ok := importedSymbols.Routines[exposed]
			if ok {
				addRoutine(&symbols, routine)
			}
		}
	}

	return symbols
}

func addService(target *SymbolTable, name string) {
	if name != "" {
		target.Services[name] = true
		target.Types[name] = true
	}
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

func addTypeBase(target *SymbolTable, name string, base string) {
	if name != "" && base != "" {
		target.TypeBases[name] = base
	}
}

func addError(target *SymbolTable, name string) {
	if name != "" {
		target.Errors[name] = true
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
	if module != nil {
		cfAnalyzer := NewControlFlowAnalyzer(module)
		module.FlowSummaries = cfAnalyzer.AnalyzeRoutines()
	}
	return analyzer.diagnostics
}

func ValidateModuleWithImports(module *ast.Module, importedModules ...*ast.Module) []*diagnostic.Diagnostic {
	analyzer := Analyzer{symbols: BuildSymbolTableWithImports(module, importedModules...)}
	analyzer.validateModule(module)
	if module != nil {
		cfAnalyzer := NewControlFlowAnalyzer(module)
		module.FlowSummaries = cfAnalyzer.AnalyzeRoutines()
	}
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
			a.validateRoutineContracts(value.Name, "function", value.Params, value.ReturnType, value.GlobalSpecs, value.DependsSpecs, value.Body, value.Pos)
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
			a.validateRoutineContracts(value.Name, "procedure", value.Params, "", value.GlobalSpecs, value.DependsSpecs, value.Body, value.Pos)
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
	contract["value"] = returnType
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
			if valueOK && a.knownType(value.Type) && !a.sameType(value.Type, valueType) {
				a.diagnostics = append(a.diagnostics, diagnostic.AssignmentTypeMismatch(locationFromPosition(value.Pos), value.Type, valueType))
			}
			env[value.Name] = value.Type
		case ast.AssignmentStmt:
			targetType, targetOK := a.inferAssignmentTarget(value.Target, env)
			valueType, valueOK := a.inferExpr(value.Value, env)
			if targetOK && valueOK && a.knownType(targetType) && !a.sameType(targetType, valueType) {
				a.diagnostics = append(a.diagnostics, diagnostic.AssignmentTypeMismatch(locationFromPosition(value.Pos), targetType, valueType))
			}
		case ast.ReturnStmt:
			a.inferExpr(value.Value, env)
		case ast.CheckStmt:
			a.inferExpr(value.Condition, env)
		case ast.CallStmt:
			if call, ok := value.Call.(ast.CallExpr); ok {
				a.validateCall(call, env, locationFromPosition(value.Pos))
				a.checkAntiAliasing(call, env, value.Pos)
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
			spawnEnv := cloneEnv(scopeEnv)
			a.validateBlock(value.SpawnBody, spawnEnv)
			joinEnv := cloneEnv(spawnEnv)
			a.validateBlock(value.JoinBody, joinEnv)
			resultEnv := cloneEnv(joinEnv)
			a.validateBlock(value.ResultBody, resultEnv)
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
			if a.symbols.Errors[value.Name] {
				return value.Name, true
			}
			a.diagnostics = append(a.diagnostics, diagnostic.UnknownVariable(locationFromPosition(value.Pos), value.Name))
		}
		return typeName, ok
	case ast.FieldAccessExpr:
		objectType, ok := a.inferExpr(value.Object, env)
		if !ok {
			return "", false
		}
		if okType, errorType, isResult := resultTypes(objectType); isResult {
			if value.Field == "value" {
				return okType, true
			}
			if value.Field == "error" {
				return errorType, true
			}
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
		if indexOK && !a.sameType("Integer", indexType) {
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
		if strings.Contains(value.Value, ".") {
			return "Double", true
		}
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
	if genericBase, genericArgs, ok := parseGenericType(typeName); ok {
		switch genericBase {
		case "JoinHandle", "Channel", "Sender", "Receiver":
			if len(genericArgs) != 1 {
				return false
			}
			return a.knownType(genericArgs[0])
		}
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

func parseGenericType(typeName string) (string, []string, bool) {
	typeName = strings.TrimSpace(typeName)
	if !strings.HasSuffix(typeName, ">") {
		return "", nil, false
	}
	index := strings.Index(typeName, "<")
	if index <= 0 {
		return "", nil, false
	}
	base := strings.TrimSpace(typeName[:index])
	inner := strings.TrimSpace(typeName[index+1 : len(typeName)-1])
	if inner == "" {
		return "", nil, false
	}
	return base, splitTopLevel(inner), true
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
	if isScopeMethodCall(name, env) {
		return "", false
	}
	if isBuiltinRoutineCall(name) {
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
		if !a.sameType(param.Type, argTypes[index]) {
			a.diagnostics = append(a.diagnostics, diagnostic.RoutineArgumentTypeMismatch(locationFromExpr(call.Arguments[index]), routine.Name, index+1, param.Type, argTypes[index]))
		}
	}
	return routine.ReturnType, routine.ReturnType != ""
}

func (a *Analyzer) sameType(expected string, found string) bool {
	return a.baseType(expected) == a.baseType(found)
}

func (a *Analyzer) baseType(t string) string {
	t = stripPackagePrefixes(t)
	t = strings.TrimSpace(t)
	if strings.HasPrefix(t, "Awaitable<") {
		return "Awaitable"
	}
	if strings.HasPrefix(t, "Result<") {
		return "Result"
	}
	if strings.HasPrefix(t, "Array<") {
		return "Array"
	}
	if _, ok := a.symbols.Records[t]; ok {
		return "Record"
	}
	if a.symbols.Errors[t] {
		return t
	}
	if base, ok := a.symbols.TypeBases[t]; ok {
		if base != t {
			return a.baseType(base)
		}
	}
	return t
}

func stripPackagePrefixes(t string) string {
	var builder strings.Builder
	var current strings.Builder

	flush := func() {
		if current.Len() > 0 {
			s := current.String()
			if idx := strings.LastIndex(s, "."); idx != -1 {
				builder.WriteString(s[idx+1:])
			} else {
				builder.WriteString(s)
			}
			current.Reset()
		}
	}

	for _, r := range t {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' || r == '.' {
			current.WriteRune(r)
		} else {
			flush()
			builder.WriteRune(r)
		}
	}
	flush()
	return builder.String()
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

func isScopeMethodCall(name string, env map[string]string) bool {
	owner, method, ok := strings.Cut(name, ".")
	if !ok {
		return false
	}
	if env[owner] != "Scope" {
		return false
	}
	return method == "spawn" || method == "join"
}

func isBuiltinRoutineCall(name string) bool {
	switch name {
	case "channel", "channel_sender", "channel_receiver", "channel_send", "channel_receive", "scope", "scope_spawn", "scope_join":
		return true
	default:
		return false
	}
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
	if depth == 0 {
		return inner, true
	}
	return "", false
}

func locationFromPosition(pos token.Position) diagnostic.Location {
	return diagnostic.Location{Line: pos.Line, Column: pos.Column, Offset: pos.Offset}
}

func (a *Analyzer) validateRoutineContracts(
	name string,
	kind string,
	params []ast.Param,
	returnType string,
	globalSpecs []ast.GlobalSpec,
	dependsSpecs []ast.DependsSpec,
	body []ast.Stmt,
	pos token.Position,
) {
	// First, check transitive globals accesses
	a.checkTransitiveGlobals(body, name, globalSpecs)

	paramNames := map[string]bool{}
	for _, p := range params {
		paramNames[p.Name] = true
	}

	seenGlobals := map[string]bool{}
	for _, g := range globalSpecs {
		if seenGlobals[g.Name] {
			a.diagnostics = append(a.diagnostics, diagnostic.DuplicateGlobal(locationFromPosition(g.Pos), g.Name))
		}
		seenGlobals[g.Name] = true
		isParam := paramNames[g.Name]
		if !isParam && !a.symbols.Services[g.Name] {
			a.diagnostics = append(a.diagnostics, diagnostic.InvalidGlobalVariable(locationFromPosition(g.Pos), g.Name))
		}
	}

	actualGlobals := map[string]bool{}
	for gName := range seenGlobals {
		if !paramNames[gName] {
			actualGlobals[gName] = true
		}
	}

	if len(dependsSpecs) == 0 {
		return
	}

	seenTargets := map[string]bool{}
	validTargets := map[string]bool{}
	for pName := range paramNames {
		validTargets[pName] = true
	}
	if kind == "function" {
		validTargets["result"] = true
	}
	for name := range actualGlobals {
		// Find global spec to check mode
		for _, gSpec := range globalSpecs {
			if gSpec.Name == name {
				mode := "Input"
				if gSpec.Mode != nil {
					mode = *gSpec.Mode
				}
				if mode == "Output" || mode == "In_Out" {
					validTargets[name] = true
				}
				break
			}
		}
	}

	validSources := map[string]bool{}
	for pName := range paramNames {
		validSources[pName] = true
	}
	for name := range actualGlobals {
		for _, gSpec := range globalSpecs {
			if gSpec.Name == name {
				mode := "Input"
				if gSpec.Mode != nil {
					mode = *gSpec.Mode
				}
				if mode == "Input" || mode == "In_Out" {
					validSources[name] = true
				}
				break
			}
		}
	}

	env := map[string]string{}
	for _, p := range params {
		env[p.Name] = p.Type
	}

	mutatedVars := a.collectMutatedVars(body, paramNames, actualGlobals)
	mutatedTargets := map[string]bool{}
	for mv := range mutatedVars {
		if paramNames[mv] || actualGlobals[mv] {
			mutatedTargets[mv] = true
		}
	}

	for _, d := range dependsSpecs {
		if seenTargets[d.Target] {
			a.diagnostics = append(a.diagnostics, diagnostic.DuplicateDependencyTarget(locationFromPosition(d.Pos), d.Target))
		}
		seenTargets[d.Target] = true

		targetRoot := strings.Split(d.Target, ".")[0]
		if !validTargets[targetRoot] {
			a.diagnostics = append(a.diagnostics, diagnostic.DependencyTargetNotAllowed(locationFromPosition(d.Pos), d.Target))
		}

		for _, src := range d.Sources {
			if src == "+" {
				if !paramNames[targetRoot] && !actualGlobals[targetRoot] {
					a.diagnostics = append(a.diagnostics, diagnostic.PlusSourceNotAllowed(locationFromPosition(d.Pos)))
				}
			} else {
				srcRoot := strings.Split(src, ".")[0]
				if !validSources[srcRoot] {
					a.diagnostics = append(a.diagnostics, diagnostic.DependencySourceNotAllowed(locationFromPosition(d.Pos), src))
				}
			}
		}
	}

	seenTargetRoots := map[string]bool{}
	for t := range seenTargets {
		seenTargetRoots[strings.Split(t, ".")[0]] = true
	}

	var sortedMutatedTargets []string
	for mt := range mutatedTargets {
		sortedMutatedTargets = append(sortedMutatedTargets, mt)
	}
	sort.Strings(sortedMutatedTargets)
	for _, mt := range sortedMutatedTargets {
		if !seenTargetRoots[mt] {
			a.diagnostics = append(a.diagnostics, diagnostic.UndeclaredMutation(locationFromPosition(pos), mt))
		}
	}

	var sortedSeenTargets []string
	for t := range seenTargets {
		sortedSeenTargets = append(sortedSeenTargets, t)
	}
	sort.Strings(sortedSeenTargets)
	for _, target := range sortedSeenTargets {
		targetRoot := strings.Split(target, ".")[0]
		if targetRoot != "result" && !mutatedTargets[targetRoot] {
			a.diagnostics = append(a.diagnostics, diagnostic.UnusedTarget(locationFromPosition(pos), target))
		}
	}

	if kind == "function" && !seenTargets["result"] {
		a.diagnostics = append(a.diagnostics, diagnostic.FunctionMissingResult(locationFromPosition(pos)))
	}

	// Information Flow / Dependency Analysis
	dependencies := a.analyzeInformationFlow(body, paramNames, seenGlobals, validSources, env)

	for _, d := range dependsSpecs {
		target := d.Target
		targetRoot := strings.Split(target, ".")[0]
		actualSources := dependencies[targetRoot]
		declaredSources := map[string]bool{}
		for _, s := range d.Sources {
			if s != "+" {
				declaredSources[strings.Split(s, ".")[0]] = true
			}
		}
		for _, s := range d.Sources {
			if s == "+" {
				declaredSources[targetRoot] = true
			}
		}

		var extraSources []string
		for s := range actualSources {
			if !declaredSources[s] {
				if paramNames[s] || seenGlobals[s] {
					extraSources = append(extraSources, s)
				}
			}
		}

		if len(extraSources) > 0 {
			sort.Strings(extraSources)
			a.diagnostics = append(a.diagnostics, diagnostic.DependencyViolation(locationFromPosition(d.Pos), target, strings.Join(extraSources, ", ")))
		}
	}
}

func (a *Analyzer) collectMutatedVars(body []ast.Stmt, paramNames map[string]bool, actualGlobals map[string]bool) map[string]bool {
	mutated := map[string]bool{}
	var visitStmt func(stmt ast.Stmt)
	var visitBody func(stmts []ast.Stmt)

	visitBody = func(stmts []ast.Stmt) {
		for _, s := range stmts {
			visitStmt(s)
		}
	}

	visitStmt = func(stmt ast.Stmt) {
		switch val := stmt.(type) {
		case ast.AssignmentStmt:
			if root, ok := getRootIdentifier(val.Target); ok {
				mutated[root] = true
			}
		case ast.CallStmt:
			call, ok := val.Call.(ast.CallExpr)
			if !ok {
				return
			}
			name, ok := callName(call.Callee)
			if !ok {
				return
			}
			callee, exists := a.symbols.Routines[name]
			if !exists {
				for _, arg := range call.Arguments {
					if root, ok := getRootIdentifier(arg); ok {
						mutated[root] = true
					}
				}
				return
			}

			calleeParams := make([]string, len(callee.Params))
			calleeParamNames := map[string]bool{}
			for i, p := range callee.Params {
				calleeParams[i] = p.Name
				calleeParamNames[p.Name] = true
			}

			if len(callee.DependsSpecs) > 0 {
				for _, dCallee := range callee.DependsSpecs {
					targetRoot := strings.Split(dCallee.Target, ".")[0]
					isParam := false
					paramIdx := -1
					for i, name := range calleeParams {
						if name == targetRoot {
							isParam = true
							paramIdx = i
							break
						}
					}
					if isParam {
						if paramIdx >= 0 && paramIdx < len(call.Arguments) {
							if root, ok := getRootIdentifier(call.Arguments[paramIdx]); ok {
								mutated[root] = true
							}
						}
					} else {
						mutated[targetRoot] = true
					}
				}
			} else {
				if callee.ReturnType == "" {
					for _, arg := range call.Arguments {
						if root, ok := getRootIdentifier(arg); ok {
							mutated[root] = true
						}
					}
					for _, cg := range callee.GlobalSpecs {
						mode := ""
						if cg.Mode != nil {
							mode = *cg.Mode
						}
						if !calleeParamNames[cg.Name] && (mode == "Output" || mode == "In_Out") {
							mutated[cg.Name] = true
						}
					}
				}
			}
		case ast.IfStmt:
			visitBody(val.ThenBody)
			visitBody(val.ElseBody)
		case ast.WhileStmt:
			visitBody(val.Body)
		case ast.CaseStmt:
			for _, branch := range val.When {
				visitBody(branch.Body)
			}
			visitBody(val.Default)
		case ast.ScopeStmt:
			visitBody(val.SpawnBody)
			visitBody(val.JoinBody)
			visitBody(val.ResultBody)
		}
	}

	visitBody(body)
	return mutated
}

func (a *Analyzer) dependenciesOf(expr ast.Expr, dependencies map[string]map[string]bool, paramNames map[string]bool, seenGlobals map[string]bool) map[string]bool {
	deps := map[string]bool{}
	if expr == nil {
		return deps
	}

	var visit func(e ast.Expr)
	visit = func(e ast.Expr) {
		if e == nil {
			return
		}
		switch val := e.(type) {
		case ast.IdentifierExpr:
			if val.Name == "result" {
				deps["result"] = true
				return
			}
			if d, ok := dependencies[val.Name]; ok {
				for k := range d {
					deps[k] = true
				}
			} else if paramNames[val.Name] || seenGlobals[val.Name] {
				deps[val.Name] = true
			}
		case ast.FieldAccessExpr:
			if root, ok := getRootIdentifier(val); ok {
				if d, ok := dependencies[root]; ok {
					for k := range d {
						deps[k] = true
					}
				} else if paramNames[root] || seenGlobals[root] {
					deps[root] = true
				}
			}
		case ast.IndexExpr:
			visit(val.Array)
			visit(val.Index)
		case ast.UnaryExpr:
			visit(val.Value)
		case ast.BinaryExpr:
			visit(val.Left)
			visit(val.Right)
		case ast.CallExpr:
			for _, arg := range val.Arguments {
				visit(arg)
			}
		case ast.RecordLiteralExpr:
			for _, field := range val.Fields {
				visit(field.Value)
			}
		case ast.ArrayLiteralExpr:
			for _, item := range val.Elements {
				visit(item)
			}
		case ast.AwaitExpr:
			visit(val.Value)
		case ast.OkExpr:
			visit(val.Value)
		}
	}

	visit(expr)
	return deps
}

func (a *Analyzer) analyzeInformationFlow(
	body []ast.Stmt,
	paramNames map[string]bool,
	seenGlobals map[string]bool,
	validSources map[string]bool,
	env map[string]string,
) map[string]map[string]bool {
	dependencies := map[string]map[string]bool{}
	for name := range validSources {
		dependencies[name] = map[string]bool{name: true}
	}

	var controlDeps []map[string]bool
	getActiveControlDeps := func() map[string]bool {
		union := map[string]bool{}
		for _, s := range controlDeps {
			for k := range s {
				union[k] = true
			}
		}
		return union
	}

	var walkBody func(stmts []ast.Stmt)
	walkBody = func(stmts []ast.Stmt) {
		for _, stmt := range stmts {
			switch val := stmt.(type) {
			case ast.AssignmentStmt:
				exprDeps := a.dependenciesOf(val.Value, dependencies, paramNames, seenGlobals)
				activeCtrl := getActiveControlDeps()
				for k := range activeCtrl {
					exprDeps[k] = true
				}
				if targetRoot, ok := getRootIdentifier(val.Target); ok {
					dependencies[targetRoot] = exprDeps
				}
			case ast.LetStmt:
				exprDeps := a.dependenciesOf(val.Value, dependencies, paramNames, seenGlobals)
				activeCtrl := getActiveControlDeps()
				for k := range activeCtrl {
					exprDeps[k] = true
				}
				dependencies[val.Name] = exprDeps
			case ast.CallStmt:
				call, ok := val.Call.(ast.CallExpr)
				if !ok {
					continue
				}
				name, ok := callName(call.Callee)
				if !ok {
					continue
				}
				callee, exists := a.symbols.Routines[name]
				if !exists {
					continue
				}

				calleeParams := make([]string, len(callee.Params))
				calleeParamNames := map[string]bool{}
				for i, p := range callee.Params {
					calleeParams[i] = p.Name
					calleeParamNames[p.Name] = true
				}

				if len(callee.DependsSpecs) > 0 {
					for _, dCallee := range callee.DependsSpecs {
						targetRoot := strings.Split(dCallee.Target, ".")[0]

						allInputs := map[string]bool{}
						for _, src := range dCallee.Sources {
							if src == "+" {
								allInputs[targetRoot] = true
							} else {
								allInputs[strings.Split(src, ".")[0]] = true
							}
						}

						allArgsDeps := map[string]bool{}
						for inputName := range allInputs {
							isParam := false
							paramIdx := -1
							for i, name := range calleeParams {
								if name == inputName {
									isParam = true
									paramIdx = i
									break
								}
							}
							if isParam {
								if paramIdx >= 0 && paramIdx < len(call.Arguments) {
									argDeps := a.dependenciesOf(call.Arguments[paramIdx], dependencies, paramNames, seenGlobals)
									for k := range argDeps {
										allArgsDeps[k] = true
									}
								}
							} else {
								if d, ok := dependencies[inputName]; ok {
									for k := range d {
										allArgsDeps[k] = true
									}
								} else if paramNames[inputName] || seenGlobals[inputName] {
									allArgsDeps[inputName] = true
								}
							}
						}

						activeCtrl := getActiveControlDeps()
						for k := range activeCtrl {
							allArgsDeps[k] = true
						}

						isParam := false
						paramIdx := -1
						for i, name := range calleeParams {
							if name == targetRoot {
								isParam = true
								paramIdx = i
								break
							}
						}

						if isParam {
							if paramIdx >= 0 && paramIdx < len(call.Arguments) {
								if targetVar, ok := getRootIdentifier(call.Arguments[paramIdx]); ok {
									dependencies[targetVar] = allArgsDeps
								}
							}
						} else {
							union := map[string]bool{}
							for k := range allArgsDeps {
								union[k] = true
							}
							if d, ok := dependencies[targetRoot]; ok {
								for k := range d {
									union[k] = true
								}
							}
							dependencies[targetRoot] = union
						}
					}
				} else {
					allArgsDeps := map[string]bool{}
					for _, arg := range call.Arguments {
						argDeps := a.dependenciesOf(arg, dependencies, paramNames, seenGlobals)
						for k := range argDeps {
							allArgsDeps[k] = true
						}
					}
					activeCtrl := getActiveControlDeps()
					for k := range activeCtrl {
						allArgsDeps[k] = true
					}

					for _, arg := range call.Arguments {
						if targetVar, ok := getRootIdentifier(arg); ok {
							dependencies[targetVar] = allArgsDeps
						}
					}

					for _, cg := range callee.GlobalSpecs {
						mode := ""
						if cg.Mode != nil {
							mode = *cg.Mode
						}
						if !calleeParamNames[cg.Name] && (mode == "Output" || mode == "In_Out") {
							union := map[string]bool{}
							for k := range allArgsDeps {
								union[k] = true
							}
							if d, ok := dependencies[cg.Name]; ok {
								for k := range d {
									union[k] = true
								}
							}
							dependencies[cg.Name] = union
						}
					}
				}
			case ast.IfStmt:
				beforeDeps := cloneDependencies(dependencies)
				condDeps := a.dependenciesOf(val.Condition, dependencies, paramNames, seenGlobals)
				controlDeps = append(controlDeps, condDeps)

				walkBody(val.ThenBody)
				thenDeps := cloneDependencies(dependencies)

				dependencies = cloneDependencies(beforeDeps)
				walkBody(val.ElseBody)
				elseDeps := cloneDependencies(dependencies)

				dependencies = map[string]map[string]bool{}
				allKeys := map[string]bool{}
				for k := range thenDeps {
					allKeys[k] = true
				}
				for k := range elseDeps {
					allKeys[k] = true
				}
				for k := range beforeDeps {
					allKeys[k] = true
				}

				for k := range allKeys {
					union := map[string]bool{}
					tD, inThen := thenDeps[k]
					if !inThen {
						tD = beforeDeps[k]
					}
					eD, inElse := elseDeps[k]
					if !inElse {
						eD = beforeDeps[k]
					}
					for x := range tD {
						union[x] = true
					}
					for x := range eD {
						union[x] = true
					}
					dependencies[k] = union
				}

				controlDeps = controlDeps[:len(controlDeps)-1]
			case ast.CaseStmt:
				beforeDeps := cloneDependencies(dependencies)
				condDeps := a.dependenciesOf(val.Value, dependencies, paramNames, seenGlobals)
				controlDeps = append(controlDeps, condDeps)

				var branchDepsList []map[string]map[string]bool
				for _, branch := range val.When {
					dependencies = cloneDependencies(beforeDeps)
					walkBody(branch.Body)
					branchDepsList = append(branchDepsList, cloneDependencies(dependencies))
				}

				if len(val.Default) > 0 {
					dependencies = cloneDependencies(beforeDeps)
					walkBody(val.Default)
					branchDepsList = append(branchDepsList, cloneDependencies(dependencies))
				} else {
					branchDepsList = append(branchDepsList, beforeDeps)
				}

				dependencies = map[string]map[string]bool{}
				allKeys := map[string]bool{}
				for k := range beforeDeps {
					allKeys[k] = true
				}
				for _, bd := range branchDepsList {
					for k := range bd {
						allKeys[k] = true
					}
				}

				for k := range allKeys {
					union := map[string]bool{}
					for _, bd := range branchDepsList {
						d, ok := bd[k]
						if !ok {
							d = beforeDeps[k]
						}
						for x := range d {
							union[x] = true
						}
					}
					dependencies[k] = union
				}

				controlDeps = controlDeps[:len(controlDeps)-1]
			case ast.WhileStmt:
				condDeps := a.dependenciesOf(val.Condition, dependencies, paramNames, seenGlobals)
				controlDeps = append(controlDeps, condDeps)

				loopReads := collectReadVars(val.Condition, val.Body)
				loopMutated := a.collectMutatedVars(val.Body, paramNames, seenGlobals)

				loopReadDeps := map[string]bool{}
				for rVar := range loopReads {
					if d, ok := dependencies[rVar]; ok {
						for k := range d {
							loopReadDeps[k] = true
						}
					} else if paramNames[rVar] || seenGlobals[rVar] {
						loopReadDeps[rVar] = true
					}
				}

				activeCtrl := getActiveControlDeps()
				for k := range condDeps {
					loopReadDeps[k] = true
				}
				for k := range activeCtrl {
					loopReadDeps[k] = true
				}

				walkBody(val.Body)
				for v := range loopMutated {
					union := map[string]bool{}
					for k := range loopReadDeps {
						union[k] = true
					}
					if d, ok := dependencies[v]; ok {
						for k := range d {
							union[k] = true
						}
					}
					dependencies[v] = union
				}

				controlDeps = controlDeps[:len(controlDeps)-1]
			case ast.ScopeStmt:
				walkBody(val.SpawnBody)
				walkBody(val.JoinBody)
				walkBody(val.ResultBody)
			}
		}
	}

	walkBody(body)
	return dependencies
}

func (a *Analyzer) checkTransitiveGlobals(
	body []ast.Stmt,
	routineName string,
	globalSpecs []ast.GlobalSpec,
) {
	rGlobals := map[string]string{}
	for _, g := range globalSpecs {
		mode := "Input"
		if g.Mode != nil {
			mode = *g.Mode
		}
		rGlobals[g.Name] = mode
	}

	var visitExpr func(expr ast.Expr, pos token.Position)
	var visitStmt func(stmt ast.Stmt)

	visitExpr = func(expr ast.Expr, pos token.Position) {
		if expr == nil {
			return
		}
		switch val := expr.(type) {
		case ast.CallExpr:
			name, ok := callName(val.Callee)
			if ok {
				if callee, exists := a.symbols.Routines[name]; exists {
					calleeParamNames := map[string]bool{}
					for _, p := range callee.Params {
						calleeParamNames[p.Name] = true
					}
					for _, cg := range callee.GlobalSpecs {
						if !calleeParamNames[cg.Name] {
							cgMode := "Input"
							if cg.Mode != nil {
								cgMode = *cg.Mode
							}
							rMode, exists := rGlobals[cg.Name]
							if !exists {
								a.diagnostics = append(a.diagnostics, diagnostic.TransitiveGlobalMissing(locationFromPosition(pos), cg.Name, name, routineName))
							} else {
								if cgMode == "In_Out" && rMode != "In_Out" {
									a.diagnostics = append(a.diagnostics, diagnostic.TransitiveGlobalModeMismatch(locationFromPosition(pos), cg.Name, cgMode, routineName, rMode))
								} else if cgMode == "Output" && rMode != "Output" && rMode != "In_Out" {
									a.diagnostics = append(a.diagnostics, diagnostic.TransitiveGlobalModeMismatch(locationFromPosition(pos), cg.Name, cgMode, routineName, rMode))
								} else if cgMode == "Input" && rMode != "Input" && rMode != "In_Out" {
									a.diagnostics = append(a.diagnostics, diagnostic.TransitiveGlobalModeMismatch(locationFromPosition(pos), cg.Name, cgMode, routineName, rMode))
								}
							}
						}
					}
				}
			}
			for _, arg := range val.Arguments {
				visitExpr(arg, pos)
			}
		case ast.FieldAccessExpr:
			visitExpr(val.Object, pos)
		case ast.IndexExpr:
			visitExpr(val.Array, pos)
			visitExpr(val.Index, pos)
		case ast.UnaryExpr:
			visitExpr(val.Value, pos)
		case ast.BinaryExpr:
			visitExpr(val.Left, pos)
			visitExpr(val.Right, pos)
		case ast.RecordLiteralExpr:
			for _, field := range val.Fields {
				visitExpr(field.Value, pos)
			}
		case ast.ArrayLiteralExpr:
			for _, item := range val.Elements {
				visitExpr(item, pos)
			}
		case ast.AwaitExpr:
			visitExpr(val.Value, pos)
		case ast.OkExpr:
			visitExpr(val.Value, pos)
		}
	}

	visitStmt = func(stmt ast.Stmt) {
		switch val := stmt.(type) {
		case ast.AssignmentStmt:
			visitExpr(val.Value, val.Pos)
		case ast.LetStmt:
			visitExpr(val.Value, val.Pos)
		case ast.ReturnStmt:
			visitExpr(val.Value, val.Pos)
		case ast.CheckStmt:
			visitExpr(val.Condition, val.Pos)
		case ast.CallStmt:
			if call, ok := val.Call.(ast.CallExpr); ok {
				visitExpr(call, val.Pos)
			}
		case ast.IfStmt:
			visitExpr(val.Condition, val.Pos)
			for _, s := range val.ThenBody {
				visitStmt(s)
			}
			for _, s := range val.ElseBody {
				visitStmt(s)
			}
		case ast.WhileStmt:
			visitExpr(val.Condition, val.Pos)
			for _, s := range val.Body {
				visitStmt(s)
			}
		case ast.CaseStmt:
			visitExpr(val.Value, val.Pos)
			for _, branch := range val.When {
				visitExpr(branch.Value, val.Pos)
				for _, s := range branch.Body {
					visitStmt(s)
				}
			}
			for _, s := range val.Default {
				visitStmt(s)
			}
		case ast.ScopeStmt:
			for _, s := range val.SpawnBody {
				visitStmt(s)
			}
			for _, s := range val.JoinBody {
				visitStmt(s)
			}
			for _, s := range val.ResultBody {
				visitStmt(s)
			}
		}
	}

	for _, s := range body {
		visitStmt(s)
	}
}

func (a *Analyzer) checkAntiAliasing(
	call ast.CallExpr,
	env map[string]string,
	pos token.Position,
) {
	name, ok := callName(call.Callee)
	if !ok {
		return
	}
	cal, exists := a.symbols.Routines[name]
	if !exists {
		return
	}

	if len(call.Arguments) == len(cal.Params) {
		getParamMode := func(paramName string) string {
			for _, g := range cal.GlobalSpecs {
				if g.Name == paramName {
					if g.Mode != nil {
						return *g.Mode
					}
					return "Input"
				}
			}
			return "Input"
		}

		argRoots := make([]string, len(call.Arguments))
		for i, arg := range call.Arguments {
			if root, ok := getRootIdentifier(arg); ok {
				if t, exists := env[root]; exists && a.symbols.Services[t] {
					argRoots[i] = t
				} else {
					argRoots[i] = root
				}
			}
		}

		var mutableParamIndices []int
		for idx, param := range cal.Params {
			if getParamMode(param.Name) == "Output" || getParamMode(param.Name) == "In_Out" {
				mutableParamIndices = append(mutableParamIndices, idx)
			}
		}

		calleeGlobals := map[string]bool{}
		calleeMutGlobals := map[string]bool{}
		calleeParamNames := map[string]bool{}
		for _, p := range cal.Params {
			calleeParamNames[p.Name] = true
		}

		for _, cg := range cal.GlobalSpecs {
			if !calleeParamNames[cg.Name] {
				calleeGlobals[cg.Name] = true
				cgMode := "Input"
				if cg.Mode != nil {
					cgMode = *cg.Mode
				}
				if cgMode == "Output" || cgMode == "In_Out" {
					calleeMutGlobals[cg.Name] = true
				}
			}
		}

		for i := 0; i < len(call.Arguments); i++ {
			rootI := argRoots[i]
			if rootI == "" {
				continue
			}
			isIMutable := false
			for _, mIdx := range mutableParamIndices {
				if mIdx == i {
					isIMutable = true
					break
				}
			}

			for j := i + 1; j < len(call.Arguments); j++ {
				rootJ := argRoots[j]
				if rootJ == "" {
					continue
				}
				isJMutable := false
				for _, mIdx := range mutableParamIndices {
					if mIdx == j {
						isJMutable = true
						break
					}
				}

				if (isIMutable || isJMutable) && rootI == rootJ {
					paramI := cal.Params[i].Name
					paramJ := cal.Params[j].Name
					msg := fmt.Sprintf("both '%s' and '%s' resolve to the same variable '%s' (at least one is mutable)", paramI, paramJ, rootI)
					a.diagnostics = append(a.diagnostics, diagnostic.AliasingViolation(locationFromPosition(pos), msg))
				}
			}
		}

		for _, idx := range mutableParamIndices {
			rootArg := argRoots[idx]
			if rootArg != "" && calleeGlobals[rootArg] {
				paramName := cal.Params[idx].Name
				msg := fmt.Sprintf("mutable parameter '%s' is passed global variable '%s' which is also accessed directly/transitively by '%s'", paramName, rootArg, name)
				a.diagnostics = append(a.diagnostics, diagnostic.AliasingViolation(locationFromPosition(pos), msg))
			}
		}

		for idx, rootArg := range argRoots {
			if rootArg != "" && calleeMutGlobals[rootArg] {
				paramName := cal.Params[idx].Name
				msg := fmt.Sprintf("argument '%s' resolves to global variable '%s' which is mutated by '%s'", paramName, rootArg, name)
				a.diagnostics = append(a.diagnostics, diagnostic.AliasingViolation(locationFromPosition(pos), msg))
			}
		}
	}
}

func getRootIdentifier(expr ast.Expr) (string, bool) {
	switch val := expr.(type) {
	case ast.IdentifierExpr:
		return val.Name, true
	case ast.FieldAccessExpr:
		return getRootIdentifier(val.Object)
	case ast.IndexExpr:
		return getRootIdentifier(val.Array)
	}
	return "", false
}

func collectReadVars(nodes ...interface{}) map[string]bool {
	reads := map[string]bool{}
	var visit func(node interface{})

	visit = func(node interface{}) {
		if node == nil {
			return
		}
		switch val := node.(type) {
		case ast.IdentifierExpr:
			reads[val.Name] = true
		case ast.FieldAccessExpr:
			if root, ok := getRootIdentifier(val); ok {
				reads[root] = true
			}
		case ast.IndexExpr:
			if root, ok := getRootIdentifier(val); ok {
				reads[root] = true
			}
			visit(val.Index)
		case ast.UnaryExpr:
			visit(val.Value)
		case ast.BinaryExpr:
			visit(val.Left)
			visit(val.Right)
		case ast.CallExpr:
			for _, arg := range val.Arguments {
				visit(arg)
			}
		case ast.RecordLiteralExpr:
			for _, field := range val.Fields {
				visit(field.Value)
			}
		case ast.ArrayLiteralExpr:
			for _, item := range val.Elements {
				visit(item)
			}
		case ast.AwaitExpr:
			visit(val.Value)
		case ast.OkExpr:
			visit(val.Value)
		case ast.AssignmentStmt:
			visit(val.Value)
		case ast.LetStmt:
			visit(val.Value)
		case ast.ReturnStmt:
			visit(val.Value)
		case ast.CheckStmt:
			visit(val.Condition)
		case ast.CallStmt:
			if call, ok := val.Call.(ast.CallExpr); ok {
				for _, arg := range call.Arguments {
					visit(arg)
				}
			}
		case ast.IfStmt:
			visit(val.Condition)
			for _, s := range val.ThenBody {
				visit(s)
			}
			for _, s := range val.ElseBody {
				visit(s)
			}
		case ast.WhileStmt:
			visit(val.Condition)
			for _, s := range val.Body {
				visit(s)
			}
		case ast.CaseStmt:
			visit(val.Value)
			for _, branch := range val.When {
				visit(branch.Value)
				for _, s := range branch.Body {
					visit(s)
				}
			}
			for _, s := range val.Default {
				visit(s)
			}
		case ast.ScopeStmt:
			for _, s := range val.SpawnBody {
				visit(s)
			}
			for _, s := range val.JoinBody {
				visit(s)
			}
			for _, s := range val.ResultBody {
				visit(s)
			}
		}
	}

	for _, n := range nodes {
		visit(n)
	}
	return reads
}

func cloneDependencies(d map[string]map[string]bool) map[string]map[string]bool {
	cloned := map[string]map[string]bool{}
	for k, v := range d {
		sub := map[string]bool{}
		for sk, sv := range v {
			sub[sk] = sv
		}
		cloned[k] = sub
	}
	return cloned
}
