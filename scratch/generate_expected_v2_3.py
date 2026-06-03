import json
from pathlib import Path

def main():
    root = Path("d:/works/Work-VeraFlow/freehold/.tmp/go-semantic-v2_3")
    cases = {}
    for path in sorted(root.glob("**/*.json")):
        rel = path.relative_to(root)
        rel_str = str(rel).replace("\\", "/")
        if "invalid_semantics" not in rel_str:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("semantic_run"):
            continue
        diagnostics = data.get("semantic_diagnostics", [])
        diag = None
        if len(diagnostics) == 1:
            diag = diagnostics[0]
        elif len(diagnostics) > 1:
            for d in diagnostics:
                code = d.get("code", "")
                if "alias" in rel_str and code == "FH-CON-3013":
                    diag = d
                    break
                if "unused_target" in rel_str and code == "FH-CON-3010":
                    diag = d
                    break
                if "function_missing_result" in rel_str and code == "FH-CON-3011":
                    diag = d
                    break
                if "invalid_dependency_source" in rel_str and (code == "FH-CON-3007" or code == "FH-CON-3006"):
                    diag = d
                    break
            if diag is None:
                diag = diagnostics[0]

        if diag is not None:
            cases[rel_str] = {
                "code": diag.get("code"),
                "name": diag.get("name"),
                "location": {
                    "line": diag.get("location", {}).get("line"),
                    "column": diag.get("location", {}).get("column")
                },
                "expected": diag.get("expected"),
                "found": diag.get("found")
            }
    
    out_path = Path("d:/works/Work-VeraFlow/freehold/tests/language_modules_v2_3/expected_go_semantic_diagnostics.json")
    out_path.write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")
    print(f"Generated {out_path} with {len(cases)} cases.")

if __name__ == "__main__":
    main()
