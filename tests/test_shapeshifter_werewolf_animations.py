"""Werewolf animation BAMs must have frames in every direction they are drawn in.

The Shapeshifter's werewolf forms use the monster_icewind animation type. Each
action has a base BAM (cycles 0-4: the five west-facing base directions) and
an ``E`` BAM (cycles 5-7: the east-facing directions, which the game mirrors).
When the game draws an empty cycle, BG2:EE 2.7.3.0 builds the sprite's FX and
bounds rectangle from uninitialized stack values
(``CGameAnimationTypeMonsterIcewind::CalculateFxRect``), and the wall
clipping polygon fill then reads and writes out of bounds, which crashes the
game or corrupts memory.

Before chriz.6, ``werewolf_white/C0W2A1.BAM`` and
``werewolf_greater_white/C0W5A1.BAM`` were byte-identical copies of their
``A1E`` files, with cycles ``[0, 0, 0, 0, 0, 15, 15, 15]``. The overhand
attack (attack 1) therefore had no frames in directions 0-4.
"""

from __future__ import annotations

import struct
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANIMATIONS = ROOT / "ArtisansKitpack/Druid/Shapeshifter/animations"

BASE_CYCLES = range(0, 5)
EAST_CYCLES = range(5, 8)
FUR_FOLDERS = 8

# Files that are not part of the eight-cycle direction sets: the inventory icon.
NOT_DIRECTIONAL_SUFFIX = "INV"


def bam_cycle_frame_counts(data: bytes, name: str = "BAM") -> list[int]:
    """Return the frame count of every cycle of a BAM V1 or BAMC file.

    BAMC is a 12-byte header (``BAMCV1  `` and the uncompressed length)
    followed by a zlib stream of the BAM V1 file.
    """

    if data[:4] == b"BAMC":
        if data[4:8] != b"V1  ":
            raise ValueError(f"{name}: unsupported BAMC version {data[4:8]!r}")
        data = zlib.decompress(data[12:])
    if data[:8] != b"BAM V1  ":
        raise ValueError(f"{name}: not a BAM V1 file: {data[:8]!r}")
    frame_count, cycle_count, _transparent, frames_offset = struct.unpack_from(
        "<HBBI", data, 8
    )
    cycle_table = frames_offset + frame_count * 12
    return [
        struct.unpack_from("<HH", data, cycle_table + index * 4)[0]
        for index in range(cycle_count)
    ]


def werewolf_sets() -> dict[str, dict[str, Path]]:
    """Map every werewolf folder to its BAM files by stem."""

    return {
        folder.name: {path.stem: path for path in sorted(folder.glob("*.BAM"))}
        for folder in sorted(ANIMATIONS.glob("werewolf*"))
        if folder.is_dir()
    }


def classify(stems: set[str]) -> tuple[set[str], set[str], set[str]]:
    """Split stems into base files, their E files and everything else.

    A base file is a stem whose ``stem + "E"`` exists (``C0W5DE`` is the death
    animation, ``C0W5DEE`` its east file).
    """

    base = {stem for stem in stems if stem + "E" in stems}
    east = {stem for stem in stems if stem.endswith("E") and stem[:-1] in stems}
    other = stems - base - east
    return base, east, other


class BamReaderTests(unittest.TestCase):
    """The helper that the checks depend on must read both BAM flavors."""

    @staticmethod
    def build_bam(cycle_frames: list[int]) -> bytes:
        total = sum(cycle_frames)
        frames_offset = 0x18
        header = b"BAM V1  " + struct.pack(
            "<HBBIII", total, len(cycle_frames), 0, frames_offset, 0, 0
        )
        frames = b"\0" * (total * 12)
        cycles = b""
        first = 0
        for count in cycle_frames:
            cycles += struct.pack("<HH", count, first)
            first += count
        return header + frames + cycles

    def test_reads_plain_bam(self) -> None:
        counts = [0, 0, 3, 0, 1, 15, 15, 15]
        self.assertEqual(counts, bam_cycle_frame_counts(self.build_bam(counts)))

    def test_reads_bamc(self) -> None:
        counts = [16, 16, 16, 16, 16, 0, 0, 0]
        plain = self.build_bam(counts)
        bamc = b"BAMCV1  " + struct.pack("<I", len(plain)) + zlib.compress(plain)
        self.assertEqual(counts, bam_cycle_frame_counts(bamc))

    def test_rejects_other_files(self) -> None:
        with self.assertRaises(ValueError):
            bam_cycle_frame_counts(b"BM" + b"\0" * 64)


class WerewolfAnimationTests(unittest.TestCase):
    def test_all_fur_folders_are_checked(self) -> None:
        sets = werewolf_sets()
        self.assertEqual(FUR_FOLDERS, len(sets), sorted(sets))
        for folder, files in sets.items():
            base, east, other = classify(set(files))
            self.assertTrue(base, folder)
            self.assertEqual({stem[:-1] for stem in east}, base, folder)
            self.assertEqual(
                {stem for stem in other if not stem.endswith(NOT_DIRECTIONAL_SUFFIX)},
                set(),
                f"{folder}: files that are neither a base file nor its E file",
            )

    def test_base_files_have_frames_in_cycles_0_to_4(self) -> None:
        empty = []
        for folder, files in werewolf_sets().items():
            base, _east, _other = classify(set(files))
            for stem in sorted(base):
                path = files[stem]
                counts = bam_cycle_frame_counts(path.read_bytes(), path.name)
                self.assertEqual(8, len(counts), f"{folder}/{path.name}")
                for cycle in BASE_CYCLES:
                    if counts[cycle] == 0:
                        empty.append(f"{folder}/{path.name} cycle {cycle}")
        self.assertEqual([], empty, "base BAMs with empty cycles 0-4")

    def test_east_files_have_frames_in_cycles_5_to_7(self) -> None:
        empty = []
        for folder, files in werewolf_sets().items():
            _base, east, _other = classify(set(files))
            for stem in sorted(east):
                path = files[stem]
                counts = bam_cycle_frame_counts(path.read_bytes(), path.name)
                self.assertEqual(8, len(counts), f"{folder}/{path.name}")
                for cycle in EAST_CYCLES:
                    if counts[cycle] == 0:
                        empty.append(f"{folder}/{path.name} cycle {cycle}")
        self.assertEqual([], empty, "E BAMs with empty cycles 5-7")

    def test_attack_1_shows_attack_2_art_in_the_white_furs(self) -> None:
        # chriz.6 repair: A1 is a copy of the same fur's A2. It is not the
        # only valid content, so this pins the shipped repair, nothing else.
        for folder, prefix in (
            ("werewolf_white", "C0W2"),
            ("werewolf_greater_white", "C0W5"),
        ):
            attack_1 = (ANIMATIONS / folder / f"{prefix}A1.BAM").read_bytes()
            attack_2 = (ANIMATIONS / folder / f"{prefix}A2.BAM").read_bytes()
            self.assertEqual(attack_2, attack_1, folder)


if __name__ == "__main__":
    unittest.main()
