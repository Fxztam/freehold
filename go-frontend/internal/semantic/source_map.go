package semantic

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	"freehold-go-frontend/internal/ast"
	"freehold-go-frontend/internal/token"
)

const SourceMapSchemaV0 = "fh-source-map-v0"

type sourceMapDocument struct {
	Schema          string            `json:"schema"`
	LanguageVersion string            `json:"language_version"`
	Purpose         string            `json:"purpose"`
	EntryModule     string            `json:"entry_module"`
	ModuleOrder     []string          `json:"module_order"`
	Modules         []sourceMapModule `json:"modules"`
}

type sourceMapModule struct {
	Name         string        `json:"name"`
	SourceFile   string        `json:"source_file"`
	SourceSHA256 string        `json:"source_sha256"`
	LineCount    int           `json:"line_count"`
	SourceLines  []string      `json:"source_lines"`
	AST          sourceMapNode `json:"ast"`
}

type sourceMapNode struct {
	ID       string          `json:"id"`
	ParentID *string         `json:"parent_id"`
	Role     string          `json:"role"`
	Index    int             `json:"index"`
	Kind     string          `json:"kind"`
	Span     sourceMapSpan   `json:"span"`
	Extra    map[string]any  `json:"-"`
	Children []sourceMapNode `json:"children"`
}

type sourceMapSpan struct {
	Line     *int   `json:"line"`
	Column   *int   `json:"column"`
	LineText string `json:"line_text"`
}

type sourceChild struct {
	role  string
	index int
	node  any
}

func (n sourceMapNode) MarshalJSON() ([]byte, error) {
	item := map[string]any{
		"id":        n.ID,
		"parent_id": n.ParentID,
		"role":      n.Role,
		"index":     n.Index,
		"kind":      n.Kind,
		"span":      n.Span,
		"children":  n.Children,
	}
	for key, value := range n.Extra {
		item[key] = value
	}
	return json.Marshal(item)
}

func ExportSourceMapJSON(entryFile string) (string, error) {
	project, err := LoadProject(entryFile)
	if err != nil {
		return "", err
	}
	if project == nil || project.Entry == nil {
		return "", fmt.Errorf("failed to load project")
	}

	moduleNames := project.ModuleNames()
	modules := make([]sourceMapModule, 0, len(moduleNames))
	for _, moduleName := range moduleNames {
		module, ok := project.Modules[moduleName]
		if !ok || module == nil {
			continue
		}
		path := project.Files[moduleName]
		exported, err := exportSourceMapModule(moduleName, path, module)
		if err != nil {
			return "", err
		}
		modules = append(modules, exported)
	}

	doc := sourceMapDocument{
		Schema:          SourceMapSchemaV0,
		LanguageVersion: FreeholdLanguageVersion,
		Purpose:         "source reconstruction sidecar for FH-IR",
		EntryModule:     project.Entry.Name,
		ModuleOrder:     moduleNames,
		Modules:         modules,
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

func exportSourceMapModule(moduleName string, path string, module *ast.Module) (sourceMapModule, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return sourceMapModule{}, err
	}
	source := normalizeSourceText(string(content))
	lines := splitSourceLines(source)
	digest := sha256.Sum256([]byte(source))
	return sourceMapModule{
		Name:         moduleName,
		SourceFile:   path,
		SourceSHA256: hex.EncodeToString(digest[:]),
		LineCount:    len(lines),
		SourceLines:  lines,
		AST:          exportSourceNode(module, moduleName, "module", nil, "module", 0, lines),
	}, nil
}

func splitSourceLines(source string) []string {
	source = normalizeSourceText(source)
	if source == "" {
		return []string{}
	}
	lines := strings.Split(source, "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	return lines
}

func normalizeSourceText(source string) string {
	source = strings.ReplaceAll(source, "\r\n", "\n")
	return strings.ReplaceAll(source, "\r", "\n")
}

func exportSourceNode(node any, moduleName string, path string, parentID *string, role string, index int, lines []string) sourceMapNode {
	id := moduleName + ":" + path
	children := sourceChildren(node)
	exportedChildren := make([]sourceMapNode, 0, len(children))
	for _, child := range children {
		childPath := fmt.Sprintf("%s/%s[%d]", path, child.role, child.index)
		exportedChildren = append(exportedChildren, exportSourceNode(child.node, moduleName, childPath, &id, child.role, child.index, lines))
	}
	return sourceMapNode{
		ID:       id,
		ParentID: parentID,
		Role:     role,
		Index:    index,
		Kind:     sourceKind(node),
		Span:     sourceSpan(sourcePos(node), lines),
		Extra:    sourceSummary(node),
		Children: exportedChildren,
	}
}

func sourceSpan(pos token.Position, lines []string) sourceMapSpan {
	if pos.Line <= 0 {
		return sourceMapSpan{Line: nil, Column: nil, LineText: ""}
	}
	line := pos.Line
	column := pos.Column
	lineText := ""
	if line > 0 && line <= len(lines) {
		lineText = lines[line-1]
	}
	return sourceMapSpan{Line: &line, Column: &column, LineText: lineText}
}

func sourceKind(node any) string {
	switch node.(type) {
	case *ast.Module, ast.Module:
		return "Program"
	case ast.TypeDecl:
		value := node.(ast.TypeDecl)
		if value.Base == "record" {
			return "RecordTypeDecl"
		}
		return "TypeDecl"
	case ast.FunctionDecl, ast.ProcedureDecl:
		return "RoutineDecl"
	case ast.Param:
		return "Param"
	case ast.AssignmentStmt:
		value := node.(ast.AssignmentStmt)
		if fieldPathFromExpr(value.Target) != nil {
			return "FieldAssignStmt"
		}
		return "AssignStmt"
	case ast.IdentifierExpr:
		return "VarExpr"
	case ast.NamedArgumentExpr, ast.RecordField:
		return "NamedArg"
	case ast.OkExpr:
		return "ReturnOk"
	case ast.ErrorExpr:
		return "ReturnError"
	default:
		name := fmt.Sprintf("%T", node)
		if strings.HasPrefix(name, "ast.") {
			return strings.TrimPrefix(name, "ast.")
		}
		return name
	}
}

func sourcePos(node any) token.Position {
	switch value := node.(type) {
	case *ast.Module:
		return value.Pos
	case ast.Module:
		return value.Pos
	case ast.ImportDecl:
		return value.Pos
	case ast.TypeDecl:
		return value.Pos
	case ast.ErrorDecl:
		return value.Pos
	case ast.ServiceDecl:
		return value.Pos
	case ast.RpcDecl:
		return value.Pos
	case ast.FunctionDecl:
		return value.Pos
	case ast.ProcedureDecl:
		return value.Pos
	case ast.AbortClause:
		return value.Pos
	case ast.Param:
		return value.Pos
	case ast.GlobalSpec:
		return value.Pos
	case ast.DependsSpec:
		return value.Pos
	case ast.ReturnStmt:
		return value.Pos
	case ast.AbortStmt:
		return value.Pos
	case ast.CheckStmt:
		return value.Pos
	case ast.LetStmt:
		return value.Pos
	case ast.AssignmentStmt:
		return value.Pos
	case ast.CallStmt:
		return value.Pos
	case ast.IfStmt:
		return value.Pos
	case ast.WhileStmt:
		return value.Pos
	case ast.CaseStmt:
		return value.Pos
	case ast.ScopeStmt:
		return value.Pos
	case ast.CaseBranch:
		return value.Pos
	case ast.IdentifierExpr:
		return value.Pos
	case ast.FieldAccessExpr:
		return value.Pos
	case ast.IndexExpr:
		return value.Pos
	case ast.ArrayLiteralExpr:
		return value.Pos
	case ast.CallExpr:
		return value.Pos
	case ast.AwaitExpr:
		return value.Pos
	case ast.NamedArgumentExpr:
		return value.Pos
	case ast.RecordLiteralExpr:
		return value.Pos
	case ast.RecordField:
		return value.Pos
	case ast.NumberExpr:
		return value.Pos
	case ast.StringExpr:
		return value.Pos
	case ast.OkExpr:
		return value.Pos
	case ast.ErrorExpr:
		return value.Pos
	case ast.UnaryExpr:
		return value.Pos
	case ast.BinaryExpr:
		return value.Pos
	case ast.ForAllExpr:
		return value.Pos
	case ast.ExistsExpr:
		return value.Pos
	default:
		return token.Position{}
	}
}

func sourceSummary(node any) map[string]any {
	item := map[string]any{}
	switch value := node.(type) {
	case *ast.Module:
		item["name"] = value.Name
	case ast.Module:
		item["name"] = value.Name
	case ast.ImportDecl:
		item["module"] = value.Module
		item["exposing"] = value.Exposing
	case ast.TypeDecl:
		item["name"] = value.Name
		if value.Base == "record" {
			item["type_params"] = nonNilStrings(value.TypeParams)
		} else {
			item["base"] = value.Base
			if value.Range != nil {
				item["min_value"] = numericOrString(value.Range.Min)
				item["max_value"] = numericOrString(value.Range.Max)
			}
		}
	case ast.Param:
		item["name"] = value.Name
		item["type"] = value.Type
		if value.ProtoID != nil {
			item["proto_id"] = *value.ProtoID
		}
	case ast.ErrorDecl:
		item["name"] = value.Name
	case ast.ServiceDecl:
		item["name"] = value.Name
	case ast.RpcDecl:
		item["name"] = value.Name
		item["request_name"] = value.RequestName
		item["request_type"] = value.RequestType
		item["response_type"] = value.ResponseType
		item["request_stream"] = value.RequestStream
		item["response_stream"] = value.ResponseStream
	case ast.FunctionDecl:
		item["name"] = value.Name
		item["routine_kind"] = "function"
		item["is_async"] = value.IsAsync
		item["type_params"] = nonNilStrings(value.TypeParams)
		item["return_type"] = value.ReturnType
	case ast.ProcedureDecl:
		item["name"] = value.Name
		item["routine_kind"] = "procedure"
		item["is_async"] = false
		item["type_params"] = []string{}
		item["return_type"] = "Void"
	case ast.GlobalSpec:
		item["name"] = value.Name
		if value.Mode != nil {
			item["mode"] = *value.Mode
		} else {
			item["mode"] = nil
		}
	case ast.DependsSpec:
		item["target"] = value.Target
		item["sources"] = value.Sources
	case ast.AbortClause:
		item["error"] = value.Error
	case ast.LetStmt:
		item["name"] = value.Name
		item["type"] = value.Type
	case ast.AssignmentStmt:
		if path := fieldPathFromExpr(value.Target); path != nil {
			item["path"] = path
		} else if name := identifierName(value.Target); name != "" {
			item["name"] = name
		}
	case ast.AbortStmt:
		item["error"] = value.Error
	case ast.CallStmt:
		if call, ok := value.Call.(ast.CallExpr); ok {
			if name := callNameForSource(call.Callee); name != "" {
				item["name"] = name
			}
			item["type_args"] = nonNilStrings(call.TypeArgs)
		}
	case ast.ScopeStmt:
		item["name"] = value.Name
	case ast.IdentifierExpr:
		item["name"] = value.Name
	case ast.FieldAccessExpr:
		item["path"] = fieldPathFromExpr(value)
	case ast.CallExpr:
		item["name"] = callNameForSource(value.Callee)
		item["type_args"] = nonNilStrings(value.TypeArgs)
	case ast.NamedArgumentExpr:
		item["name"] = value.Name
	case ast.RecordLiteralExpr:
		item["type"] = value.Type
	case ast.RecordField:
		item["name"] = value.Name
	case ast.IndexExpr:
		item["name"] = callNameForSource(value.Array)
	case ast.NumberExpr:
		item["value"] = numericOrString(value.Value)
	case ast.StringExpr:
		item["value"] = value.Value
	case ast.OkExpr:
	case ast.ErrorExpr:
		item["error"] = value.Name
	case ast.UnaryExpr:
		item["op"] = value.Op
	case ast.BinaryExpr:
		item["op"] = value.Op
	case ast.ForAllExpr:
		item["var_name"] = value.VarName
	case ast.ExistsExpr:
		item["var_name"] = value.VarName
	}
	return item
}

func sourceChildren(node any) []sourceChild {
	var children []sourceChild
	add := func(role string, nodes []any) {
		for index, child := range nodes {
			if child != nil {
				children = append(children, sourceChild{role: role, index: index, node: child})
			}
		}
	}
	one := func(role string, node any) {
		if node != nil {
			children = append(children, sourceChild{role: role, index: 0, node: node})
		}
	}

	switch value := node.(type) {
	case *ast.Module:
		add("declarations", declsToAny(value.Declarations))
	case ast.Module:
		add("declarations", declsToAny(value.Declarations))
	case ast.TypeDecl:
		if value.Base == "record" {
			add("fields", paramsToAny(value.Fields))
		}
	case ast.ServiceDecl:
		add("rpcs", rpcsToAny(value.Rpcs))
	case ast.FunctionDecl:
		add("params", paramsToAny(value.Params))
		add("globals", globalsToAny(value.GlobalSpecs))
		add("depends", dependsToAny(value.DependsSpecs))
		add("requires", exprsToAny(value.Requires))
		add("aborts", abortsToAny(value.Aborts))
		add("ensures", exprsToAny(value.Ensures))
		add("body", stmtsToAny(value.Body))
	case ast.ProcedureDecl:
		add("params", paramsToAny(value.Params))
		add("globals", globalsToAny(value.GlobalSpecs))
		add("depends", dependsToAny(value.DependsSpecs))
		add("requires", exprsToAny(value.Requires))
		add("aborts", abortsToAny(value.Aborts))
		add("ensures", exprsToAny(value.Ensures))
		add("body", stmtsToAny(value.Body))
	case ast.AbortClause:
		one("condition", value.Condition)
	case ast.ReturnStmt:
		one("value", value.Value)
	case ast.CheckStmt:
		one("condition", value.Condition)
	case ast.LetStmt:
		one("value", value.Value)
	case ast.AssignmentStmt:
		one("value", value.Value)
	case ast.CallStmt:
		if call, ok := value.Call.(ast.CallExpr); ok {
			add("args", exprsToAny(call.Arguments))
		} else {
			one("call", value.Call)
		}
	case ast.IfStmt:
		one("condition", value.Condition)
		add("then_body", stmtsToAny(value.ThenBody))
		add("else_body", stmtsToAny(value.ElseBody))
	case ast.WhileStmt:
		one("condition", value.Condition)
		add("invariants", exprsToAny(value.Invariants))
		one("variant", value.Variant)
		add("body", stmtsToAny(value.Body))
	case ast.CaseStmt:
		one("value", value.Value)
		add("branches", caseBranchesToAny(value.When))
		add("default_body", stmtsToAny(value.Default))
	case ast.CaseBranch:
		one("value", value.Value)
		add("body", stmtsToAny(value.Body))
	case ast.ScopeStmt:
		add("spawn_body", stmtsToAny(value.SpawnBody))
		add("join_body", stmtsToAny(value.JoinBody))
		add("result_body", stmtsToAny(value.ResultBody))
	case ast.FieldAccessExpr:
		one("object", value.Object)
	case ast.IndexExpr:
		one("array", value.Array)
		one("index", value.Index)
	case ast.ArrayLiteralExpr:
		add("items", exprsToAny(value.Elements))
	case ast.CallExpr:
		add("args", exprsToAny(value.Arguments))
	case ast.AwaitExpr:
		one("value", value.Value)
	case ast.NamedArgumentExpr:
		one("value", value.Value)
	case ast.RecordLiteralExpr:
		add("args", recordFieldsToAny(value.Fields))
	case ast.RecordField:
		one("value", value.Value)
	case ast.OkExpr:
		one("value", value.Value)
	case ast.UnaryExpr:
		one("value", value.Value)
	case ast.BinaryExpr:
		one("left", value.Left)
		one("right", value.Right)
	case ast.ForAllExpr:
		one("lower", value.Lower)
		one("upper", value.Upper)
		one("expr", value.Expr)
	case ast.ExistsExpr:
		one("lower", value.Lower)
		one("upper", value.Upper)
		one("expr", value.Expr)
	}
	return children
}

func declsToAny(values []ast.Decl) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func paramsToAny(values []ast.Param) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func rpcsToAny(values []ast.RpcDecl) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func globalsToAny(values []ast.GlobalSpec) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func dependsToAny(values []ast.DependsSpec) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func abortsToAny(values []ast.AbortClause) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func stmtsToAny(values []ast.Stmt) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func exprsToAny(values []ast.Expr) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func caseBranchesToAny(values []ast.CaseBranch) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func recordFieldsToAny(values []ast.RecordField) []any {
	items := make([]any, len(values))
	for i, value := range values {
		items[i] = value
	}
	return items
}

func nonNilStrings(values []string) []string {
	if values == nil {
		return []string{}
	}
	return values
}

func numericOrString(value string) any {
	if strings.Contains(value, ".") {
		return value
	}
	var parsed int
	if _, err := fmt.Sscanf(value, "%d", &parsed); err == nil {
		return parsed
	}
	return value
}

func identifierName(expr ast.Expr) string {
	if value, ok := expr.(ast.IdentifierExpr); ok {
		return value.Name
	}
	return ""
}

func callNameForSource(expr ast.Expr) string {
	switch value := expr.(type) {
	case ast.IdentifierExpr:
		return value.Name
	case ast.FieldAccessExpr:
		path := fieldPathFromExpr(value)
		if len(path) > 0 {
			return strings.Join(path, ".")
		}
	}
	return ""
}

func fieldPathFromExpr(expr ast.Expr) []string {
	switch value := expr.(type) {
	case ast.IdentifierExpr:
		return []string{value.Name}
	case ast.FieldAccessExpr:
		prefix := fieldPathFromExpr(value.Object)
		if prefix == nil {
			return nil
		}
		return append(prefix, value.Field)
	}
	return nil
}

func sortedSourceMapKeys(item map[string]any) []string {
	keys := make([]string, 0, len(item))
	for key := range item {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}
