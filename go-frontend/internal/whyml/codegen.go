package whyml

import (
	"fmt"
	"strings"

	"freehold-go-frontend/internal/ast"
)

type routineInfo struct {
	Name        string
	Params      []ast.Param
	GlobalSpecs []ast.GlobalSpec
	Body        []ast.Stmt
}

type WhyMLGenerator struct {
	moduleName   string
	declarations []ast.Decl
	routines     map[string]routineInfo
	refs         map[string]bool
}

func NewGenerator(module *ast.Module) *WhyMLGenerator {
	routines := make(map[string]routineInfo)
	for _, decl := range module.Declarations {
		switch d := decl.(type) {
		case ast.FunctionDecl:
			routines[d.Name] = routineInfo{
				Name:        d.Name,
				Params:      d.Params,
				GlobalSpecs: d.GlobalSpecs,
				Body:        d.Body,
			}
		case *ast.FunctionDecl:
			routines[d.Name] = routineInfo{
				Name:        d.Name,
				Params:      d.Params,
				GlobalSpecs: d.GlobalSpecs,
				Body:        d.Body,
			}
		case ast.ProcedureDecl:
			routines[d.Name] = routineInfo{
				Name:        d.Name,
				Params:      d.Params,
				GlobalSpecs: d.GlobalSpecs,
				Body:        d.Body,
			}
		case *ast.ProcedureDecl:
			routines[d.Name] = routineInfo{
				Name:        d.Name,
				Params:      d.Params,
				GlobalSpecs: d.GlobalSpecs,
				Body:        d.Body,
			}
		}
	}
	return &WhyMLGenerator{
		moduleName:   module.Name,
		declarations: module.Declarations,
		routines:     routines,
		refs:         make(map[string]bool),
	}
}

func hasReturns(body []ast.Stmt) bool {
	for _, stmt := range body {
		switch s := stmt.(type) {
		case ast.ReturnStmt:
			return true
		case *ast.ReturnStmt:
			return true
		case ast.IfStmt:
			if hasReturns(s.ThenBody) || hasReturns(s.ElseBody) {
				return true
			}
		case *ast.IfStmt:
			if hasReturns(s.ThenBody) || hasReturns(s.ElseBody) {
				return true
			}
		case ast.WhileStmt:
			if hasReturns(s.Body) {
				return true
			}
		case *ast.WhileStmt:
			if hasReturns(s.Body) {
				return true
			}
		case ast.CaseStmt:
			for _, b := range s.When {
				if hasReturns(b.Body) {
					return true
				}
			}
			if hasReturns(s.Default) {
				return true
			}
		case *ast.CaseStmt:
			for _, b := range s.When {
				if hasReturns(b.Body) {
					return true
				}
			}
			if hasReturns(s.Default) {
				return true
			}
		case ast.ScopeStmt:
			if hasReturns(s.SpawnBody) || hasReturns(s.JoinBody) || hasReturns(s.ResultBody) {
				return true
			}
		case *ast.ScopeStmt:
			if hasReturns(s.SpawnBody) || hasReturns(s.JoinBody) || hasReturns(s.ResultBody) {
				return true
			}
		}
	}
	return false
}

func isParamMutable(globalSpecs []ast.GlobalSpec, paramName string) bool {
	for _, g := range globalSpecs {
		if g.Name == paramName && g.Mode != nil && (*g.Mode == "In_Out" || *g.Mode == "Output") {
			return true
		}
	}
	return false
}

func getCallName(callee ast.Expr) string {
	if id, ok := callee.(ast.IdentifierExpr); ok {
		return id.Name
	}
	if id, ok := callee.(*ast.IdentifierExpr); ok {
		return id.Name
	}
	return ""
}

func resolveArgExpr(arg ast.Expr) ast.Expr {
	if na, ok := arg.(ast.NamedArgumentExpr); ok {
		return na.Value
	}
	if na, ok := arg.(*ast.NamedArgumentExpr); ok {
		return na.Value
	}
	return arg
}

func (g *WhyMLGenerator) getFieldAccessPath(e ast.Expr) ([]string, ast.Expr) {
	if fa, ok := e.(ast.FieldAccessExpr); ok {
		path, root := g.getFieldAccessPath(fa.Object)
		return append(path, fa.Field), root
	}
	if fa, ok := e.(*ast.FieldAccessExpr); ok {
		path, root := g.getFieldAccessPath(fa.Object)
		return append(path, fa.Field), root
	}
	return nil, e
}

func (g *WhyMLGenerator) mapTypeName(n string) string {
	if n == "Integer" {
		return "int"
	}
	if n == "Boolean" {
		return "bool"
	}
	if n == "Float" || n == "Double" {
		return "real"
	}
	if n == "String" {
		return "string"
	}
	if strings.HasPrefix(n, "Channel<") && strings.HasSuffix(n, ">") {
		inner := n[len("Channel<") : len(n)-1]
		return fmt.Sprintf("(channel %s)", g.mapTypeName(inner))
	}
	if strings.HasPrefix(n, "Sender<") && strings.HasSuffix(n, ">") {
		inner := n[len("Sender<") : len(n)-1]
		return fmt.Sprintf("(channel %s)", g.mapTypeName(inner))
	}
	if strings.HasPrefix(n, "Receiver<") && strings.HasSuffix(n, ">") {
		inner := n[len("Receiver<") : len(n)-1]
		return fmt.Sprintf("(channel %s)", g.mapTypeName(inner))
	}
	if strings.HasPrefix(n, "JoinHandle<") && strings.HasSuffix(n, ">") {
		inner := n[len("JoinHandle<") : len(n)-1]
		return fmt.Sprintf("(joinHandle %s)", g.mapTypeName(inner))
	}
	if strings.HasPrefix(n, "Result<") && strings.HasSuffix(n, ">") {
		inner := n[len("Result<") : len(n)-1]
		parts := strings.SplitN(inner, ",", 2)
		okStr := g.mapTypeName(strings.TrimSpace(parts[0]))
		errStr := strings.TrimSpace(parts[1])
		errStr = strings.ToLower(errStr[:1]) + errStr[1:]
		return fmt.Sprintf("(result %s %s)", okStr, errStr)
	}
	if strings.HasPrefix(n, "Array<") && strings.HasSuffix(n, ">") {
		inner := n[len("Array<") : len(n)-1]
		parts := strings.Split(inner, ",")
		elem := g.mapTypeName(strings.TrimSpace(parts[0]))
		return fmt.Sprintf("(array %s)", elem)
	}
	if len(n) == 0 {
		return "unit"
	}
	return strings.ToLower(n[:1]) + n[1:]
}

func (g *WhyMLGenerator) exprToWhyML(e ast.Expr) string {
	switch v := e.(type) {
	case ast.NumberExpr:
		return v.Value
	case *ast.NumberExpr:
		return v.Value
	case ast.StringExpr:
		return fmt.Sprintf("\"%s\"", v.Value)
	case *ast.StringExpr:
		return fmt.Sprintf("\"%s\"", v.Value)
	case ast.IdentifierExpr:
		if g.refs[v.Name] {
			return "!" + v.Name
		}
		return v.Name
	case *ast.IdentifierExpr:
		if g.refs[v.Name] {
			return "!" + v.Name
		}
		return v.Name
	case ast.OkExpr:
		return fmt.Sprintf("Ok (%s)", g.exprToWhyML(v.Value))
	case *ast.OkExpr:
		return fmt.Sprintf("Ok (%s)", g.exprToWhyML(v.Value))
	case ast.ErrorExpr:
		return v.Name
	case *ast.ErrorExpr:
		return v.Name
	case ast.UnaryExpr:
		inner := g.exprToWhyML(v.Value)
		if v.Op == "not" {
			return fmt.Sprintf("(not %s)", inner)
		}
		return fmt.Sprintf("(- %s)", inner)
	case *ast.UnaryExpr:
		inner := g.exprToWhyML(v.Value)
		if v.Op == "not" {
			return fmt.Sprintf("(not %s)", inner)
		}
		return fmt.Sprintf("(- %s)", inner)
	case ast.BinaryExpr:
		left := g.exprToWhyML(v.Left)
		right := g.exprToWhyML(v.Right)
		op := v.Op
		if op == "=" {
			return fmt.Sprintf("(%s = %s)", left, right)
		}
		if op == "!=" {
			return fmt.Sprintf("(%s <> %s)", left, right)
		}
		if op == "and" || op == "&&" {
			return fmt.Sprintf("(%s && %s)", left, right)
		}
		if op == "or" || op == "||" {
			return fmt.Sprintf("(%s || %s)", left, right)
		}
		if op == "/" {
			return fmt.Sprintf("(%s / %s)", left, right)
		}
		return fmt.Sprintf("(%s %s %s)", left, op, right)
	case *ast.BinaryExpr:
		left := g.exprToWhyML(v.Left)
		right := g.exprToWhyML(v.Right)
		op := v.Op
		if op == "=" {
			return fmt.Sprintf("(%s = %s)", left, right)
		}
		if op == "!=" {
			return fmt.Sprintf("(%s <> %s)", left, right)
		}
		if op == "and" || op == "&&" {
			return fmt.Sprintf("(%s && %s)", left, right)
		}
		if op == "or" || op == "||" {
			return fmt.Sprintf("(%s || %s)", left, right)
		}
		if op == "/" {
			return fmt.Sprintf("(%s / %s)", left, right)
		}
		return fmt.Sprintf("(%s %s %s)", left, op, right)
	case ast.IndexExpr, *ast.IndexExpr:
		var arr, idx ast.Expr
		if ie, ok := e.(ast.IndexExpr); ok {
			arr = ie.Array
			idx = ie.Index
		} else {
			arr = e.(*ast.IndexExpr).Array
			idx = e.(*ast.IndexExpr).Index
		}
		arrStr := g.exprToWhyML(arr)
		idxStr := g.exprToWhyML(idx)
		return fmt.Sprintf("(%s)[%s]", arrStr, idxStr)
	case ast.ForAllExpr:
		l := g.exprToWhyML(v.Lower)
		u := g.exprToWhyML(v.Upper)
		body := g.exprToWhyML(v.Expr)
		return fmt.Sprintf("(forall %s: int. %s <= %s <= %s -> %s)", v.VarName, l, v.VarName, u, body)
	case *ast.ForAllExpr:
		l := g.exprToWhyML(v.Lower)
		u := g.exprToWhyML(v.Upper)
		body := g.exprToWhyML(v.Expr)
		return fmt.Sprintf("(forall %s: int. %s <= %s <= %s -> %s)", v.VarName, l, v.VarName, u, body)
	case ast.ExistsExpr:
		l := g.exprToWhyML(v.Lower)
		u := g.exprToWhyML(v.Upper)
		body := g.exprToWhyML(v.Expr)
		return fmt.Sprintf("(exists %s: int. %s <= %s <= %s && %s)", v.VarName, l, v.VarName, u, body)
	case *ast.ExistsExpr:
		l := g.exprToWhyML(v.Lower)
		u := g.exprToWhyML(v.Upper)
		body := g.exprToWhyML(v.Expr)
		return fmt.Sprintf("(exists %s: int. %s <= %s <= %s && %s)", v.VarName, l, v.VarName, u, body)
	case ast.AwaitExpr, *ast.AwaitExpr:
		var val ast.Expr
		if ae, ok := e.(ast.AwaitExpr); ok {
			val = ae.Value
		} else {
			val = e.(*ast.AwaitExpr).Value
		}
		inner := g.exprToWhyML(val)
		if call, ok := val.(ast.CallExpr); ok {
			name := getCallName(call.Callee)
			if name != "channel_receive" && name != "channel_send" && name != "scope_spawn" && name != "scope_join" &&
				!strings.HasSuffix(name, ".spawn") && !strings.HasSuffix(name, ".join") {
				return inner
			}
		} else if call, ok := val.(*ast.CallExpr); ok {
			name := getCallName(call.Callee)
			if name != "channel_receive" && name != "channel_send" && name != "scope_spawn" && name != "scope_join" &&
				!strings.HasSuffix(name, ".spawn") && !strings.HasSuffix(name, ".join") {
				return inner
			}
		}
		return fmt.Sprintf("(await %s)", inner)
	case ast.CallExpr, *ast.CallExpr:
		var callee ast.Expr
		var args []ast.Expr
		if ce, ok := e.(ast.CallExpr); ok {
			callee = ce.Callee
			args = ce.Arguments
		} else {
			callee = e.(*ast.CallExpr).Callee
			args = e.(*ast.CallExpr).Arguments
		}
		name := getCallName(callee)
		if name == "scope_spawn" || strings.HasSuffix(name, ".spawn") {
			var scopeVar, taskArg string
			if name == "scope_spawn" {
				scopeVar = g.exprToWhyML(args[0])
				taskArg = g.exprToWhyML(args[1])
			} else {
				scopeVar = strings.Split(name, ".")[0]
				taskArg = g.exprToWhyML(args[0])
			}
			return fmt.Sprintf("(scope_spawn %s %s)", scopeVar, taskArg)
		}
		if name == "scope_join" || strings.HasSuffix(name, ".join") {
			var scopeVar, handleArg string
			if name == "scope_join" {
				scopeVar = g.exprToWhyML(args[0])
				handleArg = g.exprToWhyML(args[1])
			} else {
				scopeVar = strings.Split(name, ".")[0]
				handleArg = g.exprToWhyML(args[0])
			}
			return fmt.Sprintf("(scope_join %s %s)", scopeVar, handleArg)
		}
		var argStrs []string
		for _, arg := range args {
			argStrs = append(argStrs, g.exprToWhyML(arg))
		}
		if len(argStrs) > 0 {
			return fmt.Sprintf("(%s %s)", name, strings.Join(argStrs, " "))
		}
		return fmt.Sprintf("(%s)", name)
	case ast.NamedArgumentExpr, *ast.NamedArgumentExpr:
		var val ast.Expr
		if na, ok := e.(ast.NamedArgumentExpr); ok {
			val = na.Value
		} else {
			val = e.(*ast.NamedArgumentExpr).Value
		}
		return g.exprToWhyML(val)
	}
	if path, root := g.getFieldAccessPath(e); len(path) > 0 {
		rootStr := g.exprToWhyML(root)
		res := rootStr
		for _, f := range path {
			res = fmt.Sprintf("(%s).%s", res, strings.ToLower(f[:1])+f[1:])
		}
		return res
	}
	return "UNSUPPORTED"
}

func (g *WhyMLGenerator) stmtToWhyML(stmt ast.Stmt) string {
	switch stmt.(type) {
	case ast.AssignmentStmt, *ast.AssignmentStmt:
		var target, value ast.Expr
		if as, ok := stmt.(ast.AssignmentStmt); ok {
			target = as.Target
			value = as.Value
		} else {
			target = stmt.(*ast.AssignmentStmt).Target
			value = stmt.(*ast.AssignmentStmt).Value
		}
		if id, ok := target.(ast.IdentifierExpr); ok {
			return fmt.Sprintf("%s := %s", id.Name, g.exprToWhyML(value))
		}
		if id, ok := target.(*ast.IdentifierExpr); ok {
			return fmt.Sprintf("%s := %s", id.Name, g.exprToWhyML(value))
		}
		if path, root := g.getFieldAccessPath(target); len(path) > 0 {
			rootStr := g.exprToWhyML(root)
			lhs := rootStr
			for i := 0; i < len(path)-1; i++ {
				f := path[i]
				lhs = fmt.Sprintf("(%s).%s", lhs, strings.ToLower(f[:1])+f[1:])
			}
			lastField := path[len(path)-1]
			lastFieldLower := strings.ToLower(lastField[:1]) + lastField[1:]
			valStr := g.exprToWhyML(value)
			return fmt.Sprintf("(%s).%s <- %s", lhs, lastFieldLower, valStr)
		}
		if ie, ok := target.(ast.IndexExpr); ok {
			arrStr := g.exprToWhyML(ie.Array)
			idxStr := g.exprToWhyML(ie.Index)
			valStr := g.exprToWhyML(value)
			return fmt.Sprintf("(%s)[%s] <- %s", arrStr, idxStr, valStr)
		}
		if ie, ok := target.(*ast.IndexExpr); ok {
			arrStr := g.exprToWhyML(ie.Array)
			idxStr := g.exprToWhyML(ie.Index)
			valStr := g.exprToWhyML(value)
			return fmt.Sprintf("(%s)[%s] <- %s", arrStr, idxStr, valStr)
		}
		return "UNSUPPORTED_ASSIGN"
	case ast.ReturnStmt, *ast.ReturnStmt:
		var val ast.Expr
		if rs, ok := stmt.(ast.ReturnStmt); ok {
			val = rs.Value
		} else {
			val = stmt.(*ast.ReturnStmt).Value
		}
		if val == nil {
			return "raise (Return ())"
		}
		switch v := val.(type) {
		case ast.OkExpr:
			inner := g.exprToWhyML(v.Value)
			return fmt.Sprintf("raise (Return (Ok (%s)))", inner)
		case *ast.OkExpr:
			inner := g.exprToWhyML(v.Value)
			return fmt.Sprintf("raise (Return (Ok (%s)))", inner)
		case ast.ErrorExpr:
			return fmt.Sprintf("raise (Return (Err %s))", v.Name)
		case *ast.ErrorExpr:
			return fmt.Sprintf("raise (Return (Err %s))", v.Name)
		default:
			inner := g.exprToWhyML(val)
			return fmt.Sprintf("raise (Return (%s))", inner)
		}
	case ast.AbortStmt, *ast.AbortStmt:
		var errName string
		if as, ok := stmt.(ast.AbortStmt); ok {
			errName = as.Error
		} else {
			errName = stmt.(*ast.AbortStmt).Error
		}
		return fmt.Sprintf("raise %s", errName)
	case ast.CheckStmt, *ast.CheckStmt:
		var cond ast.Expr
		if cs, ok := stmt.(ast.CheckStmt); ok {
			cond = cs.Condition
		} else {
			cond = stmt.(*ast.CheckStmt).Condition
		}
		return fmt.Sprintf("assert { %s }", g.exprToWhyML(cond))
	case ast.CallStmt, *ast.CallStmt:
		var call ast.Expr
		if cs, ok := stmt.(ast.CallStmt); ok {
			call = cs.Call
		} else {
			call = stmt.(*ast.CallStmt).Call
		}
		var ce ast.CallExpr
		var isPtr bool
		if c, ok := call.(ast.CallExpr); ok {
			ce = c
		} else if c, ok := call.(*ast.CallExpr); ok {
			ce = *c
			isPtr = true
		} else {
			return g.exprToWhyML(call)
		}
		name := getCallName(ce.Callee)
		if name == "channel_send" || name == "channel_receive" || name == "scope_spawn" || name == "scope_join" ||
			strings.HasSuffix(name, ".spawn") || strings.HasSuffix(name, ".join") {
			if isPtr {
				return g.exprToWhyML(&ce)
			}
			return g.exprToWhyML(ce)
		}
		callee, hasCallee := g.routines[name]
		var argStrs []string
		for i, arg := range ce.Arguments {
			argExpr := resolveArgExpr(arg)
			isMut := false
			if hasCallee && i < len(callee.Params) {
				paramName := callee.Params[i].Name
				isMut = isParamMutable(callee.GlobalSpecs, paramName)
			}
			if isMut {
				if id, ok := argExpr.(ast.IdentifierExpr); ok {
					argStrs = append(argStrs, id.Name)
				} else if id, ok := argExpr.(*ast.IdentifierExpr); ok {
					argStrs = append(argStrs, id.Name)
				} else {
					argStrs = append(argStrs, g.exprToWhyML(argExpr))
				}
			} else {
				argStrs = append(argStrs, g.exprToWhyML(argExpr))
			}
		}
		if len(argStrs) > 0 {
			return fmt.Sprintf("(%s %s)", name, strings.Join(argStrs, " "))
		}
		return fmt.Sprintf("(%s)", name)
	case ast.IfStmt, *ast.IfStmt:
		var cond ast.Expr
		var thenBody, elseBody []ast.Stmt
		if is, ok := stmt.(ast.IfStmt); ok {
			cond = is.Condition
			thenBody = is.ThenBody
			elseBody = is.ElseBody
		} else {
			cond = stmt.(*ast.IfStmt).Condition
			thenBody = stmt.(*ast.IfStmt).ThenBody
			elseBody = stmt.(*ast.IfStmt).ElseBody
		}
		condStr := g.exprToWhyML(cond)
		thenStr := g.stmtsToWhyML(thenBody)
		elseStr := g.stmtsToWhyML(elseBody)
		thenIndented := indent(thenStr)
		elseIndented := indent(elseStr)
		return fmt.Sprintf("if %s then begin\n%s\nend else begin\n%s\nend", condStr, thenIndented, elseIndented)
	case ast.WhileStmt, *ast.WhileStmt:
		var cond ast.Expr
		var invariants []ast.Expr
		var variant ast.Expr
		var body []ast.Stmt
		if ws, ok := stmt.(ast.WhileStmt); ok {
			cond = ws.Condition
			invariants = ws.Invariants
			variant = ws.Variant
			body = ws.Body
		} else {
			cond = stmt.(*ast.WhileStmt).Condition
			invariants = stmt.(*ast.WhileStmt).Invariants
			variant = stmt.(*ast.WhileStmt).Variant
			body = stmt.(*ast.WhileStmt).Body
		}
		condStr := g.exprToWhyML(cond)
		var invLines []string
		for _, inv := range invariants {
			invLines = append(invLines, fmt.Sprintf("  invariant { %s }", g.exprToWhyML(inv)))
		}
		if variant != nil {
			invLines = append(invLines, fmt.Sprintf("  variant { %s }", g.exprToWhyML(variant)))
		}
		bodyStr := g.stmtsToWhyML(body)
		bodyIndented := indent(bodyStr)
		if len(invLines) > 0 {
			return fmt.Sprintf("while %s do\n%s\n%s\ndone", condStr, strings.Join(invLines, "\n"), bodyIndented)
		}
		return fmt.Sprintf("while %s do\n%s\ndone", condStr, bodyIndented)
	case ast.CaseStmt, *ast.CaseStmt:
		var val ast.Expr
		var branches []ast.CaseBranch
		var defaultBody []ast.Stmt
		if cs, ok := stmt.(ast.CaseStmt); ok {
			val = cs.Value
			branches = cs.When
			defaultBody = cs.Default
		} else {
			val = stmt.(*ast.CaseStmt).Value
			branches = stmt.(*ast.CaseStmt).When
			defaultBody = stmt.(*ast.CaseStmt).Default
		}
		valStr := g.exprToWhyML(val)
		var branchStrs []string
		for _, b := range branches {
			bVal := g.exprToWhyML(b.Value)
			bBody := g.stmtsToWhyML(b.Body)
			branchStrs = append(branchStrs, fmt.Sprintf("  | %s ->\n%s", bVal, indentDouble(bBody)))
		}
		if len(defaultBody) > 0 {
			dBody := g.stmtsToWhyML(defaultBody)
			branchStrs = append(branchStrs, fmt.Sprintf("  | _ ->\n%s", indentDouble(dBody)))
		}
		return fmt.Sprintf("match %s with\n%s\nend", valStr, strings.Join(branchStrs, "\n"))
	case ast.ScopeStmt, *ast.ScopeStmt:
		var name string
		var spawnBody, joinBody, resultBody []ast.Stmt
		if ss, ok := stmt.(ast.ScopeStmt); ok {
			name = ss.Name
			spawnBody = ss.SpawnBody
			joinBody = ss.JoinBody
			resultBody = ss.ResultBody
		} else {
			name = stmt.(*ast.ScopeStmt).Name
			spawnBody = stmt.(*ast.ScopeStmt).SpawnBody
			joinBody = stmt.(*ast.ScopeStmt).JoinBody
			resultBody = stmt.(*ast.ScopeStmt).ResultBody
		}
		var combined []ast.Stmt
		combined = append(combined, spawnBody...)
		combined = append(combined, joinBody...)
		combined = append(combined, resultBody...)
		bodyStr := g.stmtsToWhyML(combined)
		return fmt.Sprintf("let %s = () in\nbegin\n%s\nend", name, bodyStr)
	}
	return "(* UNSUPPORTED STATEMENT *)"
}

func (g *WhyMLGenerator) stmtsToWhyML(stmts []ast.Stmt) string {
	if len(stmts) == 0 {
		return "()"
	}
	first := stmts[0]
	rest := stmts[1:]
	var isLet bool
	var letName string
	var letVal ast.Expr
	if ls, ok := first.(ast.LetStmt); ok {
		isLet = true
		letName = ls.Name
		letVal = ls.Value
	} else if ls, ok := first.(*ast.LetStmt); ok {
		isLet = true
		letName = ls.Name
		letVal = ls.Value
	}
	if isLet {
		exprVal := g.exprToWhyML(letVal)
		oldRefs := make(map[string]bool)
		for k, v := range g.refs {
			oldRefs[k] = v
		}
		g.refs[letName] = true
		restVal := g.stmtsToWhyML(rest)
		g.refs = oldRefs
		return fmt.Sprintf("let %s = ref (%s) in\n%s", letName, exprVal, restVal)
	}
	firstVal := g.stmtToWhyML(first)
	if len(rest) > 0 {
		restVal := g.stmtsToWhyML(rest)
		return fmt.Sprintf("%s;\n%s", firstVal, restVal)
	}
	return firstVal
}

func (g *WhyMLGenerator) collectMutatedParams(body []ast.Stmt, paramNames map[string]bool) map[string]bool {
	mutated := make(map[string]bool)
	var walk func([]ast.Stmt)
	walk = func(stmts []ast.Stmt) {
		for _, stmt := range stmts {
			switch s := stmt.(type) {
			case ast.AssignmentStmt:
				if id, ok := s.Target.(ast.IdentifierExpr); ok {
					if paramNames[id.Name] {
						mutated[id.Name] = true
					}
				} else if id, ok := s.Target.(*ast.IdentifierExpr); ok {
					if paramNames[id.Name] {
						mutated[id.Name] = true
					}
				} else if path, root := g.getFieldAccessPath(s.Target); len(path) > 0 {
					if id, ok := root.(ast.IdentifierExpr); ok {
						if paramNames[id.Name] {
							mutated[id.Name] = true
						}
					} else if id, ok := root.(*ast.IdentifierExpr); ok {
						if paramNames[id.Name] {
							mutated[id.Name] = true
						}
					}
				}
			case *ast.AssignmentStmt:
				if id, ok := s.Target.(ast.IdentifierExpr); ok {
					if paramNames[id.Name] {
						mutated[id.Name] = true
					}
				} else if id, ok := s.Target.(*ast.IdentifierExpr); ok {
					if paramNames[id.Name] {
						mutated[id.Name] = true
					}
				} else if path, root := g.getFieldAccessPath(s.Target); len(path) > 0 {
					if id, ok := root.(ast.IdentifierExpr); ok {
						if paramNames[id.Name] {
							mutated[id.Name] = true
						}
					} else if id, ok := root.(*ast.IdentifierExpr); ok {
						if paramNames[id.Name] {
							mutated[id.Name] = true
						}
					}
				}
			case ast.CallStmt:
				var ce ast.CallExpr
				if c, ok := s.Call.(ast.CallExpr); ok {
					ce = c
				} else if c, ok := s.Call.(*ast.CallExpr); ok {
					ce = *c
				} else {
					continue
				}
				name := getCallName(ce.Callee)
				callee, hasCallee := g.routines[name]
				if hasCallee {
					for i, arg := range ce.Arguments {
						argExpr := resolveArgExpr(arg)
						if id, ok := argExpr.(ast.IdentifierExpr); ok {
							if paramNames[id.Name] && i < len(callee.Params) {
								if isParamMutable(callee.GlobalSpecs, callee.Params[i].Name) {
									mutated[id.Name] = true
								}
							}
						} else if id, ok := argExpr.(*ast.IdentifierExpr); ok {
							if paramNames[id.Name] && i < len(callee.Params) {
								if isParamMutable(callee.GlobalSpecs, callee.Params[i].Name) {
									mutated[id.Name] = true
								}
							}
						}
					}
				}
			case *ast.CallStmt:
				var ce ast.CallExpr
				if c, ok := s.Call.(ast.CallExpr); ok {
					ce = c
				} else if c, ok := s.Call.(*ast.CallExpr); ok {
					ce = *c
				} else {
					continue
				}
				name := getCallName(ce.Callee)
				callee, hasCallee := g.routines[name]
				if hasCallee {
					for i, arg := range ce.Arguments {
						argExpr := resolveArgExpr(arg)
						if id, ok := argExpr.(ast.IdentifierExpr); ok {
							if paramNames[id.Name] && i < len(callee.Params) {
								if isParamMutable(callee.GlobalSpecs, callee.Params[i].Name) {
									mutated[id.Name] = true
								}
							}
						} else if id, ok := argExpr.(*ast.IdentifierExpr); ok {
							if paramNames[id.Name] && i < len(callee.Params) {
								if isParamMutable(callee.GlobalSpecs, callee.Params[i].Name) {
									mutated[id.Name] = true
								}
							}
						}
					}
				}
			case ast.IfStmt:
				walk(s.ThenBody)
				walk(s.ElseBody)
			case *ast.IfStmt:
				walk(s.ThenBody)
				walk(s.ElseBody)
			case ast.WhileStmt:
				walk(s.Body)
			case *ast.WhileStmt:
				walk(s.Body)
			case ast.CaseStmt:
				for _, b := range s.When {
					walk(b.Body)
				}
				walk(s.Default)
			case *ast.CaseStmt:
				for _, b := range s.When {
					walk(b.Body)
				}
				walk(s.Default)
			case ast.ScopeStmt:
				walk(s.SpawnBody)
				walk(s.JoinBody)
				walk(s.ResultBody)
			case *ast.ScopeStmt:
				walk(s.SpawnBody)
				walk(s.JoinBody)
				walk(s.ResultBody)
			}
		}
	}
	walk(body)
	return mutated
}

func (g *WhyMLGenerator) routineToWhyML(
	name string,
	params []ast.Param,
	returnType string,
	globalSpecs []ast.GlobalSpec,
	requires []ast.Expr,
	ensures []ast.Expr,
	aborts []ast.AbortClause,
	body []ast.Stmt,
	isFunction bool,
) string {
	paramNames := make(map[string]bool)
	for _, p := range params {
		paramNames[p.Name] = true
	}
	mutatedNames := g.collectMutatedParams(body, paramNames)
	for _, spec := range globalSpecs {
		if spec.Mode != nil && (*spec.Mode == "In_Out" || *spec.Mode == "Output") {
			mutatedNames[spec.Name] = true
		}
	}
	var paramsStr []string
	g.refs = make(map[string]bool)
	for _, p := range params {
		pType := g.mapTypeName(p.Type)
		if mutatedNames[p.Name] {
			paramsStr = append(paramsStr, fmt.Sprintf("(%s: ref %s)", p.Name, pType))
			g.refs[p.Name] = true
		} else {
			paramsStr = append(paramsStr, fmt.Sprintf("(%s: %s)", p.Name, pType))
		}
	}
	paramsVal := "()"
	if len(paramsStr) > 0 {
		paramsVal = strings.Join(paramsStr, " ")
	}
	var retTypeStr string
	if isFunction {
		retTypeStr = g.mapTypeName(returnType)
	} else {
		retTypeStr = "unit"
	}
	var lines []string
	lines = append(lines, fmt.Sprintf("  let %s %s : %s", name, paramsVal, retTypeStr))
	for _, req := range requires {
		reqExpr := g.exprToWhyML(req)
		lines = append(lines, fmt.Sprintf("    requires { %s }", reqExpr))
	}
	for _, ens := range ensures {
		ensExpr := g.exprToWhyML(ens)
		lines = append(lines, fmt.Sprintf("    ensures  { %s }", ensExpr))
	}
	for _, clause := range aborts {
		if clause.Condition != nil {
			condExpr := g.exprToWhyML(clause.Condition)
			lines = append(lines, fmt.Sprintf("    raises   { %s -> %s }", clause.Error, condExpr))
		} else {
			lines = append(lines, fmt.Sprintf("    raises   { %s }", clause.Error))
		}
	}
	lines = append(lines, "  =")
	hasRet := hasReturns(body)
	if hasRet {
		if isFunction {
			lines = append(lines, fmt.Sprintf("    exception Return %s", retTypeStr))
		} else {
			lines = append(lines, "    exception Return")
		}
	}
	bodyVal := g.stmtsToWhyML(body)
	if hasRet {
		bodyIndented := indentDouble(bodyVal)
		lines = append(lines, "    try")
		lines = append(lines, bodyIndented)
		if isFunction {
			lines = append(lines, "    with Return val -> val")
		} else {
			lines = append(lines, "    with Return -> ()")
		}
		lines = append(lines, "    end")
	} else {
		bodyIndented := indent(bodyVal)
		lines = append(lines, bodyIndented)
	}
	return strings.Join(lines, "\n")
}

func (g *WhyMLGenerator) Generate() string {
	var lines []string
	lines = append(lines, fmt.Sprintf("module %s", g.moduleName))
	lines = append(lines, "  use int.Int")
	lines = append(lines, "  use ref.Ref")
	lines = append(lines, "  use array.Array")
	lines = append(lines, "  use string.String")
	lines = append(lines, "  use seq.Seq")
	lines = append(lines, "")
	lines = append(lines, "  (* Generic Result type definition *)")
	lines = append(lines, "  type result 'ok 'err = Ok 'ok | Err 'err")
	lines = append(lines, "")
	lines = append(lines, "  (* Concurrency support definitions *)")
	lines = append(lines, "  type joinHandle 'a = {")
	lines = append(lines, "    mutable value: 'a;")
	lines = append(lines, "  }")
	lines = append(lines, "")
	lines = append(lines, "  type channel 'a = {")
	lines = append(lines, "    mutable history: seq 'a;")
	lines = append(lines, "    mutable read_cursor: int;")
	lines = append(lines, "  } invariant { 0 <= read_cursor <= length history }")
	lines = append(lines, "")
	lines = append(lines, "  let channel (_capacity: int) : channel 'a")
	lines = append(lines, "    ensures { length result.history = 0 }")
	lines = append(lines, "    ensures { result.read_cursor = 0 }")
	lines = append(lines, "  =")
	lines = append(lines, "    { history = empty; read_cursor = 0 }")
	lines = append(lines, "")
	lines = append(lines, "  let channel_sender (c: channel 'a) : channel 'a = c")
	lines = append(lines, "  let channel_receiver (c: channel 'a) : channel 'a = c")
	lines = append(lines, "")
	lines = append(lines, "  let channel_send (c: channel 'a) (x: 'a) : joinHandle bool")
	lines = append(lines, "    writes { c.history }")
	lines = append(lines, "    ensures { c.history = snoc (old c.history) x }")
	lines = append(lines, "    ensures { result.value = true }")
	lines = append(lines, "  =")
	lines = append(lines, "    c.history <- snoc c.history x;")
	lines = append(lines, "    { value = true }")
	lines = append(lines, "")
	lines = append(lines, "  let channel_receive (c: channel 'a) : joinHandle 'a")
	lines = append(lines, "    requires { c.read_cursor < length c.history }")
	lines = append(lines, "    writes { c.read_cursor }")
	lines = append(lines, "    ensures { result.value = c.history[old c.read_cursor] }")
	lines = append(lines, "    ensures { c.read_cursor = old c.read_cursor + 1 }")
	lines = append(lines, "  =")
	lines = append(lines, "    let res = c.history[c.read_cursor] in")
	lines = append(lines, "    c.read_cursor <- c.read_cursor + 1;")
	lines = append(lines, "    { value = res }")
	lines = append(lines, "")
	lines = append(lines, "  let scope_spawn (s: unit) (x: 'a) : joinHandle 'a =")
	lines = append(lines, "    { value = x }")
	lines = append(lines, "")
	lines = append(lines, "  let scope_join (s: unit) (h: joinHandle 'a) : joinHandle 'a =")
	lines = append(lines, "    h")
	lines = append(lines, "")
	lines = append(lines, "  let await (h: joinHandle 'a) : 'a =")
	lines = append(lines, "    h.value")
	lines = append(lines, "")
	for _, decl := range g.declarations {
		switch d := decl.(type) {
		case ast.TypeDecl:
			typename := strings.ToLower(d.Name[:1]) + d.Name[1:]
			if d.Base == "record" {
				var fieldsStr []string
				for _, f := range d.Fields {
					fName := strings.ToLower(f.Name[:1]) + f.Name[1:]
					fType := g.mapTypeName(f.Type)
					fieldsStr = append(fieldsStr, fmt.Sprintf("mutable %s: %s", fName, fType))
				}
				fieldsBody := strings.Join(fieldsStr, "; ")
				lines = append(lines, fmt.Sprintf("  type %s = { %s }", typename, fieldsBody))
			} else {
				lines = append(lines, fmt.Sprintf("  type %s = int", typename))
			}
		case *ast.TypeDecl:
			typename := strings.ToLower(d.Name[:1]) + d.Name[1:]
			if d.Base == "record" {
				var fieldsStr []string
				for _, f := range d.Fields {
					fName := strings.ToLower(f.Name[:1]) + f.Name[1:]
					fType := g.mapTypeName(f.Type)
					fieldsStr = append(fieldsStr, fmt.Sprintf("mutable %s: %s", fName, fType))
				}
				fieldsBody := strings.Join(fieldsStr, "; ")
				lines = append(lines, fmt.Sprintf("  type %s = { %s }", typename, fieldsBody))
			} else {
				lines = append(lines, fmt.Sprintf("  type %s = int", typename))
			}
		case ast.ErrorDecl:
			lines = append(lines, fmt.Sprintf("  exception %s", d.Name))
		case *ast.ErrorDecl:
			lines = append(lines, fmt.Sprintf("  exception %s", d.Name))
		}
	}
	lines = append(lines, "")
	for _, decl := range g.declarations {
		switch d := decl.(type) {
		case ast.FunctionDecl:
			rStr := g.routineToWhyML(d.Name, d.Params, d.ReturnType, d.GlobalSpecs, d.Requires, d.Ensures, d.Aborts, d.Body, true)
			lines = append(lines, rStr)
			lines = append(lines, "")
		case *ast.FunctionDecl:
			rStr := g.routineToWhyML(d.Name, d.Params, d.ReturnType, d.GlobalSpecs, d.Requires, d.Ensures, d.Aborts, d.Body, true)
			lines = append(lines, rStr)
			lines = append(lines, "")
		case ast.ProcedureDecl:
			rStr := g.routineToWhyML(d.Name, d.Params, "", d.GlobalSpecs, d.Requires, d.Ensures, d.Aborts, d.Body, false)
			lines = append(lines, rStr)
			lines = append(lines, "")
		case *ast.ProcedureDecl:
			rStr := g.routineToWhyML(d.Name, d.Params, "", d.GlobalSpecs, d.Requires, d.Ensures, d.Aborts, d.Body, false)
			lines = append(lines, rStr)
			lines = append(lines, "")
		}
	}
	lines = append(lines, "end")
	return strings.Join(lines, "\n")
}

func indent(s string) string {
	lines := strings.Split(s, "\n")
	for i, l := range lines {
		lines[i] = "  " + l
	}
	return strings.Join(lines, "\n")
}

func indentDouble(s string) string {
	lines := strings.Split(s, "\n")
	for i, l := range lines {
		lines[i] = "    " + l
	}
	return strings.Join(lines, "\n")
}
