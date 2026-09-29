"""Offline release-identity checks; never launch WeiDU or touch a game."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_version", ROOT / "tools/version.py")
version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(version)
NEXT = "v4.81a-dev.85928f9-chriz.1"


class ReleaseVersionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.original = {}
        for index, relative in enumerate(version.INSTALLERS):
            path = self.root / relative
            path.parent.mkdir(parents=True)
            newline = b"\r\n" if index % 2 else b"\n"
            data = newline.join((
                b"AUTHOR ~The Artisan~", b"VERSION ~chriz-v1.6.0~",
                "// Existing work: — keep this".encode("utf-8"),
                b"BEGIN ~Optional dialogue~ DESIGNATED 51010", b"",
            ))
            path.write_bytes(data)
            self.original[relative] = data

    def test_migration_preserves_every_other_byte_and_is_idempotent(self):
        historical = self.root / "chriz-v1.6.0.md"
        historical.write_bytes(b"Published version: chriz-v1.6.0\r\n")
        version.set_version(self.root, NEXT)
        version.set_version(self.root, NEXT)
        self.assertEqual(version.check_version(self.root, NEXT), NEXT)
        for relative, data in self.original.items():
            self.assertEqual(
                (self.root / relative).read_bytes(),
                data.replace(b"VERSION ~chriz-v1.6.0~", f"VERSION ~{NEXT}~".encode()),
            )
        self.assertEqual(historical.read_bytes(), b"Published version: chriz-v1.6.0\r\n")

    def test_rejects_mixed_installer_versions(self):
        version.set_version(self.root, NEXT)
        path = self.root / version.INSTALLERS[-1]
        path.write_bytes(path.read_bytes().replace(NEXT.encode(), b"v4.81a-chriz.2"))
        with self.assertRaisesRegex(ValueError, "disagree"):
            version.check_version(self.root)

    def test_rejects_tag_mismatch(self):
        version.set_version(self.root, NEXT)
        with self.assertRaisesRegex(ValueError, "Expected"):
            version.check_version(self.root, "v4.81a-dev.85928f9-chriz.2")

    def test_invalid_identity_does_not_write(self):
        for invalid in ("chriz-v1.7.0", "v4.81a", "v4.81a-chriz.0", "v4.81a~chriz.1"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                version.set_version(self.root, invalid)
        for relative, data in self.original.items():
            self.assertEqual((self.root / relative).read_bytes(), data)

    def test_preflights_all_installers_before_writing(self):
        last = self.root / version.INSTALLERS[-1]
        for malformed in (b"AUTHOR ~The Artisan~\n", b"VERSION ~old~\nVERSION ~other~\n"):
            last.write_bytes(malformed)
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, "exactly one"):
                version.set_version(self.root, NEXT)
            for relative in version.INSTALLERS[:-1]:
                self.assertEqual((self.root / relative).read_bytes(), self.original[relative])
            self.assertEqual(last.read_bytes(), malformed)

    def test_upstream_only_change_can_keep_patch_revision(self):
        version.set_version(self.root, NEXT)
        for updated in ("v4.81a-dev.abcdef0-chriz.1", "v5.0-chriz.1", "v5.0-chriz.2"):
            version.set_version(self.root, updated)
            self.assertEqual(version.check_version(self.root, updated), updated)

    def test_repository_versions_have_matching_release_notes(self):
        current = version.check_version(ROOT)
        notes = ROOT / "docs/releases" / f"{current}.md"
        self.assertTrue(notes.is_file(), f"Missing release notes: {notes}")
        self.assertIn(current, notes.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
