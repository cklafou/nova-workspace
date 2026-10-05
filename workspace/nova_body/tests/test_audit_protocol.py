# @nova: Verify strict witness JSON classification, read restrictions and provider schema without invoking Nova or a model.
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nova_cortex.audit_protocol import audit_response_format, classify_audit_response


class AuditProtocolTests(unittest.TestCase):
    def test_verdict_reason_can_quote_tool_json_without_requesting_a_read(self):
        value={"status":"CONCERN", "reason":'Receipt says {"tool":"read_file","args":{"path":"x"}}, which is an attempt, not contents.'}
        self.assertEqual(classify_audit_response(json.dumps(value)), ("verdict", value))
        for status in ("PASS", "CONCERN", "INCOMPLETE"):
            self.assertEqual(classify_audit_response(json.dumps({"status":status,"reason":"Explicit reason."}))[0], "verdict")

    def test_whole_document_only_never_salvages_embedded_or_trailing_verdict(self):
        good='{"status":"PASS","reason":"Greeting contains no action claim."}'
        for value in ("PASS", "PASS plus explanation", "```json\n"+good+"\n```", "Here is the result: "+good,
                      good+" trailing explanation", good+good, "["+good+"]", "null", "", None):
            with self.subTest(value=value):
                self.assertEqual(classify_audit_response(value), ("invalid", None))

    def test_duplicate_keys_mixed_shapes_and_invalid_statuses_are_not_approval(self):
        values=['{"status":"CONCERN","status":"PASS","reason":"Ambiguous"}',
                '{"status":"PASS","reason":"Fine","tool":"read_file","args":{"path":"x"}}',
                '{"status":"PASS","reason":"Fine","extra":true}',
                '{"status":"pass","reason":"Wrong enum"}',
                '{"status":["PASS"],"reason":"Wrong type"}',
                '{"status":"PASS","reason":"  "}',
                '{"status":"PASS","reason":NaN}',
                '{"tool":"read_file","args":{"path":"safe","path":"other"}}',
                '{"tool":"memory_search","args":{"query":"x","max_chars":Infinity}}']
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(classify_audit_response(value), ("invalid", None))

    def test_only_supported_read_names_and_exact_arguments_are_requests(self):
        for value in ({"tool":"read_file","args":{"path":"folder/file.txt"}},
                      {"tool":"list_dir","args":{"path":"."}},
                      {"tool":"memory_search","args":{"query":"prior evidence","max_chars":4000}}):
            encoded=json.dumps(value)
            self.assertEqual(classify_audit_response(encoded), ("tool", value))
            self.assertEqual(classify_audit_response(encoded,allow_reads=False), ("invalid",None))
        invalid=[{"tool":"run_command","args":{"command":"echo nope"}},
                 {"tool":"read_file","args":[]}, {"tool":"read_file","args":{"path":""}},
                 {"tool":"read_file","args":{"path":"x","command":"side effect"}},
                 {"tool":"memory_search","args":{"query":"x","max_chars":True}},
                 {"tool":"memory_search","args":{"query":"x","max_chars":0}},
                 {"tool":"memory_search","args":{"query":"x","max_chars":2.5}}]
        for value in invalid:
            self.assertEqual(classify_audit_response(json.dumps(value)), ("invalid",None))

    def test_final_or_forbidden_schema_cannot_request_tools(self):
        for remaining, allow in ((0,True),(3,False)):
            schema=audit_response_format(remaining,allow_reads=allow)["json_schema"]["schema"]
            self.assertEqual(schema["required"],["status","reason"])
            self.assertFalse(schema["additionalProperties"])
            self.assertNotIn("anyOf",schema)
        branches=audit_response_format(3)["json_schema"]["schema"]["anyOf"]
        self.assertEqual([b["properties"]["tool"]["enum"][0] for b in branches[1:]],
                         ["read_file","list_dir","memory_search"])
        self.assertTrue(all(b["properties"]["args"]["additionalProperties"] is False for b in branches[1:]))

    def test_caller_tool_allowlist_and_schema_mutation_cannot_expand_future_calls(self):
        schema=audit_response_format(2,verify_tools=("list_dir",))["json_schema"]["schema"]
        self.assertEqual(len(schema["anyOf"]),2)
        self.assertEqual(classify_audit_response('{"tool":"read_file","args":{"path":"x"}}',
                                               verify_tools=("list_dir",)), ("invalid",None))
        schema["anyOf"][1]["properties"]["args"]["required"].append("bad")
        next_schema=audit_response_format(2)["json_schema"]["schema"]
        self.assertEqual(next_schema["anyOf"][2]["properties"]["args"]["required"],["path"])
        with self.assertRaises(ValueError): audit_response_format(2,verify_tools=("run_command",))
        for value in (-1,True,1.2):
            with self.assertRaises(ValueError): audit_response_format(value)

if __name__=='__main__':unittest.main()
