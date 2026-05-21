package token

type Kind string

const (
	Illegal Kind = "Illegal"
	EOF     Kind = "EOF"

	Ident  Kind = "Ident"
	Int    Kind = "Int"
	Float  Kind = "Float"
	String Kind = "String"

	Module    Kind = "module"
	Procedure Kind = "procedure"
	Function  Kind = "function"
	Type      Kind = "type"
	Error     Kind = "error"
	End       Kind = "end"
	Returns   Kind = "returns"
	Is        Kind = "is"
	Return    Kind = "return"
	Check     Kind = "check"
	Call      Kind = "call"
	Let       Kind = "let"
	Import    Kind = "import"
	Exposing  Kind = "exposing"
	Range     Kind = "range"
	Record    Kind = "record"
	If        Kind = "if"
	Then      Kind = "then"
	Else      Kind = "else"
	While     Kind = "while"
	Invariant Kind = "invariant"
	Variant   Kind = "variant"
	Do        Kind = "do"
	Case      Kind = "case"
	When      Kind = "when"
	Default   Kind = "default"
	And       Kind = "and"
	Or        Kind = "or"
	Not       Kind = "not"
	Ok        Kind = "ok"
	Requires  Kind = "requires"
	Ensures   Kind = "ensures"
	True      Kind = "true"
	False     Kind = "false"
	Success   Kind = "success"
	Failure   Kind = "failure"
	Value     Kind = "value"

	Plus         Kind = "+"
	Minus        Kind = "-"
	Star         Kind = "*"
	Equal        Kind = "="
	NotEqual     Kind = "!="
	Assign       Kind = ":="
	Less         Kind = "<"
	LessEqual    Kind = "<="
	Greater      Kind = ">"
	GreaterEqual Kind = ">="
	Arrow        Kind = "=>"
	Dot          Kind = "."
	DotDot       Kind = ".."
	Colon        Kind = ":"
	Comma        Kind = ","
	LParen       Kind = "("
	RParen       Kind = ")"
	LBrace       Kind = "{"
	RBrace       Kind = "}"
	LBracket     Kind = "["
	RBracket     Kind = "]"
)

type Position struct {
	Line   int
	Column int
	Offset int
}

type Token struct {
	Kind   Kind
	Lexeme string
	Pos    Position
}
