"""补齐 lilith 目录（WebP + AVIF）+ 确保 illustrationLowRes 为 PNG。

流程说明（PhiInfo 输出 PNG 后调用）：
  1. illustrationLowRes/*.png 已存在（PhiInfo 直接输出 PNG），无需转换
  2. illustration/*.png   → lilith/ill/*.webp + *.avif
  3. illustrationLowRes/*.png → lilith/illLow/*.webp + *.avif
  4. illustrationBlur/*.png   → lilith/illBlur/*.webp + *.avif
"""
import os
from PIL import Image

OUTPUT_DIR = "output"

# 各子目录的编码参数
LILITH_FORMATS = {
    "ill":     {"webp": {"quality": 85, "method": 6}, "avif": {"quality": 60}},
    "illLow":  {"webp": {"quality": 75, "method": 6}, "avif": {"quality": 50}},
    "illBlur": {"webp": {"quality": 80, "method": 6}, "avif": {"quality": 55}},
}


def _convert_to_lilith(src_subdir: str, lilith_subdir: str):
    """将 src_subdir/*.png 转换为 lilith/{lilith_subdir}/*.webp + *.avif"""
    src_dir = os.path.join(OUTPUT_DIR, src_subdir)
    dst_dir = os.path.join(OUTPUT_DIR, "lilith", lilith_subdir)
    if not os.path.isdir(src_dir):
        return
    os.makedirs(dst_dir, exist_ok=True)

    formats = LILITH_FORMATS[lilith_subdir]
    counts = {ext: 0 for ext in formats}

    for fname in os.listdir(src_dir):
        if not fname.lower().endswith(".png"):
            continue
        song_id = fname[:-4]
        src_path = os.path.join(src_dir, fname)

        try:
            img = Image.open(src_path).convert("RGBA")
        except Exception as e:
            print(f"  [warn] 跳过 {fname}: {e}")
            continue

        for ext, kwargs in formats.items():
            dst_path = os.path.join(dst_dir, f"{song_id}.{ext}")
            if os.path.exists(dst_path):
                continue
            try:
                out = img.copy()
                if ext == "avif":
                    out = out.convert("RGB")
                out.save(dst_path, ext.upper(), **kwargs)
                counts[ext] += 1
            except Exception as e:
                print(f"  [warn] 编码 {dst_path} 失败: {e}")

        img.close()

    for ext, n in counts.items():
        print(f"  lilith/{lilith_subdir}: {n} .{ext}")


if __name__ == "__main__":
    _convert_to_lilith("illustration", "ill")
    _convert_to_lilith("illustrationLowRes", "illLow")
    _convert_to_lilith("illustrationBlur", "illBlur")
