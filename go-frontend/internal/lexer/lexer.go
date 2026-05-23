package lexer

import (
	"unicode"

	"freehold-go-frontend/internal/token"
)

type Lexer struct {
	input  []rune
	pos    int
	line   int
	column int
}

func New(src string) *Lexer {
	return &Lexer{
		input:  []rune(src),
		line:   1,
		column: 1,
	}
}

func (l *Lexer) eof() bool {
	return l.pos >= len(l.input)
}

func (l *Lexer) peek() rune {
	if l.eof() {
		return 0
	}
	return l.input[l.pos]
}

func (l *Lexer) peekNext() rune {
	if l.pos+1 >= len(l.input) {
		return 0
	}
	return l.input[l.pos+1]
}

func (l *Lexer) advance() rune {
	r := l.peek()
	l.pos++

	if r == '\n' {
		l.line++
		l.column = 1
	} else {
		l.column++
	}

	return r
}

func (l *Lexer) skipIgnored() *token.Token {
	for !l.eof() {
		if unicode.IsSpace(l.peek()) {
			l.advance()
			continue
		}

		if l.peek() == '-' && l.peekNext() == '-' {
			for !l.eof() && l.peek() != '\n' {
				l.advance()
			}
			continue
		}

		if l.peek() == '/' && l.peekNext() == '*' {
			start := token.Position{Line: l.line, Column: l.column, Offset: l.pos}
			l.advance()
			l.advance()

			for !l.eof() {
				if l.peek() == '*' && l.peekNext() == '/' {
					l.advance()
					l.advance()
					start = token.Position{}
					break
				}
				l.advance()
			}

			if start.Line != 0 {
				return &token.Token{
					Kind:   token.Illegal,
					Lexeme: "unterminated block comment",
					Pos:    start,
				}
			}
			continue
		}

		return nil
	}

	return nil
}

func (l *Lexer) Next() token.Token {
	if tok := l.skipIgnored(); tok != nil {
		return *tok
	}

	start := token.Position{
		Line:   l.line,
		Column: l.column,
		Offset: l.pos,
	}

	if l.eof() {
		return token.Token{
			Kind: token.EOF,
			Pos:  start,
		}
	}

	r := l.peek()

	if isIdentifierStart(r) {
		return l.lexIdentifier(start)
	}

	if unicode.IsDigit(r) {
		return l.lexNumber(start)
	}

	if r == '"' {
		return l.lexString(start)
	}

	switch r {
	case '!':
		if l.peekNext() == '=' {
			l.advance()
			l.advance()
			return token.Token{
				Kind:   token.NotEqual,
				Lexeme: "!=",
				Pos:    start,
			}
		}

	case '+':
		l.advance()
		return token.Token{
			Kind:   token.Plus,
			Lexeme: "+",
			Pos:    start,
		}

	case '-':
		l.advance()
		return token.Token{
			Kind:   token.Minus,
			Lexeme: "-",
			Pos:    start,
		}

	case '*':
		l.advance()
		return token.Token{
			Kind:   token.Star,
			Lexeme: "*",
			Pos:    start,
		}

	case '=':
		if l.peekNext() == '>' {
			l.advance()
			l.advance()
			return token.Token{
				Kind:   token.Arrow,
				Lexeme: "=>",
				Pos:    start,
			}
		}

		l.advance()
		return token.Token{
			Kind:   token.Equal,
			Lexeme: "=",
			Pos:    start,
		}

	case '<':
		if l.peekNext() == '=' {
			l.advance()
			l.advance()
			return token.Token{
				Kind:   token.LessEqual,
				Lexeme: "<=",
				Pos:    start,
			}
		}

		l.advance()
		return token.Token{
			Kind:   token.Less,
			Lexeme: "<",
			Pos:    start,
		}

	case '>':
		if l.peekNext() == '=' {
			l.advance()
			l.advance()
			return token.Token{
				Kind:   token.GreaterEqual,
				Lexeme: ">=",
				Pos:    start,
			}
		}

		l.advance()
		return token.Token{
			Kind:   token.Greater,
			Lexeme: ">",
			Pos:    start,
		}

	case '.':
		if l.peekNext() == '.' {
			l.advance()
			l.advance()
			return token.Token{
				Kind:   token.DotDot,
				Lexeme: "..",
				Pos:    start,
			}
		}

		l.advance()
		return token.Token{
			Kind:   token.Dot,
			Lexeme: ".",
			Pos:    start,
		}

	case '(':
		l.advance()
		return token.Token{
			Kind:   token.LParen,
			Lexeme: "(",
			Pos:    start,
		}

	case ')':
		l.advance()
		return token.Token{
			Kind:   token.RParen,
			Lexeme: ")",
			Pos:    start,
		}

	case ':':
		if l.peekNext() == '=' {
			l.advance()
			l.advance()
			return token.Token{
				Kind:   token.Assign,
				Lexeme: ":=",
				Pos:    start,
			}
		}

		l.advance()
		return token.Token{
			Kind:   token.Colon,
			Lexeme: ":",
			Pos:    start,
		}

	case ',':
		l.advance()
		return token.Token{
			Kind:   token.Comma,
			Lexeme: ",",
			Pos:    start,
		}

	case '{':
		l.advance()
		return token.Token{
			Kind:   token.LBrace,
			Lexeme: "{",
			Pos:    start,
		}

	case '}':
		l.advance()
		return token.Token{
			Kind:   token.RBrace,
			Lexeme: "}",
			Pos:    start,
		}

	case '[':
		l.advance()
		return token.Token{
			Kind:   token.LBracket,
			Lexeme: "[",
			Pos:    start,
		}

	case ']':
		l.advance()
		return token.Token{
			Kind:   token.RBracket,
			Lexeme: "]",
			Pos:    start,
		}
	}

	l.advance()

	return token.Token{
		Kind:   token.Illegal,
		Lexeme: string(r),
		Pos:    start,
	}
}

func (l *Lexer) lexString(pos token.Position) token.Token {
	l.advance()
	start := l.pos

	for !l.eof() && l.peek() != '"' && l.peek() != '\n' {
		l.advance()
	}

	lexeme := string(l.input[start:l.pos])

	if !l.eof() && l.peek() == '"' {
		l.advance()
		return token.Token{
			Kind:   token.String,
			Lexeme: lexeme,
			Pos:    pos,
		}
	}

	return token.Token{
		Kind:   token.Illegal,
		Lexeme: "unterminated string",
		Pos:    pos,
	}
}

func (l *Lexer) lexNumber(pos token.Position) token.Token {
	start := l.pos

	for !l.eof() && unicode.IsDigit(l.peek()) {
		l.advance()
	}

	kind := token.Int

	if !l.eof() && l.peek() == '.' && unicode.IsDigit(l.peekNext()) {
		kind = token.Float
		l.advance()

		for !l.eof() && unicode.IsDigit(l.peek()) {
			l.advance()
		}
	}

	if !l.eof() && l.peek() == '.' && l.peekNext() != '.' {
		for !l.eof() && (unicode.IsDigit(l.peek()) || l.peek() == '.') {
			l.advance()
		}
		return token.Token{
			Kind:   token.Illegal,
			Lexeme: "invalid number literal",
			Pos:    pos,
		}
	}

	return token.Token{
		Kind:   kind,
		Lexeme: string(l.input[start:l.pos]),
		Pos:    pos,
	}
}

func (l *Lexer) lexIdentifier(pos token.Position) token.Token {
	start := l.pos

	for !l.eof() &&
		isIdentifierPart(l.peek()) {
		l.advance()
	}

	lexeme := string(l.input[start:l.pos])

	kind := token.Ident

	switch lexeme {
	case "module":
		kind = token.Module
	case "procedure":
		kind = token.Procedure
	case "function":
		kind = token.Function
	case "type":
		kind = token.Type
	case "error":
		kind = token.Error
	case "returns":
		kind = token.Returns
	case "is":
		kind = token.Is
	case "return":
		kind = token.Return
	case "check":
		kind = token.Check
	case "call":
		kind = token.Call
	case "let":
		kind = token.Let
	case "import":
		kind = token.Import
	case "exposing":
		kind = token.Exposing
	case "range":
		kind = token.Range
	case "record":
		kind = token.Record
	case "if":
		kind = token.If
	case "then":
		kind = token.Then
	case "else":
		kind = token.Else
	case "while":
		kind = token.While
	case "invariant":
		kind = token.Invariant
	case "variant":
		kind = token.Variant
	case "do":
		kind = token.Do
	case "case":
		kind = token.Case
	case "when":
		kind = token.When
	case "default":
		kind = token.Default
	case "and":
		kind = token.And
	case "or":
		kind = token.Or
	case "not":
		kind = token.Not
	case "ok":
		kind = token.Ok
	case "requires":
		kind = token.Requires
	case "ensures":
		kind = token.Ensures
	case "true":
		kind = token.True
	case "false":
		kind = token.False
	case "success":
		kind = token.Success
	case "failure":
		kind = token.Failure
	case "value":
		kind = token.Value
	case "end":
		kind = token.End
	}

	return token.Token{
		Kind:   kind,
		Lexeme: lexeme,
		Pos:    pos,
	}
}

func isIdentifierStart(r rune) bool {
	return unicode.IsLetter(r) || r == '_'
}

func isIdentifierPart(r rune) bool {
	return unicode.IsLetter(r) || unicode.IsDigit(r) || r == '_'
}
