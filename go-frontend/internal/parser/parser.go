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

	p.expect(token.Module)

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
	if p.at(token.Import) {
		return p.parseImport()
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
	p.expect(token.Type)

	name := p.parseName()
	typeParams := p.parseOptionalTypeParams()
	p.expect(token.Is)

	if p.at(token.Record) {
		return p.parseRecordTypeDecl(name, typeParams)
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
		Name:       name,
		TypeParams: typeParams,
		Base:       base,
		Range:      typeRange,
	}
}

func (p *Parser) parseRecordTypeDecl(name string, typeParams []string) ast.TypeDecl {
	p.expect(token.Record)

	var fields []ast.Param
	for !p.at(token.End) && !p.at(token.EOF) {
		fields = append(fields, p.parseParam())
	}

	p.expect(token.End)
	p.expect(token.Record)

	return ast.TypeDecl{
		Kind:       "TypeDecl",
		Name:       name,
		TypeParams: typeParams,
		Base:       "record",
		Fields:     fields,
	}
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
	p.expect(token.Error)

	return ast.ErrorDecl{
		Kind: "ErrorDecl",
		Name: p.parseName(),
	}
}

func (p *Parser) parseImport() ast.ImportDecl {
	p.expect(token.Import)

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
		Module:   moduleName,
		Exposing: exposing,
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
	tok := p.peek()
	if tok.Kind == token.Ident {
		p.pos++
		return tok.Lexeme
	}

	panic(diagnostic.ExpectedIdentifier(tok))
}

func (p *Parser) parseFunction() ast.FunctionDecl {
	p.expect(token.Function)

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
		Name:       name,
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
	p.expect(token.Procedure)

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
	clause := ast.AbortClause{Error: p.parseName()}
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
	if p.at(token.Ident) {
		return p.parseIdentStatement()
	}

	tok := p.peek()
	panic(diagnostic.ExpectedStatement(tok))
}

func (p *Parser) parseAbort() ast.AbortStmt {
	p.expect(token.Abort)

	return ast.AbortStmt{
		Kind:  "AbortStmt",
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
	name := p.parseName()
	if !p.at(token.Colon) {
		panic(diagnostic.ExpectedParameterColon(p.peek()))
	}
	p.expect(token.Colon)
	typ := p.parseTypeName()

	return ast.Param{
		Name: name,
		Type: typ,
	}
}

func (p *Parser) parseReturn() ast.ReturnStmt {
	p.expect(token.Return)

	return ast.ReturnStmt{
		Kind:  "ReturnStmt",
		Value: p.parseExpr(),
	}
}

func (p *Parser) parseCheck() ast.CheckStmt {
	p.expect(token.Check)

	return ast.CheckStmt{
		Kind:      "CheckStmt",
		Condition: p.parseExpr(),
	}
}

func (p *Parser) parseLet() ast.LetStmt {
	p.expect(token.Let)

	name := p.parseName()
	p.expect(token.Colon)
	typ := p.parseTypeName()
	p.expect(token.Equal)

	return ast.LetStmt{
		Kind:  "LetStmt",
		Name:  name,
		Type:  typ,
		Value: p.parseExpr(),
	}
}

func (p *Parser) parseCallStmt() ast.CallStmt {
	p.expect(token.Call)

	return ast.CallStmt{
		Kind: "CallStmt",
		Call: p.parseAtom(),
	}
}

func (p *Parser) parseIdentStatement() ast.Stmt {
	target := p.parseAtom()

	if p.at(token.Assign) {
		p.expect(token.Assign)
		return ast.AssignmentStmt{
			Kind:   "AssignmentStmt",
			Target: target,
			Value:  p.parseExpr(),
		}
	}

	if call, ok := target.(ast.CallExpr); ok {
		return ast.CallStmt{
			Kind: "CallStmt",
			Call: call,
		}
	}

	tok := p.peek()
	panic(diagnostic.ExpectedAssignmentOrCall(tok))
}

func (p *Parser) parseIf() ast.IfStmt {
	p.expect(token.If)
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
		Condition: condition,
		ThenBody:  thenBody,
		ElseBody:  elseBody,
	}
}

func (p *Parser) parseWhile() ast.WhileStmt {
	p.expect(token.While)
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
		Condition:  condition,
		Invariants: invariants,
		Variant:    variant,
		Body:       body,
	}
}

func (p *Parser) parseCase() ast.CaseStmt {
	p.expect(token.Case)
	value := p.parseExpr()
	p.expect(token.Is)

	var branches []ast.CaseBranch
	for p.at(token.When) {
		p.expect(token.When)
		branchValue := p.parseExpr()
		p.expect(token.Arrow)
		branchBody := p.parseStatements(func() bool {
			return p.at(token.When) || p.at(token.Default) || p.at(token.End) || p.at(token.EOF)
		})
		branches = append(branches, ast.CaseBranch{Value: branchValue, Body: branchBody})
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
		Value:   value,
		When:    branches,
		Default: defaultBody,
	}
}

func (p *Parser) parseAssignment() ast.AssignmentStmt {
	target := p.parseFieldAccess()
	p.expect(token.Assign)

	return ast.AssignmentStmt{
		Kind:   "AssignmentStmt",
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
		left = ast.BinaryExpr{Kind: "BinaryExpr", Op: op, Left: left, Right: right}
	}

	return left
}

func (p *Parser) parseAnd() ast.Expr {
	left := p.parseComparison()

	for p.at(token.And) {
		op := p.expect(token.And).Lexeme
		right := p.parseComparison()
		left = ast.BinaryExpr{Kind: "BinaryExpr", Op: op, Left: left, Right: right}
	}

	return left
}

func (p *Parser) parseComparison() ast.Expr {
	left := p.parseSum()

	for p.at(token.Equal) || p.at(token.NotEqual) || p.at(token.Less) || p.at(token.LessEqual) || p.at(token.Greater) || p.at(token.GreaterEqual) {
		tok := p.peek()
		p.pos++
		right := p.parseSum()
		left = ast.BinaryExpr{Kind: "BinaryExpr", Op: tok.Lexeme, Left: left, Right: right}
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
			Op:    tok.Lexeme,
			Left:  left,
			Right: right,
		}
	}

	return left
}

func (p *Parser) parseProduct() ast.Expr {
	left := p.parseUnary()

	for p.at(token.Star) {
		op := p.expect(token.Star).Lexeme
		right := p.parseUnary()

		left = ast.BinaryExpr{
			Kind:  "BinaryExpr",
			Op:    op,
			Left:  left,
			Right: right,
		}
	}

	return left
}

func (p *Parser) parseUnary() ast.Expr {
	if p.at(token.Not) || p.at(token.Minus) {
		tok := p.peek()
		p.pos++
		return ast.UnaryExpr{
			Kind:  "UnaryExpr",
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
		p.expect(token.Ok)
		return ast.OkExpr{
			Kind:  "OkExpr",
			Value: p.parseExpr(),
		}
	}

	if p.at(token.Error) {
		p.expect(token.Error)
		if !p.at(token.Ident) {
			return p.finishPostfix(ast.IdentifierExpr{
				Kind: "IdentifierExpr",
				Name: "error",
			})
		}
		return ast.ErrorExpr{
			Kind: "ErrorExpr",
			Name: p.parseName(),
		}
	}

	if p.at(token.True) || p.at(token.False) || p.at(token.Success) || p.at(token.Failure) || p.at(token.Value) {
		tok := p.peek()
		p.pos++
		return p.finishPostfix(ast.IdentifierExpr{
			Kind: "IdentifierExpr",
			Name: tok.Lexeme,
		})
	}

	if !p.at(token.Ident) {
		panic(diagnostic.ExpectedExpression(p.peek()))
	}

	if p.genericFunctionCallAhead() {
		name := p.parseName()
		typeArgs := p.parseTypeArgs()
		callee := ast.IdentifierExpr{Kind: "IdentifierExpr", Name: name}
		return p.finishCallWithTypeArgs(callee, typeArgs)
	}

	if p.genericRecordLiteralAhead() {
		typeName := p.parseTypeName()
		return p.parseRecordLiteral(typeName)
	}

	tok := p.parseName()

	if p.at(token.LBrace) {
		return p.parseRecordLiteral(tok)
	}

	expr := ast.Expr(ast.IdentifierExpr{
		Kind: "IdentifierExpr",
		Name: tok,
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
	for p.at(token.Dot) || p.at(token.LBracket) || p.at(token.LParen) {
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
				Array: expr,
				Index: index,
			}
			continue
		}

		p.expect(token.Dot)
		expr = ast.FieldAccessExpr{
			Kind:   "FieldAccessExpr",
			Object: expr,
			Field:  p.parseName(),
		}
	}

	return expr
}

func (p *Parser) parseFieldAccess() ast.Expr {
	expr := ast.Expr(ast.IdentifierExpr{
		Kind: "IdentifierExpr",
		Name: p.parseName(),
	})

	for p.at(token.Dot) || p.at(token.LBracket) || p.at(token.LParen) {
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
				Array: expr,
				Index: index,
			}
			continue
		}

		p.expect(token.Dot)
		expr = ast.FieldAccessExpr{
			Kind:   "FieldAccessExpr",
			Object: expr,
			Field:  p.parseName(),
		}
	}

	return expr
}

func (p *Parser) finishCall(callee ast.Expr) ast.CallExpr {
	return p.finishCallWithTypeArgs(callee, nil)
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
		name := p.parseName()
		p.expect(token.Colon)
		return ast.NamedArgumentExpr{
			Kind:  "NamedArgumentExpr",
			Name:  name,
			Value: p.parseExpr(),
		}
	}
	return p.parseExpr()
}

func (p *Parser) parseArrayLiteral() ast.ArrayLiteralExpr {
	p.expect(token.LBracket)

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
		Elements: elements,
	}
}

func (p *Parser) parseRecordLiteral(typeName string) ast.RecordLiteralExpr {
	p.expect(token.LBrace)

	var fields []ast.RecordField
	if !p.at(token.RBrace) {
		fields = append(fields, p.parseRecordField())

		for p.at(token.Comma) {
			p.expect(token.Comma)
			fields = append(fields, p.parseRecordField())
		}
	}

	p.expect(token.RBrace)

	return ast.RecordLiteralExpr{
		Kind:   "RecordLiteralExpr",
		Type:   typeName,
		Fields: fields,
	}
}

func (p *Parser) parseRecordField() ast.RecordField {
	name := p.parseName()
	p.expect(token.Colon)

	return ast.RecordField{
		Name:  name,
		Value: p.parseExpr(),
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
	return p.at(token.Import) || p.at(token.Type) || p.at(token.Error) || p.at(token.Function) || p.at(token.Procedure) || p.atModuleEndBoundary()
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
