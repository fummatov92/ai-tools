import os
import ast
import re
from typing import List, Dict, Any, Optional, Set, Tuple

def _dedupe(items: List[Dict[str, Any]], key_fields: tuple = ("name", "kind", "file", "line")) -> List[Dict[str, Any]]:
    """Deduplicates items preserving original order."""
    seen = set()
    result = []
    for item in items:
        key = tuple(item.get(k) for k in key_fields)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

def get_symbols(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract symbols (function, class, method, variable) using Python's stdlib ast.
    Falls back gracefully to regex on SyntaxError.
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return []

    symbols: List[Dict[str, Any]] = []

    try:
        tree = ast.parse(content, filename=abs_path)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.append({
                    "name": node.name,
                    "kind": "class",
                    "file": abs_path,
                    "line": node.lineno
                })
                # Methods inside class
                for sub_node in node.body:
                    if isinstance(sub_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append({
                            "name": sub_node.name,
                            "kind": "method",
                            "file": abs_path,
                            "line": sub_node.lineno
                        })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append({
                    "name": node.name,
                    "kind": "function",
                    "file": abs_path,
                    "line": node.lineno
                })
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.append({
                            "name": target.id,
                            "kind": "variable",
                            "file": abs_path,
                            "line": node.lineno
                        })
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    symbols.append({
                        "name": node.target.id,
                        "kind": "variable",
                        "file": abs_path,
                        "line": node.lineno
                    })
    except SyntaxError:
        # Fallback to line-by-line regex if file cannot be parsed with AST
        lines = content.splitlines()
        class_re = re.compile(r"^class\s+([a-zA-Z0-9_]+)(?:\(([^)]*)\))?:")
        def_re = re.compile(r"^\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\(")
        var_re = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=")

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            c_m = class_re.match(line)
            if c_m:
                symbols.append({
                    "name": c_m.group(1),
                    "kind": "class",
                    "file": abs_path,
                    "line": idx + 1
                })
                continue

            d_m = def_re.match(line)
            if d_m:
                kind = "method" if (line.startswith(" ") or line.startswith("\t")) else "function"
                symbols.append({
                    "name": d_m.group(1),
                    "kind": kind,
                    "file": abs_path,
                    "line": idx + 1
                })
                continue

            if not line.startswith(" ") and not line.startswith("\t"):
                v_m = var_re.match(line)
                if v_m:
                    symbols.append({
                        "name": v_m.group(1),
                        "kind": "variable",
                        "file": abs_path,
                        "line": idx + 1
                    })

    return _dedupe(symbols, key_fields=("name", "kind", "file", "line"))

def scan_symbols(file_path: str) -> List[Dict[str, Any]]:
    """Alias to get_symbols to satisfy Interface Contracts."""
    return get_symbols(file_path)

def scan_endpoints(file_path: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Scan endpoints in a single Python file (FastAPI, Flask, Django)."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    endpoints: List[Dict[str, Any]] = []

    # 1. FastAPI decorator: @app.get('/path'), @router.post('/path')
    fastapi_re = re.compile(
        r"@(?:[A-Za-z0-9_]+)\.(get|post|put|delete|patch|options|head)\s*\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE
    )

    # 2. Flask decorator: @app.route('/path', methods=['GET', 'POST'])
    flask_route_re = re.compile(
        r"@(?:[A-Za-z0-9_]+)\.route\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?",
        re.IGNORECASE
    )

    # 3. Django urlpatterns: path('route/', view), re_path(r'^route/', view)
    django_path_re = re.compile(
        r"(?:path|re_path|url)\s*\(\s*r?['\"]([^'\"]*)['\"]",
        re.IGNORECASE
    )

    func_def_re = re.compile(r"^\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\(")

    for i, line in enumerate(lines):
        # FastAPI
        f_m = fastapi_re.search(line)
        if f_m:
            method = f_m.group(1).upper()
            route_path = f_m.group(2)
            if not route_path.startswith("/"):
                route_path = "/" + route_path
            handler_name = "handler"
            for next_line in lines[i+1:min(i+6, len(lines))]:
                h_m = func_def_re.search(next_line)
                if h_m:
                    handler_name = h_m.group(1)
                    break
            endpoints.append({
                "method": method,
                "path": route_path,
                "file": abs_path,
                "line": i + 1,
                "handler": handler_name
            })
            continue

        # Flask
        fl_m = flask_route_re.search(line)
        if fl_m:
            route_path = fl_m.group(1)
            if not route_path.startswith("/"):
                route_path = "/" + route_path
            raw_methods = fl_m.group(2)
            methods = ["GET"]
            if raw_methods:
                methods = [m.strip().strip("'\"").upper() for m in raw_methods.split(",") if m.strip()]
            handler_name = "handler"
            for next_line in lines[i+1:min(i+6, len(lines))]:
                h_m = func_def_re.search(next_line)
                if h_m:
                    handler_name = h_m.group(1)
                    break
            for method in methods:
                endpoints.append({
                    "method": method,
                    "path": route_path,
                    "file": abs_path,
                    "line": i + 1,
                    "handler": handler_name
                })
            continue

        # Django urls.py
        if "urls.py" in abs_path or "urlpatterns" in line:
            dj_m = django_path_re.search(line)
            if dj_m:
                route_path = dj_m.group(1)
                clean_path = "/" + route_path.lstrip("^").rstrip("$").strip("/")
                if clean_path == "":
                    clean_path = "/"
                endpoints.append({
                    "method": "ANY",
                    "path": clean_path,
                    "file": abs_path,
                    "line": i + 1,
                    "handler": "view"
                })

    return _dedupe(endpoints, key_fields=("method", "path", "file", "line"))

def scan_project_endpoints(project_path: str, files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Scan all endpoints across Python files in project."""
    abs_root = os.path.abspath(project_path)
    if files is None:
        files = []
        for root, dirs, f_names in os.walk(abs_root):
            dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "dist", "build", ".next", "__pycache__", ".agents", "venv", ".venv"]]
            for fn in f_names:
                if fn.endswith(".py"):
                    files.append(os.path.abspath(os.path.join(root, fn)))

    all_endpoints = []
    for f in files:
        if f.endswith(".py"):
            all_endpoints.extend(scan_endpoints(f))
    return _dedupe(all_endpoints, key_fields=("method", "path", "file", "line"))
