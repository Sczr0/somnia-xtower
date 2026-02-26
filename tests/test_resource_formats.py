import unittest

from resource import (
    resolve_illustration_export_formats,
    resolve_lilith_ill_export_formats,
    resolve_lilith_ill_low_export_formats,
)


class ResolveIllustrationExportFormatsTests(unittest.TestCase):
    def test_default_formats_include_png_webp_avif_when_supported(self):
        resolved = resolve_illustration_export_formats(
            raw_formats=None,
            support_checker=lambda _fmt: True,
            logger=None,
        )
        self.assertEqual(resolved, ("png", "webp", "avif"))

    def test_unsupported_avif_will_be_filtered_out(self):
        resolved = resolve_illustration_export_formats(
            raw_formats=None,
            support_checker=lambda fmt: fmt != "avif",
            logger=None,
        )
        self.assertEqual(resolved, ("png", "webp"))

    def test_png_is_forced_even_if_not_requested(self):
        resolved = resolve_illustration_export_formats(
            raw_formats="webp,avif",
            support_checker=lambda _fmt: True,
            logger=None,
        )
        self.assertEqual(resolved, ("png", "webp", "avif"))


class ResolveLilithIllExportFormatsTests(unittest.TestCase):
    def test_default_formats_exclude_png(self):
        resolved = resolve_lilith_ill_export_formats(
            raw_formats=None,
            support_checker=lambda _fmt: True,
            logger=None,
        )
        self.assertEqual(resolved, ("webp", "avif"))

    def test_fallback_to_empty_when_only_png_available(self):
        resolved = resolve_lilith_ill_export_formats(
            raw_formats=None,
            support_checker=lambda fmt: fmt == "png",
            logger=None,
        )
        self.assertEqual(resolved, ())

    def test_explicit_png_input_will_not_produce_lilith_variant(self):
        resolved = resolve_lilith_ill_export_formats(
            raw_formats="png",
            support_checker=lambda _fmt: True,
            logger=None,
        )
        self.assertEqual(resolved, ())


class ResolveLilithIllLowExportFormatsTests(unittest.TestCase):
    def test_default_formats_exclude_png(self):
        resolved = resolve_lilith_ill_low_export_formats(
            raw_formats=None,
            support_checker=lambda _fmt: True,
            logger=None,
        )
        self.assertEqual(resolved, ("webp", "avif"))

    def test_fallback_to_empty_when_only_png_available(self):
        resolved = resolve_lilith_ill_low_export_formats(
            raw_formats=None,
            support_checker=lambda fmt: fmt == "png",
            logger=None,
        )
        self.assertEqual(resolved, ())

    def test_explicit_png_input_will_not_produce_lilith_low_variant(self):
        resolved = resolve_lilith_ill_low_export_formats(
            raw_formats="png",
            support_checker=lambda _fmt: True,
            logger=None,
        )
        self.assertEqual(resolved, ())


if __name__ == "__main__":
    unittest.main()
