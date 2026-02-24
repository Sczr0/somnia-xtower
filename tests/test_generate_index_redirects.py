import random
import tempfile
import unittest
from pathlib import Path

from generate_index import build_illustration_redirect_rules, materialize_lilith_illustration_variants


class BuildIllustrationRedirectRulesTests(unittest.TestCase):
    def test_ill_keeps_png_and_does_not_emit_lilith_rules(self):
        file_list = [
            "illustration/song_a.png",
            "illustration/song_b.png",
            "illustration/song_a.webp",
            "illustration/song_b.webp",
            "illustration/song_a.avif",
            "illustration/song_b.avif",
            "avatar/user_1.png",
        ]

        rules, meta = build_illustration_redirect_rules(
            file_list,
            hash_length=1,
            min_groups=1,
            rng=random.Random(7),
        )
        redirect_lines = [
            line.strip()
            for line in rules
            if line.strip() and not line.strip().startswith("#")
        ]

        ill_lines = [line for line in redirect_lines if line.startswith("/ill/")]
        self.assertTrue(ill_lines)
        self.assertTrue(all(line.split()[0].endswith(".jpg") for line in ill_lines))
        self.assertTrue(all(line.split()[1].endswith(".png") for line in ill_lines))
        self.assertFalse(any(line.startswith("/lilith/ill/") for line in redirect_lines))

    def test_no_png_illustration_will_skip_redirect_generation(self):
        rules, meta = build_illustration_redirect_rules(
            ["illustration/song_a.webp", "illustration/song_a.avif"],
            hash_length=1,
            min_groups=1,
            rng=random.Random(1),
        )
        self.assertEqual(rules, [])
        self.assertEqual(meta, {})


class MaterializeLilithIllustrationVariantsTests(unittest.TestCase):
    def test_copy_webp_and_avif_into_physical_lilith_folder(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            illustration = root / "illustration"
            illustration.mkdir(parents=True, exist_ok=True)
            (illustration / "song_a.webp").write_bytes(b"webp_a")
            (illustration / "song_a.avif").write_bytes(b"avif_a")
            (illustration / "song_a.png").write_bytes(b"png_a")
            (illustration / "nested").mkdir(parents=True, exist_ok=True)
            (illustration / "nested" / "song_b.webp").write_bytes(b"webp_b")

            meta = materialize_lilith_illustration_variants(str(root))

            self.assertEqual(meta["source_count"], 3)
            self.assertEqual(meta["copied_count"], 3)
            self.assertTrue((root / "lilith" / "ill" / "song_a.webp").exists())
            self.assertTrue((root / "lilith" / "ill" / "song_a.avif").exists())
            self.assertTrue((root / "lilith" / "ill" / "nested" / "song_b.webp").exists())
            self.assertFalse((root / "lilith" / "ill" / "song_a.png").exists())


if __name__ == "__main__":
    unittest.main()
