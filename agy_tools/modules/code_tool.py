"""
Facade for the new modular code_tool.
Delegates everything to agy_tools.modules.code_parser.main
"""
import sys
import os

# Yangi modular paket ichidagi importlar ishlay olishi uchun uning manzilini path'ga qo'shamiz
PACKAGE_DIR = os.path.join(os.path.dirname(__file__), "code_parser")
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

from agy_tools.modules.code_parser.main import run_blueprint, run_endpoints, run_symbols

def get_code_describe():
    """CLI yordam tizimi uchun modul tavsifini qaytaradi."""
    return {
        "name": "code",
        "help": "Dasturlash tillari va freymvorklarni AST/Regex tahlil qilish (Modular Gen2, 0-dependency)",
        "commands": {
            "blueprint": "Loyihaning to'liq strukturasini, fayllar soni va texnologiyalarini aniqlash",
            "endpoints": "Express, FastAPI, NestJS, Go kabi freymvorklardan barcha API endpointlarni topish",
            "symbols": "Barcha funksiyalar, klasslar va metodlarni ctags formatida chiqarish"
        }
    }

def run_code_blueprint(args):
    is_raw = getattr(args, "raw", False)
    run_blueprint(args.path, is_raw)

def run_code_endpoints(args):
    is_raw = getattr(args, "raw", False)
    run_endpoints(args.path, is_raw)

def run_code_symbols(args):
    is_raw = getattr(args, "raw", False)
    run_symbols(args.path, is_raw)
