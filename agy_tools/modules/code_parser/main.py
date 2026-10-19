import os
import sys
import json
import argparse
from typing import Dict, Any, List, Optional

import finder
import detector
from parsers import js_parser, py_parser, go_parser, php_parser, c_parser

CONFIG_NAMES = {
    "package.json", "tsconfig.json", "nest-cli.json", "angular.json",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "schema.prisma",
    "requirements.txt", "pyproject.toml", "pipfile", "setup.py",
    "go.mod", "go.sum", "composer.json", "composer.lock",
    "cmakelists.txt", "makefile", "meson.build"
}

KEY_COMPONENT_SUFFIXES = (
    ".module.ts", ".service.ts", ".controller.ts", ".resolver.ts", ".routes.ts",
    "main.ts", "app.ts", "server.ts", ".component.ts",
    "server.js", "app.js", "main.js", "index.js",
    "main.py", "app.py", "wsgi.py", "asgi.py", "manage.py",
    "main.go", "app.go",
    "artisan", "index.php",
    "main.c", "main.cpp", "app.cpp"
)

def emit_output(data: Any, success: bool = True, error: Optional[str] = None, raw: bool = False):
    """Outputs JSON payload to stdout with optional envelope."""
    if raw:
        payload = data if success else {"error": error}
    else:
        payload = {
            "success": success,
            "data": data if success else None,
            "error": error
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def run_blueprint(target_path: str, raw: bool = False) -> int:
    abs_target = os.path.abspath(os.path.expanduser(target_path))
    if not os.path.exists(abs_target):
        emit_output(None, success=False, error=f"Target path does not exist: {abs_target}", raw=raw)
        return 1

    framework_meta = detector.detect_framework(abs_target)
    all_files = finder.find_files(abs_target, max_files=5000)

    config_files = []
    key_components = []

    for fpath in all_files:
        fname_lower = os.path.basename(fpath).lower()
        if fname_lower in CONFIG_NAMES:
            config_files.append(fpath)

        for suffix in KEY_COMPONENT_SUFFIXES:
            if fname_lower == suffix or fname_lower.endswith(suffix):
                key_components.append(fpath)
                break

    data = {
        "project_path": abs_target,
        "framework": framework_meta,
        "config_files": config_files,
        "core_components_count": len(key_components),
        "key_components": key_components[:50]
    }
    emit_output(data, success=True, raw=raw)
    return 0

def run_endpoints(target_path: str, raw: bool = False) -> int:
    abs_target = os.path.abspath(os.path.expanduser(target_path))
    if not os.path.exists(abs_target):
        emit_output(None, success=False, error=f"Target path does not exist: {abs_target}", raw=raw)
        return 1

    framework_meta = detector.detect_framework(abs_target)

    # Discover source files
    candidate_exts = [
        ".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx",
        ".py", ".go", ".php",
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"
    ]
    all_files = finder.find_files(abs_target, extensions=candidate_exts, max_files=5000)

    js_files = [f for f in all_files if f.endswith((".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx")) and not f.endswith((".d.ts", ".min.js"))]
    py_files = [f for f in all_files if f.endswith(".py")]
    go_files = [f for f in all_files if f.endswith(".go") and not f.endswith("_test.go")]
    php_files = [f for f in all_files if f.endswith(".php")]
    c_files = [f for f in all_files if f.endswith((".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"))]

    endpoints = []

    if js_files:
        endpoints.extend(js_parser.scan_project_endpoints(abs_target, js_files))
    if py_files:
        endpoints.extend(py_parser.scan_project_endpoints(abs_target, py_files))
    if go_files:
        endpoints.extend(go_parser.scan_project_endpoints(abs_target, go_files))
    if php_files:
        endpoints.extend(php_parser.scan_project_endpoints(abs_target, php_files))
    if c_files:
        endpoints.extend(c_parser.scan_project_endpoints(abs_target, c_files))

    # Generic dedupe
    unique_endpoints = js_parser._dedupe(endpoints, key_fields=("method", "path", "file", "line"))

    data = {
        "project_path": abs_target,
        "framework": framework_meta,
        "total_endpoints": len(unique_endpoints),
        "endpoints": unique_endpoints
    }
    emit_output(data, success=True, raw=raw)
    return 0

def run_symbols(target_path: str, raw: bool = False) -> int:
    abs_target = os.path.abspath(os.path.expanduser(target_path))
    if not os.path.exists(abs_target):
        emit_output(None, success=False, error=f"Target path does not exist: {abs_target}", raw=raw)
        return 1

    candidate_exts = [
        ".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx",
        ".py", ".go", ".php",
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"
    ]

    all_symbols: List[Dict[str, Any]] = []
    scanned_files_count = 0

    if os.path.isfile(abs_target):
        target_files = [abs_target]
    else:
        target_files = finder.find_files(abs_target, extensions=candidate_exts, max_files=5000)

    for fpath in target_files:
        ext = os.path.splitext(fpath)[1].lower()
        file_syms = []
        if ext in [".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx"]:
            if not fpath.endswith((".d.ts", ".min.js")):
                file_syms = js_parser.get_symbols(fpath)
                scanned_files_count += 1
        elif ext in [".py"]:
            file_syms = py_parser.get_symbols(fpath)
            scanned_files_count += 1
        elif ext in [".go"]:
            if not fpath.endswith("_test.go"):
                file_syms = go_parser.get_symbols(fpath)
                scanned_files_count += 1
        elif ext in [".php"]:
            file_syms = php_parser.get_symbols(fpath)
            scanned_files_count += 1
        elif ext in [".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"]:
            file_syms = c_parser.get_symbols(fpath)
            scanned_files_count += 1

        all_symbols.extend(file_syms)

    unique_symbols = js_parser._dedupe(all_symbols, key_fields=("name", "kind", "file", "line"))

    kinds_breakdown: Dict[str, int] = {}
    for s in unique_symbols:
        k = s.get("kind", "unknown")
        kinds_breakdown[k] = kinds_breakdown.get(k, 0) + 1

    data = {
        "target_path": abs_target,
        "scanned_files_count": scanned_files_count,
        "total_symbols_count": len(unique_symbols),
        "kinds_breakdown": kinds_breakdown,
        "symbols": unique_symbols
    }
    emit_output(data, success=True, raw=raw)
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="code_tool_new",
        description="High-performance, modular AST & Regex code tool supporting 7 languages."
    )
    parser.add_argument("--raw", action="store_true", default=False, help="Output raw data without success/error envelope")
    parser.add_argument("--json", action="store_true", default=True, help="Output formatted JSON (default)")

    common_sub_parser = argparse.ArgumentParser(add_help=False)
    common_sub_parser.add_argument("--raw", action="store_true", default=argparse.SUPPRESS, help="Output raw data without success/error envelope")
    common_sub_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output formatted JSON (default)")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # blueprint
    bp_parser = subparsers.add_parser("blueprint", parents=[common_sub_parser], help="Extract high-level file and module map")
    bp_parser.add_argument("path", nargs="?", default=".", help="Project path (default: current directory)")

    # endpoints
    ep_parser = subparsers.add_parser("endpoints", parents=[common_sub_parser], help="Extract API routes / endpoints")
    ep_parser.add_argument("path", nargs="?", default=".", help="Project path (default: current directory)")

    # symbols
    sym_parser = subparsers.add_parser("symbols", parents=[common_sub_parser], help="Extract class and function signatures from file or directory")
    sym_parser.add_argument("path", nargs="?", default=".", help="Target file or directory path (default: current directory)")

    args = parser.parse_args()

    if args.subcommand == "blueprint":
        return run_blueprint(args.path, raw=args.raw)
    elif args.subcommand == "endpoints":
        return run_endpoints(args.path, raw=args.raw)
    elif args.subcommand == "symbols":
        return run_symbols(args.path, raw=args.raw)

    return 2

if __name__ == "__main__":
    sys.exit(main())
