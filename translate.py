"""将 PhiInfo export 输出翻译为当前站点的目录结构。"""
import os
import json
import shutil

PHIINFO_OUTPUT = "output"
ASSET_DIR = os.path.join(PHIINFO_OUTPUT, "asset")
INFO_DIR = os.path.join(PHIINFO_OUTPUT, "info")
LEVELS = ["EZ", "HD", "IN", "AT"]

# 自动检测 PhiInfo 输出的图片扩展名（png / webp / avif）
def _detect_image_ext():
    if not os.path.isdir(ASSET_DIR):
        return "png"
    for root, _dirs, files in os.walk(ASSET_DIR):
        for f in files:
            if f.endswith(".webp"):
                return "webp"
            if f.endswith(".png"):
                return "png"
            if f.endswith(".avif"):
                return "avif"
    return "png"

IMAGE_EXT = _detect_image_ext()


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
    # 表单后缀：PhiInfo 在所有原始 key 后加了 .txt / .ogg / .{IMAGE_EXT}
    if rel.endswith(".txt"):
        orig = rel[:-4]  # 去掉 .txt，得到 Assets/Tracks/Song.Author.0/Chart_EZ.json
    elif rel.endswith(".ogg"):
        orig = rel[:-4]  # 去掉 .ogg，得到 Assets/Tracks/Song.Author.0/music.wav
    elif rel.endswith(f".{IMAGE_EXT}"):
        orig = rel[:-(len(IMAGE_EXT) + 1)]  # 去掉 .png/.webp/.avif
    elif rel == "metadata.json":
        return None  # 资产清单不需要
    else:
        return None

    # 去掉 PhiInfo 保留的 "Assets/Tracks/" 前缀
    if orig.startswith("Assets/Tracks/"):
        orig = orig[len("Assets/Tracks/"):]

    # 头像：avatar.{name}.{ext} → avatar/{name}.{ext}
    if orig.startswith("avatar."):
        name = orig[len("avatar."):]
        return f"avatar/{name}.{IMAGE_EXT}"

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

    # 曲绘（PhiInfo 不过滤 Blur/LowRes，但保留映射以免未来支持）
    if "IllustrationBlur" in filename:
        return f"illustrationBlur/{song_id}.{IMAGE_EXT}"
    if "IllustrationLowRes" in filename:
        return f"illustrationLowRes/{song_id}.{IMAGE_EXT}"
    if "Illustration" in filename:
        return f"illustration/{song_id}.{IMAGE_EXT}"

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
        sid = song.get("id", "").replace(".0", "")
        name = song.get("name", "")
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


def _pick_language(mapping, preferred="zh_cn"):
    """从 PhiInfo 的多语言字段中取指定语言，缺失时退回任意非空语言。"""
    if not isinstance(mapping, dict):
        return ""
    if mapping.get(preferred):
        return mapping[preferred]
    for value in mapping.values():
        if value:
            return value
    return ""


def _safe_avatar_key(addressable_key):
    """兼容 addressableKey 为空或长度不足的情况（去掉 avatar. 前缀，与旧 tmp.tsv 一致）。"""
    if isinstance(addressable_key, str) and len(addressable_key) >= 7:
        return addressable_key[7:]
    return ""


def translate_all_info():
    """生成 info/all_info.json（合并 songs + collection + avatars + tips）。

    全部取自 PhiInfo 的导出结果（songs.json / collection.json / avatars.json / tips.json），
    collection 仍展开为旧的扁平结构，保持输出格式不变。
    """
    songs_path = os.path.join(INFO_DIR, "songs.json")
    if not os.path.exists(songs_path):
        print("  [warn] songs.json not found, skipping all_info.json")
        return

    with open(songs_path, "r", encoding="utf-8") as f:
        songs = json.load(f)

    all_info = {"songs": songs, "collection": [], "avatars": [], "tips": []}

    # --- collection ---
    # PhiInfo 4.0.0 起 collection.json 为 文件夹 -> 条目 结构，
    # 展开时对齐旧 collection.tsv：同一 key 保留首个名称、取最后一个 sub_index。
    coll_path = os.path.join(INFO_DIR, "collection.json")
    if os.path.exists(coll_path):
        with open(coll_path, "r", encoding="utf-8") as f:
            folders = json.load(f)

        collection = {}
        for folder in folders:
            for item in folder.get("files", []):
                key = item.get("key", "")
                if key in collection:
                    collection[key]["sub_index"] = item.get("sub_index")
                else:
                    collection[key] = {
                        "key": key,
                        "name": _pick_language(item.get("name")),
                        "sub_index": item.get("sub_index"),
                    }
        all_info["collection"] = list(collection.values())
        print(f"  collection: {len(all_info['collection'])} items")

    # --- avatars ---
    avatars_path = os.path.join(INFO_DIR, "avatars.json")
    if os.path.exists(avatars_path):
        with open(avatars_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                all_info["avatars"].append({
                    "name": item.get("name", ""),
                    "addressable_key": _safe_avatar_key(item.get("addressable_key", "")),
                })
        print(f"  avatars: {len(all_info['avatars'])} items")

    # --- tips ---
    tips_path = os.path.join(INFO_DIR, "tips.json")
    if os.path.exists(tips_path):
        with open(tips_path, "r", encoding="utf-8") as f:
            tips = json.load(f)
        if isinstance(tips, dict):
            for lang in ("zh_cn", "zh_tw", "en", "ja", "ko"):
                if tips.get(lang):
                    all_info["tips"] = tips[lang]
                    break
        elif isinstance(tips, list):
            all_info["tips"] = tips
        print(f"  tips: {len(all_info['tips'])} items")

    out_path = os.path.join(INFO_DIR, "all_info.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_info, f, ensure_ascii=False)
    print(f"  all_info.json written")


if __name__ == "__main__":
    print("--- Translating PhiInfo output ---")
    translate_assets()
    translate_info()
    translate_version()
    translate_all_info()
    print("--- Done ---")
