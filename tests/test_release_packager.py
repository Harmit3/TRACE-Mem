"""Exercise release archive naming and existing safety boundaries with a local Git fixture."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "package_technical_release.py"


class ReleasePackagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Release fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "fixture")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True,
                              capture_output=True, text=True)

    def package(self, name, *args):
        output = self.root / name
        result = subprocess.run([sys.executable, str(SCRIPT), "HEAD", str(output), *args],
                                cwd=self.repo, capture_output=True, text=True)
        return output, result

    def test_default_candidate_prefix(self):
        output, result = self.package("candidate.zip")
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(output) as archive:
            self.assertIn("TRACE-Mem-1.0.0-rc.1/README.md", archive.namelist())
            self.assertIsNone(archive.testzip())

    def test_final_prefix(self):
        output, result = self.package("final.zip", "--version", "1.0.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(output) as archive:
            self.assertIn("TRACE-Mem-1.0.0/README.md", archive.namelist())
            self.assertIsNone(archive.testzip())
        self.assertIn("SHA-256", result.stdout)

    def test_invalid_version_rejected(self):
        output, result = self.package("invalid.zip", "--version", "../unsafe")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_private_path_rejected(self):
        (self.repo / "data").mkdir()
        (self.repo / "data" / "private.txt").write_text("fixture", encoding="utf-8")
        self.git("add", "data/private.txt")
        self.git("commit", "-qm", "private fixture")
        output, result = self.package("private.zip", "--version", "1.0.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_existing_archive_not_overwritten(self):
        output = self.root / "existing.zip"
        output.write_bytes(b"original")
        _, result = self.package("existing.zip", "--version", "1.0.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), b"original")
