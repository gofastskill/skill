"""Generator idempotence, TOML escaping and calibration reference integrity."""
import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build", ROOT / "evals/v2/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class GenerationTests(unittest.TestCase):
    def test_regeneration_is_byte_identical(self):
        paths = [ROOT / "evals/v2" / suite / name
                 for suite in ("consultation", "restraint", "correctness", "smoke")
                 for name in ("prompts.csv", "checks.toml")]
        before = {p: p.read_bytes() for p in paths}
        build.main()
        self.assertTrue(all(p.read_bytes() == value for p, value in before.items()))

    def test_escaping_and_missing_judge_prompt(self):
        text = 'quotes " newline\n path\\file'
        self.assertEqual(tomllib.loads('value = ' + build.toml_str(text))["value"], text)
        check = tomllib.loads(build.must_not_say(text, "case"))["check"][0]
        self.assertEqual(check["pattern"], text)
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(SystemExit):
            build.judge({"name": "missing", "prompt_file": "absent.md"}, Path(directory))

    def test_calibration_has_independent_positive_negative_pairs(self):
        cases = json.loads((ROOT / "evals/v2/patterns.json").read_text())["correctness"]
        known = {c["id"] for c in cases}
        examples = json.loads((ROOT / "evals/v2/calibration.json").read_text())["examples"]
        for case_id in {e["case"] for e in examples}:
            self.assertIn(case_id, known)
            self.assertEqual({e["acceptable"] for e in examples if e["case"] == case_id}, {True, False})
        self.assertTrue(all(e["reason"] and e["answer"] for e in examples))
