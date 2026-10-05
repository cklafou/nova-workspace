# Last updated: 2026-10-05 21:48:16
# @nova: Verify local Whisper decoding, explicit English, strict backend selection and asset readiness without audio hardware.
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from config import GatewayConfig
import stt

class WhisperTests(unittest.TestCase):
    def test_local_cpu_model_cached_and_lazy_segments_consumed(self):
        calls, decodes = [], []
        class Model:
            def __init__(self, path, **kw): calls.append((path, kw))
            def transcribe(self, samples, **kw):
                decodes.append((samples.copy(), kw))
                def segments():
                    yield types.SimpleNamespace(text=' Hello Nova. ')
                    yield types.SimpleNamespace(text='Please speak aloud. ')
                return segments(), None
        cfg = GatewayConfig(whisper_model='fixture', speech_language='en')
        with patch.dict(sys.modules, {'faster_whisper':types.SimpleNamespace(WhisperModel=Model)}), \
             patch.object(stt, 'local_asset_status', return_value={'ready':True}):
            transcribe = stt._load_faster_whisper(cfg)
            for _ in range(2): self.assertEqual(transcribe(np.zeros(16000)), 'Hello Nova. Please speak aloud.')
            self.assertEqual(transcribe(np.zeros(100)), '')
            with self.assertRaises(ValueError): transcribe(np.zeros((2,16000)))
            with self.assertRaises(ValueError): transcribe(np.array([np.nan]*16000))
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][1]['device'],'cpu')
        self.assertEqual(calls[0][1]['compute_type'],'int8')
        self.assertTrue(calls[0][1]['local_files_only'])
        self.assertEqual(len(decodes),2)
        self.assertEqual(decodes[0][1]['language'],'en')
        self.assertFalse(decodes[0][1]['condition_on_previous_text'])
        self.assertFalse(decodes[0][1]['vad_filter'])

    def test_selected_backend_assets_only_and_no_network_or_import(self):
        cfg=GatewayConfig(vad_backend='none')
        with tempfile.TemporaryDirectory() as folder, patch.object(stt,'_whisper_path',return_value=Path(folder)):
            self.assertFalse(stt.local_asset_status(cfg)['ready'])
            for name in ('model.bin','config.json','tokenizer.json','preprocessor_config.json'):
                (Path(folder)/name).write_bytes(b'fixture')
            status=stt.local_asset_status(cfg)
            self.assertTrue(status['ready'])
            self.assertEqual(status['recognizer'],'faster_whisper')
            cfg.sample_rate=48000
            self.assertFalse(stt.local_asset_status(cfg)['ready'])
            self.assertIn('16000',stt.local_asset_status(cfg)['reason'])

    def test_strict_selection_does_not_turn_a_broken_microphone_into_typed_input(self):
        with patch.object(stt,'FasterWhisperSTT',side_effect=RuntimeError('missing asset')):
            with self.assertRaisesRegex(RuntimeError,'missing asset'):
                stt.make_stt(GatewayConfig(),allow_fallback=False)
        with self.assertRaisesRegex(ValueError,'Unknown'):
            stt.make_stt(GatewayConfig(stt_backend='misspelled'),allow_fallback=False)

    def test_state_observer_cannot_break_recognition(self):
        recognizer=object.__new__(stt.FasterWhisperSTT)
        recognizer.on_state=lambda state: (_ for _ in ()).throw(ValueError('observer failed'))
        recognizer._state('transcribing')
        recognizer._state('listening')

if __name__=='__main__': unittest.main()
