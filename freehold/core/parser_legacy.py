from __future__ import annotations
from lark import Lark, Tree, Token
from freehold.core.comment_rules import validate_comments
from freehold.core.grammar_inline import FREEHOLD_GRAMMAR
from freehold.core.ast import *

parser = Lark(FREEHOLD_GRAMMAR, parser="lalr", start="start", propagate_positions=True)

def pos(node) -> SourcePos:
    meta = getattr(node, "meta", None)
    line = getattr(meta, "line", None)
    column = getattr(meta, "column", None)
    if line is None and isinstance(node, Token):
        line = getattr(node, "line", None)
        column = getattr(node, "column", None)
    return SourcePos(line, column)

def num(tok):
    s = str(tok)
    return float(s) if "." in s else int(s)

class AstBuilder:
    def parse(self, source: str) -> Program:
        validate_comments(source)
        return self.program(parser.parse(source))

    def qualified_name(self, tree: Tree) -> str:
        return ".".join(str(x) for x in tree.children)

    def import_decl(self, tree: Tree) -> ImportDecl:
        module_name = self.qualified_name(tree.children[0])
        exposing: list[str] = []
        if len(tree.children) > 1:
            exposing_tree = tree.children[1].children[0]
            exposing = [str(x) for x in exposing_tree.children]
        return ImportDecl(module_name, exposing, pos(tree))

    def program(self, tree: Tree) -> Program:
        module_name = self.qualified_name(tree.children[0].children[0])
        imports = []
        declarations = []
        module_end = None
        for child in tree.children[1:]:
            if isinstance(child, Tree) and child.data == "import_decl":
                imports.append(self.import_decl(child))
            elif isinstance(child, Tree) and child.data == "module_end":
                module_end = self.qualified_name(child.children[0])
            else:
                declarations.append(self.declaration(child.children[0]))
        if module_end != module_name:
            raise TypeCheckError(f"{pos(tree).text()}: module end name mismatch: expected {module_name}, got {module_end}")
        return Program(module_name, declarations, pos(tree), imports)

    def declaration(self, tree: Tree):
        if tree.data == "record_type_decl":
            return RecordTypeDecl(str(tree.children[0]), [RecordField(str(f.children[0]), str(f.children[1].children[0]), pos(f)) for f in tree.children[1:]], pos(tree))
        if tree.data == "type_decl":
            base_tree = tree.children[1]
            base = str(base_tree.children[0]) if isinstance(base_tree, Tree) else str(base_tree)
            lo = hi = None
            if len(tree.children) > 2:
                lo, hi = num(tree.children[2].children[0]), num(tree.children[2].children[1])
            return TypeDecl(str(tree.children[0]), base, lo, hi, pos(tree))
        if tree.data == "error_decl":
            return ErrorDecl(str(tree.children[0]), pos(tree))
        if tree.data in ("function_decl", "procedure_decl"):
            return self.routine(tree)
        raise TypeCheckError(f"{pos(tree).text()}: unknown declaration {tree.data}")

    def routine(self, tree: Tree) -> RoutineDecl:
        kind = "function" if tree.data == "function_decl" else "procedure"
        name, idx = str(tree.children[0]), 1
        params = []
        if idx < len(tree.children) and isinstance(tree.children[idx], Tree) and tree.children[idx].data == "param_list":
            params = [Param(str(p.children[0]), str(p.children[1].children[0]), pos(p)) for p in tree.children[idx].children]
            idx += 1
        ret = None
        if kind == "function":
            ret = self.return_type(tree.children[idx]); idx += 1
        requires, ensures = [], []
        if idx < len(tree.children) and isinstance(tree.children[idx], Tree) and tree.children[idx].data == "contract_block":
            for c in tree.children[idx].children:
                if c.data == "requires_clause": requires.append(self.expr(c.children[0]))
                elif c.data == "ensures_clause": ensures.append(self.expr(c.children[0]))
            idx += 1
        end_name = None
        for child in reversed(tree.children):
            if not isinstance(child, Tree):
                end_name = str(child)
                break
        if end_name != name:
            raise TypeCheckError(f"{pos(tree).text()}: {kind} end name mismatch: expected {name}, got {end_name}")
        body = [self.stmt(s.children[0] if s.data == "stmt" else s) for s in tree.children[idx:] if isinstance(s, Tree)]
        return RoutineDecl(kind, name, params, ret, requires, ensures, body, pos(tree))

    def return_type(self, tree: Tree):
        inner = tree.children[0]
        if inner.data == "type_ref": return TypeName(str(inner.children[0]))
        if inner.data == "result_type": return ResultTypeName(str(inner.children[0].children[0]), str(inner.children[1].children[0]))
        if inner.data == "array_type": return ArrayTypeName(str(inner.children[0].children[0]), int(inner.children[1]))
        raise TypeCheckError(f"{pos(tree).text()}: invalid return type")

    def stmt(self, tree: Tree):
        if tree.data == "let_stmt": return LetStmt(str(tree.children[0]), self.return_type(tree.children[1]), self.expr(tree.children[2]), pos(tree))
        if tree.data == "field_assign_stmt":
            p = tree.children[0]
            return FieldAssignStmt([str(x) for x in p.children], self.expr(tree.children[1]), pos(tree))
        if tree.data == "assign_stmt": return AssignStmt(str(tree.children[0]), self.expr(tree.children[1]), pos(tree))
        if tree.data == "return_stmt": return ReturnStmt(self.return_value(tree.children[0]), pos(tree))
        if tree.data == "check_stmt": return CheckStmt(self.expr(tree.children[0]), pos(tree))
        if tree.data == "call_stmt":
            call_name = self.qualified_name(tree.children[0]) if isinstance(tree.children[0], Tree) else str(tree.children[0])
            return CallStmt(call_name, self.args(tree.children[1]) if len(tree.children)>1 else [], pos(tree))
        if tree.data == "if_stmt":
            then, els = [], []
            for c in tree.children[1:]:
                if c.data == "then_block": then = [self.stmt(x.children[0]) for x in c.children]
                elif c.data == "else_block": els = [self.stmt(x.children[0]) for x in c.children]
            return IfStmt(self.expr(tree.children[0]), then, els, pos(tree))
        if tree.data == "while_stmt":
            invs, var, body = [], None, []
            for c in tree.children[1:]:
                if c.data == "invariant_clause": invs.append(self.expr(c.children[0]))
                elif c.data == "variant_clause": var = self.expr(c.children[0])
                elif c.data == "loop_block": body = [self.stmt(x.children[0]) for x in c.children]
            return WhileStmt(self.expr(tree.children[0]), invs, var, body, pos(tree))
        if tree.data == "case_stmt":
            branches = []
            default_body = []
            for c in tree.children[1:]:
                if c.data == "case_branch":
                    value = self.expr(c.children[0])
                    block = c.children[1]
                    branches.append(CaseBranch(value, [self.stmt(x.children[0]) for x in block.children], pos(c)))
                elif c.data == "default_branch":
                    block = c.children[0]
                    default_body = [self.stmt(x.children[0]) for x in block.children]
            return CaseStmt(self.expr(tree.children[0]), branches, default_body, pos(tree))
        raise TypeCheckError(f"{pos(tree).text()}: unsupported statement {tree.data}")

    def return_value(self, tree: Tree):
        if tree.data == "return_plain": return ReturnPlain(self.expr(tree.children[0]), pos(tree))
        if tree.data == "return_ok": return ReturnOk(self.expr(tree.children[0]), pos(tree))
        if tree.data == "return_error": return ReturnError(str(tree.children[0]), pos(tree))
        raise TypeCheckError(f"{pos(tree).text()}: invalid return")

    def args(self, tree: Tree): return [self.call_arg(x) for x in tree.children]
    def call_arg(self, tree: Tree):
        if tree.data == "named_call_arg": return NamedArg(str(tree.children[0]), self.expr(tree.children[1]), pos(tree))
        if tree.data == "positional_call_arg": return self.expr(tree.children[0])
        return self.expr(tree)
    def named_args(self, tree: Tree): return [NamedArg(str(x.children[0]), self.expr(x.children[1]), pos(x)) for x in tree.children]

    def expr(self, tree: Tree):
        if tree.data == "string":
            raw = str(tree.children[0])
            try:
                value = bytes(raw[1:-1], "utf-8").decode("unicode_escape")
            except Exception:
                value = raw[1:-1]
            return StringExpr(value, pos(tree))
        if tree.data == "number": return NumberExpr(int(tree.children[0]), pos(tree))
        if tree.data == "double": return DoubleExpr(float(tree.children[0]), pos(tree))
        if tree.data == "true": return BoolExpr(True, pos(tree))
        if tree.data == "false": return BoolExpr(False, pos(tree))
        if tree.data in ("success","failure","result_value","result_error_value"):
            return SpecialResultExpr({"success":"success","failure":"failure","result_value":"value","result_error_value":"error"}[tree.data], pos(tree))
        if tree.data == "var": return VarExpr(str(tree.children[0]), pos(tree))
        if tree.data == "field_access":
            # child is field_path, which contains all NAME tokens in order
            p = tree.children[0]
            return FieldAccessExpr([str(x) for x in p.children], pos(tree))
        if tree.data == "function_call":
            fn_name = self.qualified_name(tree.children[0]) if isinstance(tree.children[0], Tree) else str(tree.children[0])
            return CallExpr(fn_name, self.args(tree.children[1]) if len(tree.children)>1 else [], pos(tree))
        if tree.data == "record_literal": return RecordLiteralExpr(str(tree.children[0]), self.named_args(tree.children[1]), pos(tree))
        if tree.data == "array_literal": return ArrayLiteralExpr(self.args(tree.children[0]) if len(tree.children)>0 else [], pos(tree))
        if tree.data == "index_expr": return IndexExpr(str(tree.children[0]), self.expr(tree.children[1]), pos(tree))
        if tree.data in ("neg_expr","not_expr"): return UnaryExpr("-" if tree.data=="neg_expr" else "not", self.expr(tree.children[0]), pos(tree))
        ops = {"add_expr":"+","sub_expr":"-","mul_expr":"*","div_expr":"/","eq_expr":"=","neq_expr":"!=","lt_expr":"<","le_expr":"<=","gt_expr":">","ge_expr":">=","and_expr":"and","or_expr":"or"}
        if tree.data in ops: return BinaryExpr(ops[tree.data], self.expr(tree.children[0]), self.expr(tree.children[1]), pos(tree))
        raise TypeCheckError(f"{pos(tree).text()}: unsupported expression {tree.data}")

def parse_source(source: str) -> Program: return AstBuilder().parse(source)
def parse_file(path: str) -> Program:
    with open(path, "r", encoding="utf-8") as f: return parse_source(f.read())
