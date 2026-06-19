from __future__ import annotations
import json
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

def grammar_children(tree: Tree):
    return [child for child in tree.children if not (isinstance(child, Token) and child.type == "TYPE_ARG_START")]

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
            name = str(tree.children[0])
            type_params = None
            field_start = 1
            if len(tree.children) > 1 and isinstance(tree.children[1], Tree) and tree.children[1].data == "type_param_list":
                type_params = [str(child) for child in grammar_children(tree.children[1])]
                field_start = 2
            fields = []
            for f in tree.children[field_start:]:
                proto_id = None
                json_name = None
                for attr in f.children[2:]:
                    if isinstance(attr, Tree) and attr.data == "proto_field_id":
                        proto_id = int(attr.children[0])
                    elif isinstance(attr, Tree) and attr.data == "json_field_name":
                        json_name = json.loads(str(attr.children[0]))
                fields.append(RecordField(str(f.children[0]), self.type_ref_name(f.children[1]), pos(f), proto_id, json_name))
            return RecordTypeDecl(name, fields, pos(tree), type_params)
        if tree.data == "choice_type_decl":
            name = str(tree.children[0])
            type_params = None
            cons_start = 1
            if len(tree.children) > 1 and isinstance(tree.children[1], Tree) and tree.children[1].data == "type_param_list":
                type_params = [str(child) for child in grammar_children(tree.children[1])]
                cons_start = 2
            constructors = []
            for const_node in tree.children[cons_start:-1]:
                if isinstance(const_node, Token):
                    cname = str(const_node)
                    cparams = []
                    constructors.append(ChoiceConstructor(cname, cparams, pos(const_node)))
                else:
                    cname = str(const_node.children[0])
                    cparams = []
                    for child in const_node.children[1:]:
                        if isinstance(child, Tree) and child.data == "param":
                            cparams.append(Param(str(child.children[0]), self.type_ref_name(child.children[1]), pos(child)))
                    constructors.append(ChoiceConstructor(cname, cparams, pos(const_node)))
            return ChoiceTypeDecl(name, constructors, pos(tree), type_params)
        if tree.data == "type_decl":
            base_tree = tree.children[1]
            base = str(base_tree.children[0]) if isinstance(base_tree, Tree) else str(base_tree)
            lo = hi = None
            if len(tree.children) > 2:
                lo, hi = num(tree.children[2].children[0]), num(tree.children[2].children[1])
            return TypeDecl(str(tree.children[0]), base, lo, hi, pos(tree))
        if tree.data == "error_decl":
            return ErrorDecl(str(tree.children[0]), pos(tree))
        if tree.data == "service_decl":
            name = str(tree.children[0])
            rpcs = [self.rpc_decl(child) for child in tree.children[1:-1]]
            end_name = str(tree.children[-1])
            if end_name != name:
                raise TypeCheckError(f"{pos(tree).text()}: service end name mismatch: expected {name}, got {end_name}")
            return ServiceDecl(name, rpcs, pos(tree))
        if tree.data in ("function_decl", "procedure_decl"):
            return self.routine(tree)
        if tree.data == "task_decl":
            return self.task_decl(tree)
        raise TypeCheckError(f"{pos(tree).text()}: unknown declaration {tree.data}")

    def rpc_decl(self, tree: Tree) -> RpcDecl:
        name = str(tree.children[0])
        req_name = str(tree.children[1])
        
        req_stream = False
        if isinstance(tree.children[2], Tree) and tree.children[2].data == "stream_marker":
            req_stream = True
            req_type_node = tree.children[3]
            next_idx = 4
        else:
            req_type_node = tree.children[2]
            next_idx = 3
            
        resp_stream = False
        if isinstance(tree.children[next_idx], Tree) and tree.children[next_idx].data == "stream_marker":
            resp_stream = True
            resp_type_node = tree.children[next_idx + 1]
        else:
            resp_type_node = tree.children[next_idx]
            
        return RpcDecl(
            name,
            req_name,
            self.type_ref_name(req_type_node),
            self.type_ref_name(resp_type_node),
            pos(tree),
            request_stream=req_stream,
            response_stream=resp_stream,
        )

    def routine(self, tree: Tree) -> RoutineDecl:
        kind = "function" if tree.data == "function_decl" else "procedure"
        is_async = False
        idx = 0
        ffi_binding = None
        if tree.children and isinstance(tree.children[0], Tree) and tree.children[0].data == "ffi_binding":
            ffi_node = tree.children[0]
            ffi_binding = FfiBinding(
                json.loads(str(ffi_node.children[0])),
                json.loads(str(ffi_node.children[1])),
                pos(ffi_node),
            )
            idx = 1
        if idx < len(tree.children) and isinstance(tree.children[idx], Tree) and tree.children[idx].data == "async_marker":
            is_async = True
            idx += 1
        name = str(tree.children[idx]); idx += 1
        type_params = None
        if idx < len(tree.children) and isinstance(tree.children[idx], Tree) and tree.children[idx].data == "type_param_list":
            type_params = [str(child) for child in grammar_children(tree.children[idx])]
            idx += 1
        params = []
        if idx < len(tree.children) and isinstance(tree.children[idx], Tree) and tree.children[idx].data == "param_list":
            params = [Param(str(p.children[0]), type_to_string(self.param_type(p.children[1])), pos(p)) for p in tree.children[idx].children]
            idx += 1
        ret = None
        if kind == "function":
            ret = self.return_type(tree.children[idx]); idx += 1
        requires, aborts, ensures = [], [], []
        global_specs, depends_specs, modifies_specs = [], [], None
        if idx < len(tree.children) and isinstance(tree.children[idx], Tree) and tree.children[idx].data == "contract_block":
            for c in tree.children[idx].children:
                if c.data == "requires_clause": requires.extend(self.constraint_list(c.children[0]))
                elif c.data == "aborts_clause": aborts.append(AbortClause(str(c.children[0]), self.expr(c.children[1]) if len(c.children) > 1 else None, pos(c)))
                elif c.data == "ensures_clause": ensures.extend(self.expr_list(c.children[0]))
                elif c.data == "global_clause": global_specs.extend(self.global_clause(c))
                elif c.data == "depends_clause": depends_specs.extend(self.depends_clause(c))
                elif c.data == "modifies_clause":
                    if modifies_specs is None:
                        modifies_specs = []
                    modifies_specs.extend(self.modifies_clause(c))
            idx += 1
        end_name = None
        for child in reversed(tree.children):
            if not isinstance(child, Tree):
                end_name = str(child)
                break
        if end_name != name:
            raise TypeCheckError(f"{pos(tree).text()}: {kind} end name mismatch: expected {name}, got {end_name}")
        body = [self.stmt(s.children[0] if s.data == "stmt" else s) for s in tree.children[idx:] if isinstance(s, Tree)]
        return RoutineDecl(kind, name, params, ret, requires, aborts, ensures, body, pos(tree), type_params, is_async, global_specs, depends_specs, ffi_binding, modifies_specs)

    def task_decl(self, tree: Tree) -> RoutineDecl:
        name = str(tree.children[0])
        idx = 1
        params = []
        if idx < len(tree.children) and isinstance(tree.children[idx], Tree) and tree.children[idx].data == "param_list":
            params = [Param(str(p.children[0]), type_to_string(self.param_type(p.children[1])), pos(p)) for p in tree.children[idx].children]
            idx += 1
        requires, aborts, ensures = [], [], []
        global_specs, depends_specs, modifies_specs = [], [], None
        if idx < len(tree.children) and isinstance(tree.children[idx], Tree) and tree.children[idx].data == "contract_block":
            for c in tree.children[idx].children:
                if c.data == "requires_clause": requires.extend(self.constraint_list(c.children[0]))
                elif c.data == "aborts_clause": aborts.append(AbortClause(str(c.children[0]), self.expr(c.children[1]) if len(c.children) > 1 else None, pos(c)))
                elif c.data == "ensures_clause": ensures.extend(self.expr_list(c.children[0]))
                elif c.data == "global_clause": global_specs.extend(self.global_clause(c))
                elif c.data == "depends_clause": depends_specs.extend(self.depends_clause(c))
                elif c.data == "modifies_clause":
                    if modifies_specs is None:
                        modifies_specs = []
                    modifies_specs.extend(self.modifies_clause(c))
            idx += 1
        end_name = None
        for child in reversed(tree.children):
            if not isinstance(child, Tree):
                end_name = str(child)
                break
        if end_name != name:
            raise TypeCheckError(f"{pos(tree).text()}: task end name mismatch: expected {name}, got {end_name}")
        body = [self.stmt(s.children[0] if s.data == "stmt" else s) for s in tree.children[idx:] if isinstance(s, Tree)]
        return RoutineDecl("task", name, params, None, requires, aborts, ensures, body, pos(tree), None, True, global_specs, depends_specs, None, modifies_specs)

    def global_clause(self, tree: Tree) -> list[GlobalSpec]:
        specs = []
        for child in tree.children:
            if isinstance(child, Tree) and child.data == "global_spec":
                mode = None
                name_idx = 0
                if len(child.children) == 2:
                    mode = str(child.children[0].children[0]) if isinstance(child.children[0], Tree) else str(child.children[0])
                    name_idx = 1
                name = str(child.children[name_idx])
                specs.append(GlobalSpec(mode, name, pos(child)))
        return specs

    def depends_clause(self, tree: Tree) -> list[DependsSpec]:
        specs = []
        for child in tree.children:
            if isinstance(child, Tree) and child.data == "dependency_spec":
                target_node = child.children[0]
                if isinstance(target_node, Tree) and target_node.data == "qualified_name":
                    target = self.qualified_name(target_node)
                else:
                    target = str(target_node)
                sources_tree = child.children[1]
                sources = []
                def collect_sources(node):
                    if isinstance(node, Tree):
                        if node.data == "dependency_source":
                            if node.children:
                                src_node = node.children[0]
                                if isinstance(src_node, Tree) and src_node.data == "qualified_name":
                                    sources.append(self.qualified_name(src_node))
                                else:
                                    sources.append(str(src_node))
                            else:
                                sources.append("+")
                        else:
                            for c in node.children:
                                collect_sources(c)
                collect_sources(sources_tree)
                specs.append(DependsSpec(target, sources, pos(child)))
        return specs

    def modifies_clause(self, tree: Tree) -> list[Any]:
        specs = []
        for child in tree.children:
            if isinstance(child, Tree) and child.data == "modifies_spec":
                inner = child.children[0]
                if isinstance(inner, Tree) and inner.data == "field_path":
                    specs.append(FieldAccessExpr([str(x) for x in inner.children], pos(inner)))
                else:
                    specs.append(VarExpr(str(inner), pos(child)))
        return specs

    def return_type(self, tree: Tree):
        inner = tree.children[0]
        return self.type_ref_tree(inner)

    def param_type(self, tree: Tree):
        inner = grammar_children(tree)[0] if tree.data == "param_type" else tree
        return self.type_ref_tree(inner)

    def constraint_list(self, tree: Tree):
        if isinstance(tree, Tree) and tree.data == "constraint_list":
            return [self.expr(child) for child in tree.children]
        return [self.expr(tree)]

    def expr_list(self, tree: Tree):
        if isinstance(tree, Tree) and tree.data == "expr_list":
            return [self.expr(child) for child in tree.children]
        return [self.expr(tree)]

    def type_ref_tree(self, tree: Tree):
        children = grammar_children(tree)
        if tree.data == "result_payload_type":
            return self.type_ref_tree(children[0])
        if tree.data == "type_ref":
            if isinstance(children[0], Tree) and children[0].data == "array_type":
                return self.type_ref_tree(children[0])
            return TypeName(self.type_ref_name(tree))
        if tree.data == "result_type": return ResultTypeName(self.type_ref_tree(children[0]), self.type_ref_name(children[1]))
        if tree.data == "array_type":
            if len(children) == 3:
                return ArrayTypeName(self.type_ref_name(children[1]), int(children[2]))
            return ArrayTypeName(self.type_ref_name(children[0]), int(children[1]))
        raise TypeCheckError(f"{pos(tree).text()}: invalid return type")

    def type_ref_name(self, tree: Tree) -> str:
        children = grammar_children(tree)
        if tree.data in ("return_type", "result_payload_type", "param_type"):
            return self.type_ref_name(children[0])
        if tree.data == "type_ref":
            if isinstance(children[0], Tree) and children[0].data == "array_type":
                return self.type_ref_name(children[0])
            name = str(children[0])
            if len(children) > 1:
                args = [self.type_ref_name(child) for child in grammar_children(children[1])]
                return f"{name}<{', '.join(args)}>"
            return name
        if tree.data == "array_type":
            if len(children) == 3:
                return f"Array<{self.type_ref_name(children[1])},{children[2]}>"
            return f"Array<{self.type_ref_name(children[0])},{children[1]}>"
        raise TypeCheckError(f"{pos(tree).text()}: invalid type reference")

    def stmt(self, tree: Tree):
        if tree.data == "let_stmt": return LetStmt(str(tree.children[0]), self.return_type(tree.children[1]), self.expr(tree.children[2]), pos(tree))
        if tree.data == "index_assign_stmt":
            return IndexAssignStmt(str(tree.children[0]), self.expr(tree.children[1]), self.expr(tree.children[2]), pos(tree))
        if tree.data == "field_assign_stmt":
            p = tree.children[0]
            return FieldAssignStmt([str(x) for x in p.children], self.expr(tree.children[1]), pos(tree))
        if tree.data == "assign_stmt": return AssignStmt(str(tree.children[0]), self.expr(tree.children[1]), pos(tree))
        if tree.data == "return_stmt": return ReturnStmt(self.return_value(tree.children[0]), pos(tree))
        if tree.data == "abort_stmt": return AbortStmt(str(tree.children[0]), pos(tree))
        if tree.data == "check_stmt": return CheckStmt(self.expr(tree.children[0]), pos(tree))
        if tree.data == "call_stmt":
            call_name = self.qualified_name(tree.children[0]) if isinstance(tree.children[0], Tree) else str(tree.children[0])
            type_args = None
            arg_index = 1
            if len(tree.children) > 1 and isinstance(tree.children[1], Tree) and tree.children[1].data == "type_arg_list":
                type_args = [self.type_ref_name(child) for child in grammar_children(tree.children[1])]
                arg_index = 2
            return CallStmt(call_name, self.args(tree.children[arg_index]) if len(tree.children)>arg_index else [], pos(tree), type_args)
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
                elif c.data == "pattern_branch":
                    p_node = c.children[0]
                    pname = str(p_node.children[0])
                    pargs = [str(x) for x in p_node.children[1:]]
                    pat = PatternExpr(pname, pargs, pos(p_node))
                    guard = None
                    if len(c.children) == 3:
                        guard = self.expr(c.children[1])
                    block = c.children[-1]
                    branches.append(PatternBranch(pat, guard, [self.stmt(x.children[0]) for x in block.children], pos(c)))
                elif c.data == "default_branch":
                    block = c.children[0]
                    default_body = [self.stmt(x.children[0]) for x in block.children]
            return CaseStmt(self.expr(tree.children[0]), branches, default_body, pos(tree))
        if tree.data == "scope_stmt":
            spawn_body = [self.stmt(x.children[0]) for x in tree.children[1].children]
            join_body = [self.stmt(x.children[0]) for x in tree.children[2].children]
            result_body = [self.stmt(x.children[0]) for x in tree.children[3].children]
            return ScopeStmt(str(tree.children[0]), spawn_body, join_body, result_body, pos(tree))
        if tree.data == "parallel_stmt":
            block_name = None
            limit_expr = None
            
            # Find the starting block name if any, other nodes are the limit expression and stmt blocks
            start_name = None
            end_name = None
            if isinstance(tree.children[0], Token) and tree.children[0].type == "NAME":
                start_name = str(tree.children[0])
            if isinstance(tree.children[-1], Token) and tree.children[-1].type == "NAME":
                end_name = str(tree.children[-1])
                
            if start_name != end_name:
                raise TypeCheckError(f"{pos(tree).text()}: parallel block name parity mismatch: start '{start_name}', end '{end_name}'")
                
            block_name = start_name
            
            # The limit expression is the only Tree children that is not a stmt
            limit_nodes = [c for c in tree.children if isinstance(c, Tree) and c.data != "stmt"]
            limit_expr = self.expr(limit_nodes[0]) if limit_nodes else None
            
            body = [self.stmt(c.children[0] if c.data == "stmt" else c) for c in tree.children if isinstance(c, Tree) and c.data == "stmt"]
            return ParallelStmt(block_name, limit_expr, body, pos(tree))
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
        if tree.data == "spawn_expr":
            target = self.expr(tree.children[0])
            attributes = {}
            if len(tree.children) > 1 and isinstance(tree.children[1], Tree) and tree.children[1].data == "spawn_attribute_list":
                for attr_node in tree.children[1].children:
                    name = str(attr_node.children[0])
                    value = self.expr(attr_node.children[1])
                    attributes[name] = value
            return SpawnExpr(target, attributes, pos(tree))
        if tree.data == "string":
            raw = str(tree.children[0])
            try:
                escaped = raw[1:-1].encode("ascii", "backslashreplace").decode("ascii")
                value = escaped.encode("utf-8").decode("unicode_escape")
            except Exception:
                value = raw[1:-1]
            return StringExpr(value, pos(tree))
        if tree.data == "number": return NumberExpr(int(tree.children[0]), pos(tree))
        if tree.data == "double": return DoubleExpr(float(tree.children[0]), pos(tree))
        if tree.data == "true": return BoolExpr(True, pos(tree))
        if tree.data == "false": return BoolExpr(False, pos(tree))
        if tree.data in ("success","failure","result_value","result_error_value"):
            return SpecialResultExpr({"success":"success","failure":"failure","result_value":"value","result_error_value":"error"}[tree.data], pos(tree))
        if tree.data == "result_var": return VarExpr("result", pos(tree))
        if tree.data == "var": return VarExpr(str(tree.children[0]), pos(tree))
        if tree.data == "field_access":
            # child is field_path, which contains all NAME tokens in order
            p = tree.children[0]
            return FieldAccessExpr([str(x) for x in p.children], pos(tree))
        if tree.data in ("result_field_access", "result_value_field_access", "result_error_field_access"):
            root = {"result_field_access": "result", "result_value_field_access": "value", "result_error_field_access": "error"}[tree.data]
            return FieldAccessExpr([root] + [str(x) for x in tree.children], pos(tree))
        if tree.data == "function_call":
            fn_name = self.qualified_name(tree.children[0]) if isinstance(tree.children[0], Tree) else str(tree.children[0])
            type_args = None
            arg_index = 1
            if len(tree.children) > 1 and isinstance(tree.children[1], Tree) and tree.children[1].data == "type_arg_list":
                type_args = [self.type_ref_name(child) for child in grammar_children(tree.children[1])]
                arg_index = 2
            return CallExpr(fn_name, self.args(tree.children[arg_index]) if len(tree.children)>arg_index else [], pos(tree), type_args)
        if tree.data == "record_literal": return RecordLiteralExpr(self.type_ref_name(tree.children[0]), self.named_args(tree.children[1]), pos(tree))
        if tree.data == "map_literal":
            type_name = self.type_ref_name(tree.children[0])
            entries = []
            if len(tree.children) > 1 and isinstance(tree.children[1], Tree) and tree.children[1].data == "map_entries":
                for entry_node in tree.children[1].children:
                    raw_key = str(entry_node.children[0])
                    key = json.loads(raw_key)
                    val_expr = self.expr(entry_node.children[1])
                    entries.append(MapEntry(key, val_expr, pos(entry_node)))
            return MapLiteralExpr(type_name, entries, pos(tree))
        if tree.data == "set_literal":
            type_name = self.type_ref_name(tree.children[0])
            items = []
            if len(tree.children) > 1 and isinstance(tree.children[1], Tree) and tree.children[1].data == "set_entries":
                items = [self.expr(child) for child in tree.children[1].children]
            return SetLiteralExpr(type_name, items, pos(tree))
        if tree.data == "array_literal": return ArrayLiteralExpr(self.args(tree.children[0]) if len(tree.children)>0 else [], pos(tree))
        if tree.data == "result_index_expr": return IndexExpr("result", self.expr(tree.children[0]), pos(tree))
        if tree.data == "result_index_field_access": return IndexedFieldAccessExpr("result", self.expr(tree.children[0]), [str(x) for x in tree.children[1:]], pos(tree))
        if tree.data == "result_value_index_expr": return IndexExpr("value", self.expr(tree.children[0]), pos(tree))
        if tree.data == "result_value_index_field_access": return IndexedFieldAccessExpr("value", self.expr(tree.children[0]), [str(x) for x in tree.children[1:]], pos(tree))
        if tree.data == "index_expr": return IndexExpr(str(tree.children[0]), self.expr(tree.children[1]), pos(tree))
        if tree.data == "for_all_expr":
            return ForAllExpr(str(tree.children[0]), self.expr(tree.children[1]), self.expr(tree.children[2]), self.expr(tree.children[3]), pos(tree))
        if tree.data == "exists_expr":
            return ExistsExpr(str(tree.children[0]), self.expr(tree.children[1]), self.expr(tree.children[2]), self.expr(tree.children[3]), pos(tree))
        if tree.data == "channel_create_with_invariant":
            fn_name = str(tree.children[0])
            if fn_name != "channel":
                raise TypeCheckError(f"{pos(tree).text()}: invariant only allowed on channel creation, got {fn_name}")
            type_args = None
            if len(tree.children) > 1 and isinstance(tree.children[1], Tree) and tree.children[1].data == "type_arg_list":
                type_args = [self.type_ref_name(child) for child in grammar_children(tree.children[1])]
            args_list = []
            if len(tree.children) > 2 and tree.children[2] is not None:
                args_list = self.args(tree.children[2])
            invariant = self.expr(tree.children[3])
            return CallExpr("channel", args_list, pos(tree), type_args, invariant)
        if tree.data == "await_expr": return AwaitExpr(self.expr(tree.children[0]), pos(tree))
        if tree.data == "await_all_expr": return AwaitAllExpr(self.expr(tree.children[0]), pos(tree))
        if tree.data == "is_expr":
            left_token = tree.children[0]
            left_var = VarExpr(str(left_token), pos(left_token))
            return IsExpr(left_var, str(tree.children[1]), pos(tree))
        if tree.data in ("neg_expr","not_expr"): return UnaryExpr("-" if tree.data=="neg_expr" else "not", self.expr(tree.children[0]), pos(tree))
        ops = {"add_expr":"+","sub_expr":"-","mul_expr":"*","div_expr":"/","modulo_expr":"%","eq_expr":"=","neq_expr":"!=","lt_expr":"<","le_expr":"<=","gt_expr":">","ge_expr":">=","and_expr":"and","or_expr":"or"}
        if tree.data in ops: return BinaryExpr(ops[tree.data], self.expr(tree.children[0]), self.expr(tree.children[1]), pos(tree))
        raise TypeCheckError(f"{pos(tree).text()}: unsupported expression {tree.data}")

def parse_source(source: str) -> Program: return AstBuilder().parse(source)
def parse_file(path: str) -> Program:
    with open(path, "r", encoding="utf-8") as f: return parse_source(f.read())
