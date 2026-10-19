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
    """Extract ctags symbols (function, class, method, variable) from a Go source file."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    symbols: List[Dict[str, Any]] = []

    type_re = re.compile(r"^type\s+([a-zA-Z0-9_]+)\s+(struct|interface)")
    func_re = re.compile(r"^func\s+(?:\(([^)]+)\)\s+)?([a-zA-Z0-9_]+)\s*\(")
    var_re = re.compile(r"^(?:var|const)\s+([a-zA-Z0-9_]+)\s*(?:[a-zA-Z0-9_\[\]\*]+\s*)?=")
    var_block_re = re.compile(r"^(?:var|const)\s*\(")

    in_var_block = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if var_block_re.match(stripped):
            in_var_block = True
            continue

        if in_var_block:
            if stripped == ")":
                in_var_block = False
                continue
            item_m = re.match(r"^([a-zA-Z0-9_]+)", stripped)
            if item_m:
                symbols.append({
                    "name": item_m.group(1),
                    "kind": "variable",
                    "file": abs_path,
                    "line": idx + 1
                })
            continue

        t_m = type_re.match(stripped)
        if t_m:
            symbols.append({
                "name": t_m.group(1),
                "kind": "class",
                "file": abs_path,
                "line": idx + 1
            })
            continue

        f_m = func_re.match(stripped)
        if f_m:
            receiver, name = f_m.group(1), f_m.group(2)
            kind = "method" if receiver else "function"
            symbols.append({
                "name": name,
                "kind": kind,
                "file": abs_path,
                "line": idx + 1
            })
            continue

        v_m = var_re.match(stripped)
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
    """Scan endpoints in a single Go file (Gin, Fiber, Chi, Echo, net/http)."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    endpoints: List[Dict[str, Any]] = []

    # Detect route groups within the file
    group_re = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=)\s*[A-Za-z_][A-Za-z0-9_]*\.Group\(\s*['\"]([^'\"]+)['\"]")
    group_prefixes: Dict[str, str] = {}
    for line in lines:
        for gm in group_re.finditer(line):
            group_prefixes[gm.group(1)] = gm.group(2)

    # Gin, Fiber, Chi: r.GET('/path', handler), app.Post('/path', handler)
    route_re = re.compile(
        r"([A-Za-z_][A-Za-z0-9_]*)\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|Get|Post|Put|Delete|Patch|Options|Head|Any)"
        r"\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*([A-Za-z0-9_.]+))?",
        re.IGNORECASE
    )

    # net/http HandleFunc
    http_re = re.compile(
        r"(?:http|mux|[A-Za-z_][A-Za-z0-9_]*)\.HandleFunc\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*([A-Za-z0-9_.]+))?"
    )

    for i, line in enumerate(lines):
        for rm in route_re.finditer(line):
            receiver = rm.group(1)
            method = rm.group(2).upper()
            if method == "ANY":
                method = "GET"
            sub_path = rm.group(3)
            handler = rm.group(4) or "handler"

            parent_prefix = group_prefixes.get(receiver, "")
            clean_parent = parent_prefix.strip("/")
            clean_sub = sub_path.strip("/")
            full_path = "/" + "/".join(filter(None, [clean_parent, clean_sub]))
            if full_path == "":
                full_path = "/"

            endpoints.append({
                "method": method,
                "path": full_path,
                "file": abs_path,
                "line": i + 1,
                "handler": handler
            })

        for hm in http_re.finditer(line):
            sub_path = hm.group(1)
            handler = hm.group(2) or "handler"
            clean_path = "/" + sub_path.strip("/")
            if clean_path == "":
                clean_path = "/"
            endpoints.append({
                "method": "GET",
                "path": clean_path,
                "file": abs_path,
                "line": i + 1,
                "handler": handler
            })

    return _dedupe(endpoints, key_fields=("method", "path", "file", "line"))

def scan_project_endpoints(project_path: str, files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Scan all endpoints across Go files in project."""
    abs_root = os.path.abspath(project_path)
    if files is None:
        files = []
        for root, dirs, f_names in os.walk(abs_root):
            dirs[:] = [d for d in dirs if d not in ["vendor", ".git", "bin"]]
            for fn in f_names:
                if fn.endswith(".go") and not fn.endswith("_test.go"):
                    files.append(os.path.abspath(os.path.join(root, fn)))

    all_endpoints = []
    for f in files:
        if f.endswith(".go") and not f.endswith("_test.go"):
            all_endpoints.extend(scan_endpoints(f))
    return _dedupe(all_endpoints, key_fields=("method", "path", "file", "line"))
