package semantic

import (
	"strings"

	"freehold-go-frontend/internal/ast"
)

type blockFlow struct {
	normalReturnPossible bool
	guaranteedExit       bool
	emittedAborts        map[string]bool
	calledRoutines       map[string]bool
}

type ControlFlowAnalyzer struct {
	routines   map[string]ast.Decl
	moduleName string
}

func NewControlFlowAnalyzer(module *ast.Module) *ControlFlowAnalyzer {
	routines := make(map[string]ast.Decl)
	if module != nil {
		for _, decl := range module.Declarations {
			switch d := decl.(type) {
			case ast.FunctionDecl:
				routines[d.Name] = d
			case ast.ProcedureDecl:
				routines[d.Name] = d
			}
		}
	}
	var moduleName string
	if module != nil {
		moduleName = module.Name
	}
	return &ControlFlowAnalyzer{
		routines:   routines,
		moduleName: moduleName,
	}
}

func (c *ControlFlowAnalyzer) AnalyzeRoutines() map[string]ast.RoutineFlowSummary {
	summaries := make(map[string]ast.RoutineFlowSummary)
	for name, decl := range c.routines {
		summaries[name] = c.AnalyzeRoutine(decl)
	}
	return summaries
}

func (c *ControlFlowAnalyzer) AnalyzeRoutine(decl ast.Decl) ast.RoutineFlowSummary {
	var body []ast.Stmt
	var kind string
	var name string
	var aborts []ast.AbortClause

	switch d := decl.(type) {
	case ast.FunctionDecl:
		body = d.Body
		kind = "function"
		name = d.Name
		aborts = d.Aborts
	case ast.ProcedureDecl:
		body = d.Body
		kind = "procedure"
		name = d.Name
		aborts = d.Aborts
	}

	bodyFlow := c.analyzeBlock(body)
	declaredAborts := make(map[string]bool)
	for _, clause := range aborts {
		declaredAborts[clause.Error] = true
	}

	normalReturnPossible := bodyFlow.normalReturnPossible || (kind == "procedure" && !bodyFlow.guaranteedExit)

	// In V0, propagated aborts is equivalent to declared aborts
	propagatedAborts := make(map[string]bool)
	for k, v := range declaredAborts {
		propagatedAborts[k] = v
	}

	return ast.RoutineFlowSummary{
		RoutineName:          name,
		RoutineKind:          kind,
		NormalReturnPossible: normalReturnPossible,
		GuaranteedExit:       bodyFlow.guaranteedExit,
		DeclaredAborts:       declaredAborts,
		EmittedAborts:        bodyFlow.emittedAborts,
		CalledRoutines:       bodyFlow.calledRoutines,
		PropagatedAborts:     propagatedAborts,
	}
}

func (c *ControlFlowAnalyzer) analyzeBlock(body []ast.Stmt) blockFlow {
	normalReturnPossible := false
	emittedAborts := make(map[string]bool)
	calledRoutines := make(map[string]bool)

	for _, stmt := range body {
		stmtFlow := c.analyzeStatement(stmt)
		if stmtFlow.normalReturnPossible {
			normalReturnPossible = true
		}
		for k, v := range stmtFlow.emittedAborts {
			emittedAborts[k] = v
		}
		for k, v := range stmtFlow.calledRoutines {
			calledRoutines[k] = v
		}
		if stmtFlow.guaranteedExit {
			return blockFlow{
				normalReturnPossible: normalReturnPossible,
				guaranteedExit:       true,
				emittedAborts:        emittedAborts,
				calledRoutines:       calledRoutines,
			}
		}
	}

	return blockFlow{
		normalReturnPossible: normalReturnPossible,
		guaranteedExit:       false,
		emittedAborts:        emittedAborts,
		calledRoutines:       calledRoutines,
	}
}

func (c *ControlFlowAnalyzer) analyzeStatement(stmt ast.Stmt) blockFlow {
	switch s := stmt.(type) {
	case ast.ReturnStmt:
		calls := c.callsInExpr(s.Value)
		return blockFlow{
			normalReturnPossible: true,
			guaranteedExit:       true,
			emittedAborts:        make(map[string]bool),
			calledRoutines:       calls,
		}
	case ast.AbortStmt:
		emitted := map[string]bool{s.Error: true}
		return blockFlow{
			normalReturnPossible: false,
			guaranteedExit:       true,
			emittedAborts:        emitted,
			calledRoutines:       make(map[string]bool),
		}
	case ast.CallStmt:
		calls := make(map[string]bool)
		if callExpr, ok := s.Call.(ast.CallExpr); ok {
			for k, v := range c.routineCallName(callExpr.Callee) {
				calls[k] = v
			}
			for _, arg := range callExpr.Arguments {
				for k, v := range c.callsInExpr(arg) {
					calls[k] = v
				}
			}
		} else {
			for k, v := range c.callsInExpr(s.Call) {
				calls[k] = v
			}
		}
		return blockFlow{
			normalReturnPossible: false,
			guaranteedExit:       false,
			emittedAborts:        make(map[string]bool),
			calledRoutines:       calls,
		}
	case ast.LetStmt:
		return blockFlow{
			normalReturnPossible: false,
			guaranteedExit:       false,
			emittedAborts:        make(map[string]bool),
			calledRoutines:       c.callsInExpr(s.Value),
		}
	case ast.AssignmentStmt:
		calls := c.callsInExpr(s.Value)
		for k, v := range c.callsInExpr(s.Target) {
			calls[k] = v
		}
		return blockFlow{
			normalReturnPossible: false,
			guaranteedExit:       false,
			emittedAborts:        make(map[string]bool),
			calledRoutines:       calls,
		}
	case ast.CheckStmt:
		return blockFlow{
			normalReturnPossible: false,
			guaranteedExit:       false,
			emittedAborts:        make(map[string]bool),
			calledRoutines:       c.callsInExpr(s.Condition),
		}
	case ast.IfStmt:
		conditionCalls := c.callsInExpr(s.Condition)
		thenFlow := c.analyzeBlock(s.ThenBody)
		elseFlow := c.analyzeBlock(s.ElseBody)

		emitted := make(map[string]bool)
		for k, v := range thenFlow.emittedAborts {
			emitted[k] = v
		}
		for k, v := range elseFlow.emittedAborts {
			emitted[k] = v
		}

		calls := make(map[string]bool)
		for k, v := range conditionCalls {
			calls[k] = v
		}
		for k, v := range thenFlow.calledRoutines {
			calls[k] = v
		}
		for k, v := range elseFlow.calledRoutines {
			calls[k] = v
		}

		return blockFlow{
			normalReturnPossible: thenFlow.normalReturnPossible || elseFlow.normalReturnPossible,
			guaranteedExit:       thenFlow.guaranteedExit && elseFlow.guaranteedExit,
			emittedAborts:        emitted,
			calledRoutines:       calls,
		}
	case ast.WhileStmt:
		bodyFlow := c.analyzeBlock(s.Body)
		calls := c.callsInExpr(s.Condition)
		for k, v := range bodyFlow.calledRoutines {
			calls[k] = v
		}
		for _, invariant := range s.Invariants {
			for k, v := range c.callsInExpr(invariant) {
				calls[k] = v
			}
		}
		if s.Variant != nil {
			for k, v := range c.callsInExpr(s.Variant) {
				calls[k] = v
			}
		}
		return blockFlow{
			normalReturnPossible: false,
			guaranteedExit:       false,
			emittedAborts:        bodyFlow.emittedAborts,
			calledRoutines:       calls,
		}
	case ast.CaseStmt:
		caseCalls := c.callsInExpr(s.Value)
		var branchFlows []blockFlow
		for _, branch := range s.When {
			branchFlows = append(branchFlows, c.analyzeBlock(branch.Body))
		}
		defaultFlow := c.analyzeBlock(s.Default)

		emitted := make(map[string]bool)
		calls := make(map[string]bool)
		for k, v := range caseCalls {
			calls[k] = v
		}

		for _, branch := range s.When {
			for k, v := range c.callsInExpr(branch.Value) {
				calls[k] = v
			}
		}

		normalReturnPossible := false
		guaranteedExit := true

		allFlows := append(branchFlows, defaultFlow)
		for _, flow := range allFlows {
			for k, v := range flow.emittedAborts {
				emitted[k] = v
			}
			for k, v := range flow.calledRoutines {
				calls[k] = v
			}
			if flow.normalReturnPossible {
				normalReturnPossible = true
			}
			if !flow.guaranteedExit {
				guaranteedExit = false
			}
		}

		return blockFlow{
			normalReturnPossible: normalReturnPossible,
			guaranteedExit:       guaranteedExit,
			emittedAborts:        emitted,
			calledRoutines:       calls,
		}
	case ast.ScopeStmt:
		// A scope runs SpawnBody, JoinBody, then ResultBody in sequence
		spawnFlow := c.analyzeBlock(s.SpawnBody)
		joinFlow := c.analyzeBlock(s.JoinBody)
		resultFlow := c.analyzeBlock(s.ResultBody)

		emitted := make(map[string]bool)
		calls := make(map[string]bool)

		// Accumulate emitted aborts
		for k, v := range spawnFlow.emittedAborts {
			emitted[k] = v
		}
		for k, v := range joinFlow.emittedAborts {
			emitted[k] = v
		}
		for k, v := range resultFlow.emittedAborts {
			emitted[k] = v
		}

		// Accumulate called routines
		for k, v := range spawnFlow.calledRoutines {
			calls[k] = v
		}
		for k, v := range joinFlow.calledRoutines {
			calls[k] = v
		}
		for k, v := range resultFlow.calledRoutines {
			calls[k] = v
		}

		normalReturnPossible := spawnFlow.normalReturnPossible || joinFlow.normalReturnPossible || resultFlow.normalReturnPossible
		guaranteedExit := spawnFlow.guaranteedExit || joinFlow.guaranteedExit || resultFlow.guaranteedExit

		return blockFlow{
			normalReturnPossible: normalReturnPossible,
			guaranteedExit:       guaranteedExit,
			emittedAborts:        emitted,
			calledRoutines:       calls,
		}
	}

	return blockFlow{
		normalReturnPossible: false,
		guaranteedExit:       false,
		emittedAborts:        make(map[string]bool),
		calledRoutines:       make(map[string]bool),
	}
}

func (c *ControlFlowAnalyzer) callsInExpr(expr ast.Expr) map[string]bool {
	calls := make(map[string]bool)
	if expr == nil {
		return calls
	}

	switch e := expr.(type) {
	case ast.OkExpr:
		return c.callsInExpr(e.Value)
	case ast.CallExpr:
		for k, v := range c.routineCallName(e.Callee) {
			calls[k] = v
		}
		for _, arg := range e.Arguments {
			for k, v := range c.callsInExpr(arg) {
				calls[k] = v
			}
		}
	case ast.NamedArgumentExpr:
		return c.callsInExpr(e.Value)
	case ast.RecordLiteralExpr:
		for _, field := range e.Fields {
			for k, v := range c.callsInExpr(field.Value) {
				calls[k] = v
			}
		}
	case ast.ArrayLiteralExpr:
		for _, elem := range e.Elements {
			for k, v := range c.callsInExpr(elem) {
				calls[k] = v
			}
		}
	case ast.IndexExpr:
		for k, v := range c.callsInExpr(e.Array) {
			calls[k] = v
		}
		for k, v := range c.callsInExpr(e.Index) {
			calls[k] = v
		}
	case ast.UnaryExpr:
		return c.callsInExpr(e.Value)
	case ast.BinaryExpr:
		for k, v := range c.callsInExpr(e.Left) {
			calls[k] = v
		}
		for k, v := range c.callsInExpr(e.Right) {
			calls[k] = v
		}
	case ast.AwaitExpr:
		return c.callsInExpr(e.Value)
	}

	return calls
}

func (c *ControlFlowAnalyzer) routineCallName(expr ast.Expr) map[string]bool {
	calls := make(map[string]bool)
	name, ok := callName(expr)
	if !ok {
		return calls
	}

	localName := c.localRoutineName(name)
	if _, exists := c.routines[localName]; exists {
		calls[localName] = true
	}
	return calls
}

func (c *ControlFlowAnalyzer) localRoutineName(name string) string {
	if c.moduleName == "" {
		return name
	}
	prefix := c.moduleName + "."
	if strings.HasPrefix(name, prefix) {
		return name[len(prefix):]
	}
	return name
}
