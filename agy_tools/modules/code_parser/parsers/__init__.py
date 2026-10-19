import os
import sys
from typing import Dict, List, Any, Optional, Callable

EXTENSION_MAP: Dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".py": "python",
    ".go": "go",
    ".php": "php",
    ".c": "c",
    ".cpp": "c",
    ".cc": "c",
    ".cxx": "c",
    ".h": "c",
    ".hpp": "c",
    ".hh": "c",
}

def _dedupe(items: List[Dict[str, Any]], key_fields: tuple = ("name", "kind", "file", "line")) -> List[Dict[str, Any]]:
    """Generic deduplication helper."""
    seen = set()
    result = []
    for item in items:
        key = tuple(item.get(k) for k in key_fields)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

def get_parser_module(extension_or_lang: str):
    """Dynamically loads and returns the parser module for a given file extension or language."""
    ext = extension_or_lang.lower().strip()
    lang = EXTENSION_MAP.get(ext, ext)
    if lang in ["javascript", "typescript", "js", "ts"]:
        return __import__("parsers.js_parser", fromlist=["js_parser"])
    elif lang in ["python", "py"]:
        return __import__("parsers.py_parser", fromlist=["py_parser"])
    elif lang in ["go"]:
        return __import__("parsers.go_parser", fromlist=["go_parser"])
    elif lang in ["php"]:
        return __import__("parsers.php_parser", fromlist=["php_parser"])
    elif lang in ["c", "c++", "cpp"]:
        return __import__("parsers.c_parser", fromlist=["c_parser"])
    return None
