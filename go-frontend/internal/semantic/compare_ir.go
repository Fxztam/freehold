package semantic

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"

	"freehold-go-frontend/internal/ast"
)

const (
	CompareIRSchemaV0       = "fh-compare-ir-v0"
	CompareIRSchemaV1       = "fh-compare-ir-v1"
	FreeholdLanguageVersion = "freehold-v1"
)

type compareIRDocument struct {
	Schema          string          `json:"schema"`
	LanguageVersion string          `json:"language_version"`
	Module          moduleIR        `json:"module"`
	Analysis        analysisSection `json:"analysis"`
}

type moduleIR struct {
	Node         string         `json:"node,omitempty"`
	Name         string         `json:"name"`
	Imports      []importDeclIR `json:"imports"`
	Declarations []any          `json:"declarations"`
}

type analysisSection struct {
	Types    []typeDefIR   `json:"types"`
	Records  []recordDefIR `json:"records"`
	Errors   []string      `json:"errors"`
	Routines []routineDecl `json:"routines"`
	Services []serviceDecl `json:"services"`
}

type importDeclIR struct {
	Kind     string   `json:"kind"`
	Module   string   `json:"module"`
	Exposing []string `json:"exposing"`
}

type typeDeclIR struct {
	Kind     string   `json:"kind"`
	Name     string   `json:"name"`
	Base     string   `json:"base"`
	MinValue *float64 `json:"min_value,omitempty"`
	MaxValue *float64 `json:"max_value,omitempty"`
}

type recordTypeDeclIR struct {
	Kind       string    `json:"kind"`
	Name       string    `json:"name"`
	Fields     []paramIR `json:"fields"`
	TypeParams []string  `json:"type_params,omitempty"`
}

type errorDeclIR struct {
	Kind string `json:"kind"`
	Name string `json:"name"`
}

type typeDefIR struct {
	Kind     string     `json:"kind,omitempty"`
	Name     string     `json:"name"`
	Base     string     `json:"base"`
	BaseType *typeRefIR `json:"base_type,omitempty"`
	MinValue *float64   `json:"min_value,omitempty"`
	MaxValue *float64   `json:"max_value,omitempty"`
}

type recordDefIR struct {
	Kind        string          `json:"kind,omitempty"`
	Name        string          `json:"name"`
	Fields      []recordFieldIR `json:"fields"`
	ProtoFields []protoFieldIR  `json:"proto_fields"`
}

type recordFieldIR struct {
	Kind     string    `json:"kind"`
	Name     string    `json:"name"`
	Type     string    `json:"type"`
	TypeRepr typeRefIR `json:"type_repr"`
}

type protoFieldIR struct {
	Name string `json:"name"`
	ID   int    `json:"id"`
}

type serviceDecl struct {
	Kind string    `json:"kind"`
	Name string    `json:"name"`
	Rpcs []rpcDecl `json:"rpcs"`
}

type rpcDecl struct {
	Kind             string    `json:"kind"`
	Name             string    `json:"name"`
	RequestName      string    `json:"request_name"`
	RequestType      string    `json:"request_type"`
	RequestTypeRepr  typeRefIR `json:"request_type_repr"`
	ResponseType     string    `json:"response_type"`
	ResponseTypeRepr typeRefIR `json:"response_type_repr"`
}

type routineDecl struct {
	Kind             string             `json:"kind"`
	RoutineKind      string             `json:"routine_kind"`
	Name             string             `json:"name"`
	TypeParams       []string           `json:"type_params"`
	IsAsync          bool               `json:"is_async"`
	Params           []paramIR          `json:"params"`
	ReturnType       typeRefIR          `json:"return_type"`
	Requires         []any              `json:"requires"`
	Aborts           []abortClause      `json:"aborts"`
	Ensures          []any              `json:"ensures"`
	Contracts        contractSection    `json:"contracts,omitempty"`
	ContractBindings contractBindingsIR `json:"contract_bindings,omitempty"`
	Body             []any              `json:"body"`
}

type paramIR struct {
	Name     string    `json:"name"`
	Type     string    `json:"type"`
	TypeRepr typeRefIR `json:"type_repr,omitempty"`
	ProtoID  *int      `json:"proto_id,omitempty"`
}

type typeRefIR struct {
	Kind            string      `json:"kind"`
	Name            string      `json:"name,omitempty"`
	Args            []typeRefIR `json:"args,omitempty"`
	Text            string      `json:"text,omitempty"`
	OkType          *typeRefIR  `json:"ok_type,omitempty"`
	ErrorType       string      `json:"error_type,omitempty"`
	ErrorRef        *errorRefIR `json:"error_ref,omitempty"`
	ElementType     string      `json:"element_type,omitempty"`
	ElementTypeRepr *typeRefIR  `json:"element_type_repr,omitempty"`
	Size            *int        `json:"size,omitempty"`
}

type errorRefIR struct {
	Kind string `json:"kind"`
	Name string `json:"name"`
}

type contractSection struct {
	Requires []any         `json:"requires"`
	Ensures  []any         `json:"ensures"`
	Aborts   []abortClause `json:"aborts"`
}

type contractClauseIR struct {
	Kind      string `json:"kind"`
	Role      string `json:"role"`
	Index     int    `json:"index"`
	Condition any    `json:"condition"`
}

type contractContextIR struct {
	Result  bool `json:"result"`
	Success bool `json:"success"`
	Failure bool `json:"failure"`
	Value   bool `json:"value"`
	Error   bool `json:"error"`
}

type contractContextMatrixIR struct {
	Requires contractContextIR `json:"requires"`
	Ensures  contractContextIR `json:"ensures"`
	Aborts   contractContextIR `json:"aborts"`
}

type contractBindingIR struct {
	Kind      string    `json:"kind"`
	Name      string    `json:"name"`
	Available bool      `json:"available"`
	Type      typeRefIR `json:"type"`
}

type errorContractBindingIR struct {
	Kind      string      `json:"kind"`
	Name      string      `json:"name"`
	Available bool        `json:"available"`
	Type      typeRefIR   `json:"type"`
	ErrorRef  *errorRefIR `json:"error_ref"`
}

type resultBindingIR struct {
	Name      string    `json:"name"`
	Available bool      `json:"available"`
	Type      typeRefIR `json:"type"`
}

type resultErrorBindingIR struct {
	Name      string      `json:"name"`
	Available bool        `json:"available"`
	Type      typeRefIR   `json:"type"`
	ErrorRef  *errorRefIR `json:"error_ref"`
}

type contractBindingsIR struct {
	Kind               string                  `json:"kind"`
	IsResultReturn     bool                    `json:"is_result_return"`
	Contexts           contractContextMatrixIR `json:"contexts"`
	Bindings           []any                   `json:"bindings"`
	ResultValueBinding resultBindingIR         `json:"result_value_binding"`
	ResultErrorBinding resultErrorBindingIR    `json:"result_error_binding"`
}

type abortClause struct {
	Kind      string      `json:"kind"`
	Error     string      `json:"error"`
	ErrorRef  *errorRefIR `json:"error_ref,omitempty"`
	Condition any         `json:"condition,omitempty"`
}

type returnStmtIR struct {
	Kind  string `json:"kind"`
	Value any    `json:"value"`
}

type returnPlainIR struct {
	Kind  string `json:"kind"`
	Value any    `json:"value"`
}

type returnOkIR struct {
	Kind  string `json:"kind"`
	Value any    `json:"value"`
}

type returnErrorIR struct {
	Kind  string `json:"kind"`
	Error string `json:"error"`
}

type letStmtIR struct {
	Kind  string    `json:"kind"`
	Name  string    `json:"name"`
	Type  typeRefIR `json:"type"`
	Value any       `json:"value"`
}

type assignStmtIR struct {
	Kind  string `json:"kind"`
	Name  string `json:"name"`
	Value any    `json:"value"`
}

type fieldAssignStmtIR struct {
	Kind  string   `json:"kind"`
	Path  []string `json:"path"`
	Value any      `json:"value"`
}

type abortStmtIR struct {
	Kind  string `json:"kind"`
	Error string `json:"error"`
}

type checkStmtIR struct {
	Kind      string `json:"kind"`
	Condition any    `json:"condition"`
}

type callStmtIR struct {
	Kind string `json:"kind"`
	Name string `json:"name"`
	Args []any  `json:"args"`
}

type ifStmtIR struct {
	Kind      string `json:"kind"`
	Condition any    `json:"condition"`
	ThenBody  []any  `json:"then_body"`
	ElseBody  []any  `json:"else_body"`
}

type whileStmtIR struct {
	Kind       string `json:"kind"`
	Condition  any    `json:"condition"`
	Invariants []any  `json:"invariants"`
	Body       []any  `json:"body"`
	Variant    any    `json:"variant,omitempty"`
}

type caseBranchIR struct {
	Value any   `json:"value"`
	Body  []any `json:"body"`
}

type caseStmtIR struct {
	Kind        string         `json:"kind"`
	Value       any            `json:"value"`
	Branches    []caseBranchIR `json:"branches"`
	DefaultBody []any          `json:"default_body"`
}

type scopeStmtIR struct {
	Kind       string `json:"kind"`
	Name       string `json:"name"`
	SpawnBody  []any  `json:"spawn_body"`
	JoinBody   []any  `json:"join_body"`
	ResultBody []any  `json:"result_body"`
}

type positionalArgIR struct {
	Kind  string `json:"kind"`
	Value any    `json:"value"`
}

type namedArgIR struct {
	Kind  string `json:"kind"`
	Name  string `json:"name"`
	Value any    `json:"value"`
}

type stringExprIR struct {
	Kind  string `json:"kind"`
	Value string `json:"value"`
}

type numberExprIR struct {
	Kind  string `json:"kind"`
	Value any    `json:"value"`
}

type boolExprIR struct {
	Kind  string `json:"kind"`
	Value bool   `json:"value"`
}

type specialResultExprIR struct {
	Kind string `json:"kind"`
	Name string `json:"name"`
}

type varExprIR struct {
	Kind string `json:"kind"`
	Name string `json:"name"`
}

type fieldAccessExprIR struct {
	Kind string   `json:"kind"`
	Path []string `json:"path"`
}

type callExprIR struct {
	Kind     string   `json:"kind"`
	Name     string   `json:"name"`
	Args     []any    `json:"args"`
	TypeArgs []string `json:"type_args,omitempty"`
}

type awaitExprIR struct {
	Kind  string `json:"kind"`
	Value any    `json:"value"`
}

type recordLiteralExprIR struct {
	Kind string `json:"kind"`
	Type string `json:"type"`
	Args []any  `json:"args"`
}

type arrayLiteralExprIR struct {
	Kind  string `json:"kind"`
	Items []any  `json:"items"`
}

type indexExprIR struct {
	Kind  string `json:"kind"`
	Name  string `json:"name"`
	Index any    `json:"index"`
}

type indexedFieldAccessExprIR struct {
	Kind   string   `json:"kind"`
	Name   string   `json:"name"`
	Index  any      `json:"index"`
	Fields []string `json:"fields"`
}

type unaryExprIR struct {
	Kind  string `json:"kind"`
	Op    string `json:"op"`
	Value any    `json:"value"`
}

type binaryExprIR struct {
	Kind  string `json:"kind"`
	Op    string `json:"op"`
	Left  any    `json:"left"`
	Right any    `json:"right"`
}

type nullExprIR struct {
	Kind string `json:"kind"`
}

type moduleEnv struct {
	Types    map[string]typeDefIR
	Records  map[string]recordDefIR
	Errors   map[string]bool
	Routines map[string]routineDecl
	Services map[string]serviceDecl
}

func schemaForCompareProfile(profile string) (string, error) {
	switch strings.ToLower(strings.TrimSpace(profile)) {
	case "", "v1":
		return CompareIRSchemaV1, nil
	case "v0":
		return CompareIRSchemaV0, nil
	default:
		return "", fmt.Errorf("unsupported compare-ir profile: %q", profile)
	}
}

func ExportCompareIRJSON(entryFile string, profile string) (string, error) {
	project, diagnostics, err := ValidateProject(entryFile)
	if err != nil {
		return "", err
	}
	if len(diagnostics) > 0 {
		return "", errors.New(diagnostics[0].Error())
	}
	if project == nil || project.Entry == nil {
		return "", fmt.Errorf("failed to load project")
	}

	schema, err := schemaForCompareProfile(profile)
	if err != nil {
		return "", err
	}

	envCache := map[string]moduleEnv{}
	env, err := buildModuleEnv(project, project.Entry.Name, envCache)
	if err != nil {
		return "", err
	}

	doc := compareIRDocument{
		Schema:          schema,
		LanguageVersion: FreeholdLanguageVersion,
		Module:          exportModule(project.Entry),
		Analysis: analysisSection{
			Types:    sortedTypeDefs(env.Types),
			Records:  sortedRecordDefs(env.Records),
			Errors:   sortedErrorNames(env.Errors),
			Routines: sortedRoutines(localRoutines(project.Entry)),
			Services: sortedServices(localServices(project.Entry)),
		},
	}

	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(doc); err != nil {
		return "", err
	}
	return buffer.String(), nil
}

func exportModule(module *ast.Module) moduleIR {
	imports := []importDeclIR{}
	declarations := []any{}

	for _, decl := range module.Declarations {
		switch value := decl.(type) {
		case ast.ImportDecl:
			exposing := append([]string{}, value.Exposing...)
			sort.Strings(exposing)
			imports = append(imports, importDeclIR{Kind: "ImportDecl", Module: value.Module, Exposing: exposing})
		case ast.TypeDecl:
			if value.Base == "record" {
				declarations = append(declarations, exportRecordTypeDecl(value))
			} else {
				declarations = append(declarations, exportTypeDecl(value))
			}
		case ast.ErrorDecl:
			declarations = append(declarations, errorDeclIR{Kind: "ErrorDecl", Name: value.Name})
		case ast.ServiceDecl:
			declarations = append(declarations, exportServiceDecl(value))
		case ast.FunctionDecl:
			declarations = append(declarations, exportRoutineFromFunction(value))
		case ast.ProcedureDecl:
			declarations = append(declarations, exportRoutineFromProcedure(value))
		}
	}

	sort.Slice(imports, func(i, j int) bool {
		if imports[i].Module == imports[j].Module {
			return strings.Join(imports[i].Exposing, "\x00") < strings.Join(imports[j].Exposing, "\x00")
		}
		return imports[i].Module < imports[j].Module
	})
	sortModuleDeclarations(declarations)

	return moduleIR{Node: "Module", Name: module.Name, Imports: imports, Declarations: declarations}
}

func sortModuleDeclarations(declarations []any) {
	sort.Slice(declarations, func(i, j int) bool {
		leftKind, leftName := declarationSortData(declarations[i])
		rightKind, rightName := declarationSortData(declarations[j])
		if leftKind == rightKind {
			return leftName < rightName
		}
		return leftKind < rightKind
	})
}

func declarationSortData(item any) (int, string) {
	switch value := item.(type) {
	case typeDeclIR:
		return 0, value.Name
	case recordTypeDeclIR:
		return 1, value.Name
	case errorDeclIR:
		return 2, value.Name
	case serviceDecl:
		return 3, value.Name
	case routineDecl:
		return 4, value.Name
	default:
		return 9, ""
	}
}

func exportTypeDecl(value ast.TypeDecl) typeDeclIR {
	item := typeDeclIR{Kind: "TypeDecl", Name: value.Name, Base: value.Base}
	if value.Range != nil {
		if parsed, ok := parseNumber(value.Range.Min); ok {
			item.MinValue = &parsed
		}
		if parsed, ok := parseNumber(value.Range.Max); ok {
			item.MaxValue = &parsed
		}
	}
	return item
}

func exportRecordTypeDecl(value ast.TypeDecl) recordTypeDeclIR {
	fields := make([]paramIR, 0, len(value.Fields))
	for _, field := range sortedParams(value.Fields) {
		fields = append(fields, paramIR{Name: field.Name, Type: field.Type, TypeRepr: typeRefFromName(field.Type), ProtoID: field.ProtoID})
	}
	item := recordTypeDeclIR{Kind: "RecordTypeDecl", Name: value.Name, Fields: fields}
	if len(value.TypeParams) > 0 {
		item.TypeParams = append([]string(nil), value.TypeParams...)
		sort.Strings(item.TypeParams)
	}
	return item
}

func sortedParams(params []ast.Param) []ast.Param {
	items := append([]ast.Param(nil), params...)
	sort.Slice(items, func(i, j int) bool { return items[i].Name < items[j].Name })
	return items
}

func localServices(module *ast.Module) map[string]serviceDecl {
	services := map[string]serviceDecl{}
	for _, decl := range module.Declarations {
		value, ok := decl.(ast.ServiceDecl)
		if !ok {
			continue
		}
		services[value.Name] = exportServiceDecl(value)
	}
	return services
}

func localRoutines(module *ast.Module) map[string]routineDecl {
	routines := map[string]routineDecl{}
	for _, decl := range module.Declarations {
		switch value := decl.(type) {
		case ast.FunctionDecl:
			routines[value.Name] = exportRoutineFromFunction(value)
		case ast.ProcedureDecl:
			routines[value.Name] = exportRoutineFromProcedure(value)
		}
	}
	return routines
}

func exportServiceDecl(value ast.ServiceDecl) serviceDecl {
	rpcs := append([]ast.RpcDecl(nil), value.Rpcs...)
	sort.Slice(rpcs, func(i, j int) bool { return rpcs[i].Name < rpcs[j].Name })
	items := make([]rpcDecl, 0, len(rpcs))
	for _, rpc := range rpcs {
		items = append(items, rpcDecl{
			Kind:             "RpcDecl",
			Name:             rpc.Name,
			RequestName:      rpc.RequestName,
			RequestType:      rpc.RequestType,
			RequestTypeRepr:  typeRefFromName(rpc.RequestType),
			ResponseType:     rpc.ResponseType,
			ResponseTypeRepr: typeRefFromName(rpc.ResponseType),
		})
	}
	return serviceDecl{Kind: "ServiceDecl", Name: value.Name, Rpcs: items}
}

func exportRoutineFromFunction(value ast.FunctionDecl) routineDecl {
	params := make([]paramIR, 0, len(value.Params))
	for _, param := range value.Params {
		params = append(params, paramIR{Name: param.Name, Type: param.Type, TypeRepr: typeRefFromName(param.Type)})
	}
	typeParams := append([]string{}, value.TypeParams...)
	sort.Strings(typeParams)
	requires := exportExprList(value.Requires)
	ensures := exportExprList(value.Ensures)
	contracts := contractSection{Requires: exportContractClauses("requires", value.Requires), Ensures: exportContractClauses("ensures", value.Ensures), Aborts: exportAbortClauses(value.Aborts)}
	returnType := typeRefFromName(value.ReturnType)
	return routineDecl{
		Kind:             "RoutineDecl",
		RoutineKind:      "function",
		Name:             value.Name,
		TypeParams:       typeParams,
		IsAsync:          value.IsAsync,
		Params:           params,
		ReturnType:       returnType,
		Requires:         requires,
		Aborts:           contracts.Aborts,
		Ensures:          ensures,
		Contracts:        contracts,
		ContractBindings: buildContractBindings(returnType),
		Body:             exportStmtList(value.Body),
	}
}

func exportRoutineFromProcedure(value ast.ProcedureDecl) routineDecl {
	params := make([]paramIR, 0, len(value.Params))
	for _, param := range value.Params {
		params = append(params, paramIR{Name: param.Name, Type: param.Type, TypeRepr: typeRefFromName(param.Type)})
	}
	returnType := typeRefIR{Kind: "Void"}
	requires := exportExprList(value.Requires)
	ensures := exportExprList(value.Ensures)
	contracts := contractSection{Requires: exportContractClauses("requires", value.Requires), Ensures: exportContractClauses("ensures", value.Ensures), Aborts: exportAbortClauses(value.Aborts)}
	return routineDecl{
		Kind:             "RoutineDecl",
		RoutineKind:      "procedure",
		Name:             value.Name,
		TypeParams:       []string{},
		IsAsync:          false,
		Params:           params,
		ReturnType:       returnType,
		Requires:         requires,
		Aborts:           contracts.Aborts,
		Ensures:          ensures,
		Contracts:        contracts,
		ContractBindings: buildContractBindings(returnType),
		Body:             exportStmtList(value.Body),
	}
}

func exportAbortClauses(clauses []ast.AbortClause) []abortClause {
	items := make([]abortClause, 0, len(clauses))
	for _, clause := range clauses {
		errorRef := &errorRefIR{Kind: "ErrorRef", Name: clause.Error}
		if clause.Condition != nil {
			items = append(items, abortClause{Kind: "AbortContractClause", Error: clause.Error, ErrorRef: errorRef, Condition: exportExpr(clause.Condition)})
		} else {
			items = append(items, abortClause{Kind: "AbortContractClause", Error: clause.Error, ErrorRef: errorRef})
		}
	}
	return items
}

func exportContractClauses(role string, expressions []ast.Expr) []any {
	items := make([]any, 0, len(expressions))
	for index, expr := range expressions {
		items = append(items, contractClauseIR{Kind: "ContractClause", Role: role, Index: index, Condition: exportExpr(expr)})
	}
	return items
}

func exportStmtList(stmts []ast.Stmt) []any {
	items := make([]any, 0, len(stmts))
	for _, stmt := range stmts {
		items = append(items, exportStmt(stmt))
	}
	return items
}

func exportStmt(stmt ast.Stmt) any {
	switch value := stmt.(type) {
	case ast.LetStmt:
		return letStmtIR{Kind: "LetStmt", Name: value.Name, Type: typeRefFromName(value.Type), Value: exportExpr(value.Value)}
	case ast.AssignmentStmt:
		if path, ok := flattenFieldPath(value.Target); ok && len(path) > 1 {
			return fieldAssignStmtIR{Kind: "FieldAssignStmt", Path: path, Value: exportExpr(value.Value)}
		}
		if id, ok := value.Target.(ast.IdentifierExpr); ok {
			return assignStmtIR{Kind: "AssignStmt", Name: id.Name, Value: exportExpr(value.Value)}
		}
		return assignStmtIR{Kind: "AssignStmt", Name: "<expr>", Value: exportExpr(value.Value)}
	case ast.ReturnStmt:
		return returnStmtIR{Kind: "ReturnStmt", Value: exportReturnValue(value.Value)}
	case ast.AbortStmt:
		return abortStmtIR{Kind: "AbortStmt", Error: value.Error}
	case ast.CheckStmt:
		return checkStmtIR{Kind: "CheckStmt", Condition: exportExpr(value.Condition)}
	case ast.CallStmt:
		if call, ok := value.Call.(ast.CallExpr); ok {
			name, _ := callName(call.Callee)
			return callStmtIR{Kind: "CallStmt", Name: name, Args: exportCallArgs(call.Arguments)}
		}
		return callStmtIR{Kind: "CallStmt", Name: "<expr>", Args: []any{}}
	case ast.IfStmt:
		return ifStmtIR{Kind: "IfStmt", Condition: exportExpr(value.Condition), ThenBody: exportStmtList(value.ThenBody), ElseBody: exportStmtList(value.ElseBody)}
	case ast.WhileStmt:
		item := whileStmtIR{Kind: "WhileStmt", Condition: exportExpr(value.Condition), Invariants: exportExprList(value.Invariants), Body: exportStmtList(value.Body)}
		if value.Variant != nil {
			item.Variant = exportExpr(value.Variant)
		}
		return item
	case ast.CaseStmt:
		branches := []caseBranchIR{}
		for _, branch := range value.When {
			branches = append(branches, caseBranchIR{Value: exportExpr(branch.Value), Body: exportStmtList(branch.Body)})
		}
		return caseStmtIR{Kind: "CaseStmt", Value: exportExpr(value.Value), Branches: branches, DefaultBody: exportStmtList(value.Default)}
	case ast.ScopeStmt:
		return scopeStmtIR{Kind: "ScopeStmt", Name: value.Name, SpawnBody: exportStmtList(value.SpawnBody), JoinBody: exportStmtList(value.JoinBody), ResultBody: exportStmtList(value.ResultBody)}
	default:
		return nullExprIR{Kind: "UnknownStmt"}
	}
}

func exportReturnValue(expr ast.Expr) any {
	switch value := expr.(type) {
	case ast.OkExpr:
		return returnOkIR{Kind: "ReturnOk", Value: exportExpr(value.Value)}
	case ast.ErrorExpr:
		return returnErrorIR{Kind: "ReturnError", Error: value.Name}
	default:
		return returnPlainIR{Kind: "ReturnPlain", Value: exportExpr(expr)}
	}
}

func exportExprList(expressions []ast.Expr) []any {
	items := make([]any, 0, len(expressions))
	for _, expr := range expressions {
		items = append(items, exportExpr(expr))
	}
	return items
}

func exportCallArgs(args []ast.Expr) []any {
	items := make([]any, 0, len(args))
	for _, arg := range args {
		if named, ok := arg.(ast.NamedArgumentExpr); ok {
			items = append(items, namedArgIR{Kind: "NamedArg", Name: named.Name, Value: exportExpr(named.Value)})
			continue
		}
		items = append(items, positionalArgIR{Kind: "PositionalArg", Value: exportExpr(arg)})
	}
	return items
}

func exportExpr(expr ast.Expr) any {
	switch value := expr.(type) {
	case nil:
		return nullExprIR{Kind: "NullExpr"}
	case ast.StringExpr:
		return stringExprIR{Kind: "StringExpr", Value: value.Value}
	case ast.NumberExpr:
		if strings.Contains(value.Value, ".") {
			if _, err := strconv.ParseFloat(value.Value, 64); err == nil {
				return numberExprIR{Kind: "DoubleExpr", Value: json.Number(value.Value)}
			}
		}
		if parsed, err := strconv.Atoi(value.Value); err == nil {
			return numberExprIR{Kind: "NumberExpr", Value: parsed}
		}
		if parsed, err := strconv.ParseFloat(value.Value, 64); err == nil {
			return numberExprIR{Kind: "DoubleExpr", Value: parsed}
		}
		return numberExprIR{Kind: "NumberExpr", Value: value.Value}
	case ast.IdentifierExpr:
		if value.Name == "true" {
			return boolExprIR{Kind: "BoolExpr", Value: true}
		}
		if value.Name == "false" {
			return boolExprIR{Kind: "BoolExpr", Value: false}
		}
		return varExprIR{Kind: "VarExpr", Name: value.Name}
	case ast.FieldAccessExpr:
		if name, index, fields, ok := flattenIndexedFieldAccess(value); ok {
			return indexedFieldAccessExprIR{Kind: "IndexedFieldAccessExpr", Name: name, Index: exportExpr(index), Fields: fields}
		}
		if path, ok := flattenFieldPath(value); ok {
			return fieldAccessExprIR{Kind: "FieldAccessExpr", Path: path}
		}
		return fieldAccessExprIR{Kind: "FieldAccessExpr", Path: []string{"<field>"}}
	case ast.CallExpr:
		name, _ := callName(value.Callee)
		item := callExprIR{Kind: "CallExpr", Name: name, Args: exportCallArgs(value.Arguments)}
		if len(value.TypeArgs) > 0 {
			item.TypeArgs = append([]string(nil), value.TypeArgs...)
		}
		return item
	case ast.AwaitExpr:
		return awaitExprIR{Kind: "AwaitExpr", Value: exportExpr(value.Value)}
	case ast.RecordLiteralExpr:
		return recordLiteralExprIR{Kind: "RecordLiteralExpr", Type: value.Type, Args: exportRecordLiteralArgs(value.Fields)}
	case ast.ArrayLiteralExpr:
		items := make([]any, 0, len(value.Elements))
		for _, element := range value.Elements {
			items = append(items, exportExpr(element))
		}
		return arrayLiteralExprIR{Kind: "ArrayLiteralExpr", Items: items}
	case ast.IndexExpr:
		if id, ok := value.Array.(ast.IdentifierExpr); ok {
			return indexExprIR{Kind: "IndexExpr", Name: id.Name, Index: exportExpr(value.Index)}
		}
		return indexExprIR{Kind: "IndexExpr", Name: "<expr>", Index: exportExpr(value.Index)}
	case ast.UnaryExpr:
		return unaryExprIR{Kind: "UnaryExpr", Op: value.Op, Value: exportExpr(value.Value)}
	case ast.BinaryExpr:
		return binaryExprIR{Kind: "BinaryExpr", Op: value.Op, Left: exportExpr(value.Left), Right: exportExpr(value.Right)}
	case ast.OkExpr:
		return exportExpr(value.Value)
	case ast.ErrorExpr:
		return varExprIR{Kind: "VarExpr", Name: value.Name}
	default:
		return nullExprIR{Kind: "UnknownExpr"}
	}
}

func exportRecordLiteralArgs(fields []ast.RecordField) []any {
	items := make([]any, 0, len(fields))
	for _, field := range fields {
		items = append(items, namedArgIR{Kind: "NamedArg", Name: field.Name, Value: exportExpr(field.Value)})
	}
	return items
}

func flattenFieldPath(expr ast.Expr) ([]string, bool) {
	switch value := expr.(type) {
	case ast.IdentifierExpr:
		return []string{value.Name}, true
	case ast.FieldAccessExpr:
		base, ok := flattenFieldPath(value.Object)
		if !ok {
			return nil, false
		}
		return append(base, value.Field), true
	default:
		return nil, false
	}
}

func flattenIndexedFieldAccess(expr ast.FieldAccessExpr) (string, ast.Expr, []string, bool) {
	fields := []string{expr.Field}
	current := expr.Object
	for {
		switch value := current.(type) {
		case ast.FieldAccessExpr:
			fields = append([]string{value.Field}, fields...)
			current = value.Object
		case ast.IndexExpr:
			if id, ok := value.Array.(ast.IdentifierExpr); ok {
				return id.Name, value.Index, fields, true
			}
			return "", nil, nil, false
		default:
			return "", nil, nil, false
		}
	}
}

func typeRefFromName(name string) typeRefIR {
	name = strings.TrimSpace(name)
	if name == "" {
		return typeRefIR{Kind: "Void"}
	}
	if strings.HasPrefix(name, "Result<") && strings.HasSuffix(name, ">") {
		parts := splitTopLevel(name[len("Result<") : len(name)-1])
		if len(parts) == 2 {
			okType := typeRefFromName(parts[0])
			errorName := strings.TrimSpace(parts[1])
			return typeRefIR{Kind: "ResultTypeName", OkType: &okType, ErrorType: errorName, ErrorRef: &errorRefIR{Kind: "ErrorRef", Name: errorName}}
		}
	}
	if strings.HasPrefix(name, "Array<") && strings.HasSuffix(name, ">") {
		parts := splitTopLevel(name[len("Array<") : len(name)-1])
		if len(parts) == 2 {
			elementName := strings.TrimSpace(parts[0])
			elementType := typeRefFromName(elementName)
			sizeValue, err := strconv.Atoi(strings.TrimSpace(parts[1]))
			if err == nil {
				return typeRefIR{Kind: "ArrayTypeName", ElementType: elementName, ElementTypeRepr: &elementType, Size: &sizeValue}
			}
		}
	}
	if genericBase, genericArgs, ok := parseGenericType(name); ok {
		args := make([]typeRefIR, 0, len(genericArgs))
		for _, arg := range genericArgs {
			args = append(args, typeRefFromName(arg))
		}
		return typeRefIR{Kind: "GenericTypeName", Name: genericBase, Args: args, Text: name}
	}
	return typeRefIR{Kind: "TypeName", Name: name}
}

func boolTypeRef() typeRefIR {
	return typeRefIR{Kind: "TypeName", Name: "Boolean"}
}

func voidTypeRef() typeRefIR {
	return typeRefIR{Kind: "Void"}
}

func isResultType(ref typeRefIR) bool {
	return ref.Kind == "ResultTypeName" && ref.OkType != nil
}

func buildContractBindings(returnType typeRefIR) contractBindingsIR {
	isResult := isResultType(returnType)
	hasReturn := returnType.Kind != "Void"
	ensuresCtx := contractContextIR{Result: true}
	ensuresCtx.Value = hasReturn
	if isResult {
		ensuresCtx.Success = true
		ensuresCtx.Failure = true
		ensuresCtx.Error = true
	}

	valueType := returnType
	if isResult && returnType.OkType != nil {
		valueType = *returnType.OkType
	} else if !hasReturn {
		valueType = voidTypeRef()
	}

	errorType := voidTypeRef()
	var errorRef *errorRefIR
	if isResult && returnType.ErrorType != "" {
		errorType = typeRefIR{Kind: "TypeName", Name: returnType.ErrorType}
		errorRef = &errorRefIR{Kind: "ErrorRef", Name: returnType.ErrorType}
	}

	bindings := []any{
		contractBindingIR{Kind: "ContractBinding", Name: "result", Available: true, Type: returnType},
		contractBindingIR{Kind: "ContractBinding", Name: "success", Available: isResult, Type: boolTypeRef()},
		contractBindingIR{Kind: "ContractBinding", Name: "failure", Available: isResult, Type: boolTypeRef()},
		contractBindingIR{Kind: "ContractBinding", Name: "value", Available: hasReturn, Type: valueType},
		errorContractBindingIR{Kind: "ContractBinding", Name: "error", Available: isResult, Type: errorType, ErrorRef: errorRef},
	}

	return contractBindingsIR{
		Kind:           "ContractBindings",
		IsResultReturn: isResult,
		Contexts: contractContextMatrixIR{
			Requires: contractContextIR{},
			Ensures:  ensuresCtx,
			Aborts:   contractContextIR{},
		},
		Bindings:           bindings,
		ResultValueBinding: resultBindingIR{Name: "value", Available: hasReturn, Type: valueType},
		ResultErrorBinding: resultErrorBindingIR{Name: "error", Available: isResult, Type: errorType, ErrorRef: errorRef},
	}
}

func buildModuleEnv(project *Project, moduleName string, cache map[string]moduleEnv) (moduleEnv, error) {
	if env, ok := cache[moduleName]; ok {
		return env, nil
	}
	module := project.Modules[moduleName]
	if module == nil {
		return moduleEnv{}, fmt.Errorf("unknown module: %s", moduleName)
	}

	env := moduleEnv{
		Types:    map[string]typeDefIR{},
		Records:  map[string]recordDefIR{},
		Errors:   map[string]bool{},
		Routines: map[string]routineDecl{},
		Services: map[string]serviceDecl{},
	}
	for _, name := range []string{"BigFloat", "BigInteger", "Boolean", "Double", "Executor", "Integer", "Scope", "String"} {
		baseType := typeRefIR{Kind: "TypeName", Name: name}
		env.Types[name] = typeDefIR{Kind: "TypeDef", Name: name, Base: name, BaseType: &baseType}
	}

	for _, decl := range module.Declarations {
		switch value := decl.(type) {
		case ast.TypeDecl:
			if value.Base == "record" {
				env.Records[value.Name] = exportRecordDef(value)
			} else {
				env.Types[value.Name] = exportTypeDef(value)
			}
		case ast.ErrorDecl:
			env.Errors[value.Name] = true
		case ast.FunctionDecl:
			env.Routines[value.Name] = exportRoutineFromFunction(value)
		case ast.ProcedureDecl:
			env.Routines[value.Name] = exportRoutineFromProcedure(value)
		case ast.ServiceDecl:
			env.Services[value.Name] = exportServiceDecl(value)
		}
	}

	for _, decl := range module.Declarations {
		importDecl, ok := decl.(ast.ImportDecl)
		if !ok || runtimeModules[importDecl.Module] {
			continue
		}
		imported, err := buildModuleEnv(project, importDecl.Module, cache)
		if err != nil {
			return moduleEnv{}, err
		}
		for _, symbol := range importDecl.Exposing {
			exposesSymbol := false
			if value, ok := imported.Types[symbol]; ok {
				exposesSymbol = true
				if _, exists := env.Types[symbol]; !exists {
					env.Types[symbol] = value
				}
			}
			if value, ok := imported.Records[symbol]; ok {
				exposesSymbol = true
				if _, exists := env.Records[symbol]; !exists {
					env.Records[symbol] = value
				}
			}
			if imported.Errors[symbol] {
				exposesSymbol = true
				env.Errors[symbol] = true
			}
			if value, ok := imported.Routines[symbol]; ok {
				exposesSymbol = true
				if _, exists := env.Routines[symbol]; !exists {
					env.Routines[symbol] = value
				}
			}
			if exposesSymbol {
				mergeImportedTypeEnv(&env, imported)
			}
		}
	}

	cache[moduleName] = env
	return env, nil
}

func mergeImportedTypeEnv(env *moduleEnv, imported moduleEnv) {
	for name, value := range imported.Types {
		if _, exists := env.Types[name]; !exists {
			env.Types[name] = value
		}
	}
	for name, value := range imported.Records {
		if _, exists := env.Records[name]; !exists {
			env.Records[name] = value
		}
	}
	for name := range imported.Errors {
		env.Errors[name] = true
	}
}

func exportTypeDef(value ast.TypeDecl) typeDefIR {
	baseType := typeRefFromName(value.Base)
	item := typeDefIR{Kind: "TypeDef", Name: value.Name, Base: value.Base, BaseType: &baseType}
	if value.Range != nil {
		if parsed, ok := parseNumber(value.Range.Min); ok {
			item.MinValue = &parsed
		}
		if parsed, ok := parseNumber(value.Range.Max); ok {
			item.MaxValue = &parsed
		}
	}
	return item
}

func exportRecordDef(value ast.TypeDecl) recordDefIR {
	fields := make([]recordFieldIR, 0, len(value.Fields))
	protoFields := []protoFieldIR{}
	for _, field := range sortedParams(value.Fields) {
		fields = append(fields, recordFieldIR{Kind: "RecordFieldDef", Name: field.Name, Type: field.Type, TypeRepr: typeRefFromName(field.Type)})
		if field.ProtoID != nil {
			protoFields = append(protoFields, protoFieldIR{Name: field.Name, ID: *field.ProtoID})
		}
	}
	return recordDefIR{Kind: "RecordDef", Name: value.Name, Fields: fields, ProtoFields: protoFields}
}

func parseNumber(value string) (float64, bool) {
	parsed, err := strconv.ParseFloat(strings.TrimSpace(value), 64)
	if err != nil {
		return 0, false
	}
	return parsed, true
}

func sortedTypeDefs(values map[string]typeDefIR) []typeDefIR {
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Strings(names)
	items := make([]typeDefIR, 0, len(names))
	for _, name := range names {
		items = append(items, values[name])
	}
	return items
}

func sortedRecordDefs(values map[string]recordDefIR) []recordDefIR {
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Strings(names)
	items := make([]recordDefIR, 0, len(names))
	for _, name := range names {
		items = append(items, values[name])
	}
	return items
}

func sortedErrorNames(values map[string]bool) []string {
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func sortedRoutines(values map[string]routineDecl) []routineDecl {
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Strings(names)
	items := make([]routineDecl, 0, len(names))
	for _, name := range names {
		items = append(items, values[name])
	}
	return items
}

func sortedServices(values map[string]serviceDecl) []serviceDecl {
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Strings(names)
	items := make([]serviceDecl, 0, len(names))
	for _, name := range names {
		items = append(items, values[name])
	}
	return items
}
