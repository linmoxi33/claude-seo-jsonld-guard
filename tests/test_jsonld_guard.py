import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin" / "jsonld-guard"


def write(tmp, name, text):
    path = Path(tmp) / name
    path.write_text(text, encoding="utf-8")
    return path


def run(*args):
    proc = subprocess.run([sys.executable, str(BIN), *map(str, args)],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


VALID = """<script type="application/ld+json">
{"@context":"https://schema.org","@type":["Organization","LocalBusiness"],
 "name":"Acme","address":{"@type":"PostalAddress","streetAddress":"1 Main St"}}
</script>"""


class BehaviorTests(unittest.TestCase):
    def test_valid_multitype_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "ok.html", VALID)
            code, out, _ = run(page)
            self.assertEqual(code, 0, out)
            self.assertIn("0 error(s)", out)

    def test_missing_required_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "bad.html", """<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","sku":"X"}</script>""")
            code, out, _ = run(page)
            self.assertEqual(code, 1)
            self.assertIn("missing-required", out)
            self.assertIn("'name'", out)

    def test_invalid_json_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "bad.html", """<script type="application/ld+json">
{"@context":"https://schema.org",}</script>""")
            code, out, _ = run(page)
            self.assertEqual(code, 1)
            self.assertIn("invalid-json", out)

    def test_missing_path_exits_two(self):
        code, _, err = run("/nonexistent/nope.html")
        self.assertEqual(code, 2)
        self.assertIn("no such file", err)

    def test_no_arguments_exits_two(self):
        proc = subprocess.run([sys.executable, str(BIN)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_json_output_is_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "ok.html", VALID)
            code, out, _ = run("--json", page)
            self.assertEqual(code, 0)
            payload = json.loads(out)
            self.assertEqual(payload["tool"], "jsonld-guard")
            self.assertEqual(payload["summary"]["errors"], 0)
            self.assertEqual(payload["summary"]["nodes"], 2)

    def test_json_output_lists_issue_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "bad.html", """<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Article","headline":"Hi"}</script>""")
            code, out, _ = run("--json", page)
            self.assertEqual(code, 1)
            payload = json.loads(out)
            codes = {i["code"] for i in payload["issues"]}
            self.assertIn("missing-required", codes)
            self.assertEqual(payload["summary"]["errors"], 1)


class RuleTests(unittest.TestCase):
    def test_type_array_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "ok.html", VALID)
            code, out, _ = run("--json", page)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["summary"]["nodes"], 2)

    def test_missing_type_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "x.html", """<script type="application/ld+json">
{"@context":"https://schema.org","name":"No type"}</script>""")
            code, out, _ = run("--json", page)
            self.assertEqual(code, 1)
            self.assertIn("missing-type", {i["code"] for i in json.loads(out)["issues"]})

    def test_invalid_type_number_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "x.html", """<script type="application/ld+json">
{"@context":"https://schema.org","@type":42}</script>""")
            code, out, _ = run("--json", page)
            self.assertEqual(code, 1)
            self.assertIn("invalid-type", {i["code"] for i in json.loads(out)["issues"]})

    def test_duplicate_id_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "x.html", """<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
 {"@id":"#a","@type":"Person","name":"A"},
 {"@id":"#a","@type":"Person","name":"B"}]}</script>""")
            code, out, _ = run("--json", page)
            self.assertEqual(code, 1)
            self.assertIn("duplicate-id", {i["code"] for i in json.loads(out)["issues"]})

    def test_missing_context_is_warning_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "x.html", """<script type="application/ld+json">
{"@type":"Person","name":"A"}</script>""")
            code, out, _ = run("--json", page)
            self.assertEqual(code, 0)
            payload = json.loads(out)
            self.assertEqual(payload["summary"]["warnings"], 1)
            self.assertEqual(payload["issues"][0]["code"], "missing-context")

    def test_directory_input_and_no_jsonld_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.html", VALID)
            write(tmp, "empty.html", "<html></html>")
            code, out, _ = run("--json", tmp)
            self.assertEqual(code, 0)
            payload = json.loads(out)
            self.assertEqual(payload["summary"]["files"], 2)
            self.assertIn("no-jsonld", {i["code"] for i in payload["issues"]})

    def test_plain_json_file_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = write(tmp, "doc.json", json.dumps({
                "@context": "https://schema.org",
                "@type": "Event", "name": "Launch", "startDate": "2026-11-01"}))
            code, out, _ = run("--json", doc)
            self.assertEqual(code, 0, out)
            self.assertEqual(json.loads(out)["summary"]["nodes"], 1)

    def test_missing_address_for_localbusiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = write(tmp, "x.html", """<script type="application/ld+json">
{"@context":"https://schema.org","@type":"LocalBusiness","name":"Cafe"}</script>""")
            code, out, _ = run("--json", page)
            self.assertEqual(code, 1)
            msgs = [i["message"] for i in json.loads(out)["issues"]]
            self.assertTrue(any("'address'" in m for m in msgs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
