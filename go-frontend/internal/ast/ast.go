package ast

type Module struct {
	Kind         string `json:"kind"`
	Name         string `json:"name"`
	Declarations []Decl `json:"declarations"`
	EndName      string `json:"end_name"`
}

type Decl interface{}

type ImportDecl struct {
	Kind     string   `json:"kind"`
	Module   string   `json:"module"`
	Exposing []string `json:"exposing,omitempty"`
}

type TypeDecl struct {
	Kind   string     `json:"kind"`
	Name   string     `json:"name"`
	Base   string     `json:"base"`
	Range  *TypeRange `json:"range,omitempty"`
	Fields []Param    `json:"fields,omitempty"`
}

type TypeRange struct {
	Min string `json:"min"`
	Max string `json:"max"`
}

type ErrorDecl struct {
	Kind string `json:"kind"`
	Name string `json:"name"`
}

type FunctionDecl struct {
	Kind       string  `json:"kind"`
	Name       string  `json:"name"`
	Params     []Param `json:"params"`
	ReturnType string  `json:"return_type"`
	Requires   []Expr  `json:"requires,omitempty"`
	Ensures    []Expr  `json:"ensures,omitempty"`
	Body       []Stmt  `json:"body"`
	EndName    string  `json:"end_name"`
}

type ProcedureDecl struct {
	Kind     string  `json:"kind"`
	Name     string  `json:"name"`
	Params   []Param `json:"params"`
	Requires []Expr  `json:"requires,omitempty"`
	Ensures  []Expr  `json:"ensures,omitempty"`
	Body     []Stmt  `json:"body"`
	EndName  string  `json:"end_name"`
}

type Param struct {
	Name string `json:"name"`
	Type string `json:"type"`
}

type Stmt interface{}

type ReturnStmt struct {
	Kind  string `json:"kind"`
	Value Expr   `json:"value"`
}

type CheckStmt struct {
	Kind      string `json:"kind"`
	Condition Expr   `json:"condition"`
}

type LetStmt struct {
	Kind  string `json:"kind"`
	Name  string `json:"name"`
	Type  string `json:"type"`
	Value Expr   `json:"value"`
}

type AssignmentStmt struct {
	Kind   string `json:"kind"`
	Target Expr   `json:"target"`
	Value  Expr   `json:"value"`
}

type CallStmt struct {
	Kind string `json:"kind"`
	Call Expr   `json:"call"`
}

type IfStmt struct {
	Kind      string `json:"kind"`
	Condition Expr   `json:"condition"`
	ThenBody  []Stmt `json:"then_body"`
	ElseBody  []Stmt `json:"else_body,omitempty"`
}

type WhileStmt struct {
	Kind       string `json:"kind"`
	Condition  Expr   `json:"condition"`
	Invariants []Expr `json:"invariants,omitempty"`
	Variant    Expr   `json:"variant,omitempty"`
	Body       []Stmt `json:"body"`
}

type CaseStmt struct {
	Kind    string       `json:"kind"`
	Value   Expr         `json:"value"`
	When    []CaseBranch `json:"when"`
	Default []Stmt       `json:"default,omitempty"`
}

type CaseBranch struct {
	Value Expr   `json:"value"`
	Body  []Stmt `json:"body"`
}

type Expr interface{}

type IdentifierExpr struct {
	Kind string `json:"kind"`
	Name string `json:"name"`
}

type FieldAccessExpr struct {
	Kind   string `json:"kind"`
	Object Expr   `json:"object"`
	Field  string `json:"field"`
}

type IndexExpr struct {
	Kind  string `json:"kind"`
	Array Expr   `json:"array"`
	Index Expr   `json:"index"`
}

type ArrayLiteralExpr struct {
	Kind     string `json:"kind"`
	Elements []Expr `json:"elements"`
}

type CallExpr struct {
	Kind      string `json:"kind"`
	Callee    Expr   `json:"callee"`
	Arguments []Expr `json:"arguments"`
}

type NamedArgumentExpr struct {
	Kind  string `json:"kind"`
	Name  string `json:"name"`
	Value Expr   `json:"value"`
}

type RecordLiteralExpr struct {
	Kind   string        `json:"kind"`
	Type   string        `json:"type"`
	Fields []RecordField `json:"fields"`
}

type RecordField struct {
	Name  string `json:"name"`
	Value Expr   `json:"value"`
}

type NumberExpr struct {
	Kind  string `json:"kind"`
	Value string `json:"value"`
}

type StringExpr struct {
	Kind  string `json:"kind"`
	Value string `json:"value"`
}

type OkExpr struct {
	Kind  string `json:"kind"`
	Value Expr   `json:"value"`
}

type ErrorExpr struct {
	Kind string `json:"kind"`
	Name string `json:"name"`
}

type UnaryExpr struct {
	Kind  string `json:"kind"`
	Op    string `json:"op"`
	Value Expr   `json:"value"`
}

type BinaryExpr struct {
	Kind  string `json:"kind"`
	Op    string `json:"op"`
	Left  Expr   `json:"left"`
	Right Expr   `json:"right"`
}
