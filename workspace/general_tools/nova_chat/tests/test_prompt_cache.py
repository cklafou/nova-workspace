# Last updated: 2026-10-06 03:19:20
# @nova: Verify cache-friendly prompt ordering retains the exact clock, evidence, audit policy and strict verdict handling.
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

WORKSPACE = Path(__file__).resolve().parents[3]
BODY = WORKSPACE / "nova_body"
sys.path.insert(0, str(BODY))
from nova_cortex import witness

# Captured from the pre-relocation builder with only its READ BUDGET line removed.
# These fixture hashes protect all other policy, receipt, image and formatting bytes.
POLICY_HASHES = {'None:False': 'c6018a80dfd8c9d5a0099b82af58aedb8f796703dfd628c0bc58f34c4071c888', 'None:True': '1e9d0d9e4eb910fe368b96947141280df81455e3bbcda44df5ccef1fef7155cb', '3:False': 'c6018a80dfd8c9d5a0099b82af58aedb8f796703dfd628c0bc58f34c4071c888', '3:True': '1e9d0d9e4eb910fe368b96947141280df81455e3bbcda44df5ccef1fef7155cb', '2:False': '4d25471009bbed2d476c686e97bfb5ebf65f6300a2659c0a974cc4f02ffc64ff', '2:True': 'aa42501f2f4142c85a32bfdc686aa1bc3d9a920849ca6766e2a707ca5d03abe2', '1:False': '18ba731d2655e12b00996d6e709787f173e07a6bb8e84b91d17eb7bcbd605411', '1:True': '088f2fcf533dd658999cf03539736584459651e51eb2c1d403ad400912e152fd', '0:False': '58ad9a25a4abee23e8170891505dab28f8137c6f24c3b9a7dc7d2341fc607807', '0:True': '3ed372abc489fe5167ce74f01c6d77be981db39c0838c73038d5c83493750ab8'}


def without_budget(value):
    if isinstance(value, str):
        return re.sub(r"READ BUDGET: [^\n]*\n", "", value)
    if isinstance(value, list):
        return [without_budget(item) for item in value]
    if isinstance(value, dict):
        return {key: without_budget(item) for key, item in value.items()}
    return value


def audit(remaining, visual=False):
    checks = [("read_file", {"path": "fixture.txt"}, "fixture read result")] * (0 if remaining is None else 3-remaining)
    with patch.object(witness, "wire_record", return_value="fixture wire"), \
         patch.object(witness, "human_record", return_value="fixture human"), \
         patch.object(witness, "session_tool_record", return_value="fixture session"), \
         patch.object(witness, "_audit_limit", side_effect=lambda key, fallback: fallback):
        return witness.build_witness("fixture draft", [("read_file", {}, "fixture receipt")],
            thinking="fixture reasoning", prior_concern="fixture concern", checks=checks,
            reads_remaining=remaining, has_image=visual,
            visual_evidence=([{"label": "fixture image", "url": "data:image/png;base64,AA=="}] if visual else []))


class PromptCacheTests(unittest.TestCase):
    def transcript(self, clock, prefix="STABLE INSTRUCTIONS", context="WORKSPACE FIXTURE"):
        # Execute the real method without importing a transcript store or making any files.
        tree = ast.parse((WORKSPACE / "general_tools/nova_chat/transcript.py").read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Transcript")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "to_messages")
        ns = {"_re_speaker": re.compile(r"^$a")}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "transcript fixture", "exec"), ns)
        fixture = SimpleNamespace(_now_block=lambda: clock, messages=[
            {"author": "Cole", "content": "Current fixture request"},
            {"author": "Nova", "content": "Prior fixture reply"}])
        return ns["to_messages"](fixture, "Nova", prefix, context)

    def test_clock_keeps_exact_text_priority_and_current_request(self):
        clock = "[RIGHT NOW: fixture time; fixture gap.]\n\n"
        messages = self.transcript(clock)
        self.assertEqual(messages[0], {"role": "system", "content":
            "STABLE INSTRUCTIONS\n\n" + clock + "\n\n--- WORKSPACE CONTEXT ---\nWORKSPACE FIXTURE\n--- END CONTEXT ---"})
        self.assertEqual(messages[0]["content"].count(clock), 1)
        self.assertEqual(messages[1], {"role": "user", "content": "Cole → you: Current fixture request"})
        self.assertEqual(messages[2], {"role": "assistant", "content": "Prior fixture reply"})

    def test_clock_change_does_not_invalidate_stable_instruction_prefix(self):
        prefix = "UNCHANGING POLICY\n" * 1500
        a = self.transcript("[clock A]\n\n", prefix)[0]["content"]
        b = self.transcript("[clock B]\n\n", prefix)[0]["content"]
        stable = prefix.strip() + "\n\n"
        self.assertTrue(a.startswith(stable))
        self.assertTrue(b.startswith(stable))
        self.assertNotEqual(a, b)
        self.assertEqual(self.transcript("clock", "", "")[0]["content"], "clock")

    def test_every_nonbudget_prompt_byte_matches_before_relocation(self):
        for remaining in (None, 3, 2, 1, 0):
            for visual in (False, True):
                with self.subTest(remaining=remaining, visual=visual):
                    cleaned = without_budget(audit(remaining, visual))
                    actual = hashlib.sha256(json.dumps(cleaned, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                    self.assertEqual(actual, POLICY_HASHES[str(remaining)+":"+str(visual)])

    def test_exact_read_counter_and_evidence_survive_each_round_once(self):
        prefixes = []
        for remaining in (3, 2, 1, 0):
            content = audit(remaining)[1]["content"]
            counter = f"READ BUDGET: {remaining} further read(s) are available. "
            counter += ("No further tool calls will run. Give PASS, CONCERN or INCOMPLETE now.\n"
                        if remaining == 0 else "Use them only to settle a relevant fact.\n")
            self.assertEqual(content.count("READ BUDGET:"), 1)
            self.assertEqual(content.count(counter), 1)
            for evidence in ("fixture draft", "fixture receipt", "fixture session", "fixture human", "fixture wire", "fixture concern"):
                self.assertIn(evidence, content)
                self.assertLess(content.index(evidence), content.index(counter))
            if remaining < 3:
                self.assertLess(content.index(counter), content.index("fixture read result"))
            if remaining > 0:
                prefixes.append(content[:content.index(counter)])
        self.assertEqual(prefixes, [prefixes[0]] * 3)
        self.assertGreater(len(prefixes[0]), 1500)
        self.assertNotIn("READ BUDGET:", audit(None)[1]["content"])

    def test_final_no_read_protocol_and_strict_parser_unchanged(self):
        final = audit(0)
        self.assertIn("FINAL AUDIT: no tool calls are available.", final[0]["content"])
        self.assertNotIn(witness._VERIFY_BLOCK, final[1]["content"])
        self.assertNotIn("A single read-only tool call", final[1]["content"])
        self.assertEqual(witness.parse_witness_verdict("PASS").status, "PASS")
        for text in ("PASS because this seems okay", "PASS\nExtra prose", "{}", ""):
            self.assertEqual(witness.parse_witness_verdict(text).status, "INCOMPLETE")
        self.assertEqual(witness.parse_witness_verdict("PASS", exhausted=True).status, "INCOMPLETE")
        self.assertEqual(witness.parse_witness_verdict("PASS", error="fixture error").status, "ERROR")


if __name__ == "__main__":
    unittest.main()
