from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

from freehold.core.diagnostics import diagnose_exception
from freehold.core.module_resolver import ModuleResolver
from freehold.core.parser import parse_source
from freehold.core.verifier import verify_program

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LANGUAGE_MODULES_ROOT = PROJECT_ROOT / "tests" / "language_modules"

def canonical(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [canonical(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): canonical(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if hasattr(obj, "__dataclass_fields__"):
        result = {"node": type(obj).__name__}
        for name in obj.__dataclass_fields__:
            if name == "pos":
                continue
            if name == "aborts" and not getattr(obj, name):
                continue
            result[name] = canonical(getattr(obj, name))
        return result
    return repr(obj)

def normalize(s: str) -> str:
    return s.strip().replace("\r\n", "\n")

def parse_and_verify(source: str):
    ast = parse_source(source)
    verified = verify_program(ast)
    return ast, verified

def resolve_fixture(module_dir: Path, case: dict):
    root = module_dir / case["root"]
    entry = root / case["entry"]
    return ModuleResolver().resolve_entry(entry)

def run_case(module_dir: Path, case: dict, update: bool = False):
    kind = case["kind"]

    if kind == "valid":
        source = (module_dir / case["file"]).read_text(encoding="utf-8")
        ast, _ = parse_and_verify(source)
        actual = json.dumps(canonical(ast), indent=2, sort_keys=True)
        expected_path = module_dir / case["expected_ast"]
        if update or not expected_path.exists():
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(actual + "\n", encoding="utf-8")
        expected = expected_path.read_text(encoding="utf-8")
        if normalize(actual) != normalize(expected):
            return False, f"AST mismatch: {case['name']}"
        return True, f"valid OK: {case['name']}"

    if kind in {"invalid_syntax", "invalid_semantics"}:
        source = (module_dir / case["file"]).read_text(encoding="utf-8")
        try:
            parse_and_verify(source)
        except Exception as exc:
            diag = diagnose_exception(source, exc).format()
            expected_path = module_dir / case["expected_error"]
            if update or not expected_path.exists():
                expected_path.parent.mkdir(parents=True, exist_ok=True)
                expected_path.write_text(diag + "\n", encoding="utf-8")
            expected = expected_path.read_text(encoding="utf-8")
            if normalize(diag) != normalize(expected):
                return False, f"Diagnostic mismatch: {case['name']}\n--- actual ---\n{diag}\n--- expected ---\n{expected}"
            return True, f"{kind} OK: {case['name']}"
        return False, f"Expected failure but passed: {case['name']}"

    if kind == "valid_resolution":
        resolved = resolve_fixture(module_dir, case)
        actual = json.dumps(sorted(resolved), indent=2)
        expected_path = module_dir / case["expected_modules"]
        if update or not expected_path.exists():
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(actual + "\n", encoding="utf-8")
        expected = expected_path.read_text(encoding="utf-8")
        if normalize(actual) != normalize(expected):
            return False, f"Resolved module mismatch: {case['name']}"
        return True, f"valid_resolution OK: {case['name']}"

    if kind == "invalid_resolution":
        try:
            resolve_fixture(module_dir, case)
        except Exception as exc:
            entry_source = (module_dir / case["root"] / case["entry"]).read_text(encoding="utf-8")
            diag = diagnose_exception(entry_source, exc).format()
            expected_path = module_dir / case["expected_error"]
            if update or not expected_path.exists():
                expected_path.parent.mkdir(parents=True, exist_ok=True)
                expected_path.write_text(diag + "\n", encoding="utf-8")
            expected = expected_path.read_text(encoding="utf-8")
            if normalize(diag) != normalize(expected):
                return False, f"Diagnostic mismatch: {case['name']}\n--- actual ---\n{diag}\n--- expected ---\n{expected}"
            return True, f"invalid_resolution OK: {case['name']}"
        return False, f"Expected resolution failure but passed: {case['name']}"

    return False, f"Unknown case kind: {kind}"

def iter_modules(selected: str | None):
    dirs = [LANGUAGE_MODULES_ROOT / selected] if selected else [p for p in sorted(LANGUAGE_MODULES_ROOT.iterdir()) if p.is_dir()]
    for d in dirs:
        manifest = d / "manifest.json"
        if manifest.exists():
            yield d, json.loads(manifest.read_text(encoding="utf-8"))

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run Freehold modular language conformance tests")
    ap.add_argument("--module", default=None)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--json-summary", default=None)
    args = ap.parse_args(argv)

    total = passed = 0
    failures = []
    modules = {}
    for module_dir, manifest in iter_modules(args.module):
        name = module_dir.name
        modules[name] = {"passed": 0, "total": 0}
        print(f"\n[{name}] {manifest.get('title', name)}")
        for case in manifest.get("cases", []):
            total += 1
            modules[name]["total"] += 1
            ok, msg = run_case(module_dir, case, args.update)
            if ok:
                passed += 1
                modules[name]["passed"] += 1
                print(f"  [OK] {msg}")
            else:
                failures.append(msg)
                print(f"  [FAIL] {msg}")

    print("")
    for name, data in modules.items():
        print(f"{name}: {data['passed']}/{data['total']}")
    print(f"{passed}/{total} language module tests passed")

    if args.json_summary:
        Path(args.json_summary).write_text(json.dumps({"passed": passed, "total": total, "modules": modules, "failures": failures}, indent=2), encoding="utf-8")
    return 0 if not failures else 1

if __name__ == "__main__":
    raise SystemExit(main())
