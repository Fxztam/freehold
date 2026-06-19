from __future__ import annotations
import json
import math
from freehold.core.ast import *
from freehold.core.string_templates import render_template
from freehold.core.verifier import VerifiedProgram
from freehold.runtime import big as std_big
from freehold.runtime import std_io

def param_type_ref(type_name: str):
    if type_name.startswith("Array<") and type_name.endswith(">"):
        inner = type_name[len("Array<"):-1]
        element_type, _, size_text = inner.rpartition(",")
        if element_type and size_text.strip().isdigit():
            return ArrayTypeName(element_type.strip(), int(size_text.strip()))
    return TypeName(type_name)

def json_loads_strict(text: str):
    def object_pairs_hook(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate object key: {key}")
            obj[key] = value
        return obj
    return json.loads(text, object_pairs_hook=object_pairs_hook)

class Interpreter:
    def __init__(self, verified: VerifiedProgram):
        self.v=verified; self.types=verified.types; self.records=verified.records; self.errors=verified.errors; self.routines=verified.routines
    def run_main(self):
        if "main" in self.routines: self.call("main", [])
    def call(self,name,args):
        name = self.local_routine_name(name)
        r=self.routines[name]; env={}; env_types={}
        for p,v in zip(r.params,args): env[p.name]=v; env_types[p.name]=param_type_ref(p.type_name)
        for req in r.requires:
            if self.eval(req, env) is not True:
                raise VerificationError(f"{req.pos.text()}: requires failed in {name}: {req}")
        try:
            self.block(r.body, env, env_types)
        except ReturnSignal as sig:
            self.check_value(sig.value, r.return_type, f"return value of {name}")
            env["result"] = sig.value
            if isinstance(sig.value, ResultValue):
                env["success"] = sig.value.ok
                env["failure"] = not sig.value.ok
                if sig.value.ok: env["value"] = sig.value.value
                else: env["error"] = sig.value.error
            for ens in r.ensures:
                if self.eval(ens, env) is not True:
                    raise VerificationError(f"{ens.pos.text()}: ensures failed in {name}: {ens}")
            return sig.value
        if r.kind=="function": raise VerificationError(f"function {name} ended without return")
    def block(self,body,env,env_types):
        for s in body: self.stmt(s,env,env_types)
    def std_procedure_call(self, name, args, env) -> bool:
        if name in ("Std.IO.log", "Std.IO.log_int", "Std.IO.log_bool", "Std.IO.log_double"):
            values = [self.eval(a, env) for a in args]
            std_io.log(values[0])
            return True
        if name == "Std.IO.logf":
            template = self.eval(args[0], env)
            positional = [self.eval(a, env) for a in args[1:] if not isinstance(a, NamedArg)]
            named = {a.name: self.eval(a.expr, env) for a in args[1:] if isinstance(a, NamedArg)}
            std_io.log(render_template(template, positional, named))
            return True
        return False

    def stmt(self,s,env,env_types):
        if isinstance(s, LetStmt):
            v=self.eval(s.expr,env); self.check_value(v,s.type_ref,f"{s.pos.text()}: variable {s.name}"); env[s.name]=v; env_types[s.name]=s.type_ref
        elif isinstance(s, AssignStmt):
            v=self.eval(s.expr,env); self.check_value(v,env_types[s.name],f"{s.pos.text()}: assignment {s.name}"); env[s.name]=v
        elif isinstance(s, FieldAssignStmt):
            self.assign_field_path(s.path, self.eval(s.expr, env), env, s.pos)
        elif isinstance(s, ReturnStmt): raise ReturnSignal(self.retval(s.value,env))
        elif isinstance(s, AbortStmt): raise AbortSignal(s.error_name)
        elif isinstance(s, CheckStmt):
            if self.eval(s.expr,env) is not True: raise VerificationError(f"{s.pos.text()}: check failed")
        elif isinstance(s, IfStmt):
            cond = self.eval(s.condition, env)
            if not isinstance(cond, bool):
                raise TypeCheckError(f"{s.pos.text()}: if condition must be Boolean")
            self.block(s.then_body if cond else s.else_body, env, env_types)
        elif isinstance(s, WhileStmt):
            count = 0
            prev = None
            for inv in s.invariants:
                if self.eval(inv, env) is not True:
                    raise VerificationError(f"{inv.pos.text()}: loop invariant failed at entry")
            while self.eval(s.condition, env) is True:
                if s.variant:
                    v = self.eval(s.variant, env)
                    if prev is not None and v >= prev:
                        raise VerificationError(f"{s.variant.pos.text()}: loop variant did not decrease")
                    prev = v
                self.block(s.body, env, env_types)
                for inv in s.invariants:
                    if self.eval(inv, env) is not True:
                        raise VerificationError(f"{inv.pos.text()}: loop invariant failed after body")
                count += 1
                if count > 10000:
                    raise VerificationError(f"{s.pos.text()}: loop limit exceeded")
        elif isinstance(s, CaseStmt):
            case_value = self.eval(s.expr, env)
            matched = False
            for br in s.branches:
                if case_value == self.eval(br.value, env):
                    self.block(br.body, env, env_types)
                    matched = True
                    break
            if not matched:
                self.block(s.default_body, env, env_types)
        elif isinstance(s, CallStmt):
            if self.std_procedure_call(s.name, s.args, env):
                return
            self.call(s.name, [self.eval(a, env) for a in s.args])
    def retval(self,rv,env):
        if isinstance(rv, ReturnPlain): return self.eval(rv.expr,env)
        if isinstance(rv, ReturnOk): return ResultValue(True,self.eval(rv.expr,env),None)
        if isinstance(rv, ReturnError): return ResultValue(False,None,rv.error_name)
    def eval_field_path(self, e, env):
        value = env[e.path[0]]
        for field in e.path[1:]:
            if isinstance(value, ResultValue):
                if field == "ok":
                    value = value.ok
                elif field == "value":
                    value = value.value
                elif field == "error":
                    value = value.error
                else:
                    raise VerificationError(f"{e.pos.text()}: unknown Result field {field}")
                continue
            if not isinstance(value, RecordValue): raise VerificationError(f"{e.pos.text()}: field access requires record value")
            if field not in value.fields: raise VerificationError(f"{e.pos.text()}: missing field {field}")
            value = value.fields[field]
        return value

    def json_value(self, value):
        if isinstance(value, RecordValue):
            record = self.records[value.type_name]
            json_fields = record.json_fields or {}
            return {json_fields.get(field_name, field_name): self.json_value(value.fields[field_name]) for field_name in record.fields}
        if isinstance(value, dict):
            return {k: self.json_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.json_value(item) for item in value]
        if value is None or isinstance(value, (str, bool)):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float):
            return value
        raise VerificationError(f"Json.stringify cannot serialize runtime value {type(value).__name__}")

    def json_record_value(self, target_type, value, path):
        if target_type not in self.records:
            raise VerificationError(f"Json.parse target is not a record: {target_type}")
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected object")
        record = self.records[target_type]
        json_fields = record.json_fields or {}
        json_to_field = {json_fields.get(field_name, field_name): field_name for field_name in record.fields}
        expected_fields = set(json_to_field)
        actual_fields = set(value)
        missing = sorted(expected_fields - actual_fields)
        if missing:
            raise ValueError(f"{path}: missing required field {missing[0]}")
        unknown = sorted(actual_fields - expected_fields)
        if unknown:
            raise ValueError(f"{path}: unknown field {unknown[0]}")
        fields = {
            field_name: self.json_typed_value(record.fields[field_name], value[json_name], f"{path}.{json_name}")
            for json_name, field_name in json_to_field.items()
        }
        return RecordValue(target_type, fields)

    def json_typed_value(self, type_name, value, path):
        import re
        generic_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)<(.+)>", type_name.strip())
        if generic_match and generic_match.group(1) == "Map":
            val_t_str = generic_match.group(2)
            if not isinstance(value, dict):
                raise ValueError(f"{path}: expected Map (JSON object)")
            res_dict = {}
            for k, val in value.items():
                if not isinstance(k, str):
                    raise ValueError(f"{path}: map key must be String, got {type(k).__name__}")
                res_dict[k] = self.json_typed_value(val_t_str, val, f"{path}.{k}")
            return res_dict

        type_ref = param_type_ref(type_name)
        if isinstance(type_ref, ArrayTypeName):
            if not isinstance(value, list):
                raise ValueError(f"{path}: expected array")
            if len(value) != type_ref.size:
                raise ValueError(f"{path}: expected array length {type_ref.size}, got {len(value)}")
            return [self.json_typed_value(type_ref.element_type, item, f"{path}[]") for item in value]
        if type_name in self.records:
            return self.json_record_value(type_name, value, path)
        base = self.types[type_name].base if type_name in self.types else type_name
        if base == "String":
            if isinstance(value, str):
                return value
            raise ValueError(f"{path}: expected String")
        if base == "Integer":
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            raise ValueError(f"{path}: expected Integer")
        if base == "Boolean":
            if isinstance(value, bool):
                return value
            raise ValueError(f"{path}: expected Boolean")
        if base == "Double":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            raise ValueError(f"{path}: expected Double")
        raise ValueError(f"{path}: unsupported JSON target type {type_name}")

    def json_parse_record(self, target_type, text):
        try:
            data = json_loads_strict(text)
            return ResultValue(True, self.json_record_value(target_type, data, "value"), None)
        except Exception as exc:
            return ResultValue(False, None, str(exc))

    def assign_field_path(self, path, new_value, env, pos):
        if len(path) < 2:
            raise VerificationError(f"{pos.text()}: invalid field assignment")
        value = env[path[0]]
        for field in path[1:-1]:
            if not isinstance(value, RecordValue): raise VerificationError(f"{pos.text()}: field assignment requires record value")
            value = value.fields[field]
        if not isinstance(value, RecordValue): raise VerificationError(f"{pos.text()}: field assignment target is not a record")
        value.fields[path[-1]] = new_value
    def eval(self,e,env):
        if isinstance(e, StringExpr): return e.value
        if isinstance(e, NumberExpr): return e.value
        if isinstance(e, DoubleExpr): return e.value
        if isinstance(e, BoolExpr): return e.value
        if isinstance(e, RecordLiteralExpr): return RecordValue(e.type_name,{a.name:self.eval(a.expr,env) for a in e.args})
        if isinstance(e, ArrayLiteralExpr): return [self.eval(x, env) for x in e.items]
        if isinstance(e, MapLiteralExpr): return {entry.key: self.eval(entry.expr, env) for entry in e.entries}
        if isinstance(e, IndexExpr):
            arr = env[e.name]
            idx = self.eval(e.index, env)
            if isinstance(arr, dict):
                if not isinstance(idx, str):
                    raise TypeCheckError(f"{e.pos.text()}: map index must be String")
                if idx in arr:
                    return ResultValue(True, arr[idx], None)
                else:
                    return ResultValue(False, None, "SchemaError")
            if not isinstance(idx, int) or isinstance(idx, bool):
                raise TypeCheckError(f"{e.pos.text()}: array index must be Integer")
            if idx < 0 or idx >= len(arr):
                raise VerificationError(f"{e.pos.text()}: array index out of bounds")
            return arr[idx]
        if isinstance(e, FieldAccessExpr): return self.eval_field_path(e, env)
        if isinstance(e, VarExpr): return env[e.name]
        if isinstance(e, CallExpr):
            args = [self.eval(a, env) for a in e.args if not isinstance(a, NamedArg)]
            if e.name == "System.args" or (e.name == "args" and "args" not in self.routines):
                import sys
                argv = sys.argv[1:]
                return [argv[i] if i < len(argv) else "" for i in range(10)]
            if e.name == "System.run_command" or (e.name == "run_command" and "run_command" not in self.routines):
                import subprocess
                cmd_str = args[0]
                try:
                    res = subprocess.run(cmd_str, shell=True)
                    return res.returncode
                except Exception:
                    return -1
            if e.name == "System.get_env" or (e.name == "get_env" and "get_env" not in self.routines):
                import os
                return os.environ.get(args[0], "")
            if e.name == "File.read_to_string" or (e.name == "read_to_string" and "read_to_string" not in self.routines):
                path = args[0]
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    return ResultValue(True, content, None)
                except Exception as ex:
                    return ResultValue(False, None, str(ex))
            if e.name == "File.write_string" or (e.name == "write_string" and "write_string" not in self.routines):
                path, content = args
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return ResultValue(True, True, None)
                except Exception as ex:
                    return ResultValue(False, None, str(ex))
            if e.name == "Map.keys":
                k_list = list(args[0].keys())
                k_list = k_list[:16]
                while len(k_list) < 16:
                    k_list.append("")
                return k_list
            if e.name == "Map.size":
                return len(args[0])
            if e.name == "Map.set":
                m, key, val = args
                m_copy = dict(m)
                m_copy[key] = val
                return m_copy
            if e.name == "Map.remove":
                m, key = args
                m_copy = dict(m)
                if key in m_copy:
                    del m_copy[key]
                return m_copy
            if e.name == "String.concat":
                return args[0] + args[1]
            if e.name == "String.substr":
                s, start, length = args
                if start < 0 or length < 0 or start + length > len(s):
                    raise VerificationError(f"{e.pos.text()}: String.substr out of bounds")
                return s[start:start+length]
            if e.name == "String.replace":
                s, old, new = args
                return s.replace(old, new)
            if e.name == "String.instr":
                s, needle = args
                return s.find(needle)
            if e.name == "String.length":
                return len(args[0])
            if e.name == "String.error_text":
                return str(args[0])
            if e.name == "String.template":
                named = {a.name: self.eval(a.expr, env) for a in e.args[1:] if isinstance(a, NamedArg)}
                return render_template(args[0], args[1:], named)
            if e.name == "Json.stringify":
                return json.dumps(self.json_value(args[0]), ensure_ascii=False, separators=(",", ":"))
            if e.name == "Json.parse":
                return self.json_parse_record(e.type_args[0], args[0])
            if e.name == "Math.sin":
                return math.sin(args[0])
            if e.name == "Math.cos":
                return math.cos(args[0])
            if e.name == "Math.tan":
                return math.tan(args[0])
            if e.name == "Math.sqrt":
                if args[0] < 0:
                    raise VerificationError(f"{e.pos.text()}: Math.sqrt domain error")
                return math.sqrt(args[0])
            if e.name == "Math.pow":
                return math.pow(args[0], args[1])
            if e.name == "Math.abs":
                return abs(args[0])
            if e.name == "Math.min":
                return min(args[0], args[1])
            if e.name == "Math.max":
                return max(args[0], args[1])
            if e.name == "Math.floor":
                return math.floor(args[0])
            if e.name == "Math.ceil":
                return math.ceil(args[0])
            if e.name in ("Big.int", "Big.integer"):
                return std_big.integer(args[0])
            if e.name == "Big.fromInteger":
                return std_big.from_integer(args[0])
            if e.name == "Big.float":
                return std_big.float_from_string(args[0], args[1])
            if e.name == "Big.floatFromInteger":
                return std_big.float_from_integer(args[0], args[1])
            if e.name == "Big.addInt":
                return std_big.add_int(args[0], args[1])
            if e.name == "Big.subInt":
                return std_big.sub_int(args[0], args[1])
            if e.name == "Big.mulInt":
                return std_big.mul_int(args[0], args[1])
            if e.name == "Big.divInt":
                return std_big.div_int(args[0], args[1], e.pos)
            if e.name == "Big.negInt":
                return std_big.neg_int(args[0])
            if e.name == "Big.absInt":
                return std_big.abs_int(args[0])
            if e.name == "Big.signInt":
                return std_big.sign_int(args[0])
            if e.name == "Big.addFloat":
                return std_big.add_float(args[0], args[1])
            if e.name == "Big.subFloat":
                return std_big.sub_float(args[0], args[1])
            if e.name == "Big.mulFloat":
                return std_big.mul_float(args[0], args[1])
            if e.name == "Big.divFloat":
                return std_big.div_float(args[0], args[1], e.pos)
            if e.name == "Big.sqrt":
                return std_big.sqrt(args[0], e.pos)
            if e.name == "Big.absFloat":
                return std_big.abs_float(args[0])
            if e.name == "Big.signFloat":
                return std_big.sign_float(args[0])
            if e.name == "Big.toString":
                return std_big.to_string(args[0])
            if e.name == "Big.format":
                return std_big.format_float(args[0], args[1])
            return self.call(e.name,args)
        if isinstance(e, BinaryExpr):
            a,b=self.eval(e.left,env),self.eval(e.right,env)
            if e.op=="=": return a==b
            if e.op=="!=": return a!=b
            if e.op=="+": return a+b
            if e.op=="-": return a-b
            if e.op=="*": return a*b
            if e.op=="%": return a%b
            if e.op=="/": return a/b if isinstance(a,float) or isinstance(b,float) else a//b
            if e.op=="<": return a<b
            if e.op=="<=": return a<=b
            if e.op==">": return a>b
            if e.op==">=": return a>=b
            if e.op=="and": return a and b
            if e.op=="or": return a or b
        if isinstance(e, UnaryExpr):
            v=self.eval(e.expr,env); return -v if e.op=="-" else not v
        raise VerificationError(f"unsupported expr {e}")
    def local_routine_name(self,name):
        prefix = f"{self.v.ast.module_name}."
        return name[len(prefix):] if name.startswith(prefix) else name
    def check_value(self,v,t,ctx):
        if isinstance(t, TypeName):
            self.check_plain(v,t.name,ctx)
        elif isinstance(t, ArrayTypeName):
            if not isinstance(v, list):
                raise TypeCheckError(f"expected Array in {ctx}")
            if len(v) != t.size:
                raise VerificationError(f"{ctx}: array length mismatch")
            for item in v:
                self.check_plain(item, t.element_type, ctx)
        elif isinstance(t, ResultTypeName):
            if not isinstance(v, ResultValue):
                raise TypeCheckError(f"expected Result in {ctx}")
    def check_plain(self,v,name,ctx):
        if name in self.records:
            if not isinstance(v, RecordValue) or v.type_name != name: raise TypeCheckError(f"expected record {name} in {ctx}")
            for fname, ftype in self.records[name].fields.items(): self.check_plain(v.fields[fname], ftype, f"{ctx}.{fname}")
            return
        if name in self.types:
            td=self.types[name]
            if td.base=="Integer" and (not isinstance(v,int) or isinstance(v,bool)): raise TypeCheckError(f"Expected Integer in {ctx}")
            if td.base=="Boolean" and not isinstance(v,bool): raise TypeCheckError(f"Expected Boolean in {ctx}")
            if td.base=="Double" and (not isinstance(v,(int,float)) or isinstance(v,bool)): raise TypeCheckError(f"Expected Double in {ctx}")
            if td.base=="String" and not isinstance(v,str): raise TypeCheckError(f"Expected String in {ctx}")
            if td.base=="BigInteger" and not isinstance(v,BigIntegerValue): raise TypeCheckError(f"Expected BigInteger in {ctx}")
            if td.base=="BigFloat" and not isinstance(v,BigFloatValue): raise TypeCheckError(f"Expected BigFloat in {ctx}")
            if td.base in ("Integer", "Double"):
                if td.min_value is not None and v < td.min_value:
                    raise VerificationError(f"{ctx} below range {td.name}: {v} < {td.min_value}")
                if td.max_value is not None and v > td.max_value:
                    raise VerificationError(f"{ctx} above range {td.name}: {v} > {td.max_value}")
