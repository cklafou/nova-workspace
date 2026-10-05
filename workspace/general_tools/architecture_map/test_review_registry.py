# Last updated: 2026-10-05 21:33:05
# @nova: Ensures corrupted review metadata cannot silently certify Orient.
import json
from pathlib import Path
import tempfile
import unittest
from orient import load_reviews, refresh, REVIEWS_REL

class RegistryTests(unittest.TestCase):
    def test_invalid_registry_cannot_publish_apparently_healthy_docs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/REVIEWS_REL;p.parent.mkdir(parents=True)
            for value in ['{broken', '[]', '{}', '{"sections": []}', '{"sections": {"README.md": null}}']:
                p.write_text(value)
                with self.subTest(value=value), self.assertRaisesRegex(ValueError,'invalid review registry'):
                    refresh(root,force=True)
                self.assertFalse((root/'Orient/README.md').exists())
