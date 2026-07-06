"""从 illustration 降采样生成 illustrationLowRes（Phira 需要 PNG），并同步 lilith 目录。"""
import os
from PIL import Image

OUTPUT_DIR = "output"


def generate_lowres():
    ill_dir = os.path.join(OUTPUT_DIR, "illustration")
    low_dir = os.path.join(OUTPUT_DIR, "illustrationLowRes")
    if not os.path.isdir(ill_dir):
        return

    os.makedirs(low_dir, exist_ok=True)
    for f in os.listdir(ill_dir):
        if not f.endswith(".webp"):
            continue
        song_id = f[:-5]
        img = Image.open(os.path.join(ill_dir, f))
        img.thumbnail((256, 256))
        img.save(os.path.join(low_dir, f"{song_id}.png"))
        print(f"  lowres: {song_id}.png")


def sync_lilith():
    ill_dir = os.path.join(OUTPUT_DIR, "illustration")
    lilith_dir = os.path.join(OUTPUT_DIR, "lilith", "ill")
    if not os.path.isdir(ill_dir):
        return
    os.makedirs(lilith_dir, exist_ok=True)
    import shutil
    for f in os.listdir(ill_dir):
        if f.endswith(".webp"):
            shutil.copy2(os.path.join(ill_dir, f), os.path.join(lilith_dir, f))
    print("  lilith/ill: synced")


if __name__ == "__main__":
    generate_lowres()
    sync_lilith()
