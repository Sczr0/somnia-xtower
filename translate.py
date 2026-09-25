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


if __name__ == "__main__":
    print("--- Translating PhiInfo asset output ---")
    translate_assets()
    print("--- Done ---")
