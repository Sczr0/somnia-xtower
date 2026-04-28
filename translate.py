"""将 PhiInfo export 输出翻译为当前站点的目录结构。"""
import os
import json
import shutil

PHIINFO_OUTPUT = "output"
ASSET_DIR = os.path.join(PHIINFO_OUTPUT, "asset")
INFO_DIR = os.path.join(PHIINFO_OUTPUT, "info")
LEVELS = ["EZ", "HD", "IN", "AT"]


def translate_assets():
    """将 PhiInfo 的 asset/ 文件映射到站点目录结构。"""
    if not os.path.isdir(ASSET_DIR):
        print("  [skip] asset/ 目录不存在")
        return

    counts = {}
    for root, _dirs, files in os.walk(ASSET_DIR):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, ASSET_DIR).replace("\\", "/")
            dest = _map_asset_path(rel)
            if dest is None:
                continue
            dest = os.path.join(PHIINFO_OUTPUT, dest)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(src, dest)
            cat = dest.rsplit("/", 2)[-2] if dest.count("/") >= 2 else "root"
            counts[cat] = counts.get(cat, 0) + 1

    shutil.rmtree(ASSET_DIR, ignore_errors=True)
    for cat, n in sorted(counts.items()):
        print(f"  {cat}: {n} files")


def _map_asset_path(rel):
    """将一条 PhiInfo asset 路径映射为目标站点路径。"""
    # 表单后缀：PhiInfo 在所有原始 key 后加了 .txt / .ogg / .png
    if rel.endswith(".txt"):
        orig = rel[:-4]  # 去掉 .txt，得到 Assets/Tracks/Song.Author.0/Chart_EZ.json
    elif rel.endswith(".ogg"):
        orig = rel[:-4]  # 去掉 .ogg，得到 Assets/Tracks/Song.Author.0/music.wav
    elif rel.endswith(".png"):
        orig = rel[:-4]  # 去掉 .png，得到 Assets/Tracks/Song.Author.0/Illustration.jpg 或 avatar.xxx
    elif rel == "metadata.json":
        return None  # 资产清单不需要
    else:
        return None

    # 去掉 PhiInfo 保留的 "Assets/Tracks/" 前缀
    if orig.startswith("Assets/Tracks/"):
        orig = orig[len("Assets/Tracks/"):]

    # 头像：avatar.{name}.png → avatar/{name}.png
    if orig.startswith("avatar."):
        name = orig[len("avatar."):]
        return f"avatar/{name}.png"

    # 谱面 / 音乐 / 曲绘：SongID.Author.0/XXX
    folder, filename = os.path.split(orig)
    song_id = folder.replace(".0", "")

    if filename.startswith("Chart_"):
        # Song.Author.0/Chart_EZ.json → chart/Song.Author.0/EZ.json
        diff = filename.replace("Chart_", "").replace(".json", "")
        return f"chart/{folder}/{diff}.json"

    if filename.startswith("music"):
        # Song.Author.0/music.wav → music/Song.Author.ogg
        return f"music/{song_id}.ogg"

    # 曲绘
    if "IllustrationBlur" in filename:
        return f"illustrationBlur/{song_id}.png"
    if "IllustrationLowRes" in filename:
        return f"illustrationLowRes/{song_id}.png"
    if "Illustration" in filename:
        return f"illustration/{song_id}.png"

    return None


def translate_info():
    """将 PhiInfo 的 info/songs.json 转为 phira.py 所需的 TSV 文件。"""
    songs_path = os.path.join(INFO_DIR, "songs.json")
    if not os.path.exists(songs_path):
        print("  [warn] songs.json not found, skipping info translation")
        return

    with open(songs_path, "r", encoding="utf-8") as f:
        songs = json.load(f)

    info_lines = []
    diff_lines = []

    for song in songs:
        sid = song.get("key", "")
        name = song.get("name", {})
        if isinstance(name, dict):
            name = name.get("zh_cn", "") or next(iter(name.values()), "")
        composer = song.get("composer", "")
        illustrator = song.get("illustrator", "")

        levels = song.get("levels", {})
        charters = []
        diffs = []
        charter_map = song.get("charters", {})
        diff_map = song.get("difficulty", {})

        if isinstance(levels, dict):
            # levels = {"EZ": ..., "HD": ..., "IN": ..., "AT": ...}
            for lv_name in LEVELS:
                lv_data = levels.get(lv_name)
                if isinstance(lv_data, dict):
                    charters.append(str(lv_data.get("charter", "")))
                    diffs.append(str(lv_data.get("difficulty", "")))
                elif lv_name in levels:
                    # value is a number (difficulty), charter from separate map
                    charters.append(str(charter_map.get(lv_name, "")))
                    diffs.append(str(lv_data))
                else:
                    charters.append("")
                    diffs.append("")
        elif isinstance(levels, list) and levels and isinstance(levels[0], str):
            song_charters = song.get("charters", [])
            song_diffs = song.get("difficulty", [])
            for i in range(len(levels)):
                charters.append(str(song_charters[i]) if i < len(song_charters) else "")
                diffs.append(str(song_diffs[i]) if i < len(song_diffs) else "")
        else:
            for lv in levels:
                charters.append(str(lv.get("charter", "") or ""))
                diffs.append(str(lv.get("difficulty", "")))

        while len(charters) < len(LEVELS):
            charters.append("")
        while len(diffs) < len(LEVELS):
            diffs.append("")

        info_lines.append("\t".join([sid, name, composer, illustrator] + charters[:4]))
        diff_lines.append("\t".join([sid] + diffs[:4]))

    with open(os.path.join(INFO_DIR, "info.tsv"), "w", encoding="utf-8") as f:
        f.write("\n".join(info_lines) + "\n")
    with open(os.path.join(INFO_DIR, "difficulty.tsv"), "w", encoding="utf-8") as f:
        f.write("\n".join(diff_lines) + "\n")

    print(f"  info.tsv: {len(songs)} songs")
    print(f"  difficulty.tsv: {len(songs)} songs")


def translate_version():
    """将 PhiInfo 的 info/version.json 转为 version.txt。"""
    ver_path = os.path.join(INFO_DIR, "version.json")
    if not os.path.exists(ver_path):
        print("  [warn] version.json not found")
        return

    with open(ver_path, "r", encoding="utf-8") as f:
        ver = json.load(f)

    text = f'{ver.get("name", "unknown")} ({ver.get("code", "0")})'
    with open(os.path.join(INFO_DIR, "version.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"  version.txt: {text}")


if __name__ == "__main__":
    print("--- Translating PhiInfo output ---")
    translate_assets()
    translate_info()
    translate_version()
    print("--- Done ---")
