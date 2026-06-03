package ast

import "freehold-go-frontend/internal/token"

type Module struct {
	Kind          string                        `json:"kind"`
	Pos           token.Position                `json:"-"`
	Name          string                        `json:"name"`
	Declarations  []Decl                        `json:"declarations"`
	EndName       string                        `json:"end_name"`
	FlowSummaries map[string]RoutineFlowSummary `json:"flow_summaries,omitempty"`
}

type Decl interface{}

type ImportDecl struct {
	Kind     string         `json:"kind"`
	Pos      token.Position `json:"-"`
	Module   string         `json:"module"`
	Exposing []string       `json:"exposing,omitempty"`
}

type TypeDecl struct {
	Kind       string         `json:"kind"`
	Pos        token.Position `json:"-"`
	Name       string         `json:"name"`
	TypeParams []string       `json:"type_params,omitempty"`
	Base       string         `json:"base"`
	Range      *TypeRange     `json:"range,omitempty"`
	Fields     []Param        `json:"fields,omitempty"`
}

type TypeRange struct {
	Min string `json:"min"`
	Max string `json:"max"`
}

type ErrorDecl struct {
	Kind string         `json:"kind"`
	Pos  token.Position `json:"-"`
	Name string         `json:"name"`
}

type FunctionDecl struct {
	Kind        string         `json:"kind"`
	Pos         token.Position `json:"-"`
	Name        string         `json:"name"`
	IsAsync     bool           `json:"is_async,omitempty"`
	TypeParams  []string       `json:"type_params,omitempty"`
	Params      []Param        `json:"params"`
	ReturnType   string         `json:"return_type"`
	GlobalSpecs  []GlobalSpec   `json:"global_specs,omitempty"`
	DependsSpecs []DependsSpec  `json:"depends_specs,omitempty"`
	Requires     []Expr         `json:"requires,omitempty"`
	Aborts       []AbortClause  `json:"aborts,omitempty"`
	Ensures      []Expr         `json:"ensures,omitempty"`
	Body         []Stmt         `json:"body"`
	EndName      string         `json:"end_name"`
}

type ProcedureDecl struct {
	Kind         string         `json:"kind"`
	Pos          token.Position `json:"-"`
	Name         string         `json:"name"`
	Params       []Param        `json:"params"`
	GlobalSpecs  []GlobalSpec   `json:"global_specs,omitempty"`
	DependsSpecs []DependsSpec  `json:"depends_specs,omitempty"`
	Requires     []Expr         `json:"requires,omitempty"`
	Aborts       []AbortClause  `json:"aborts,omitempty"`
	Ensures      []Expr         `json:"ensures,omitempty"`
	Body         []Stmt         `json:"body"`
	EndName      string         `json:"end_name"`
}

type AbortClause struct {
	Pos       token.Position `json:"-"`
	Error     string         `json:"error"`
	Condition Expr           `json:"condition,omitempty"`
}

type Param struct {
	Pos     token.Position `json:"-"`
	Name    string         `json:"name"`
	Type    string         `json:"type"`
	ProtoID *int           `json:"proto_id,omitempty"`
}

type ServiceDecl struct {
	Kind    string         `json:"kind"`
	Pos     token.Position `json:"-"`
	Name    string         `json:"name"`
	Rpcs    []RpcDecl      `json:"rpcs"`
	EndName string         `json:"end_name"`
}

type RpcDecl struct {
	Kind           string         `json:"kind"`
	Pos            token.Position `json:"-"`
	Name           string         `json:"name"`
	RequestName    string         `json:"request_name"`
	RequestType    string         `json:"request_type"`
	ResponseType   string         `json:"response_type"`
	RequestStream  bool           `json:"request_stream"`
	ResponseStream bool           `json:"response_stream"`
}

type Stmt interface{}

type ReturnStmt struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Value Expr           `json:"value"`
}

type AbortStmt struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Error string         `json:"error"`
}

type CheckStmt struct {
	Kind      string         `json:"kind"`
	Pos       token.Position `json:"-"`
	Condition Expr           `json:"condition"`
}

type LetStmt struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Name  string         `json:"name"`
	Type  string         `json:"type"`
	Value Expr           `json:"value"`
}

type AssignmentStmt struct {
	Kind   string         `json:"kind"`
	Pos    token.Position `json:"-"`
	Target Expr           `json:"target"`
	Value  Expr           `json:"value"`
}

type CallStmt struct {
	Kind string         `json:"kind"`
	Pos  token.Position `json:"-"`
	Call Expr           `json:"call"`
}

type IfStmt struct {
	Kind      string         `json:"kind"`
	Pos       token.Position `json:"-"`
	Condition Expr           `json:"condition"`
	ThenBody  []Stmt         `json:"then_body"`
	ElseBody  []Stmt         `json:"else_body,omitempty"`
}

type WhileStmt struct {
	Kind       string         `json:"kind"`
	Pos        token.Position `json:"-"`
	Condition  Expr           `json:"condition"`
	Invariants []Expr         `json:"invariants,omitempty"`
	Variant    Expr           `json:"variant,omitempty"`
	Body       []Stmt         `json:"body"`
}

type CaseStmt struct {
	Kind    string         `json:"kind"`
	Pos     token.Position `json:"-"`
	Value   Expr           `json:"value"`
	When    []CaseBranch   `json:"when"`
	Default []Stmt         `json:"default,omitempty"`
}

type ScopeStmt struct {
	Kind       string         `json:"kind"`
	Pos        token.Position `json:"-"`
	Name       string         `json:"name"`
	SpawnBody  []Stmt         `json:"spawn_body"`
	JoinBody   []Stmt         `json:"join_body"`
	ResultBody []Stmt         `json:"result_body"`
}

type CaseBranch struct {
	Pos   token.Position `json:"-"`
	Value Expr           `json:"value"`
	Body  []Stmt         `json:"body"`
}

type Expr interface{}

type IdentifierExpr struct {
	Kind string         `json:"kind"`
	Pos  token.Position `json:"-"`
	Name string         `json:"name"`
}

type FieldAccessExpr struct {
	Kind   string         `json:"kind"`
	Pos    token.Position `json:"-"`
	Object Expr           `json:"object"`
	Field  string         `json:"field"`
}

type IndexExpr struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Array Expr           `json:"array"`
	Index Expr           `json:"index"`
}

type ArrayLiteralExpr struct {
	Kind     string         `json:"kind"`
	Pos      token.Position `json:"-"`
	Elements []Expr         `json:"elements"`
}

type CallExpr struct {
	Kind      string         `json:"kind"`
	Pos       token.Position `json:"-"`
	Callee    Expr           `json:"callee"`
	TypeArgs  []string       `json:"type_args,omitempty"`
	Arguments []Expr         `json:"arguments"`
}

type AwaitExpr struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Value Expr           `json:"value"`
}

type NamedArgumentExpr struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Name  string         `json:"name"`
	Value Expr           `json:"value"`
}

type RecordLiteralExpr struct {
	Kind   string         `json:"kind"`
	Pos    token.Position `json:"-"`
	Type   string         `json:"type"`
	Fields []RecordField  `json:"fields"`
}

type RecordField struct {
	Pos   token.Position `json:"-"`
	Name  string         `json:"name"`
	Value Expr           `json:"value"`
}

type NumberExpr struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Value string         `json:"value"`
}

type StringExpr struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Value string         `json:"value"`
}

type OkExpr struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Value Expr           `json:"value"`
}

type ErrorExpr struct {
	Kind string         `json:"kind"`
	Pos  token.Position `json:"-"`
	Name string         `json:"name"`
}

type UnaryExpr struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Op    string         `json:"op"`
	Value Expr           `json:"value"`
}

type BinaryExpr struct {
	Kind  string         `json:"kind"`
	Pos   token.Position `json:"-"`
	Op    string         `json:"op"`
	Left  Expr           `json:"left"`
	Right Expr           `json:"right"`
}

type RoutineFlowSummary struct {
	RoutineName          string          `json:"routine_name"`
	RoutineKind          string          `json:"routine_kind"`
	NormalReturnPossible bool            `json:"normal_return_possible"`
	GuaranteedExit       bool            `json:"guaranteed_exit"`
	DeclaredAborts       map[string]bool `json:"declared_aborts,omitempty"`
	EmittedAborts        map[string]bool `json:"emitted_aborts,omitempty"`
	CalledRoutines       map[string]bool `json:"called_routines,omitempty"`
	PropagatedAborts     map[string]bool `json:"propagated_aborts,omitempty"`
}

type GlobalSpec struct {
	Pos  token.Position `json:"-"`
	Mode *string        `json:"mode,omitempty"`
	Name string         `json:"name"`
}

type ForAllExpr struct {
	Kind    string         `json:"kind"`
	Pos     token.Position `json:"-"`
	VarName string         `json:"var_name"`
	Lower   Expr           `json:"lower"`
	Upper   Expr           `json:"upper"`
	Expr    Expr           `json:"expr"`
}

type ExistsExpr struct {
	Kind    string         `json:"kind"`
	Pos     token.Position `json:"-"`
	VarName string         `json:"var_name"`
	Lower   Expr           `json:"lower"`
	Upper   Expr           `json:"upper"`
	Expr    Expr           `json:"expr"`
}

type DependsSpec struct {
	Pos     token.Position `json:"-"`
	Target  string         `json:"target"`
	Sources []string       `json:"sources"`
}
