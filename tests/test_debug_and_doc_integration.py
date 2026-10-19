import os
import sys
import unittest
import tempfile
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from agy_tools.modules.debug_tool import extract_code_context, parse_stack_trace, find_enclosing_symbol_scope
from agy_tools.modules.doc_tool import select_adapter, CodeParserAdapter

class TestDebugDocIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_01_debug_python_scope_enrichment(self):
        sample_file = os.path.join(self.tmpdir.name, "payment_service.py")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write('''class BillingManager:
    def __init__(self):
        self.active = True

    def calculate_tax(self, val: float):
        return val * 0.12

    def process_invoice(self, invoice_id: int):
        # Line 9
        res = 1 / 0
        return res
''')
        scope = find_enclosing_symbol_scope(sample_file, 9)
        self.assertEqual(scope.get("enclosing_class"), "BillingManager")
        self.assertEqual(scope.get("enclosing_function"), "process_invoice")
        self.assertIn("def process_invoice", scope.get("signature", ""))

    def test_02_debug_js_scope_enrichment(self):
        sample_file = os.path.join(self.tmpdir.name, "user_controller.js")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write('''class UserController {
    constructor() {}

    async getUserProfile(req, res) {
        // Line 5
        throw new Error("User not found");
    }
}
module.exports = UserController;
''')
        scope = find_enclosing_symbol_scope(sample_file, 5)
        self.assertEqual(scope.get("enclosing_class"), "UserController")
        self.assertEqual(scope.get("enclosing_function"), "getUserProfile")
        self.assertIn("async getUserProfile", scope.get("signature", ""))

    def test_03_doc_codeparser_adapter_fastapi(self):
        mock_app = os.path.join(self.tmpdir.name, "mock_fastapi")
        os.makedirs(mock_app, exist_ok=True)
        with open(os.path.join(mock_app, "requirements.txt"), "w") as f:
            f.write("fastapi>=0.100.0\n")
        with open(os.path.join(mock_app, "main.py"), "w") as f:
            f.write('''from fastapi import FastAPI
app = FastAPI()

@app.get("/items")
def list_items():
    return []

@app.post("/items")
def create_item():
    return {}
''')
        adapter = select_adapter(mock_app)
        self.assertIsInstance(adapter, CodeParserAdapter)
        eps = adapter.scan()
        self.assertEqual(len(eps), 2)
        paths = [ep["path"] for ep in eps]
        self.assertIn("/items", paths)

if __name__ == "__main__":
    unittest.main()
