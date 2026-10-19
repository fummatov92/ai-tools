import os
import re
from typing import List, Dict, Any, Optional, Set, Tuple

def _dedupe(items: List[Dict[str, Any]], key_fields: tuple = ("method", "path", "file", "line")) -> List[Dict[str, Any]]:
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
    """Extract ctags symbols (function, class, method, variable) from a PHP source file."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    symbols: List[Dict[str, Any]] = []

    class_re = re.compile(r"^(?:abstract\s+|final\s+)?(class|interface|trait)\s+([a-zA-Z0-9_]+)")
    func_re = re.compile(r"^\s*(?:(?:public|private|protected|static|final)\s+)*function\s+([a-zA-Z0-9_]+)\s*\(")
    const_re = re.compile(r"^\s*const\s+([a-zA-Z0-9_]+)\s*=")

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
            continue

        c_m = class_re.match(stripped)
        if c_m:
            symbols.append({
                "name": c_m.group(2),
                "kind": "class",
                "file": abs_path,
                "line": idx + 1
            })
            continue

        f_m = func_re.match(line)
        if f_m:
            name = f_m.group(1)
            # If line is indented or has visibility keywords, it's a method
            is_method = (line.startswith(" ") or line.startswith("\t") or
                         any(vis in line for vis in ["public", "protected", "private"]))
            kind = "method" if is_method else "function"
            symbols.append({
                "name": name,
                "kind": kind,
                "file": abs_path,
                "line": idx + 1
            })
            continue

        k_m = const_re.match(stripped)
        if k_m:
            symbols.append({
                "name": k_m.group(1),
                "kind": "variable",
                "file": abs_path,
                "line": idx + 1
            })

    return _dedupe(symbols, key_fields=("name", "kind", "file", "line"))

def scan_symbols(file_path: str) -> List[Dict[str, Any]]:
    """Alias to get_symbols to satisfy Interface Contracts."""
    return get_symbols(file_path)

def scan_endpoints(file_path: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Scan endpoints in a single PHP file (Laravel, Symfony)."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    endpoints: List[Dict[str, Any]] = []

    # 1. Laravel Route::get/post/put/delete/patch
    laravel_route_re = re.compile(
        r"Route::(get|post|put|delete|patch|options|any)\s*\(\s*['\"]([^'\"]*)['\"](?:\s*,\s*(?:\[\s*([A-Za-z0-9_]+)::class|\s*['\"]?([^'\",\)]+)['\"]?))?",
        re.IGNORECASE
    )

    # 2. Laravel Route::match(['get', 'post'], ...)
    laravel_match_re = re.compile(
        r"Route::match\s*\(\s*\[([^\]]+)\]\s*,\s*['\"]([^'\"]*)['\"]",
        re.IGNORECASE
    )

    # 3. Laravel Route::apiResource('posts', PostController::class)
    laravel_resource_re = re.compile(
        r"Route::(?:apiResource|resource)\s*\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE
    )

    # 4. Symfony #[Route('/path', methods: ['GET'])]
    symfony_attr_re = re.compile(
        r"#\[Route\s*\(\s*['\"]([^'\"]+)['\"](?:.*methods:\s*\[([^\]]+)\])?",
        re.IGNORECASE
    )

    # Track prefix groups
    prefix_group_re = re.compile(r"Route::prefix\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
    current_prefix = ""

    for i, line in enumerate(lines):
        pm = prefix_group_re.search(line)
        if pm:
            current_prefix = pm.group(1).strip("/")

        # Standard Route::verb
        for rm in laravel_route_re.finditer(line):
            method = rm.group(1).upper()
            if method == "ANY":
                method = "GET"
            sub_path = rm.group(2).strip("/")
            handler = rm.group(3) or rm.group(4) or "handler"

            full_path = "/" + "/".join(filter(None, [current_prefix, sub_path]))
            if full_path == "":
                full_path = "/"

            endpoints.append({
                "method": method,
                "path": full_path,
                "file": abs_path,
                "line": i + 1,
                "handler": handler.strip("'\"")
            })

        # Route::match
        for mm in laravel_match_re.finditer(line):
            verbs = [v.strip().strip("'\"").upper() for v in mm.group(1).split(",") if v.strip()]
            sub_path = mm.group(2).strip("/")
            full_path = "/" + "/".join(filter(None, [current_prefix, sub_path]))
            if full_path == "":
                full_path = "/"
            for v in verbs:
                endpoints.append({
                    "method": v,
                    "path": full_path,
                    "file": abs_path,
                    "line": i + 1,
                    "handler": "handler"
                })

        # Route::resource
        for res_m in laravel_resource_re.finditer(line):
            base_res = res_m.group(1).strip("/")
            full_base = "/" + "/".join(filter(None, [current_prefix, base_res]))
            resource_actions = [
                ("GET", full_base),
                ("POST", full_base),
                ("GET", f"{full_base}/{{id}}"),
                ("PUT", f"{full_base}/{{id}}"),
                ("DELETE", f"{full_base}/{{id}}")
            ]
            for verb, rpath in resource_actions:
                endpoints.append({
                    "method": verb,
                    "path": rpath,
                    "file": abs_path,
                    "line": i + 1,
                    "handler": "resource"
                })

        # Symfony #[Route]
        for sm in symfony_attr_re.finditer(line):
            rpath = sm.group(1).strip("/")
            methods_raw = sm.group(2)
            verbs = ["GET"]
            if methods_raw:
                verbs = [v.strip().strip("'\"").upper() for v in methods_raw.split(",") if v.strip()]
            full_path = "/" + rpath
            for v in verbs:
                endpoints.append({
                    "method": v,
                    "path": full_path,
                    "file": abs_path,
                    "line": i + 1,
                    "handler": "controller"
                })

    return _dedupe(endpoints, key_fields=("method", "path", "file", "line"))

def scan_project_endpoints(project_path: str, files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Scan all endpoints across PHP files in project."""
    abs_root = os.path.abspath(project_path)
    if files is None:
        files = []
        for root, dirs, f_names in os.walk(abs_root):
            dirs[:] = [d for d in dirs if d not in ["vendor", ".git", "storage"]]
            for fn in f_names:
                if fn.endswith(".php"):
                    files.append(os.path.abspath(os.path.join(root, fn)))

    all_endpoints = []
    for f in files:
        if f.endswith(".php"):
            all_endpoints.extend(scan_endpoints(f))
    return _dedupe(all_endpoints, key_fields=("method", "path", "file", "line"))
