# Last updated: 2026-10-05 21:33:05
# @nova: Verify that actual GPU-run reproducibility details are checksummed, bounded and retained with training inputs.
import hashlib
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import tempfile
from nova_updater import train

class RunDetails(TestCase):
    def test_verified_details_are_preserved_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            source=root/'outputs'/'training_details';source.mkdir(parents=True)
            data=b'{"revision":"tested"}\n'
            (source/'base_source.json').write_bytes(data)
            (source/'SHA256SUMS.txt').write_text(hashlib.sha256(data).hexdigest()+'  base_source.json\n')
            spec={"base_model_id":"unsloth/Qwen3.8-27B","output_name":"core"}
            with patch.object(train.paths,'training_model_dir',return_value=root/'inputs'):
                result=train.preserve_run_details(spec,source.parent,'job1')
                self.assertIsNotNone(result)
                self.assertEqual((root/'inputs/core/Run Details/job1/base_source.json').read_bytes(),data)
                (source/'base_source.json').write_text('changed')
                with self.assertRaises(train.TrainError):
                    train.preserve_run_details(spec,source.parent,'job2')
                self.assertFalse((root/'inputs/core/Run Details/job2').exists())

    def test_parent_paths_are_refused_before_copying(self):
        with tempfile.TemporaryDirectory() as raw:
            source=Path(raw)/'training_details';source.mkdir()
            (source/'SHA256SUMS.txt').write_text('0'*64+'  ../secret.txt\n')
            with self.assertRaises(train.TrainError):
                train.preserve_run_details({},source.parent,'job3')
