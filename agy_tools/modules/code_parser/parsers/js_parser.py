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

def _find_nestjs_global_prefix(src_dir: str) -> str:
    """Discovers global prefix from main.ts / bootstrap files."""
    candidate_files = [
        "src/main.ts", "src/main.js", "main.ts", "main.js",
        "src/bootstrap.ts", "src/bootstrap.js", "src/index.ts", "src/index.js",
        "src/app.ts", "src/app.js", "src/server.ts", "src/server.js"
    ]
    found_files = []
    for rel in candidate_files:
        p = os.path.abspath(os.path.join(src_dir, rel))
        if os.path.isfile(p):
            found_files.append(p)

    for fpath in found_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            match = re.search(r"(?:app|server)\.setGlobalPrefix\s*\(\s*([^,\)]+)", content)
            if match:
                raw_arg = match.group(1).strip()
                str_match = re.match(r"^['\"`]([^'\"`]+)['\"`]$", raw_arg)
                if str_match:
                    return str_match.group(1).strip("/")
                str_in_expr = re.search(r"['\"`]([^'\"`]+)['\"`]", raw_arg)
                if str_in_expr:
                    return str_in_expr.group(1).strip("/")
        except Exception:
            pass
    return ""

def _build_express_mount_map(src_dir: str, files: List[str]) -> Dict[str, str]:
    """
    Builds router mount map mapping normalized absolute file paths
    to their URL mount prefixes.
    """
    raw_mounts: List[Tuple[str, str, str]] = []
    file_imports: Dict[str, Dict[str, str]] = {}

    for filepath in files:
        abs_file = os.path.abspath(filepath)
        file_dir = os.path.dirname(abs_file)

        try:
            with open(abs_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        current_imports: Dict[str, str] = {}

        # 1. require('./...')
        req_matches = re.finditer(
            r"(?:const|let|var)\s+(?:\{\s*(?:[A-Za-z0-9_$]+\s*:\s*)?([A-Za-z0-9_$]+)\s*\}|([A-Za-z0-9_$]+))\s*=\s*require\(\s*['\"`]([^'\"`]+)['\"`]\s*\)",
            content
        )
        for m in req_matches:
            var_name = m.group(1) or m.group(2)
            imp_path = m.group(3).strip()
            if imp_path.startswith("."):
                target_abs = os.path.abspath(os.path.join(file_dir, imp_path))
                current_imports[var_name] = target_abs

        # 2. import ... from './...'
        imp_matches = re.finditer(
            r"import\s+(?:(?:\*\s+as\s+)?([A-Za-z0-9_$]+)|\{\s*(?:[A-Za-z0-9_$]+\s+as\s+)?([A-Za-z0-9_$]+)\s*\})\s+from\s+['\"`]([^'\"`]+)['\"`]",
            content
        )
        for m in imp_matches:
            var_name = m.group(1) or m.group(2)
            imp_path = m.group(3).strip()
            if imp_path.startswith("."):
                target_abs = os.path.abspath(os.path.join(file_dir, imp_path))
                current_imports[var_name] = target_abs

        file_imports[abs_file] = current_imports

        # 3. app.use('/prefix', routerVar) or app.use('/prefix', require('./...'))
        use_matches = re.finditer(
            r"(?:app|router|server)\.use\(\s*['\"`]([^'\"`]+)['\"`]\s*,\s*(.*?)\)",
            content,
            re.DOTALL
        )
        for m in use_matches:
            mount_path = m.group(1).strip()
            args_part = m.group(2)

            inline_req = re.search(r"require\(\s*['\"`]([^'\"`]+)['\"`]\s*\)", args_part)
            if inline_req:
                imp_path = inline_req.group(1).strip()
                if imp_path.startswith("."):
                    target_abs = os.path.abspath(os.path.join(file_dir, imp_path))
                    raw_mounts.append((abs_file, mount_path, target_abs))
            else:
                for var_name, target_abs in current_imports.items():
                    if re.search(rf"\b{re.escape(var_name)}\b", args_part):
                        raw_mounts.append((abs_file, mount_path, target_abs))

    mount_map: Dict[str, str] = {}

    def register_aliases(target_abs: str, prefix: str):
        clean_p = "/" + prefix.strip("/") if prefix.strip("/") else ""
        norm_tgt = os.path.abspath(target_abs)
        mount_map[norm_tgt] = clean_p
        base_no_ext, ext = os.path.splitext(norm_tgt)
        mount_map[base_no_ext] = clean_p
        for candidate_ext in [".js", ".ts", ".mjs", ".cjs"]:
            mount_map[base_no_ext + candidate_ext] = clean_p
        mount_map[os.path.abspath(os.path.join(norm_tgt, "index.js"))] = clean_p
        mount_map[os.path.abspath(os.path.join(norm_tgt, "index.ts"))] = clean_p
        mount_map[os.path.abspath(os.path.join(base_no_ext, "index.js"))] = clean_p
        mount_map[os.path.abspath(os.path.join(base_no_ext, "index.ts"))] = clean_p

    # Multi-pass resolution for nested router mounts (up to 3 passes)
    for _ in range(3):
        for parent_file, mount_path, target_abs in raw_mounts:
            parent_prefix = mount_map.get(parent_file, "")
            combined_prefix = "/" + "/".join(filter(None, [parent_prefix.strip("/"), mount_path.strip("/")]))
            register_aliases(target_abs, combined_prefix)

    return mount_map

def scan_endpoints(file_path: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Scan endpoints in a single JS/TS file."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    mount_prefix = ""
    if context and "mount_map" in context:
        norm_file = os.path.abspath(abs_path)
        base_no_ext, _ = os.path.splitext(norm_file)
        mount_prefix = context["mount_map"].get(norm_file) or context["mount_map"].get(base_no_ext, "")

    endpoints: List[Dict[str, Any]] = []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    # Check for NestJS controller
    is_nestjs_controller = abs_path.endswith(".controller.ts") or abs_path.endswith(".controller.js")
    if is_nestjs_controller:
        controller_re = re.compile(r"@Controller\((?:['\"]([^'\"]*)['\"])?\)")
        method_re = re.compile(r"@(Get|Post|Put|Delete|Patch|Options|Head)\((?:['\"]([^'\"]*)['\"])?\)")
        func_re = re.compile(r"(?:async\s+)?([a-zA-Z0-9_]+)\s*\(")
        global_prefix = context.get("global_prefix", "") if context else ""

        base_route = ""
        for i, line in enumerate(lines):
            c_m = controller_re.search(line)
            if c_m:
                base_route = c_m.group(1) or ""
            m_m = method_re.search(line)
            if m_m:
                verb = m_m.group(1).upper()
                sub_path = m_m.group(2) or ""
                func_name = "handler"
                for next_line in lines[i+1:min(i+10, len(lines))]:
                    trimmed = next_line.strip()
                    if trimmed.startswith("@") or trimmed.startswith("//") or not trimmed:
                        continue
                    f_m = func_re.search(next_line)
                    if f_m and f_m.group(1) not in {"constructor", "if", "for", "while", "return"}:
                        func_name = f_m.group(1)
                        break

                clean_global = global_prefix.strip("/")
                clean_base = base_route.strip("/")
                clean_sub = sub_path.strip("/")
                parts = [clean_global, clean_base, clean_sub]
                full_path = "/" + "/".join(filter(None, parts))
                if full_path == "":
                    full_path = "/"

                endpoints.append({
                    "method": verb,
                    "path": full_path,
                    "file": abs_path,
                    "line": i + 1,
                    "handler": func_name
                })
        return _dedupe(endpoints)

    # Express & General Router matching
    express_re = re.compile(r"(?:app|router|server)\.(get|post|put|delete|patch|options|head|all)\s*\(\s*['\"`]([^'\"`]+)['\"`]", re.IGNORECASE)
    chain_route_re = re.compile(r"(?:app|router)\.route\s*\(\s*['\"`]([^'\"`]+)['\"`]\s*\)", re.IGNORECASE)
    chain_method_re = re.compile(r"\.(get|post|put|delete|patch|options|head|all)\s*\(", re.IGNORECASE)

    current_chain_path = None
    for i, line in enumerate(lines):
        # Chained router.route('/path').get(...).post(...)
        cm = chain_route_re.search(line)
        if cm:
            current_chain_path = cm.group(1)
        if current_chain_path:
            for meth_m in chain_method_re.finditer(line):
                verb = meth_m.group(1).upper()
                clean_mount = mount_prefix.strip("/")
                clean_route = current_chain_path.strip("/")
                if clean_mount:
                    if clean_route == clean_mount or clean_route.startswith(clean_mount + "/"):
                        full_path = "/" + clean_route
                    else:
                        full_path = "/" + "/".join(filter(None, [clean_mount, clean_route]))
                else:
                    full_path = "/" + clean_route if clean_route else "/"

                endpoints.append({
                    "method": verb,
                    "path": full_path,
                    "file": abs_path,
                    "line": i + 1,
                    "handler": "handler"
                })
            if ";" in line:
                current_chain_path = None

        # Standard app.get('/path', ...)
        m = express_re.search(line)
        if m:
            verb = m.group(1).upper()
            route_path = m.group(2)
            clean_mount = mount_prefix.strip("/")
            clean_route = route_path.strip("/")

            if clean_mount:
                if clean_route == clean_mount or clean_route.startswith(clean_mount + "/"):
                    full_path = "/" + clean_route
                else:
                    full_path = "/" + "/".join(filter(None, [clean_mount, clean_route]))
            else:
                full_path = "/" + clean_route if clean_route else "/"

            if full_path == "":
                full_path = "/"

            endpoints.append({
                "method": verb,
                "path": full_path,
                "file": abs_path,
                "line": i + 1,
                "handler": "handler"
            })

    return _dedupe(endpoints)

def scan_project_endpoints(project_path: str, files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Scans all endpoints in a JS/TS project resolving router mount prefixes."""
    abs_root = os.path.abspath(project_path)
    if files is None:
        files = []
        for root, dirs, f_names in os.walk(abs_root):
            dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "dist", "build", ".next", "__pycache__", ".agents", ".angular"]]
            for fn in f_names:
                if fn.endswith((".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx")) and not fn.endswith((".d.ts", ".min.js", ".bundle.js")):
                    files.append(os.path.abspath(os.path.join(root, fn)))


    mount_map = _build_express_mount_map(abs_root, files)
    global_prefix = _find_nestjs_global_prefix(abs_root)
    context = {"mount_map": mount_map, "global_prefix": global_prefix}

    all_endpoints = []
    for f in files:
        eps = scan_endpoints(f, context)
        all_endpoints.extend(eps)

    return _dedupe(all_endpoints)

def scan_symbols(file_path: str) -> List[Dict[str, Any]]:
    """Extract ctags symbols from a JS/TS file."""
    return get_symbols(file_path)

def get_symbols(file_path: str) -> List[Dict[str, Any]]:
    """Extract ctags symbols conforming to function|class|variable|method."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return []

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    symbols: List[Dict[str, Any]] = []

    class_re = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([a-zA-Z0-9_$]+)")
    iface_re = re.compile(r"^(?:export\s+)?interface\s+([a-zA-Z0-9_$]+)")
    type_re = re.compile(r"^(?:export\s+)?type\s+([a-zA-Z0-9_$]+)\s*=")
    func_re = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(")
    arrow_re = re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")
    method_re = re.compile(r"^\s*(?:(?:public|private|protected|static|readonly|override|async)\s+)*([a-zA-Z0-9_$]+)\s*\([^)]*\)\s*(?::\s*[^{;]+)?\s*\{")
    var_re = re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=")

    in_class_depth = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Track class boundaries simply
        c_m = class_re.search(stripped)
        if c_m:
            symbols.append({
                "name": c_m.group(1),
                "kind": "class",
                "file": abs_path,
                "line": idx + 1
            })
            in_class_depth += 1
            continue

        i_m = iface_re.search(stripped)
        if i_m:
            symbols.append({
                "name": i_m.group(1),
                "kind": "class",
                "file": abs_path,
                "line": idx + 1
            })
            continue

        t_m = type_re.search(stripped)
        if t_m:
            symbols.append({
                "name": t_m.group(1),
                "kind": "variable",
                "file": abs_path,
                "line": idx + 1
            })
            continue

        f_m = func_re.search(stripped)
        if f_m:
            symbols.append({
                "name": f_m.group(1),
                "kind": "function",
                "file": abs_path,
                "line": idx + 1
            })
            continue

        a_m = arrow_re.search(stripped)
        if a_m:
            symbols.append({
                "name": a_m.group(1),
                "kind": "function",
                "file": abs_path,
                "line": idx + 1
            })
            continue

        # Class method check
        m_m = method_re.search(line)
        if m_m:
            name = m_m.group(1)
            if name not in {"if", "for", "while", "switch", "catch", "return", "function", "constructor"}:
                symbols.append({
                    "name": name,
                    "kind": "method",
                    "file": abs_path,
                    "line": idx + 1
                })
                continue

        # Top-level variable
        if not line.startswith(" ") and not line.startswith("\t"):
            v_m = var_re.search(stripped)
            if v_m:
                v_name = v_m.group(1)
                symbols.append({
                    "name": v_name,
                    "kind": "variable",
                    "file": abs_path,
                    "line": idx + 1
                })

    return _dedupe(symbols, key_fields=("name", "kind", "file", "line"))
