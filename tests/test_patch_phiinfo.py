import unittest

from patch_phiinfo import patch_source

UPSTREAM = """        switch (raw.Format)
        {
            case 34:
            {
                EtcDecoder.DecompressETC<ColorBGRA<byte>, byte>(
                    bytes, raw.Width, raw.Height, out var data);
                img = Image.LoadPixelData<Bgra32>(data, raw.Width, raw.Height);
                break;
            }

            case 47:
            {
                EtcDecoder.DecompressETC2A8<ColorBGRA<byte>, byte>(
                    bytes, raw.Width, raw.Height, out var data);
                img = Image.LoadPixelData<Bgra32>(data, raw.Width, raw.Height);
                break;
            }

            default:
                throw new NotSupportedException($"Unknown format: {raw.Format}");
        }
"""


class PatchPhiInfoTestCase(unittest.TestCase):
    def test_inserts_etc2_rgb_case_before_case_47(self):
        patched = patch_source(UPSTREAM)
        self.assertIn("case 45:", patched)
        self.assertIn(
            "EtcDecoder.DecompressETC2<ColorBGRA<byte>, byte>(\n"
            "                    bytes, raw.Width, raw.Height, out var data);",
            patched,
        )
        self.assertLess(patched.index("case 45:"), patched.index("case 47:"))
        self.assertEqual(patched.count("case 45:"), 1)

    def test_is_idempotent(self):
        once = patch_source(UPSTREAM)
        self.assertEqual(patch_source(once), once)

    def test_missing_anchor_fails_loudly(self):
        with self.assertRaises(ValueError):
            patch_source("class Foo { }\n")


if __name__ == "__main__":
    unittest.main()
