# Last updated: 2026-10-06 03:07:41
# @nova: Verify cached embedder initialization and singleton concurrency without loading models, querying memory or accessing Nova state.
import concurrent.futures
import importlib.util
import io
from pathlib import Path
import sys
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BODY / 'nova_lancedb' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class LocalEntryNotFoundError(FileNotFoundError):
    __module__ = 'huggingface_hub.errors'

class CachedModelTests(unittest.TestCase):
    def setUp(self):
        self.module = load('memory_embedder_fixture', 'embedder.py')
        self.logs = io.StringIO()
        self.enterContext(patch('sys.stdout', self.logs))

    def factory(self, constructor):
        return patch.dict(sys.modules, {'sentence_transformers': types.SimpleNamespace(SentenceTransformer=constructor)})

    def test_both_cached_models_only_attempt_local_loading(self):
        model = object(); constructor = Mock(return_value=model)
        with self.factory(constructor):
            for loader in (self.module._load_text_model, self.module._load_clip_model):
                self.assertIs(loader(), model)
                self.assertIs(loader(), model)
        self.assertEqual(constructor.call_count, 2)
        self.assertEqual(constructor.call_args_list[0].args, ('all-MiniLM-L6-v2',))
        self.assertEqual(constructor.call_args_list[1].args, ('clip-ViT-B-32',))
        self.assertTrue(all(call.kwargs == {'local_files_only':True, 'device':'cpu'} for call in constructor.call_args_list))
        self.assertIn('local cache; init=', self.logs.getvalue())

    def test_explicit_cache_miss_preserves_existing_download_fallback(self):
        model = object(); constructor = Mock(side_effect=[LocalEntryNotFoundError('missing asset'), model])
        with self.factory(constructor):
            self.assertIs(self.module._load_text_model(), model)
        self.assertEqual(constructor.call_args_list[0].kwargs, {'local_files_only':True, 'device':'cpu'})
        self.assertEqual(constructor.call_args_list[1].kwargs, {'device':'cpu'})
        self.assertIn('missing-cache download fallback', self.logs.getvalue())

    def test_wrapped_transformers_cache_absence_is_recognized(self):
        missing = OSError("We couldn't connect to the hub and couldn't find them in the cached files.")
        constructor = Mock(side_effect=[missing, object()])
        with self.factory(constructor): self.assertIsNotNone(self.module._load_clip_model())
        self.assertEqual(constructor.call_count, 2)
        outer = RuntimeError('loader failed'); outer.__cause__ = LocalEntryNotFoundError('missing')
        self.assertTrue(self.module._missing_local_assets(outer))

    def test_corruption_permissions_or_device_failures_do_not_trigger_download(self):
        for error in (RuntimeError('CUDA out of memory'), ValueError('corrupt model config'),
                      PermissionError('access denied'), OSError('invalid model weights')):
            with self.subTest(error=type(error).__name__):
                constructor = Mock(side_effect=error)
                with self.factory(constructor):
                    self.assertIsNone(self.module._load_text_model())
                constructor.assert_called_once_with('all-MiniLM-L6-v2', local_files_only=True, device='cpu')

    def test_concurrent_callers_construct_each_model_only_once(self):
        for loader in (self.module._load_text_model, self.module._load_clip_model):
            model = object(); started, release = threading.Event(), threading.Event()
            def construct(*args, **kwargs):
                started.set()
                if not release.wait(2): raise RuntimeError('fixture stalled')
                return model
            constructor = Mock(side_effect=construct)
            with self.factory(constructor), concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(loader) for _ in range(8)]
                self.assertTrue(started.wait(1))
                time.sleep(.03)
                release.set()
                self.assertTrue(all(future.result(timeout=2) is model for future in futures))
            constructor.assert_called_once()

    def test_encoding_keeps_existing_normalization_and_failure_semantics(self):
        model = Mock(); model.encode.return_value.tolist.return_value = [1.0, 2.0]
        with self.factory(Mock(return_value=model)):
            self.assertEqual(self.module.embed_text('current question'), [1.0, 2.0])
            model.encode.assert_called_once_with('current question', normalize_embeddings=True)
            model.encode.side_effect = RuntimeError('fixture encode failure')
            with self.assertRaisesRegex(RuntimeError, 'no valid vector'):
                self.module.embed_text('another question')

class StoreSingletonTests(unittest.TestCase):
    def test_indexer_and_context_cannot_create_duplicate_stores(self):
        module = load('memory_store_fixture', 'hippocampus.py')
        store = object(); started, release = threading.Event(), threading.Event()
        def construct():
            started.set()
            if not release.wait(2): raise RuntimeError('fixture stalled')
            return store
        factory = Mock(side_effect=construct)
        with patch.object(module, 'NovaMemoryStore', factory), concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(module.get_store) for _ in range(8)]
            self.assertTrue(started.wait(1)); time.sleep(.03); release.set()
            self.assertTrue(all(f.result(timeout=2) is store for f in futures))
        factory.assert_called_once_with()

if __name__ == '__main__': unittest.main()
