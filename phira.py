import os
import shutil
import zipfile
from zipfile import ZipFile, ZipInfo

BASE_DIR = "output"
PHIRA_DIR = os.path.join(BASE_DIR, "phira")
LEVELS = ["EZ", "HD", "IN", "AT"]

# 设定一个固定的时间 (2025-01-01 00:00:00)
# 格式: (年, 月, 日, 时, 分, 秒)
FIXED_TIME = (2025, 1, 1, 0, 0, 0)

def add_file_deterministic(zip_obj, file_path, arcname):
    """读取文件并以固定的时间戳写入 Zip"""
    if not os.path.exists(file_path):
        return
        
    with open(file_path, 'rb') as f:
        file_data = f.read()
    
    # 创建 ZipInfo 对象
    zinfo = ZipInfo(filename=arcname)
    # 强制设置时间
    zinfo.date_time = FIXED_TIME
    # 设置压缩格式
    zinfo.compress_type = zipfile.ZIP_DEFLATED
    # 赋予读写权限 (防止某些系统解压后只读)
    zinfo.external_attr = 0o644 << 16
    
    # 写入数据
    zip_obj.writestr(zinfo, file_data)

def add_text_deterministic(zip_obj, text_content, arcname):
    """将文本以固定的时间戳写入 Zip"""
    zinfo = ZipInfo(filename=arcname)
    zinfo.date_time = FIXED_TIME
    zinfo.compress_type = zipfile.ZIP_DEFLATED
    zinfo.external_attr = 0o644 << 16
    zip_obj.writestr(zinfo, text_content)

def generate_phira_packages():
    print("--- 开始打包 Phira (.pez) 文件 (确定性打包模式) ---")
    if os.path.exists(PHIRA_DIR):
        shutil.rmtree(PHIRA_DIR)
    os.makedirs(PHIRA_DIR, exist_ok=True)
    for level in LEVELS:
        os.makedirs(os.path.join(PHIRA_DIR, level), exist_ok=True)

    infos = {}
    info_path = os.path.join(BASE_DIR, "info", "info.tsv")
    try:
        with open(info_path, "r", encoding="utf8") as f:
            for line in f:
                line = line.strip().split("\t")
                if len(line) < 5: continue
                infos[line[0]] = {"Name": line[1], "Composer": line[2], "Illustrator": line[3], "Chater": line[4:]}
    except FileNotFoundError:
        print(f"错误：找不到 info.tsv ({info_path})")
        return

    diff_path = os.path.join(BASE_DIR, "info", "difficulty.tsv")
    try:
        with open(diff_path, "r", encoding="utf8") as f:
            for line in f:
                line = line.strip().split("\t")
                if len(line) < 2: continue
                if line[0] in infos:
                    infos[line[0]]["difficulty"] = line[1:]
    except FileNotFoundError:
        print(f"错误：找不到 difficulty.tsv ({diff_path})")
        return

    packaged_count = 0
    missing_parts_log = []

    for song_id, info in infos.items():
        if "difficulty" not in info:
            continue

        for level_index, difficulty_value in enumerate(info["difficulty"]):
            if level_index >= len(LEVELS) or level_index >= len(info["Chater"]):
                continue
            level = LEVELS[level_index]
            
            src_chart = os.path.join(BASE_DIR, "chart", f"{song_id}.0", f"{level}.json")
            src_img = os.path.join(BASE_DIR, "illustrationLowRes", f"{song_id}.png")
            src_music = os.path.join(BASE_DIR, "music", f"{song_id}.ogg")

            if not (os.path.exists(src_chart) and os.path.exists(src_img) and os.path.exists(src_music)):
                reason = f"Song '{song_id}' Level '{level}': 缺失零件"
                missing_parts_log.append(reason)
                continue

            pez_filename = f"{song_id}-{level}.pez"
            pez_path = os.path.join(PHIRA_DIR, level, pez_filename)
            try:
                with ZipFile(pez_path, "w", compression=zipfile.ZIP_DEFLATED) as pez:
                    # 1. 写入 info.txt (使用固定时间)
                    info_txt_content = (f"#\nName: {info['Name']}\nSong: {song_id}.ogg\nPicture: {song_id}.png\n"
                                        f"Chart: {song_id}.json\nLevel: {level} Lv.{difficulty_value}\n"
                                        f"Composer: {info['Composer']}\nIllustrator: {info['Illustrator']}\n"
                                        f"Charter: {info['Chater'][level_index]}")
                    add_text_deterministic(pez, info_txt_content, "info.txt")

                    # 2. 写入资源文件 (使用固定时间)
                    add_file_deterministic(pez, src_chart, f"{song_id}.json")
                    add_file_deterministic(pez, src_img, f"{song_id}.png")
                    add_file_deterministic(pez, src_music, f"{song_id}.ogg")
                    
                    packaged_count += 1
            except Exception as e:
                print(f"!! 打包 {pez_filename} 失败: {e}")

    if packaged_count == 0 and missing_parts_log:
        print("\n--- Phira 打包失败原因分析 (抽样) ---")
        print(missing_parts_log[0])

    print(f"--- Phira 打包完成, 共生成 {packaged_count} 个文件 ---")

if __name__ == "__main__":
    generate_phira_packages()