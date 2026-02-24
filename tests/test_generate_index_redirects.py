import random
import unittest

from generate_index import build_illustration_redirect_rules


class BuildIllustrationRedirectRulesTests(unittest.TestCase):
    def test_ill_keeps_png_and_does_not_emit_lilith_rules(self):
        file_list = [
            "illustration/song_a.png",
            "illustration/song_b.png",
            "lilith/ill/song_a.webp",
            "lilith/ill/song_b.webp",
            "lilith/ill/song_a.avif",
            "lilith/ill/song_b.avif",
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


if __name__ == "__main__":
    unittest.main()
