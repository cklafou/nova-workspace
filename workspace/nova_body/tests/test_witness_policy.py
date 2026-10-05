# @nova: Guard witness evidence-policy consistency and offline case transport without grading model intelligence.
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))
from nova_cortex import witness


def as_text(messages):
    return "\n".join(m["content"] if isinstance(m["content"], str) else "\n".join(
        item.get("text", "") for item in m["content"]) for m in messages)


class WitnessPolicyTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("wire_record", "Cole: What did the check find?"),
                            ("human_record", "COMPLETE recent record: What did the check find?"),
                            ("session_tool_record", "Earlier receipt: value=7")):
            mock = patch.object(witness, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_policy_is_identical_before_and_after_read_budget(self):
        for reads in (None, 3, 1, 0):
            messages = witness.build_witness("The value is 7.", [], reads_remaining=reads)
            self.assertIn(witness._AUDIT_POLICY, messages[0]["content"])
            self.assertIn("One concrete CONCERN takes precedence", messages[0]["content"])
            self.assertIn("Earlier evidence supports its recorded time", messages[0]["content"])
            self.assertNotIn("LAST AND BINDING", as_text(messages))
            self.assertNotIn("the hedge IS the grounding", as_text(messages))

    def test_final_protocol_has_no_new_read_invitation(self):
        messages = witness.build_witness("The value is 7.", [], reads_remaining=0)
        text = as_text(messages)
        self.assertIn("no tool calls are available", text)
        self.assertNotIn(witness._VERIFY_BLOCK, text)
        self.assertNotIn('"tool":"read_file"', text)
        self.assertTrue(messages[1]["content"].endswith("never counts as completed verification."))

    def test_refused_read_is_preserved_as_refusal_not_settled_fact(self):
        checks = [("read_file", {"path": "fixture.md"}, "REFUSED: replay mode — files changed.")]
        text = as_text(witness.build_witness("The value is 7.", [], checks=checks, reads_remaining=2))
        self.assertIn("REFUSED: replay mode", text)
        self.assertIn("Previously refused reads are not facts", text)
        self.assertIn("all fresh historical reads are unavailable", text)
        self.assertNotIn("treat these as settled fact", text)

    def test_complete_candidate_and_evidence_survive_both_protocols(self):
        draft = "Done, saved.\n" + ("original candidate " * 1800) + "\nThe write was refused."
        receipt = [("write_file", {"path": "fixture.md"}, "[status=failed] already exists")]
        for reads in (3, 0):
            text = as_text(witness.build_witness(draft, receipt, prior_concern="Prior object count was wrong.",
                                                reads_remaining=reads))
            self.assertIn(draft, text)
            self.assertIn("[status=failed] already exists", text)
            self.assertIn("Earlier receipt: value=7", text)
            self.assertIn("Prior object count was wrong.", text)
            self.assertIn("unless the draft explicitly corrects or withdraws it", text)

    def test_image_cap_does_not_turn_relevant_supplied_pixels_into_missing_evidence(self):
        evidence = [{"label": f"frame {i} target=nova_desktop display=:1",
                     "url": f"data:image/png;base64,{i}"} for i in range(5)]
        with patch.object(witness, "_audit_limit", side_effect=lambda key, fallback: fallback):
            messages = witness.build_witness("The last frame shows the answer.", [],
                                             visual_evidence=evidence, reads_remaining=0)
        parts = messages[1]["content"]
        self.assertEqual([p["image_url"]["url"] for p in parts if p["type"] == "image_url"],
                         [p["url"] for p in evidence[-4:]])
        self.assertIn("1 earlier image(s) were omitted", as_text(messages))
        self.assertIn("they do not invalidate supplied evidence", as_text(messages))

    def test_heavy_arbiter_retains_same_evidence_policy(self):
        messages = witness.build_heavy_witness("The value is 7.", [], history=[{"role": "user", "content": "fixture"}])
        self.assertIn(witness._AUDIT_POLICY, messages[0]["content"])
        self.assertIn("PASS, CONCERN, or INCOMPLETE", as_text(messages))
        self.assertIn("[THEM (Cole/human)] fixture", as_text(messages))


if __name__ == "__main__":
    unittest.main()
