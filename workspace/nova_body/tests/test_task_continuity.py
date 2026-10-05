# @nova: Verify canonical task checkpoint persistence and bounded context fitting without live Nova state or inference.
import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))
from nova_cortex import tasking
from nova_cortex.context_budget import fit_messages, text_size, prompt_char_budget
from nova_voice.tool_result import ToolResult


def extract(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name in names]
    if {n.name for n in nodes} != set(names):
        raise AssertionError('Tested source contract was removed')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def literal(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


class TaskContinuity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.board = Path(self.temp.name) / 'Tasking' / 'tasks.json'
        p = patch.object(tasking, '_STORE', self.board)
        p.start(); self.addCleanup(p.stop)
        self.checks = [{'kind': 'file', 'path': 'output.md', 'contains': 'fixture'}]
        self.tid = tasking.create('Fixture objective', 'Keep the original intent', acceptance=self.checks)

    def test_checkpoint_survives_fresh_module_load(self):
        tasking.progress(self.tid, 'Read fixture.py; receipt in test log', continuity={
            'next_step': 'Run its isolated tests', 'constraints': ['No live model calls'],
            'observations': ['Fixture exposes two paths']})
        spec = importlib.util.spec_from_file_location('restarted_task_board', BODY / 'nova_cortex/tasking.py')
        restarted = importlib.util.module_from_spec(spec); spec.loader.exec_module(restarted)
        restarted._STORE = self.board
        task = restarted.get(self.tid)
        self.assertEqual(task['title'], 'Fixture objective')
        self.assertEqual(task['notes'], 'Keep the original intent')
        self.assertEqual(task['acceptance'], self.checks)
        self.assertEqual(task['continuity']['next_step'], 'Run its isolated tests')
        self.assertEqual(task['continuity']['constraints'], ['No live model calls'])
        self.assertEqual(task['continuity']['observations'], ['Fixture exposes two paths'])

    def test_partial_updates_and_note_pruning_retain_prior_fields(self):
        tasking.progress(self.tid, 'first', continuity={'next_step': 'one', 'constraints': ['stable'],
                                                      'observations': ['receipt one']})
        for i in range(25):
            tasking.progress(self.tid, f'Note {i}')
        tasking.progress(self.tid, 'second', continuity={'next_step': 'two'})
        task = tasking.get(self.tid)
        self.assertEqual(len(task['progress']), 20)
        self.assertEqual(task['continuity']['constraints'], ['stable'])
        self.assertEqual(task['continuity']['observations'], ['receipt one'])
        self.assertEqual(task['continuity']['next_step'], 'two')
        tasking.progress(self.tid, '', continuity={'observations': [], 'next_step': ''})
        self.assertEqual(tasking.get(self.tid)['continuity']['observations'], [])
        self.assertEqual(tasking.get(self.tid)['continuity']['constraints'], ['stable'])

    def test_malformed_or_oversize_patch_does_not_modify_file(self):
        before = self.board.read_bytes()
        for bad in ['bad', {'unknown': 'x'}, {'next_step': 5}, {'next_step': 'x' * 1001},
                    {'constraints': ['x'] * 9}, {'observations': ['x' * 601]}, {'constraints': [None]}]:
            with self.subTest(bad_type=type(bad).__name__):
                with self.assertRaises(ValueError):
                    tasking.progress(self.tid, 'must not persist', continuity=bad)
                self.assertEqual(self.board.read_bytes(), before)

    def test_saved_malformed_continuity_is_not_silently_replaced(self):
        store = tasking._load(); store['tasks'][self.tid]['continuity'] = 'broken'
        tasking._save(store)
        before = self.board.read_bytes()
        with self.assertRaises(ValueError):
            tasking.progress(self.tid, 'no', continuity={'next_step': 'guess'})
        self.assertEqual(self.board.read_bytes(), before)
        self.assertIn('malformed', tasking.render_resume_context())

    def test_legacy_task_read_is_nonmutating_and_honest(self):
        before = self.board.read_bytes()
        rendered = tasking.render_resume_context()
        self.assertIn('Fixture objective', rendered)
        self.assertIn('Next step: (not recorded)', rendered)
        self.assertIn('not independent verification', rendered)
        self.assertEqual(self.board.read_bytes(), before)

    def test_completed_and_abandoned_tasks_do_not_dominate_context(self):
        done = tasking.create('DONE_SENTINEL'); abandoned = tasking.create('ABANDONED_SENTINEL')
        waiting = tasking.create('Waiting task')
        store = tasking._load()
        store['tasks'][done]['status'] = tasking.DONE
        store['tasks'][abandoned]['status'] = tasking.ABANDONED
        store['tasks'][waiting]['status'] = tasking.WAITING
        store['tasks'][waiting]['waiting_on'] = 'Need source access'
        tasking._save(store)
        rendered = tasking.render_resume_context(done)
        self.assertIn('Active focus: none', rendered)
        self.assertNotIn('DONE_SENTINEL', rendered)
        self.assertNotIn('ABANDONED_SENTINEL', rendered)
        self.assertIn('Need source access', rendered)
        self.assertIn('Fixture objective', rendered)

    def test_active_task_first_and_render_strictly_bounded(self):
        last = None
        for i in range(6):
            last = tasking.create('Other ' + str(i), 'n' * 3000, priority=1)
            tasking.progress(last, 'p' * 1000, continuity={'next_step': 'next' * 200,
                'constraints': ['c' * 400] * 8, 'observations': ['o' * 600] * 8})
        for limit in [0, 500, 1000, 1500, 6000]:
            text = tasking.render_resume_context(last, max_chars=limit)
            self.assertLessEqual(len(text), limit)
            if limit >= 1500:
                self.assertIn('TASK [' + last + ']', text)
                self.assertTrue(text.endswith(tasking.CONTINUITY_END))
        for limit in [0, 20, 400, 4200]:
            self.assertLessEqual(len(tasking.render_task_resume(tasking.get(last), limit)), limit)

    def test_decision_actions_preserve_acceptance_and_checkpoint(self):
        tasking.apply_actions({'create': [{'title': 'Action-created', 'acceptance': self.checks}]})
        task = next(t for t in tasking.all_tasks().values() if t['title'] == 'Action-created')
        self.assertEqual(task['acceptance'], self.checks)
        tasking.apply_actions({'progress': [{'id': task['id'], 'note': 'A real step',
                                            'continuity': {'next_step': 'Verify'}}]})
        self.assertEqual(tasking.get(task['id'])['continuity']['next_step'], 'Verify')

    def test_real_tool_dispatch_forwards_optional_checkpoint_and_errors(self):
        ns = extract(BODY / 'nova_voice/tool_router.py', {'task_progress', '_execute_tool_inner'},
                     {'ToolResult': ToolResult})
        result = ns['_execute_tool_inner']('task_progress', {'task_id': self.tid, 'note': 'Saved',
                                                          'continuity': {'next_step': 'Continue'}})
        self.assertTrue(result.ok)
        self.assertEqual(tasking.get(self.tid)['continuity']['next_step'], 'Continue')
        rejected = ns['_execute_tool_inner']('task_progress', {'task_id': self.tid, 'note': 'No',
                                                             'continuity': {'next_step': None}})
        self.assertFalse(rejected.ok)
        self.assertEqual(tasking.get(self.tid)['progress'][-1]['note'], 'Saved')

    def test_workspace_context_reads_checkpoint_fresh_before_large_self_model(self):
        ns = extract(BODY / 'nova_cortex/workspace_context.py', {'build_nova_context_block'}, {
            '_clock_stamp': lambda: 'fixture time', '_load_self_core': lambda: ('SELF_SENTINEL' + 's' * 52000, 52013),
            'NOVA_TOTAL_MAX': 100000, 'NOVA_ONDEMAND_FILE_MAX': 15000})
        fake = types.SimpleNamespace(_always={}, _on_demand={})
        with patch.dict(sys.modules, {'nova_cortex.executive': types.SimpleNamespace(active_focus=lambda: self.tid)}):
            # Import-from may use a previously imported package attribute; patch that too.
            import nova_cortex
            with patch.object(nova_cortex, 'executive', types.SimpleNamespace(active_focus=lambda: self.tid), create=True):
                first = ns['build_nova_context_block'](fake)
                tasking.progress(self.tid, 'Checkpoint now', continuity={'next_step': 'Fresh next step'})
                second = ns['build_nova_context_block'](fake)
        self.assertNotIn('Fresh next step', first)
        self.assertIn('Fresh next step', second)
        self.assertLess(second.index(tasking.CONTINUITY_START), second.index('SELF_SENTINEL'))

    def test_execution_prompt_contains_persisted_continuity(self):
        tasking.progress(self.tid, 'Reached checkpoint', continuity={'next_step': 'Continue exact step',
                                                                   'constraints': ['No inference']})
        ns = extract(BODY / 'nova_cortex/executive.py', {'build_execution'}, {
            'json': json, 'tasking': tasking, 'clock': types.SimpleNamespace(stamp=lambda: 'time'),
            '_progress_loop_count': lambda task: 0, '_artifact_hint': lambda task: '',
            '_asked_by': lambda task: '', '_asker': lambda task: 'fixture author'})
        prompt = ns['build_execution'](tasking.get(self.tid))
        self.assertIn('Continue exact step', prompt)
        self.assertIn('No inference', prompt)
        self.assertIn('Acceptance criteria:', prompt)
        self.assertIn('Omitted fields', prompt)


class ContextBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BODY / 'nova_voice/nova.py'
        cls.prefix = literal(cls.source, 'SYSTEM_PREFIX')
        cls.ns = extract(cls.source, {'_fit_messages_to_window', '_truncate_to_context'}, {
            'MAX_TOKENS_CHAT': 16384, '_PER_MSG_MAX_CHARS': 24000, '_PROMPT_MAX_CHARS': 174000})

    def test_actual_prefix_and_tail_checkpoint_survive_final_fit_with_request(self):
        self.assertGreater(len(self.prefix), 22000)
        checkpoint = tasking.CONTINUITY_START + '\nNext step: CHECKPOINT_SENTINEL\n' + tasking.CONTINUITY_END
        system = self.prefix + '\n' + 'large identity and memory\n' * 6500 + checkpoint
        messages = [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': 'Old turn ' + 'x' * 50000},
                    {'role': 'assistant', 'content': 'Old reply ' + 'y' * 50000},
                    {'role': 'user', 'content': 'Cole → you: CURRENT_REQUEST_SENTINEL'},
                    {'role': 'assistant', 'content': 'Tool call'},
                    {'role': 'user', 'content': '[System Result from read_file]\n' + 'z' * 50000}]
        original = deepcopy(messages)
        # Avoid even Pipeline logging from the actual wrapper in this isolated test.
        import nova_cortex
        witness = types.SimpleNamespace(pipeline_event=Mock())
        with patch.dict(sys.modules, {'nova_cortex.witness': witness}), patch.object(nova_cortex, 'witness', witness, create=True):
            fitted = self.ns['_truncate_to_context'](messages)
            final = self.ns['_fit_messages_to_window'](fitted)
        self.assertTrue(final[0]['content'].startswith(self.prefix))
        self.assertIn('CHECKPOINT_SENTINEL', final[0]['content'])
        self.assertIn('CURRENT_REQUEST_SENTINEL', str(final))
        self.assertLessEqual(text_size(final), prompt_char_budget())
        self.assertEqual(messages, original)
        self.assertLess(len(final), len(messages))

    def test_under_budget_system_is_never_subject_to_tool_cap(self):
        system = self.prefix + 's' * 52000
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': 'Hi'}]
        self.assertEqual(self.ns['_fit_messages_to_window'](messages), messages)

    def test_configured_output_reserve_changes_budget_without_overflow_override(self):
        messages = [{'role': 'system', 'content': 's' * 60000}] + [
            {'role': 'user' if i % 2 else 'assistant', 'content': 'x' * 24000} for i in range(8)]
        for ctx, output in [(65536, 16384), (32768, 16384), (16384, 8192)]:
            result = self.ns['_fit_messages_to_window'](messages, ctx_limit=ctx, max_output=output)
            self.assertLessEqual(text_size(result), prompt_char_budget(ctx, output))
        with self.assertRaises(ValueError):
            self.ns['_fit_messages_to_window'](messages, ctx_limit=8192, max_output=8192)

    def test_multimodal_text_counted_and_images_unchanged(self):
        image = {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,fixture'}}
        messages = [{'role': 'system', 'content': 's' * 5000}, {'role': 'user', 'content': [
            {'type': 'text', 'text': 'Cole → you: ' + 'q' * 25000}, image,
            {'type': 'text', 'text': 'r' * 25000}]}]
        original = deepcopy(messages)
        fitted = fit_messages(messages, max_chars=10000)
        self.assertLessEqual(text_size(fitted), 10000)
        self.assertIn(image, fitted[-1]['content'])
        self.assertEqual(messages, original)

    def test_headless_request_survives_newer_tool_result(self):
        messages = [{'role': 'system', 'content': 's' * 20000},
                    {'role': 'user', 'content': 'HEADLESS_OBJECTIVE'},
                    {'role': 'assistant', 'content': 'older tool call' * 500},
                    {'role': 'user', 'content': '[System Result from read_file]\n' + 'r' * 5000}]
        result = fit_messages(messages, max_chars=12000)
        self.assertIn('HEADLESS_OBJECTIVE', str(result))
        self.assertLessEqual(text_size(result), 12000)

    def test_fetch_uses_actual_output_reserve_and_preserves_audit_bypass(self):
        # Execute the real fetch prelude, stopping at the request payload assignment;
        # no HTTP/client import or model call is performed.
        tree = ast.parse(self.source.read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_fetch_llama_streaming')
        prelude = []
        for statement in node.body:
            if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'payload' for t in statement.targets):
                break
            prelude.append(statement)
        code = compile(ast.Module(body=prelude, type_ignores=[]), str(self.source), 'exec')
        fit = Mock(return_value=['bounded'])
        ns = {'messages': ['original'], 'max_tokens': 8192, 'preserve_messages': False,
              '_fit_messages_to_window': fit}
        exec(code, ns)
        fit.assert_called_once_with(['original'], max_output=8192)
        self.assertEqual(ns['messages'], ['bounded'])
        fit.reset_mock(); ns.update(messages=['exact candidate'], preserve_messages=True)
        exec(code, ns)
        fit.assert_not_called()
        self.assertEqual(ns['messages'], ['exact candidate'])


if __name__ == '__main__':
    unittest.main()
