# @nova: Verify persistent training-input packages, separate finished adapters and quoted Windows adapter paths using disposable files only.
import hashlib
import json
from pathlib import Path
import unittest

from support import Workspace
from nova_updater import current, gguf, inventory, jobs, paths, train


class TrainingFiles(Workspace):
    def spec(self, **extra):
        data = self.ws / 'source' / 'Nova Personality.jsonl'
        data.parent.mkdir(exist_ok=True)
        if not data.exists():
            data.write_text(json.dumps({'messages': [{'role': 'user', 'content': 'Hi'},
                                                    {'role': 'assistant', 'content': 'Hello'}]}) + '\n')
        return train.prepare_spec({'base_model_id': 'unsloth/Qwen3.8-27B',
                                   'data_files': [str(data)], 'output_name': 'nova_personality_v8', **extra})

    def output(self, name='nova_personality_v8_epoch1.gguf'):
        folder = self.ws / 'Temp' / 'downloaded'
        folder.mkdir(parents=True, exist_ok=True)
        adapter = folder / name
        gguf.write_minimal(adapter, {'general.type': 'adapter', 'adapter.type': 'lora'})
        (folder / 'SHA256SUMS.txt').write_text(f'{hashlib.sha256(adapter.read_bytes()).hexdigest()}  {name}\n')
        return folder

    def test_preview_paths_do_not_create_packages_or_finished_weights(self):
        spec = self.spec()
        self.assertEqual(spec['training_directory'], 'models/Training Files/Qwen 3.8 27B Dense/nova_personality_v8')
        self.assertEqual(spec['output_directory'], 'models/qwen3.8')
        self.assertEqual(spec['data_center_ids'], ['AP-JP-1'])
        self.assertFalse(paths.training_root().exists())
        self.assertEqual(paths.training_model_name('Qwen/Qwen3-30B-A3B-Instruct-2507'),
                         'Qwen 3 30B MoE A3B Instruct 2507')
        self.assertNotEqual(paths.training_model_name('Qwen/Qwen3.8-27B'),
                            paths.training_model_name('Qwen/Qwen3.8-32B'))

    def test_export_preserves_inputs_without_creating_or_activating_adapters(self):
        spec = self.spec()
        result = train.export(spec)
        package = self.ws / result['training_directory']
        self.assertTrue(package.is_dir())
        self.assertTrue((package.parent / 'README.md').is_file())
        self.assertTrue((package / 'README.md').read_text().startswith('<!-- @nova:'))
        self.assertIn('does not train or activate', (package / 'README.md').read_text())
        self.assertEqual((package / 'Nova Personality.jsonl').read_bytes(), (self.ws / spec['data'][0]['path']).read_bytes())
        self.assertEqual(json.loads((package / 'job.json').read_text())['output_directory'], 'models/qwen3.8')
        for line in (package / 'inputs.sha256').read_text().splitlines():
            digest, name = line.split(None, 1)
            self.assertEqual(hashlib.sha256((package / name).read_bytes()).hexdigest(), digest)
        self.assertTrue((self.ws / result['zip']).is_file())
        self.assertFalse(list(paths.training_root().rglob('*.gguf')))
        self.assertFalse(paths.boot_file('active_lora.txt').exists())

    def test_identical_package_reused_but_new_recipe_does_not_replace_it(self):
        spec = self.spec()
        first = train.export(spec)
        recipe = self.ws / first['training_directory'] / 'job.json'
        before = recipe.read_bytes()
        self.assertEqual(train.export(spec)['training_directory'], first['training_directory'])
        self.assertEqual(recipe.read_bytes(), before)
        with self.assertRaises(train.TrainError):
            train.export(self.spec(params={'epochs': 3}))
        self.assertEqual(recipe.read_bytes(), before)

    def test_modified_or_incomplete_frozen_package_is_refused(self):
        spec = self.spec()
        result = train.export(spec)
        manifest = self.ws / result['training_directory'] / 'inputs.sha256'
        manifest.write_text('')
        with self.assertRaises(train.TrainError):
            train.export(spec)

    def test_import_puts_adapters_beside_selected_model_and_inputs_separately(self):
        spec = self.spec(base_model_path='models/My Qwen 3.8/Base Model.gguf')
        result = train.install_outputs(spec, self.output())
        self.assertEqual(result['installed'], ['models/My Qwen 3.8/nova_personality_v8_epoch1.gguf'])
        self.assertEqual(result['output_directory'], 'models/My Qwen 3.8')
        receipt = json.loads((self.ws / result['receipt']).read_text())
        self.assertEqual(receipt['base_model_id'], 'unsloth/Qwen3.8-27B')
        self.assertEqual(receipt['outputs'][0]['path'], result['pick'])
        self.assertFalse(list(paths.training_root().rglob('*.gguf')))
        self.assertFalse(paths.boot_file('active_lora.txt').exists())
        with self.assertRaises(train.TrainError):
            train.install_outputs(spec, self.output())

    def test_real_run_receives_persistent_inputs_and_temporary_output_location(self):
        spec = self.spec()
        outer = self
        class Runner:
            def run(self, bundle, output, job):
                outer.assertEqual(paths.display(bundle), spec['training_directory'])
                outer.assertTrue(output.is_relative_to(paths.work_dir()))
                outer.assertTrue((bundle / 'job.json').is_file())
                return outer.output()
        result = train.run(spec, jobs.Job('train', 'fixture'), Runner())
        self.assertEqual(result['training_directory'], spec['training_directory'])
        self.assertEqual(result['output_directory'], 'models/qwen3.8')

    def test_finished_output_cannot_be_redirected_into_training_inputs(self):
        for destination in ('models/Training Files/Qwen 3.8 27B Dense', '../outside'):
            with self.assertRaises(train.TrainError):
                self.spec(output_directory=destination)

    def test_manifest_cannot_copy_files_outside_selected_output_folder(self):
        output = self.output()
        (output / 'SHA256SUMS.txt').write_text('0' * 64 + '  ../elsewhere.gguf\n')
        with self.assertRaises(train.TrainError):
            train.install_outputs(self.spec(), output)
        self.assertFalse(paths.training_root().exists())

    def test_training_input_tree_is_not_installed_model_inventory(self):
        self.model_file('models/Training Files/Qwen 3.8 27B Dense/run/scratch.gguf')
        self.model_file('models/qwen3.8/model.gguf')
        self.assertEqual([item['path'] for item in inventory.scan()['models']], ['models/qwen3.8/model.gguf'])

    def test_spaced_adapter_token_is_quoted_and_discovered_as_active(self):
        adapter = 'models/Qwen 3.8 27B Dense/Nova Personality Epoch 2.gguf'
        line = train.activate_lora(adapter, 0.6)
        self.assertEqual(line, '--lora-scaled "models\\Qwen 3.8 27B Dense\\Nova Personality Epoch 2.gguf:0.6"')
        self.assertEqual(current.active_loras(), [{'role': 'personality', 'path': adapter, 'scale': 0.6}])
        self.boot('koels_lora_args.txt', '--lora-scaled "models/Qwen 3.8 27B Dense/Code Skill.gguf:0.0"\n')
        self.assertEqual(current.active_loras()[1], {'role': 'koels', 'path': 'models/Qwen 3.8 27B Dense/Code Skill.gguf', 'scale': 0.0})

    def test_selected_adapter_header_normalizes_display_name(self):
        adapter = self.model_file('models/custom/adapter.gguf', {'general.type': 'adapter', 'adapter.type': 'lora',
                   'general.base_model.count': 1, 'general.base_model.0.name': 'Qwen3.6 27B'})
        self.assertEqual(inventory.describe_adapter(adapter)['bound_to'], 'qwen3.6')
        self.assertEqual(inventory._family_of('Qwen 3.8 27B Dense'), 'qwen3.8')
        self.assertEqual(inventory._family_of('qwen3.6'), 'qwen3.6')

    def test_datacenter_review_is_explicit(self):
        self.assertEqual(self.spec(data_center_ids=['ap-jp-1', 'AP-JP-1'])['data_center_ids'], ['AP-JP-1'])
        for value in ([], '', [''], [3], ['AP-JP-1;whatever']):
            with self.assertRaises(train.TrainError):
                self.spec(data_center_ids=value)


if __name__ == '__main__':
    unittest.main()
