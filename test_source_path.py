"""Reject source drift before any upstream script is executed."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import source_path


class SourcePathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "audit"
        root.mkdir()
        self.primary = root / "upstream" / "scripts"
        self.fallback = root.parent / "sources" / "rustchain-bounties" / "scripts"
        self.fixtures = {"gate.py": b"gate fixture\n", "payer.py": b"payer fixture\n"}
        pins = {name: source_path.git_blob_sha(data) for name, data in self.fixtures.items()}
        patcher = patch.multiple(source_path, __file__=str(root / "source_path.py"), UPSTREAM_BLOBS=pins)
        patcher.start()
        self.addCleanup(patcher.stop)

    def populate(self, directory):
        directory.mkdir(parents=True)
        for name, data in self.fixtures.items():
            (directory / name).write_bytes(data)

    def test_valid_cached_sources_are_accepted(self):
        self.populate(self.primary)
        self.assertEqual(source_path.scripts_dir(), self.primary)

    def test_modified_cache_is_rejected_even_with_valid_fallback(self):
        self.populate(self.primary)
        self.populate(self.fallback)
        for filename in self.fixtures:
            with self.subTest(filename=filename):
                (self.primary / filename).write_bytes(b"modified source\n")
                with self.assertRaisesRegex(SystemExit, filename + ": expected Git blob"):
                    source_path.scripts_dir()
                (self.primary / filename).write_bytes(self.fixtures[filename])

    def test_valid_fallback_is_accepted_when_cache_is_missing(self):
        self.populate(self.fallback)
        self.assertEqual(source_path.scripts_dir(), self.fallback)

    def test_modified_fallback_is_rejected(self):
        self.populate(self.fallback)
        (self.fallback / "payer.py").write_bytes(b"modified source\n")
        with self.assertRaisesRegex(SystemExit, "payer.py: expected Git blob"):
            source_path.scripts_dir()

    def test_missing_sources_explain_preparation_command(self):
        with self.assertRaisesRegex(SystemExit, "python prepare_source.py"):
            source_path.scripts_dir()


if __name__ == "__main__":
    unittest.main()
