# @nova: Verify that tool lifecycle identifiers match canonical receipts on success, refusal and exceptions.
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nova_cortex import integrity
from nova_runtime.operations import Operation, current_operation, current_phase
from nova_voice import tool_router
from nova_voice.tool_result import ToolResult


class ToolCorrelationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'receipts.jsonl'
        patcher = patch.object(integrity, 'RECEIPTS_PATH', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.run = Operation()
        token = current_operation.set(self.run)
        self.addCleanup(current_operation.reset, token)

    def receipt(self):
        return json.loads(self.path.read_text(encoding='utf-8'))['outcome']

    def test_return_and_receipt_share_started_call_id(self):
        with patch.object(tool_router, '_execute_tool_inner', return_value=ToolResult('ok')):
            result = tool_router.execute_tool('fixture', {}, operation_id='started-call')
        row = self.receipt()
        self.assertEqual(result.operation_id, 'started-call')
        self.assertEqual(row['operation_id'], result.operation_id)
        self.assertEqual(row['run_id'], self.run.id)
        self.assertEqual(row['status'], 'succeeded')

    def test_exception_receipt_keeps_started_id_and_failure(self):
        with patch.object(tool_router, '_execute_tool_inner', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                tool_router.execute_tool('fixture', {}, operation_id='failed-call')
        row = self.receipt()
        self.assertEqual(row['operation_id'], 'failed-call')
        self.assertEqual(row['run_id'], self.run.id)
        self.assertFalse(row['ok'])
        self.assertEqual(row['stderr'], 'fixture failure')

    def test_reflection_refusal_retains_started_id(self):
        token = current_phase.set('reflection')
        try:
            result = tool_router.execute_tool('run_command', {'command': 'must never run'},
                                              operation_id='refused-call')
        finally:
            current_phase.reset(token)
        self.assertEqual(result.status, 'refused')
        self.assertEqual(self.receipt()['operation_id'], 'refused-call')

    def test_legacy_call_still_gets_generated_id(self):
        with patch.object(tool_router, '_execute_tool_inner', return_value=ToolResult('ok')):
            result = tool_router.execute_tool('fixture', {})
        self.assertTrue(result.operation_id)
        self.assertEqual(self.receipt()['operation_id'], result.operation_id)


if __name__ == '__main__':
    unittest.main()
