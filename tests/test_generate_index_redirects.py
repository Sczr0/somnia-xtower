import random
import unittest

from generate_index import (
    build_illustration_redirect_rules,
    is_hidden_web_path,
    METADATA_FILE_WEB_PATHS,
    remove_generated_illustration_redirects,
)


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

    def test_existing_generated_ill_redirects_are_removed_before_rewrite(self):
        content = "\n".join(
            [
                "/manual/path /target 200",
                "# === Auto-generated illustration redirects (2 png files, 1 groups) ===",
                "/ill/1/0.jpg /illustration/song_a.png 200",
                "/ill/1/1.jpg /illustration/song_b.png 200",
                "# === Auto-generated lilith illustration redirects ===",
                "/lilith/ill/1/0.webp /lilith/ill/song_a.webp 200",
            ]
        )

        cleaned = remove_generated_illustration_redirects(content)

        self.assertIn("/manual/path /target 200", cleaned)
        self.assertNotIn("/ill/1/0.jpg", cleaned)
        self.assertNotIn("/lilith/ill/1/0.webp", cleaned)
        self.assertNotIn("Auto-generated illustration redirects", cleaned)

    def test_hidden_output_paths_are_filtered(self):
        self.assertTrue(is_hidden_web_path(".git/HEAD"))
        self.assertTrue(is_hidden_web_path("nested/.cache/file.json"))
        self.assertFalse(is_hidden_web_path("_headers"))
        self.assertFalse(is_hidden_web_path("assets/index.css"))

    def test_frontend_metadata_paths_are_excluded_from_search_index(self):
        self.assertIn("checksums.sha256", METADATA_FILE_WEB_PATHS)
        self.assertIn("_redirects", METADATA_FILE_WEB_PATHS)
        self.assertIn("version.txt", METADATA_FILE_WEB_PATHS)
        self.assertIn("info/version.txt", METADATA_FILE_WEB_PATHS)


if __name__ == "__main__":
    unittest.main()
