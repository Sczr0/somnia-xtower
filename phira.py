import os
import shutil
from zipfile import ZipFile

# === 配置区域 ===
BASE_DIR = "output"
PHIRA_DIR = os.path.join(BASE_DIR, "phira")
LEVELS = ["EZ", "HD", "IN", "AT"]

def generate_phira_packages():
    print("--- 开始打包 Phira (.pez) 文件 ---")

    # 1. 重置 phira 输出目录
    if os.path.exists(PHIRA_DIR):
        try:
            shutil.rmtree(PHIRA_DIR)
        except Exception as e:
            print(f"警告：清理旧目录失败 - {e}")

    try:
        os.makedirs(PHIRA_DIR, exist_ok=True)
        for level in LEVELS:
            os.makedirs(os.path.join(PHIRA_DIR, level), exist_ok=True)
    except Exception as e:
        print(f"错误：创建目录结构失败 - {e}")
        return

    # 2. 读取 info.tsv
    infos = {}
    info_path = os.path.join(BASE_DIR, "info", "info.tsv")
    try:
        with open(info_path, "r", encoding="utf8") as f:
            for line in f:
                line = line.strip().split("\t")
                if len(line) < 5: continue
                # key: song_id, value: {Name, Composer, ...}
                infos[line[0]] = {
                    "Name": line[1],
                    "Composer": line[2],
                    "Illustrator": line[3],
                    "Chater": line[4:]
                }
    except FileNotFoundError:
        print(f"错误：找不到 info.tsv ({info_path})，无法打包 Phira。")
        return

    # 3. 读取 difficulty.tsv
    diff_path = os.path.join(BASE_DIR, "info", "difficulty.tsv")
    try:
        with open(diff_path, "r", encoding="utf8") as f:
            for line in f:
                line = line.strip().split("\t")
                if len(line) < 2: continue
                if line[0] in infos:
                    infos[line[0]]["difficulty"] = line[1:]
    except FileNotFoundError:
        print(f"错误：找不到 difficulty.tsv ({diff_path})，无法打包 Phira。")
        return

    # 4. 开始打包
    packaged_count = 0
    for song_id, info in infos.items():
        if "difficulty" not in info:
            continue

        print(f"正在处理: {info['Name']} ({song_id})")
        
        for level_index, difficulty_value in enumerate(info["difficulty"]):
            # 防止索引越界
            if level_index >= len(LEVELS) or level_index >= len(info["Chater"]):
                continue

            level = LEVELS[level_index]
            
            # 原材料路径
            src_chart = os.path.join(BASE_DIR, "chart", f"{song_id}.0", f"{level}.json")
            # ★★★ 核心修复：现在 resource.py 会统一保存为 png，所以这里必须找 .png ★★★
            src_img = os.path.join(BASE_DIR, "illustrationLowRes", f"{song_id}.png")
            src_music = os.path.join(BASE_DIR, "music", f"{song_id}.ogg")

            # 检查所有零件是否存在
            if not (os.path.exists(src_chart) and os.path.exists(src_img) and os.path.exists(src_music)):
                # print(f"  - 跳过 {level}: 缺少零件。") # 本地调试时可以取消注释
                continue

            # 零件齐全，开始打包
            pez_filename = f"{song_id}-{level}.pez"
            pez_path = os.path.join(PHIRA_DIR, level, pez_filename)

            try:
                with ZipFile(pez_path, "w") as pez:
                    # 写入 info.txt
                    info_txt_content = (
                        f"#\n"
                        f"Name: {info['Name']}\n"
                        f"Song: {song_id}.ogg\n"
                        f"Picture: {song_id}.png\n" # pez 包内也统一叫 .png
                        f"Chart: {song_id}.json\n"
                        f"Level: {level} Lv.{difficulty_value}\n"
                        f"Composer: {info['Composer']}\n"
                        f"Illustrator: {info['Illustrator']}\n"
                        f"Charter: {info['Chater'][level_index]}"
                    )
                    pez.writestr("info.txt", info_txt_content)

                    # 写入资源文件 (arcname 是文件在 zip 包里的名字)
                    pez.write(src_chart, f"{song_id}.json")
                    pez.write(src_img, f"{song_id}.png")
                    pez.write(src_music, f"{song_id}.ogg")
                    
                    packaged_count += 1
            except Exception as e:
                print(f"  !! 打包 {pez_filename} 失败: {e}")

    print(f"--- Phira 打包完成, 共生成 {packaged_count} 个文件 ---")

if __name__ == "__main__":
    generate_phira_packages()