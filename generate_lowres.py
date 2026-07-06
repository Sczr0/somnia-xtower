"""补齐 lilith 目录 + 生成 Phira 所需的 PNG。

PhiInfo 输出 illustration*/ *.webp 文件后，此脚本负责：
  1. illustrationLowRes/*.webp → *.png（Phira 打包需要 PNG 格式）
  2. illustrationLowRes/*.webp → lilith/illLow/（同步 WebP）
  3. illustrationBlur/*.webp   → lilith/illBlur/（同步 WebP）
  4. illustration/*.webp       → lilith/ill/   （同步 WebP）
"""
import os
import shutil
from PIL import Image

OUTPUT_DIR = "output"


def _sync_webp(src_subdir: str, dst_subdir: str):
    src_dir = os.path.join(OUTPUT_DIR, src_subdir)
    dst_dir = os.path.join(OUTPUT_DIR, "lilith", dst_subdir)
    if not os.path.isdir(src_dir):
        return
    os.makedirs(dst_dir, exist_ok=True)
    count = 0
    for f in os.listdir(src_dir):
        if f.endswith(".webp"):
            shutil.copy2(os.path.join(src_dir, f), os.path.join(dst_dir, f))
            count += 1
    print(f"  lilith/{dst_subdir}: {count} files")


def _convert_lowres_to_png():
    """PhiInfo 输出 illustrationLowRes/*.webp → *.png（Phira 需要）"""
    src_dir = os.path.join(OUTPUT_DIR, "illustrationLowRes")
    if not os.path.isdir(src_dir):
        return
    count = 0
    for f in os.listdir(src_dir):
        if not f.endswith(".webp"):
            continue
        song_id = f[:-5]
        png_path = os.path.join(src_dir, f"{song_id}.png")
        if os.path.exists(png_path):
            continue
        img = Image.open(os.path.join(src_dir, f))
        img.save(png_path)
        count += 1
    print(f"  lowres -> png: {count} files")


if __name__ == "__main__":
    _convert_lowres_to_png()
    _sync_webp("illustration", "ill")
    _sync_webp("illustrationLowRes", "illLow")
    _sync_webp("illustrationBlur", "illBlur")
