import csv
import json
import os
import shutil
import tempfile
import unittest

import info_export
import translate
from info_export import InfoContractError

SONG_COUNT = 120


def _base_song(index, with_at=False):
    levels = {
        "EZ": {"charter": f"EZCharter{index}", "difficulty": 1 + (index % 5)},
        "HD": {"charter": f"HDCharter{index}", "difficulty": 7 + (index % 5)},
        "IN": {"charter": f"INCharter{index}", "difficulty": 12 + (index % 5)},
    }
    if with_at:
        levels["AT"] = {"charter": f"ATCharter{index}", "difficulty": 15.5}
    return {
        "id": f"Song{index}.Author{index}.0",
        "key": f"Song{index}",
        "name": f"Song {index}",
        "composer": f"Composer {index}",
        "illustrator": f"Illustrator {index}",
        "preview_time": 1.0,
        "preview_end_time": 2.0,
        "levels": levels,
    }


class InfoExportTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.output_root = os.path.join(self.root, "output")
        self.info_dir = os.path.join(self.output_root, "info")
        os.makedirs(self.info_dir)

        self.songs = [_base_song(index, with_at=(index == 1)) for index in range(SONG_COUNT)]
        self.songs[0]["name"] = {"zh_cn": "第一首", "en": "First"}
        self._write("songs.json", self.songs)
        self._write("version.json", {"code": 155, "name": "4.0.0"})
        self._write("collection.json", [
            {"title": {"zh_cn": "A"}, "files": [
                {"key": "k1", "sub_index": 1, "name": {"zh_cn": "收藏一"}},
                {"key": "k2", "sub_index": 2, "name": {"zh_cn": "收藏二"}},
            ]},
            {"title": {"zh_cn": "B"}, "files": [
                {"key": "k1", "sub_index": 9, "name": {"zh_cn": "重复键"}},
            ]},
        ])
        self._write("avatars.json", [
            {"name": "Glaciaxion", "addressable_key": "avatar.Glaciaxion"},
            {"name": "NoKey", "addressable_key": ""},
        ])
        self._write("tips.json", {"zh_cn": ["# 标题", "提示二"], "zh_tw": ["提示一"]})

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, name, data):
        with open(os.path.join(self.info_dir, name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _export(self):
        return info_export.export_published_info(self.output_root)

    def _read_rows(self, name):
        with open(os.path.join(self.info_dir, name), encoding="utf-8", newline="") as f:
            return list(csv.reader(f))

    def _read_lines(self, name):
        with open(os.path.join(self.info_dir, name), encoding="utf-8") as f:
            return f.read().splitlines()


class InfoTableTests(InfoExportTestCase):
    def test_info_csv_uses_canonical_columns(self):
        self._export()
        rows = self._read_rows("info.csv")

        self.assertEqual(rows[0], info_export.SONG_HEADER)
        self.assertEqual(len(rows), SONG_COUNT + 1)
        self.assertTrue(all(len(row) == 12 for row in rows))

        first = rows[1]
        self.assertEqual(first[0], "Song0.Author0")
        self.assertEqual(first[1], "第一首")
        self.assertEqual(first[4:8], ["1.0", "7.0", "12.0", ""])
        self.assertEqual(first[8:12], ["EZCharter0", "HDCharter0", "INCharter0", ""])

    def test_at_level_is_written_when_present(self):
        self._export()
        rows = self._read_rows("info.csv")
        row = next(row for row in rows[1:] if row[0] == "Song1.Author1")

        self.assertEqual(row[7], "15.5")
        self.assertEqual(row[11], "ATCharter1")

    def test_difficulty_csv_is_constants_only(self):
        self._export()
        rows = self._read_rows("difficulty.csv")

        self.assertEqual(rows[0], info_export.DIFFICULTY_HEADER)
        self.assertTrue(all(len(row) == 5 for row in rows))
        self.assertEqual(rows[1][1:], ["1.0", "7.0", "12.0", ""])

    def test_info_tsv_matches_info_csv(self):
        self._export()
        tsv_rows = [line.split("\t") for line in self._read_lines("info.tsv")]

        self.assertEqual(tsv_rows[0], info_export.SONG_HEADER)
        self.assertEqual(tsv_rows, self._read_rows("info.csv"))

    def test_difficulty_tsv_matches_difficulty_csv(self):
        self._export()
        tsv_rows = [line.split("\t") for line in self._read_lines("difficulty.tsv")]

        self.assertEqual(tsv_rows, self._read_rows("difficulty.csv"))

    def test_all_info_keeps_phiinfo_ids(self):
        self._export()
        with open(os.path.join(self.info_dir, "all_info.json"), encoding="utf-8") as f:
            all_info = json.load(f)

        self.assertEqual(all_info["songs"][0]["id"], "Song0.Author0.0")
        self.assertEqual([item["key"] for item in all_info["collection"]], ["k1", "k2"])
        self.assertEqual(all_info["collection"][0]["sub_index"], 9)
        self.assertEqual(all_info["collection"][0]["name"], "收藏一")

    def test_avatar_and_tmp_files_strip_prefix(self):
        self._export()

        self.assertEqual(self._read_lines("avatar.txt"), ["Glaciaxion", "NoKey"])
        self.assertEqual(self._read_lines("tmp.tsv"), ["Glaciaxion\tGlaciaxion", "NoKey\t"])

    def test_tips_txt_falls_back_and_skips_comments(self):
        self._export()
        self.assertEqual(self._read_lines("tips.txt"), ["提示二"])

        self._write("tips.json", {"ja": ["ヒント"]})
        self._export()
        self.assertEqual(self._read_lines("tips.txt"), ["ヒント"])

    def test_version_txt(self):
        self._export()
        self.assertEqual(self._read_lines("version.txt"), ["4.0.0 (155)"])


class ValidateTests(InfoExportTestCase):
    def test_export_returns_summary(self):
        summary = self._export()

        self.assertEqual(summary["songs"], SONG_COUNT)
        self.assertEqual(summary["version"], "4.0.0 (155)")

    def test_manifest_covers_every_published_file(self):
        self._export()
        with open(os.path.join(self.info_dir, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)

        present = {name for name in os.listdir(self.info_dir) if name != "manifest.json"}
        self.assertEqual(set(manifest["files"]), present)
        for name in ("info.csv", "difficulty.csv", "info.tsv", "difficulty.tsv", "all_info.json",
                     "version.txt", "collection.tsv", "avatar.txt", "tmp.tsv", "tips.txt"):
            self.assertIn(name, manifest["files"])
        self.assertEqual(manifest["counts"]["songs"], SONG_COUNT)
        self.assertEqual(manifest["version"], "4.0.0 (155)")

    def test_verify_only_accepts_generated_output(self):
        self._export()
        summary = info_export.validate(self.output_root, check_manifest=True)

        self.assertEqual(summary["songs"], SONG_COUNT)

    def test_verify_only_detects_tampering(self):
        self._export()
        with open(os.path.join(self.info_dir, "difficulty.csv"), "a", encoding="utf-8") as f:
            f.write("Extra.Song,9.9,9.9,9.9,9.9\n")

        with self.assertRaises(InfoContractError):
            info_export.validate(self.output_root, check_manifest=True)

    def test_rejects_song_count_mismatch(self):
        self._export()
        rows = self._read_rows("difficulty.csv")
        with open(os.path.join(self.info_dir, "difficulty.csv"), "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(rows[:-1])

        with self.assertRaises(InfoContractError) as ctx:
            info_export.validate(self.output_root)
        self.assertIn("曲目集合", str(ctx.exception))

    def test_rejects_header_drift(self):
        self._export()
        rows = self._read_rows("info.csv")
        rows[0] = info_export.SONG_HEADER[:8]
        with open(os.path.join(self.info_dir, "info.csv"), "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(rows)

        with self.assertRaises(InfoContractError) as ctx:
            info_export.validate(self.output_root)
        self.assertIn("表头", str(ctx.exception))

    def test_rejects_ragged_rows(self):
        self._export()
        lines = self._read_lines("difficulty.tsv")
        lines[1:] = ["\t".join(line.split("\t")[:-1]) for line in lines[1:]]
        with open(os.path.join(self.info_dir, "difficulty.tsv"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        with self.assertRaises(InfoContractError) as ctx:
            info_export.validate(self.output_root)
        self.assertIn("列", str(ctx.exception))

    def test_rejects_out_of_range_difficulty(self):
        self.songs[0]["levels"]["EZ"]["difficulty"] = 99
        self._write("songs.json", self.songs)

        with self.assertRaises(InfoContractError) as ctx:
            self._export()
        self.assertIn("定数越界", str(ctx.exception))

    def test_missing_songs_export_fails(self):
        os.remove(os.path.join(self.info_dir, "songs.json"))

        with self.assertRaises(InfoContractError):
            self._export()

    def test_duplicate_song_id_fails(self):
        self.songs.append(_base_song(0))
        self._write("songs.json", self.songs)

        with self.assertRaises(InfoContractError) as ctx:
            self._export()
        self.assertIn("重复 id", str(ctx.exception))


class TranslateAssetPathTests(unittest.TestCase):
    def test_chart_and_music_mapping(self):
        self.assertEqual(
            translate._map_asset_path("Assets/Tracks/Song.Author.0/Chart_EZ.json.txt"),
            "chart/Song.Author.0/EZ.json",
        )
        self.assertEqual(
            translate._map_asset_path("Assets/Tracks/Song.Author.0/music.wav.ogg"),
            "music/Song.Author.ogg",
        )

    def test_illustration_and_avatar_mapping(self):
        self.assertEqual(
            translate._map_asset_path("Assets/Tracks/Song.Author.0/Illustration.jpg.png"),
            "illustration/Song.Author.png",
        )
        self.assertEqual(
            translate._map_asset_path("Assets/Tracks/Song.Author.0/IllustrationLowRes.jpg.png"),
            "illustrationLowRes/Song.Author.png",
        )
        self.assertEqual(translate._map_asset_path("avatar.SunsetRay.png"), "avatar/SunsetRay.png")

    def test_metadata_is_skipped(self):
        self.assertIsNone(translate._map_asset_path("metadata.json"))


if __name__ == "__main__":
    unittest.main()
