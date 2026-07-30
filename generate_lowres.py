"""补齐 lilith 目录（WebP + AVIF）+ 确保 illustrationLowRes 为 PNG。

流程说明（PhiInfo 输出 PNG 后调用）：
  1. illustrationLowRes/*.png 已存在（PhiInfo 直接输出 PNG），无需转换
  2. illustration/*.png   → lilith/ill/*.webp + *.avif
  3. illustrationLowRes/*.png → lilith/illLow/*.webp + *.avif
  4. illustrationBlur/*.png   → lilith/illBlur/*.webp + *.avif
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

OUTPUT_DIR = "output"

# 各子目录的编码参数
LILITH_FORMATS = {
    "ill":     {"webp": {"quality": 85, "method": 6}, "avif": {"quality": 60}},
    "illLow":  {"webp": {"quality": 75, "method": 6}, "avif": {"quality": 50}},
    "illBlur": {"webp": {"quality": 80, "method": 6}, "avif": {"quality": 55}},
}


def _encode_one(src_path: str, dst_dir: str, formats: dict) -> dict:
    """处理单张 PNG，返回 {ext: count}。"""
    fname = os.path.basename(src_path)
    song_id = fname[:-4]
    counts = {ext: 0 for ext in formats}

    try:
        img = Image.open(src_path).convert("RGBA")
    except Exception as e:
        return {"__error__": f"跳过 {fname}: {e}"}

    for ext, kwargs in formats.items():
        dst_path = os.path.join(dst_dir, f"{song_id}.{ext}")
        if os.path.exists(dst_path):
            continue
        try:
            # WebP 支持 RGBA 直接保存，无需 copy；AVIF 需要转 RGB
            if ext == "avif":
                out = img.convert("RGB")
            else:
                out = img
            out.save(dst_path, ext.upper(), **kwargs)
            counts[ext] += 1
        except Exception as e:
            print(f"  [warn] 编码 {dst_path} 失败: {e}", flush=True)

    img.close()
    return counts


def _convert_to_lilith(src_subdir: str, lilith_subdir: str, max_workers: int | None = None):
    """将 src_subdir/*.png 并行转换为 lilith/{lilith_subdir}/*.webp + *.avif"""
    src_dir = os.path.join(OUTPUT_DIR, src_subdir)
    dst_dir = os.path.join(OUTPUT_DIR, "lilith", lilith_subdir)
    if not os.path.isdir(src_dir):
        return
    os.makedirs(dst_dir, exist_ok=True)

    formats = LILITH_FORMATS[lilith_subdir]

    # 收集待处理的 PNG 文件
    tasks = []
    for fname in os.listdir(src_dir):
        if not fname.lower().endswith(".png"):
            continue
        src_path = os.path.join(src_dir, fname)
        if all(os.path.exists(os.path.join(dst_dir, f"{fname[:-4]}.{ext}")) for ext in formats):
            continue  # 所有格式都已存在，跳过
        tasks.append(src_path)

    if not tasks:
        print(f"  lilith/{lilith_subdir}: 无新文件需要处理")
        return

    print(f"  lilith/{lilith_subdir}: 共 {len(tasks)} 张图片，使用 {max_workers or os.cpu_count()} 线程并行编码...")

    if max_workers is None:
        max_workers = os.cpu_count() or 4

    total_counts = {ext: 0 for ext in formats}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_encode_one, src, dst_dir, formats): src for src in tasks}
        for future in as_completed(futures):
            result = future.result()
            if "__error__" in result:
                print(f"  [warn] {result['__error__']}", flush=True)
            else:
                for ext, n in result.items():
                    total_counts[ext] += n

    for ext, n in total_counts.items():
        print(f"  lilith/{lilith_subdir}: {n} .{ext}")


if __name__ == "__main__":
    workers = int(os.environ.get("LOWRES_WORKERS", "0")) or None
    _convert_to_lilith("illustration", "ill", max_workers=workers)
    _convert_to_lilith("illustrationLowRes", "illLow", max_workers=workers)
    _convert_to_lilith("illustrationBlur", "illBlur", max_workers=workers)
