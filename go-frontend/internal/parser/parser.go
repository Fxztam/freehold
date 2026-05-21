package parser

import (
	"fmt"

	"freehold-go-frontend/internal/ast"
	"freehold-go-frontend/internal/token"
)

type Parser struct {
	tokens []token.Token
	pos    int
}

func New(tokens []token.Token) *Parser {
	return &Parser{tokens: tokens}
}

func (p *Parser) ParseModule() (*ast.Module, error) {
	p.expect(token.Module)

	name := p.parseQualifiedName()

	var decls []ast.Decl

	for !p.at(token.End) && !p.at(token.EOF) {
		if p.at(token.Type) {
			decls = append(decls, p.parseTypeDecl())
		} else if p.at(token.Error) {
			decls = append(decls, p.parseErrorDecl())
		} else if p.at(token.Import) {
			decls = append(decls, p.parseImport())
		} else if p.at(token.Function) {
			fn := p.parseFunction()
			decls = append(decls, fn)
		} else if p.at(token.Procedure) {
			proc := p.parseProcedure()
			decls = append(decls, proc)
		} else {
			return nil, fmt.Errorf(
				"expected declaration, got %s %q at line %d col %d",
				p.peek().Kind,
				p.peek().Lexeme,
				p.peek().Pos.Line,
				p.peek().Pos.Column,
			)
		}
	}

	p.expect(token.End)
	endName := p.parseQualifiedName()

	return &ast.Module{
		Kind:         "Module",
		Name:         name,
		Declarations: decls,
		EndName:      endName,
	}, nil
}

func (p *Parser) parseTypeDecl() ast.TypeDecl {
	p.expect(token.Type)

	name := p.parseName()
	p.expect(token.Is)

	if p.at(token.Record) {
		return p.parseRecordTypeDecl(name)
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
		Kind:  "TypeDecl",
		Name:  name,
		Base:  base,
		Range: typeRange,
	}
}

func (p *Parser) parseRecordTypeDecl(name string) ast.TypeDecl {
	p.expect(token.Record)

	var fields []ast.Param
	for !p.at(token.End) && !p.at(token.EOF) {
		fields = append(fields, p.parseParam())
	}

	p.expect(token.End)
	p.expect(token.Record)

	return ast.TypeDecl{
		Kind:   "TypeDecl",
		Name:   name,
		Base:   "record",
		Fields: fields,
	}
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
	if tok.Kind == token.Ident || isKeywordName(tok.Kind) {
		p.pos++
		return tok.Lexeme
	}

	panic(fmt.Sprintf(
		"expected Ident, got %s %q at line %d col %d",
		tok.Kind,
		tok.Lexeme,
		tok.Pos.Line,
		tok.Pos.Column,
	))
}

func isKeywordName(kind token.Kind) bool {
	switch kind {
	case token.Module,
		token.Procedure,
		token.Function,
		token.Type,
		token.Error,
		token.Returns,
		token.Is,
		token.Return,
		token.Check,
		token.Call,
		token.Let,
		token.Import,
		token.Exposing,
		token.Range,
		token.Record,
		token.If,
		token.Then,
		token.Else,
		token.While,
		token.Invariant,
		token.Variant,
		token.Do,
		token.Case,
		token.When,
		token.Default,
		token.And,
		token.Or,
		token.Not,
		token.Ok,
		token.Requires,
		token.Ensures:
		return true
	default:
		return false
	}
}

func (p *Parser) parseFunction() ast.FunctionDecl {
	p.expect(token.Function)

	name := p.parseName()

	p.expect(token.LParen)
	params := p.parseParams()
	p.expect(token.RParen)

	p.expect(token.Returns)
	returnType := p.parseTypeName()

	requires, ensures := p.parseContracts()

	p.expect(token.Is)

	body := p.parseStatements(func() bool { return p.at(token.End) || p.at(token.EOF) })

	p.expect(token.End)
	endName := p.parseName()

	return ast.FunctionDecl{
		Kind:       "FunctionDecl",
		Name:       name,
		Params:     params,
		ReturnType: returnType,
		Requires:   requires,
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

	requires, ensures := p.parseContracts()

	p.expect(token.Is)

	body := p.parseStatements(func() bool { return p.at(token.End) || p.at(token.EOF) })

	p.expect(token.End)
	endName := p.parseName()

	return ast.ProcedureDecl{
		Kind:     "ProcedureDecl",
		Name:     name,
		Params:   params,
		Requires: requires,
		Ensures:  ensures,
		Body:     body,
		EndName:  endName,
	}
}

func (p *Parser) parseContracts() ([]ast.Expr, []ast.Expr) {
	var requires []ast.Expr
	var ensures []ast.Expr

	for p.at(token.Requires) {
		p.expect(token.Requires)
		requires = append(requires, p.parseExpr())
	}

	for p.at(token.Ensures) {
		p.expect(token.Ensures)
		ensures = append(ensures, p.parseExpr())
	}

	return requires, ensures
}

func (p *Parser) parseStatements(stop func() bool) []ast.Stmt {
	var body []ast.Stmt

	for !stop() {
		body = append(body, p.parseStatement())
	}

	return body
}

func (p *Parser) parseStatement() ast.Stmt {
	if p.at(token.Return) {
		return p.parseReturn()
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
	panic(fmt.Sprintf(
		"expected statement, got %s %q at line %d col %d",
		tok.Kind,
		tok.Lexeme,
		tok.Pos.Line,
		tok.Pos.Column,
	))
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
	panic(fmt.Sprintf(
		"expected assignment or call statement, got %s %q at line %d col %d",
		tok.Kind,
		tok.Lexeme,
		tok.Pos.Line,
		tok.Pos.Column,
	))
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

	p.expect(token.End)
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
		panic(fmt.Sprintf(
			"expected invariant, got %s %q at line %d col %d",
			tok.Kind,
			tok.Lexeme,
			tok.Pos.Line,
			tok.Pos.Column,
		))
	}

	var variant ast.Expr
	if p.at(token.Variant) {
		p.expect(token.Variant)
		variant = p.parseExpr()
	}

	p.expect(token.Do)
	body := p.parseStatements(func() bool { return p.at(token.End) || p.at(token.EOF) })
	p.expect(token.End)
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
		panic(fmt.Sprintf(
			"expected default, got %s %q at line %d col %d",
			tok.Kind,
			tok.Lexeme,
			tok.Pos.Line,
			tok.Pos.Column,
		))
	}

	p.expect(token.End)
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
	p.expect(token.LParen)

	var args []ast.Expr
	if !p.at(token.RParen) {
		args = append(args, p.parseExpr())

		for p.at(token.Comma) {
			p.expect(token.Comma)
			args = append(args, p.parseExpr())
		}
	}

	p.expect(token.RParen)

	return ast.CallExpr{
		Kind:      "CallExpr",
		Callee:    callee,
		Arguments: args,
	}
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
	panic(fmt.Sprintf(
		"expected number, got %s %q at line %d col %d",
		tok.Kind,
		tok.Lexeme,
		tok.Pos.Line,
		tok.Pos.Column,
	))
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

func (p *Parser) expect(kind token.Kind) token.Token {
	tok := p.peek()

	if tok.Kind != kind {
		panic(fmt.Sprintf(
			"expected %s, got %s %q at line %d col %d",
			kind,
			tok.Kind,
			tok.Lexeme,
			tok.Pos.Line,
			tok.Pos.Column,
		))
	}

	p.pos++
	return tok
}
