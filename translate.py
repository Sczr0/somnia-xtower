"""将 PhiInfo 导出的 asset/ 映射成站点目录结构（chart / music / illustration / avatar）。

info/ 下的发布文件不在这里生成：统一由 info_export.py 从 PhiInfo 的 info/*.json 归一化产出。
"""
import os
import shutil

PHIINFO_OUTPUT = "output"
ASSET_DIR = os.path.join(PHIINFO_OUTPUT, "asset")


def _detect_image_ext():
    """自动检测 PhiInfo 输出的图片扩展名（png / webp / avif）。"""
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

# 差分曲绘的难度后缀（如 Illustration_AT.jpg）。AT 作为无后缀的默认图。
LEVEL_SUFFIXES = ("EZ", "HD", "IN", "AT")


def _split_illustration(filename):
    """解析曲绘文件名，返回 (分组目录, 难度)。

    普通歌曲为 ``Illustration.jpg``（无难度）；差分歌曲为
    ``Illustration_EZ.jpg`` / ``IllustrationBlur_AT.jpg`` 等。分组取
    illustration / illustrationBlur / illustrationLowRes，难度为 EZ/HD/IN/AT 或 None。
    """
    if "IllustrationBlur" in filename:
        group, rest = "illustrationBlur", filename.split("IllustrationBlur", 1)[1]
    elif "IllustrationLowRes" in filename:
        group, rest = "illustrationLowRes", filename.split("IllustrationLowRes", 1)[1]
    elif "Illustration" in filename:
        group, rest = "illustration", filename.split("Illustration", 1)[1]
    else:
        return None, None

    stem = rest.rsplit(".", 1)[0]  # 去掉 .jpg 之类的原始扩展名
    difficulty = None
    if stem.startswith("_") and stem[1:].upper() in LEVEL_SUFFIXES:
        difficulty = stem[1:].upper()
    return group, difficulty


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
            dests = _map_asset_paths(rel)
            if not dests:
                continue
            # 一个源可能对应多个目标（如 AT 同时产出带后缀与无后缀两份），
            # 前几份复制，最后一份直接移动，避免重复读盘。
            for dest in dests[:-1]:
                full = os.path.join(PHIINFO_OUTPUT, dest)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                shutil.copy2(src, full)
                cat = dest.rsplit("/", 2)[-2] if dest.count("/") >= 2 else "root"
                counts[cat] = counts.get(cat, 0) + 1
            dest = dests[-1]
            full = os.path.join(PHIINFO_OUTPUT, dest)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            shutil.move(src, full)
            cat = dest.rsplit("/", 2)[-2] if dest.count("/") >= 2 else "root"
            counts[cat] = counts.get(cat, 0) + 1

    shutil.rmtree(ASSET_DIR, ignore_errors=True)
    for cat, n in sorted(counts.items()):
        print(f"  {cat}: {n} files")


def _map_asset_paths(rel):
    """将一条 PhiInfo asset 路径映射为一组目标站点路径（可能为空）。"""
    # 表单后缀：PhiInfo 在所有原始 key 后加了 .txt / .ogg / .{IMAGE_EXT}
    if rel.endswith(".txt"):
        orig = rel[:-4]  # 去掉 .txt，得到 Assets/Tracks/Song.Author.0/Chart_EZ.json
    elif rel.endswith(".ogg"):
        orig = rel[:-4]  # 去掉 .ogg，得到 Assets/Tracks/Song.Author.0/music.wav
    elif rel.endswith(f".{IMAGE_EXT}"):
        orig = rel[:-(len(IMAGE_EXT) + 1)]  # 去掉 .png/.webp/.avif
    elif rel == "metadata.json":
        return []  # 资产清单不需要
    else:
        return []

    # 去掉 PhiInfo 保留的 "Assets/Tracks/" 前缀
    if orig.startswith("Assets/Tracks/"):
        orig = orig[len("Assets/Tracks/"):]

    # 头像：avatar.{name}.{ext} → avatar/{name}.{ext}
    if orig.startswith("avatar."):
        name = orig[len("avatar."):]
        return [f"avatar/{name}.{IMAGE_EXT}"]

    # 谱面 / 音乐 / 曲绘：SongID.Author.0/XXX
    folder, filename = os.path.split(orig)
    song_id = folder.replace(".0", "")

    if filename.startswith("Chart_"):
        # Song.Author.0/Chart_EZ.json → chart/Song.Author.0/EZ.json
        diff = filename.replace("Chart_", "").replace(".json", "")
        return [f"chart/{folder}/{diff}.json"]

    if filename.startswith("music"):
        # Song.Author.0/music.wav → music/Song.Author.ogg
        return [f"music/{song_id}.ogg"]

    # 曲绘（PhiInfo 不过滤 Blur/LowRes，但保留映射以免未来支持）
    # 差分曲绘按难度保留为独立文件：EZ/HD/IN/AT 都加难度后缀，
    # 另外 AT 再额外产出一份无后缀的默认图。
    illustration_group, difficulty = _split_illustration(filename)
    if illustration_group:
        base = f"{illustration_group}/{song_id}"
        if difficulty is None:
            return [f"{base}.{IMAGE_EXT}"]
        suffixed = f"{base}_{difficulty}.{IMAGE_EXT}"
        if difficulty == "AT":
            return [f"{base}.{IMAGE_EXT}", suffixed]
        return [suffixed]

    return []


if __name__ == "__main__":
    print("--- Translating PhiInfo asset output ---")
    translate_assets()
    print("--- Done ---")
