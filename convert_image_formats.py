"""在 PhiInfo 导出 PNG 后，将 illustration 转换为 webp/avif 写入 lilith 目录。"""
import os
from PIL import Image

OUTPUT_DIR = "output"
TARGET_FORMATS = [("webp", {"quality": 85, "method": 6}), ("avif", {"quality": 60})]
LOW_RES_FORMATS = [("webp", {"quality": 75, "method": 6}), ("avif", {"quality": 50})]
BLUR_FORMATS = [("webp", {"quality": 80, "method": 6}), ("avif", {"quality": 55})]

def convert_illustrations():
    ill_dir = os.path.join(OUTPUT_DIR, "illustration")
    if not os.path.isdir(ill_dir):
        print("illustration/ 不存在，跳过。")
        return

    for fname in os.listdir(ill_dir):
        if not fname.lower().endswith(".png"):
            continue
        song_id = fname[:-4]
        src = os.path.join(ill_dir, fname)
        try:
            img = Image.open(src).convert("RGBA")
        except Exception as e:
            print(f"  跳过 {fname}: {e}")
            continue

        for ext, kwargs in TARGET_FORMATS:
            dst_dir = os.path.join(OUTPUT_DIR, "lilith", "ill")
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, f"{song_id}.{ext}")
            if os.path.exists(dst):
                continue
            try:
                out = img.copy()
                if ext == "avif":
                    out = out.convert("RGB")
                out.save(dst, ext.upper(), **kwargs)
                print(f"  {dst}")
            except Exception as e:
                print(f"  编码 {dst} 失败: {e}")

def convert_blur():
    blur_dir = os.path.join(OUTPUT_DIR, "illustrationBlur")
    if not os.path.isdir(blur_dir):
        return
    for fname in os.listdir(blur_dir):
        if not fname.lower().endswith(".png"):
            continue
        song_id = fname[:-4]
        src = os.path.join(blur_dir, fname)
        try:
            img = Image.open(src).convert("RGBA")
        except Exception:
            continue
        for ext, kwargs in BLUR_FORMATS:
            dst_dir = os.path.join(OUTPUT_DIR, "lilith", "illBlur")
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, f"{song_id}.{ext}")
            if os.path.exists(dst):
                continue
            try:
                out = img.copy()
                if ext == "avif":
                    out = out.convert("RGB")
                out.save(dst, ext.upper(), **kwargs)
                print(f"  {dst}")
            except Exception:
                pass


def convert_low_res():
    low_dir = os.path.join(OUTPUT_DIR, "illustrationLowRes")
    if not os.path.isdir(low_dir):
        return
    for fname in os.listdir(low_dir):
        if not fname.lower().endswith(".png"):
            continue
        song_id = fname[:-4]
        src = os.path.join(low_dir, fname)
        try:
            img = Image.open(src).convert("RGBA")
        except Exception:
            continue
        for ext, kwargs in LOW_RES_FORMATS:
            dst_dir = os.path.join(OUTPUT_DIR, "lilith", "illLow")
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, f"{song_id}.{ext}")
            if os.path.exists(dst):
                continue
            try:
                out = img.copy()
                if ext == "avif":
                    out = out.convert("RGB")
                out.save(dst, ext.upper(), **kwargs)
                print(f"  {dst}")
            except Exception:
                pass

if __name__ == "__main__":
    print("--- 转换 illustration PNG -> webp/avif ---")
    convert_illustrations()
    convert_low_res()
    convert_blur()
    print("--- 完成 ---")
