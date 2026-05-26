package parser

import (
	"freehold-go-frontend/internal/ast"
	"freehold-go-frontend/internal/diagnostic"
	"freehold-go-frontend/internal/token"
)

type Parser struct {
	tokens      []token.Token
	pos         int
	moduleName  string
	diagnostics []*diagnostic.Diagnostic
}

func New(tokens []token.Token) *Parser {
	return &Parser{tokens: tokens}
}

func (p *Parser) Diagnostics() []*diagnostic.Diagnostic {
	return p.diagnostics
}

func (p *Parser) ParseModule() (module *ast.Module, err error) {
	defer func() {
		if r := recover(); r != nil {
			diag := p.diagnosticFromRecover(r)
			p.addDiagnostic(diag)
			err = p.diagnostics[0]
		}
	}()

	start := p.expect(token.Module)

	name := p.parseQualifiedName()
	p.moduleName = name

	var decls []ast.Decl

	for !p.at(token.End) && !p.at(token.EOF) {
		decl, ok := p.parseDeclarationRecovering()
		if ok {
			decls = append(decls, decl)
		}
	}

	p.expect(token.End)
	endName := p.parseQualifiedName()

	module = &ast.Module{
		Kind:         "Module",
		Pos:          start.Pos,
		Name:         name,
		Declarations: decls,
		EndName:      endName,
	}

	if len(p.diagnostics) > 0 {
		return module, p.diagnostics[0]
	}

	return module, nil
}

func (p *Parser) parseDeclarationRecovering() (decl ast.Decl, ok bool) {
	defer func() {
		if r := recover(); r != nil {
			diag := p.diagnosticFromRecover(r)
			p.addDiagnostic(diag)
			p.synchronizeDeclaration()
			decl = nil
			ok = false
		}
	}()

	return p.parseDeclaration(), true
}

func (p *Parser) parseDeclaration() ast.Decl {
	if p.at(token.Type) {
		return p.parseTypeDecl()
	}
	if p.at(token.Error) {
		return p.parseErrorDecl()
	}
	if p.at(token.Service) {
		return p.parseServiceDecl()
	}
	if p.at(token.Import) {
		return p.parseImport()
	}
	if p.at(token.Async) {
		return p.parseFunction()
	}
	if p.at(token.Function) {
		return p.parseFunction()
	}
	if p.at(token.Procedure) {
		return p.parseProcedure()
	}

	panic(diagnostic.ExpectedDeclaration(p.peek()))
}

func (p *Parser) parseTypeDecl() ast.TypeDecl {
	start := p.expect(token.Type)

	name := p.parseName()
	typeParams := p.parseOptionalTypeParams()
	p.expect(token.Is)

	if p.at(token.Record) {
		return p.parseRecordTypeDecl(name, typeParams, start.Pos)
	}

	base := p.parseTypeName()

	var typeRange *ast.TypeRange
	if p.at(token.Range) {
		p.expect(token.Range)
		min := p.parseSignedNumberLiteral()
		p.expect(token.DotDot)
		max := p.parseSignedNumberLiteral()
		typeRange = &ast.TypeRange{Min: min, Max: max}
	}

	return ast.TypeDecl{
		Kind:       "TypeDecl",
		Pos:        start.Pos,
		Name:       name,
		TypeParams: typeParams,
		Base:       base,
		Range:      typeRange,
	}
}

func (p *Parser) parseRecordTypeDecl(name string, typeParams []string, pos token.Position) ast.TypeDecl {
	p.expect(token.Record)

	var fields []ast.Param
	for !p.at(token.End) && !p.at(token.EOF) {
		fields = append(fields, p.parseRecordField())
	}

	p.expect(token.End)
	p.expect(token.Record)

	return ast.TypeDecl{
		Kind:       "TypeDecl",
		Pos:        pos,
		Name:       name,
		TypeParams: typeParams,
		Base:       "record",
		Fields:     fields,
	}
}

func (p *Parser) parseRecordField() ast.Param {
	field := p.parseParam()
	if p.at(token.Proto) {
		p.expect(token.Proto)
		protoID := p.parseIntLiteral()
		field.ProtoID = &protoID
	}
	return field
}

func (p *Parser) parseOptionalTypeParams() []string {
	if !p.at(token.Less) {
		return nil
	}

	p.expect(token.Less)
	params := []string{p.parseName()}
	for p.at(token.Comma) {
		p.expect(token.Comma)
		params = append(params, p.parseName())
	}
	p.expect(token.Greater)
	return params
}

func (p *Parser) parseErrorDecl() ast.ErrorDecl {
	start := p.expect(token.Error)

	return ast.ErrorDecl{
		Kind: "ErrorDecl",
		Pos:  start.Pos,
		Name: p.parseName(),
	}
}

func (p *Parser) parseImport() ast.ImportDecl {
	start := p.expect(token.Import)

	moduleName := p.parseQualifiedName()
	var exposing []string

	if p.at(token.Exposing) {
		p.expect(token.Exposing)
		exposing = append(exposing, p.parseName())

		for p.at(token.Comma) {
			p.expect(token.Comma)
			exposing = append(exposing, p.parseName())
		}
	}

	return ast.ImportDecl{
		Kind:     "ImportDecl",
		Pos:      start.Pos,
		Module:   moduleName,
		Exposing: exposing,
	}
}

func (p *Parser) parseServiceDecl() ast.ServiceDecl {
	start := p.expect(token.Service)
	name := p.parseName()
	p.expect(token.Is)

	var rpcs []ast.RpcDecl
	for p.at(token.Rpc) {
		rpcs = append(rpcs, p.parseRpcDecl())
	}

	p.expect(token.End)
	endName := p.parseName()

	return ast.ServiceDecl{
		Kind:    "ServiceDecl",
		Pos:     start.Pos,
		Name:    name,
		Rpcs:    rpcs,
		EndName: endName,
	}
}

func (p *Parser) parseRpcDecl() ast.RpcDecl {
	start := p.expect(token.Rpc)
	name := p.parseName()
	p.expect(token.LParen)
	requestName := p.parseName()
	p.expect(token.Colon)
	requestType := p.parseTypeName()
	p.expect(token.RParen)
	p.expect(token.Colon)
	responseType := p.parseTypeName()

	return ast.RpcDecl{
		Kind:         "RpcDecl",
		Pos:          start.Pos,
		Name:         name,
		RequestName:  requestName,
		RequestType:  requestType,
		ResponseType: responseType,
	}
}

func (p *Parser) parseQualifiedName() string {
	name := p.parseName()

	for p.at(token.Dot) {
		p.expect(token.Dot)
		name += "." + p.parseName()
	}

	return name
}

func (p *Parser) parseName() string {
	return p.parseNameToken().Lexeme
}

func (p *Parser) parseNameToken() token.Token {
	tok := p.peek()
	if tok.Kind == token.Ident || tok.Kind == token.Scope || tok.Kind == token.Spawn || tok.Kind == token.Join || tok.Kind == token.Result || tok.Kind == token.Value {
		p.pos++
		return tok
	}

	panic(diagnostic.ExpectedIdentifier(tok))
}

func (p *Parser) parseFunction() ast.FunctionDecl {
	isAsync := false
	start := p.peek()
	if p.at(token.Async) {
		start = p.expect(token.Async)
		isAsync = true
	}
	functionTok := p.expect(token.Function)
	if !isAsync {
		start = functionTok
	}

	name := p.parseName()
	typeParams := p.parseOptionalTypeParams()

	p.expect(token.LParen)
	params := p.parseParams()
	p.expect(token.RParen)

	p.expect(token.Returns)
	if p.at(token.Is) || p.at(token.Requires) || p.at(token.Aborts) || p.at(token.Ensures) || p.at(token.EOF) {
		panic(diagnostic.MissingReturnType(p.peek()))
	}
	returnType := p.parseTypeName()

	requires, aborts, ensures := p.parseContracts()

	p.expect(token.Is)

	body := p.parseStatements(func() bool { return p.at(token.End) || p.at(token.EOF) })

	if !p.at(token.End) {
		panic(diagnostic.MissingFunctionEnd(p.peek()))
	}
	p.expect(token.End)
	endName := p.parseName()

	return ast.FunctionDecl{
		Kind:       "FunctionDecl",
		Pos:        start.Pos,
		Name:       name,
		IsAsync:    isAsync,
		TypeParams: typeParams,
		Params:     params,
		ReturnType: returnType,
		Requires:   requires,
		Aborts:     aborts,
		Ensures:    ensures,
		Body:       body,
		EndName:    endName,
	}
}

func (p *Parser) parseProcedure() ast.ProcedureDecl {
	start := p.expect(token.Procedure)

	name := p.parseName()

	p.expect(token.LParen)
	params := p.parseParams()
	p.expect(token.RParen)

	requires, aborts, ensures := p.parseContracts()

	p.expect(token.Is)

	body := p.parseStatements(func() bool { return p.at(token.End) || p.at(token.EOF) })

	if !p.at(token.End) {
		panic(diagnostic.MissingProcedureEnd(p.peek()))
	}
	p.expect(token.End)
	endName := p.parseName()

	return ast.ProcedureDecl{
		Kind:     "ProcedureDecl",
		Pos:      start.Pos,
		Name:     name,
		Params:   params,
		Requires: requires,
		Aborts:   aborts,
		Ensures:  ensures,
		Body:     body,
		EndName:  endName,
	}
}

func (p *Parser) parseContracts() ([]ast.Expr, []ast.AbortClause, []ast.Expr) {
	var requires []ast.Expr
	var aborts []ast.AbortClause
	var ensures []ast.Expr

	for p.at(token.Requires) {
		p.expect(token.Requires)
		requires = append(requires, p.parseContractExprList()...)
	}

	for p.at(token.Aborts) {
		p.expect(token.Aborts)
		aborts = append(aborts, p.parseAbortClause())
	}

	for p.at(token.Ensures) {
		p.expect(token.Ensures)
		ensures = append(ensures, p.parseContractExprList()...)
	}

	return requires, aborts, ensures
}

func (p *Parser) parseAbortClause() ast.AbortClause {
	errorTok := p.parseNameToken()
	clause := ast.AbortClause{Pos: errorTok.Pos, Error: errorTok.Lexeme}
	if p.at(token.When) {
		p.expect(token.When)
		clause.Condition = p.parseExpr()
	}
	return clause
}

func (p *Parser) parseContractExprList() []ast.Expr {
	exprs := []ast.Expr{p.parseExpr()}

	for p.at(token.Comma) {
		p.expect(token.Comma)
		exprs = append(exprs, p.parseExpr())
	}

	return exprs
}

func (p *Parser) parseStatements(stop func() bool) []ast.Stmt {
	var body []ast.Stmt

	for !stop() {
		stmt, ok := p.parseStatementRecovering(stop)
		if ok {
			body = append(body, stmt)
		}
	}

	return body
}

func (p *Parser) parseStatementRecovering(stop func() bool) (stmt ast.Stmt, ok bool) {
	defer func() {
		if r := recover(); r != nil {
			diag := p.diagnosticFromRecover(r)
			p.addDiagnostic(diag)
			p.synchronizeStatement(stop)
			stmt = nil
			ok = false
		}
	}()

	return p.parseStatement(), true
}

func (p *Parser) parseStatement() ast.Stmt {
	if p.at(token.Return) {
		return p.parseReturn()
	}
	if p.at(token.Abort) {
		return p.parseAbort()
	}
	if p.at(token.Check) {
		return p.parseCheck()
	}
	if p.at(token.Call) {
		return p.parseCallStmt()
	}
	if p.at(token.Let) {
		return p.parseLet()
	}
	if p.at(token.If) {
		return p.parseIf()
	}
	if p.at(token.While) {
		return p.parseWhile()
	}
	if p.at(token.Case) {
		return p.parseCase()
	}
	if p.at(token.Scope) {
		return p.parseScope()
	}
	if p.at(token.Ident) {
		return p.parseIdentStatement()
	}

	tok := p.peek()
	panic(diagnostic.ExpectedStatement(tok))
}

func (p *Parser) parseAbort() ast.AbortStmt {
	start := p.expect(token.Abort)

	return ast.AbortStmt{
		Kind:  "AbortStmt",
		Pos:   start.Pos,
		Error: p.parseName(),
	}
}

func (p *Parser) parseParams() []ast.Param {
	var params []ast.Param

	if p.at(token.RParen) {
		return params
	}

	params = append(params, p.parseParam())

	for p.at(token.Comma) {
		p.expect(token.Comma)
		params = append(params, p.parseParam())
	}

	return params
}

func (p *Parser) parseParam() ast.Param {
	nameTok := p.parseNameToken()
	if !p.at(token.Colon) {
		panic(diagnostic.ExpectedParameterColon(p.peek()))
	}
	p.expect(token.Colon)
	typ := p.parseTypeName()

	return ast.Param{
		Pos:  nameTok.Pos,
		Name: nameTok.Lexeme,
		Type: typ,
	}
}

func (p *Parser) parseReturn() ast.ReturnStmt {
	start := p.expect(token.Return)

	return ast.ReturnStmt{
		Kind:  "ReturnStmt",
		Pos:   start.Pos,
		Value: p.parseExpr(),
	}
}

func (p *Parser) parseCheck() ast.CheckStmt {
	start := p.expect(token.Check)

	return ast.CheckStmt{
		Kind:      "CheckStmt",
		Pos:       start.Pos,
		Condition: p.parseExpr(),
	}
}

func (p *Parser) parseLet() ast.LetStmt {
	start := p.expect(token.Let)

	name := p.parseName()
	p.expect(token.Colon)
	typ := p.parseTypeName()
	p.expect(token.Equal)

	return ast.LetStmt{
		Kind:  "LetStmt",
		Pos:   start.Pos,
		Name:  name,
		Type:  typ,
		Value: p.parseExpr(),
	}
}

func (p *Parser) parseCallStmt() ast.CallStmt {
	start := p.expect(token.Call)

	return ast.CallStmt{
		Kind: "CallStmt",
		Pos:  start.Pos,
		Call: p.parseAtom(),
	}
}

func (p *Parser) parseIdentStatement() ast.Stmt {
	target := p.parseAtom()

	if p.at(token.Assign) {
		pos := exprPos(target)
		p.expect(token.Assign)
		return ast.AssignmentStmt{
			Kind:   "AssignmentStmt",
			Pos:    pos,
			Target: target,
			Value:  p.parseExpr(),
		}
	}

	if call, ok := target.(ast.CallExpr); ok {
		return ast.CallStmt{
			Kind: "CallStmt",
			Pos:  call.Pos,
			Call: call,
		}
	}

	tok := p.peek()
	panic(diagnostic.ExpectedAssignmentOrCall(tok))
}

func (p *Parser) parseIf() ast.IfStmt {
	start := p.expect(token.If)
	condition := p.parseExpr()
	p.expect(token.Then)

	thenBody := p.parseStatements(func() bool { return p.at(token.Else) || p.at(token.End) || p.at(token.EOF) })
	var elseBody []ast.Stmt

	if p.at(token.Else) {
		p.expect(token.Else)
		elseBody = p.parseStatements(func() bool { return p.at(token.End) || p.at(token.EOF) })
	}

	if !p.at(token.End) {
		panic(diagnostic.MissingIfEnd(p.peek()))
	}
	p.expect(token.End)
	if !p.at(token.If) {
		panic(diagnostic.MissingIfEnd(p.peek()))
	}
	p.expect(token.If)

	return ast.IfStmt{
		Kind:      "IfStmt",
		Pos:       start.Pos,
		Condition: condition,
		ThenBody:  thenBody,
		ElseBody:  elseBody,
	}
}

func (p *Parser) parseWhile() ast.WhileStmt {
	start := p.expect(token.While)
	condition := p.parseExpr()

	var invariants []ast.Expr
	for p.at(token.Invariant) {
		p.expect(token.Invariant)
		invariants = append(invariants, p.parseExpr())
	}
	if len(invariants) == 0 {
		tok := p.peek()
		panic(diagnostic.MissingWhileInvariant(tok))
	}

	var variant ast.Expr
	if p.at(token.Variant) {
		p.expect(token.Variant)
		variant = p.parseExpr()
	}

	p.expect(token.Do)
	body := p.parseStatements(func() bool { return p.at(token.End) || p.at(token.EOF) })
	if !p.at(token.End) {
		panic(diagnostic.MissingWhileEnd(p.peek()))
	}
	p.expect(token.End)
	if !p.at(token.While) {
		panic(diagnostic.MissingWhileEnd(p.peek()))
	}
	p.expect(token.While)

	return ast.WhileStmt{
		Kind:       "WhileStmt",
		Pos:        start.Pos,
		Condition:  condition,
		Invariants: invariants,
		Variant:    variant,
		Body:       body,
	}
}

func (p *Parser) parseCase() ast.CaseStmt {
	start := p.expect(token.Case)
	value := p.parseExpr()
	p.expect(token.Is)

	var branches []ast.CaseBranch
	for p.at(token.When) {
		whenTok := p.expect(token.When)
		branchValue := p.parseExpr()
		p.expect(token.Arrow)
		branchBody := p.parseStatements(func() bool {
			return p.at(token.When) || p.at(token.Default) || p.at(token.End) || p.at(token.EOF)
		})
		branches = append(branches, ast.CaseBranch{Pos: whenTok.Pos, Value: branchValue, Body: branchBody})
	}

	var defaultBody []ast.Stmt
	if p.at(token.Default) {
		p.expect(token.Default)
		p.expect(token.Arrow)
		defaultBody = p.parseStatements(func() bool { return p.at(token.End) || p.at(token.EOF) })
	} else {
		tok := p.peek()
		panic(diagnostic.MissingCaseDefault(tok))
	}

	if !p.at(token.End) {
		panic(diagnostic.MissingCaseEnd(p.peek()))
	}
	p.expect(token.End)
	if !p.at(token.Case) {
		panic(diagnostic.MissingCaseEnd(p.peek()))
	}
	p.expect(token.Case)

	return ast.CaseStmt{
		Kind:    "CaseStmt",
		Pos:     start.Pos,
		Value:   value,
		When:    branches,
		Default: defaultBody,
	}
}

func (p *Parser) parseScope() ast.ScopeStmt {
	start := p.expect(token.Scope)
	name := p.parseName()
	p.expect(token.Do)

	p.expect(token.Spawn)
	spawnBody := p.parseStatements(func() bool { return p.at(token.Join) || p.at(token.End) || p.at(token.EOF) })

	p.expect(token.Join)
	joinBody := p.parseStatements(func() bool { return p.at(token.Result) || p.at(token.End) || p.at(token.EOF) })

	p.expect(token.Result)
	resultBody := p.parseStatements(func() bool { return p.at(token.End) || p.at(token.EOF) })

	p.expect(token.End)
	p.expect(token.Scope)

	return ast.ScopeStmt{
		Kind:       "ScopeStmt",
		Pos:        start.Pos,
		Name:       name,
		SpawnBody:  spawnBody,
		JoinBody:   joinBody,
		ResultBody: resultBody,
	}
}

func (p *Parser) parseAssignment() ast.AssignmentStmt {
	target := p.parseFieldAccess()
	pos := exprPos(target)
	p.expect(token.Assign)

	return ast.AssignmentStmt{
		Kind:   "AssignmentStmt",
		Pos:    pos,
		Target: target,
		Value:  p.parseExpr(),
	}
}

func (p *Parser) parseExpr() ast.Expr {
	return p.parseOr()
}

func (p *Parser) parseOr() ast.Expr {
	left := p.parseAnd()

	for p.at(token.Or) {
		op := p.expect(token.Or).Lexeme
		right := p.parseAnd()
		left = ast.BinaryExpr{Kind: "BinaryExpr", Pos: exprPos(left), Op: op, Left: left, Right: right}
	}

	return left
}

func (p *Parser) parseAnd() ast.Expr {
	left := p.parseComparison()

	for p.at(token.And) {
		op := p.expect(token.And).Lexeme
		right := p.parseComparison()
		left = ast.BinaryExpr{Kind: "BinaryExpr", Pos: exprPos(left), Op: op, Left: left, Right: right}
	}

	return left
}

func (p *Parser) parseComparison() ast.Expr {
	left := p.parseSum()

	for p.at(token.Equal) || p.at(token.NotEqual) || p.at(token.Less) || p.at(token.LessEqual) || p.at(token.Greater) || p.at(token.GreaterEqual) {
		tok := p.peek()
		p.pos++
		right := p.parseSum()
		left = ast.BinaryExpr{Kind: "BinaryExpr", Pos: exprPos(left), Op: tok.Lexeme, Left: left, Right: right}
	}

	return left
}

func (p *Parser) parseEquality() ast.Expr {
	left := p.parseSum()

	for p.at(token.Equal) {
		op := p.expect(token.Equal).Lexeme
		right := p.parseSum()

		left = ast.BinaryExpr{
			Kind:  "BinaryExpr",
			Pos:   exprPos(left),
			Op:    op,
			Left:  left,
			Right: right,
		}
	}

	return left
}

func (p *Parser) parseSum() ast.Expr {
	left := p.parseProduct()

	for p.at(token.Plus) || p.at(token.Minus) {
		tok := p.peek()
		p.pos++
		right := p.parseProduct()

		left = ast.BinaryExpr{
			Kind:  "BinaryExpr",
			Pos:   exprPos(left),
			Op:    tok.Lexeme,
			Left:  left,
			Right: right,
		}
	}

	return left
}

func (p *Parser) parseProduct() ast.Expr {
	left := p.parseUnary()

	for p.at(token.Star) || p.at(token.Slash) {
		tok := p.peek()
		p.pos++
		right := p.parseUnary()

		left = ast.BinaryExpr{
			Kind:  "BinaryExpr",
			Pos:   exprPos(left),
			Op:    tok.Lexeme,
			Left:  left,
			Right: right,
		}
	}

	return left
}

func (p *Parser) parseUnary() ast.Expr {
	if p.at(token.Await) {
		start := p.expect(token.Await)
		return ast.AwaitExpr{
			Kind:  "AwaitExpr",
			Pos:   start.Pos,
			Value: p.parseUnary(),
		}
	}

	if p.at(token.Not) || p.at(token.Minus) {
		tok := p.peek()
		p.pos++
		return ast.UnaryExpr{
			Kind:  "UnaryExpr",
			Pos:   tok.Pos,
			Op:    tok.Lexeme,
			Value: p.parseUnary(),
		}
	}

	return p.parseAtom()
}

func (p *Parser) parseAtom() ast.Expr {
	if p.at(token.Int) || p.at(token.Float) {
		tok := p.peek()
		p.pos++
		return ast.NumberExpr{
			Kind:  "NumberExpr",
			Pos:   tok.Pos,
			Value: tok.Lexeme,
		}
	}

	if p.at(token.LBracket) {
		return p.parseArrayLiteral()
	}

	if p.at(token.String) {
		tok := p.expect(token.String)
		return ast.StringExpr{
			Kind:  "StringExpr",
			Pos:   tok.Pos,
			Value: tok.Lexeme,
		}
	}

	if p.at(token.LParen) {
		p.expect(token.LParen)
		expr := p.parseExpr()
		p.expect(token.RParen)
		return expr
	}

	if p.at(token.Ok) {
		start := p.expect(token.Ok)
		return ast.OkExpr{
			Kind:  "OkExpr",
			Pos:   start.Pos,
			Value: p.parseExpr(),
		}
	}

	if p.at(token.Error) {
		start := p.expect(token.Error)
		if !p.at(token.Ident) {
			return p.finishPostfix(ast.IdentifierExpr{
				Kind: "IdentifierExpr",
				Pos:  start.Pos,
				Name: "error",
			})
		}
		return ast.ErrorExpr{
			Kind: "ErrorExpr",
			Pos:  start.Pos,
			Name: p.parseName(),
		}
	}

	if p.at(token.True) || p.at(token.False) || p.at(token.Success) || p.at(token.Failure) || p.at(token.Value) {
		tok := p.peek()
		p.pos++
		return p.finishPostfix(ast.IdentifierExpr{
			Kind: "IdentifierExpr",
			Pos:  tok.Pos,
			Name: tok.Lexeme,
		})
	}

	if p.at(token.Scope) || p.at(token.Spawn) || p.at(token.Join) || p.at(token.Result) {
		tok := p.parseNameToken()
		expr := ast.Expr(ast.IdentifierExpr{Kind: "IdentifierExpr", Pos: tok.Pos, Name: tok.Lexeme})
		return p.finishPostfix(expr)
	}

	if !p.at(token.Ident) {
		panic(diagnostic.ExpectedExpression(p.peek()))
	}

	if p.genericFunctionCallAhead() {
		nameTok := p.parseNameToken()
		typeArgs := p.parseTypeArgs()
		callee := ast.IdentifierExpr{Kind: "IdentifierExpr", Pos: nameTok.Pos, Name: nameTok.Lexeme}
		return p.finishCallWithTypeArgs(callee, typeArgs)
	}

	if p.genericRecordLiteralAhead() {
		pos := p.peek().Pos
		typeName := p.parseTypeName()
		return p.parseRecordLiteral(typeName, pos)
	}

	tok := p.parseNameToken()

	if p.at(token.LBrace) {
		return p.parseRecordLiteral(tok.Lexeme, tok.Pos)
	}

	expr := ast.Expr(ast.IdentifierExpr{
		Kind: "IdentifierExpr",
		Pos:  tok.Pos,
		Name: tok.Lexeme,
	})

	return p.finishPostfix(expr)
}

func (p *Parser) genericFunctionCallAhead() bool {
	if !p.at(token.Ident) || p.peekAhead(1).Kind != token.Less {
		return false
	}
	depth := 0
	for i := p.pos + 1; i < len(p.tokens); i++ {
		switch p.tokens[i].Kind {
		case token.Less:
			depth++
		case token.Greater:
			depth--
			if depth == 0 {
				return i+1 < len(p.tokens) && p.tokens[i+1].Kind == token.LParen
			}
		}
	}
	return false
}

func (p *Parser) genericRecordLiteralAhead() bool {
	if !p.at(token.Ident) || p.peekAhead(1).Kind != token.Less {
		return false
	}
	depth := 0
	for i := p.pos + 1; i < len(p.tokens); i++ {
		switch p.tokens[i].Kind {
		case token.Less:
			depth++
		case token.Greater:
			depth--
			if depth == 0 {
				return i+1 < len(p.tokens) && p.tokens[i+1].Kind == token.LBrace
			}
		}
	}
	return false
}

func (p *Parser) finishPostfix(expr ast.Expr) ast.Expr {
	for p.at(token.Dot) || p.at(token.LBracket) || p.at(token.LParen) || p.genericPostfixCallAhead() {
		if p.genericPostfixCallAhead() {
			typeArgs := p.parseTypeArgs()
			expr = p.finishCallWithTypeArgs(expr, typeArgs)
			continue
		}

		if p.at(token.LParen) {
			expr = p.finishCall(expr)
			continue
		}

		if p.at(token.LBracket) {
			p.expect(token.LBracket)
			index := p.parseExpr()
			p.expect(token.RBracket)
			expr = ast.IndexExpr{
				Kind:  "IndexExpr",
				Pos:   exprPos(expr),
				Array: expr,
				Index: index,
			}
			continue
		}

		p.expect(token.Dot)
		expr = ast.FieldAccessExpr{
			Kind:   "FieldAccessExpr",
			Pos:    exprPos(expr),
			Object: expr,
			Field:  p.parseName(),
		}
	}

	return expr
}

func (p *Parser) parseFieldAccess() ast.Expr {
	nameTok := p.parseNameToken()
	expr := ast.Expr(ast.IdentifierExpr{
		Kind: "IdentifierExpr",
		Pos:  nameTok.Pos,
		Name: nameTok.Lexeme,
	})

	for p.at(token.Dot) || p.at(token.LBracket) || p.at(token.LParen) || p.genericPostfixCallAhead() {
		if p.genericPostfixCallAhead() {
			typeArgs := p.parseTypeArgs()
			expr = p.finishCallWithTypeArgs(expr, typeArgs)
			continue
		}

		if p.at(token.LParen) {
			expr = p.finishCall(expr)
			continue
		}

		if p.at(token.LBracket) {
			p.expect(token.LBracket)
			index := p.parseExpr()
			p.expect(token.RBracket)
			expr = ast.IndexExpr{
				Kind:  "IndexExpr",
				Pos:   exprPos(expr),
				Array: expr,
				Index: index,
			}
			continue
		}

		p.expect(token.Dot)
		expr = ast.FieldAccessExpr{
			Kind:   "FieldAccessExpr",
			Pos:    exprPos(expr),
			Object: expr,
			Field:  p.parseName(),
		}
	}

	return expr
}

func (p *Parser) finishCall(callee ast.Expr) ast.CallExpr {
	return p.finishCallWithTypeArgs(callee, nil)
}

func (p *Parser) genericPostfixCallAhead() bool {
	if !p.at(token.Less) {
		return false
	}
	depth := 0
	for i := p.pos; i < len(p.tokens); i++ {
		switch p.tokens[i].Kind {
		case token.Less:
			depth++
		case token.Greater:
			depth--
			if depth == 0 {
				return i+1 < len(p.tokens) && p.tokens[i+1].Kind == token.LParen
			}
		case token.EOF:
			return false
		}
	}
	return false
}

func (p *Parser) finishCallWithTypeArgs(callee ast.Expr, typeArgs []string) ast.CallExpr {
	p.expect(token.LParen)

	var args []ast.Expr
	if !p.at(token.RParen) {
		args = append(args, p.parseCallArg())

		for p.at(token.Comma) {
			p.expect(token.Comma)
			args = append(args, p.parseCallArg())
		}
	}

	p.expect(token.RParen)

	return ast.CallExpr{
		Kind:      "CallExpr",
		Pos:       exprPos(callee),
		Callee:    callee,
		TypeArgs:  typeArgs,
		Arguments: args,
	}
}

func (p *Parser) parseTypeArgs() []string {
	p.expect(token.Less)
	args := []string{p.parseTypeName()}
	for p.at(token.Comma) {
		p.expect(token.Comma)
		args = append(args, p.parseTypeName())
	}
	p.expect(token.Greater)
	return args
}

func (p *Parser) parseCallArg() ast.Expr {
	if p.at(token.Ident) && p.peekAhead(1).Kind == token.Colon {
		nameTok := p.parseNameToken()
		p.expect(token.Colon)
		return ast.NamedArgumentExpr{
			Kind:  "NamedArgumentExpr",
			Pos:   nameTok.Pos,
			Name:  nameTok.Lexeme,
			Value: p.parseExpr(),
		}
	}
	return p.parseExpr()
}

func (p *Parser) parseArrayLiteral() ast.ArrayLiteralExpr {
	start := p.expect(token.LBracket)

	var elements []ast.Expr
	if !p.at(token.RBracket) {
		elements = append(elements, p.parseExpr())

		for p.at(token.Comma) {
			p.expect(token.Comma)
			elements = append(elements, p.parseExpr())
		}
	}

	p.expect(token.RBracket)

	return ast.ArrayLiteralExpr{
		Kind:     "ArrayLiteralExpr",
		Pos:      start.Pos,
		Elements: elements,
	}
}

func (p *Parser) parseRecordLiteral(typeName string, pos token.Position) ast.RecordLiteralExpr {
	p.expect(token.LBrace)

	var fields []ast.RecordField
	if !p.at(token.RBrace) {
		fields = append(fields, p.parseRecordLiteralField())

		for p.at(token.Comma) {
			p.expect(token.Comma)
			fields = append(fields, p.parseRecordLiteralField())
		}
	}

	p.expect(token.RBrace)

	return ast.RecordLiteralExpr{
		Kind:   "RecordLiteralExpr",
		Pos:    pos,
		Type:   typeName,
		Fields: fields,
	}
}

func (p *Parser) parseRecordLiteralField() ast.RecordField {
	nameTok := p.parseNameToken()
	p.expect(token.Colon)

	return ast.RecordField{
		Pos:   nameTok.Pos,
		Name:  nameTok.Lexeme,
		Value: p.parseExpr(),
	}
}

func exprPos(expr ast.Expr) token.Position {
	switch value := expr.(type) {
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
	default:
		return token.Position{}
	}
}

func (p *Parser) parseSignedNumberLiteral() string {
	sign := ""
	if p.at(token.Minus) {
		sign = p.expect(token.Minus).Lexeme
	}

	if p.at(token.Int) || p.at(token.Float) {
		tok := p.peek()
		p.pos++
		return sign + tok.Lexeme
	}

	tok := p.peek()
	panic(diagnostic.ExpectedNumber(tok))
}

func (p *Parser) parseIntLiteral() int {
	tok := p.expect(token.Int)
	value := 0
	for _, r := range tok.Lexeme {
		value = value*10 + int(r-'0')
	}
	return value
}

func (p *Parser) parseTypeName() string {
	name := p.parseName()

	if p.at(token.Less) {
		p.expect(token.Less)
		name += "<" + p.parseTypeName()

		for p.at(token.Comma) {
			p.expect(token.Comma)
			if p.at(token.Int) {
				name += ", " + p.expect(token.Int).Lexeme
			} else {
				name += ", " + p.parseTypeName()
			}
		}

		p.expect(token.Greater)
		name += ">"
	}

	return name
}

func (p *Parser) at(kind token.Kind) bool {
	return p.peek().Kind == kind
}

func (p *Parser) peek() token.Token {
	if p.pos >= len(p.tokens) {
		return p.tokens[len(p.tokens)-1]
	}
	return p.tokens[p.pos]
}

func (p *Parser) peekAhead(offset int) token.Token {
	index := p.pos + offset
	if index >= len(p.tokens) {
		return p.tokens[len(p.tokens)-1]
	}
	return p.tokens[index]
}

func (p *Parser) expect(kind token.Kind) token.Token {
	tok := p.peek()

	if tok.Kind != kind {
		panic(diagnostic.ExpectedToken(kind, tok))
	}

	p.pos++
	return tok
}

func (p *Parser) addDiagnostic(diag *diagnostic.Diagnostic) {
	if diag == nil {
		return
	}
	for _, existing := range p.diagnostics {
		if existing.Code == diag.Code && existing.Location.Line == diag.Location.Line && existing.Location.Column == diag.Location.Column {
			return
		}
	}
	p.diagnostics = append(p.diagnostics, diag)
}

func (p *Parser) diagnosticFromRecover(value interface{}) *diagnostic.Diagnostic {
	if diag, ok := value.(*diagnostic.Diagnostic); ok {
		return diag
	}
	panic(value)
}

func (p *Parser) synchronizeDeclaration() {
	for !p.at(token.EOF) {
		if p.atDeclarationBoundary() {
			return
		}
		p.pos++
	}
}

func (p *Parser) synchronizeStatement(stop func() bool) {
	for !stop() && !p.at(token.EOF) {
		if p.atStatementBoundary() {
			return
		}
		p.pos++
	}
}

func (p *Parser) atDeclarationBoundary() bool {
	return p.at(token.Import) || p.at(token.Type) || p.at(token.Error) || p.at(token.Service) || p.at(token.Function) || p.at(token.Procedure) || p.atModuleEndBoundary()
}

func (p *Parser) atStatementBoundary() bool {
	return p.at(token.Return) || p.at(token.Check) || p.at(token.Call) || p.at(token.Let) || p.at(token.If) || p.at(token.While) || p.at(token.Case) || p.at(token.Ident)
}

func (p *Parser) atModuleEndBoundary() bool {
	if !p.at(token.End) || p.moduleName == "" {
		return false
	}

	pos := p.pos + 1
	if pos >= len(p.tokens) || p.tokens[pos].Kind != token.Ident {
		return false
	}

	name := p.tokens[pos].Lexeme
	pos++
	for pos+1 < len(p.tokens) && p.tokens[pos].Kind == token.Dot && p.tokens[pos+1].Kind == token.Ident {
		name += "." + p.tokens[pos+1].Lexeme
		pos += 2
	}

	return name == p.moduleName
}
