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
    """Extract ctags symbols (function, class, method, variable) from C/C++ source files."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    symbols: List[Dict[str, Any]] = []

    class_re = re.compile(r"^\s*(?:template\s*<[^>]*>\s*)?(?:class|struct)\s+([a-zA-Z0-9_]+)(?:\s*:\s*[^{]+)?\s*\{?")
    method_def_re = re.compile(r"^(?:[a-zA-Z0-9_:\*<>\s]+)\s+([a-zA-Z0-9_]+)::([a-zA-Z0-9_]+)\s*\([^)]*\)\s*(?:const)?\s*\{")
    func_def_re = re.compile(r"^(?:[a-zA-Z0-9_:\*<>\s]+)\s+([a-zA-Z0-9_]+)\s*\([^)]*\)\s*(?:const)?\s*\{")
    macro_re = re.compile(r"^\s*#\s*define\s+([a-zA-Z0-9_]+)(?:\([^)]*\))?")
    const_var_re = re.compile(r"^\s*(?:static\s+)?(?:const|constexpr)\s+[a-zA-Z0-9_:\*<>\s]+\s+([a-zA-Z0-9_]+)\s*=")

    RESERVED = {"if", "for", "while", "switch", "catch", "return", "sizeof", "case", "typedef"}

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        c_m = class_re.match(stripped)
        if c_m:
            c_name = c_m.group(1)
            if c_name not in RESERVED:
                symbols.append({
                    "name": c_name,
                    "kind": "class",
                    "file": abs_path,
                    "line": idx + 1
                })
                continue

        m_m = method_def_re.match(line)
        if m_m:
            cls, meth = m_m.group(1), m_m.group(2)
            if meth not in RESERVED:
                symbols.append({
                    "name": f"{cls}::{meth}",
                    "kind": "method",
                    "file": abs_path,
                    "line": idx + 1
                })
                continue

        f_m = func_def_re.match(line)
        if f_m:
            name = f_m.group(1)
            if name not in RESERVED:
                symbols.append({
                    "name": name,
                    "kind": "function",
                    "file": abs_path,
                    "line": idx + 1
                })
                continue

        mac_m = macro_re.match(stripped)
        if mac_m:
            symbols.append({
                "name": mac_m.group(1),
                "kind": "variable",
                "file": abs_path,
                "line": idx + 1
            })
            continue

        cv_m = const_var_re.match(stripped)
        if cv_m:
            symbols.append({
                "name": cv_m.group(1),
                "kind": "variable",
                "file": abs_path,
                "line": idx + 1
            })

    return _dedupe(symbols, key_fields=("name", "kind", "file", "line"))

def scan_symbols(file_path: str) -> List[Dict[str, Any]]:
    """Alias to get_symbols to satisfy Interface Contracts."""
    return get_symbols(file_path)

def scan_endpoints(file_path: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Scan endpoints in C/C++ web frameworks (Crow, Pistache, Drogon, Oatpp)."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    endpoints: List[Dict[str, Any]] = []

    # Crow: CROW_ROUTE(app, "/path").methods("POST"_method, ...)
    crow_re = re.compile(
        r"CROW_ROUTE\s*\(\s*[a-zA-Z0-9_]+\s*,\s*['\"]([^'\"]+)['\"]\s*\)(?:\.methods\s*\(([^)]+)\))?",
        re.IGNORECASE
    )

    # Pistache: Routes::Get(router, "/path", ...)
    pistache_re = re.compile(
        r"Routes::(Get|Post|Put|Delete)\s*\(\s*[a-zA-Z0-9_]+\s*,\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE
    )

    # Drogon: registerHandler("/path", ...)
    drogon_re = re.compile(
        r"registerHandler\s*\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE
    )

    # Oatpp: ENDPOINT("GET", "/path", ...)
    oatpp_re = re.compile(
        r"ENDPOINT\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE
    )

    for i, line in enumerate(lines):
        # Crow
        for cm in crow_re.finditer(line):
            rpath = cm.group(1)
            raw_methods = cm.group(2)
            method = "GET"
            if raw_methods:
                if "POST" in raw_methods.upper():
                    method = "POST"
                elif "PUT" in raw_methods.upper():
                    method = "PUT"
                elif "DELETE" in raw_methods.upper():
                    method = "DELETE"
            endpoints.append({
                "method": method,
                "path": rpath if rpath.startswith("/") else "/" + rpath,
                "file": abs_path,
                "line": i + 1,
                "handler": "handler"
            })

        # Pistache
        for pm in pistache_re.finditer(line):
            verb = pm.group(1).upper()
            rpath = pm.group(2)
            endpoints.append({
                "method": verb,
                "path": rpath if rpath.startswith("/") else "/" + rpath,
                "file": abs_path,
                "line": i + 1,
                "handler": "handler"
            })

        # Drogon
        for dm in drogon_re.finditer(line):
            rpath = dm.group(1)
            endpoints.append({
                "method": "ANY",
                "path": rpath if rpath.startswith("/") else "/" + rpath,
                "file": abs_path,
                "line": i + 1,
                "handler": "handler"
            })

        # Oatpp
        for om in oatpp_re.finditer(line):
            verb = om.group(1).upper()
            rpath = om.group(2)
            endpoints.append({
                "method": verb,
                "path": rpath if rpath.startswith("/") else "/" + rpath,
                "file": abs_path,
                "line": i + 1,
                "handler": "handler"
            })

    return _dedupe(endpoints, key_fields=("method", "path", "file", "line"))

def scan_project_endpoints(project_path: str, files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Scan all endpoints across C/C++ files in project."""
    abs_root = os.path.abspath(project_path)
    if files is None:
        files = []
        for root, dirs, f_names in os.walk(abs_root):
            dirs[:] = [d for d in dirs if d not in [".git", "build", "CMakeFiles"]]
            for fn in f_names:
                if fn.endswith((".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh")):
                    files.append(os.path.abspath(os.path.join(root, fn)))

    all_endpoints = []
    for f in files:
        if f.endswith((".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh")):
            all_endpoints.extend(scan_endpoints(f))
    return _dedupe(all_endpoints, key_fields=("method", "path", "file", "line"))
