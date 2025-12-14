import os
import shutil
from zipfile import ZipFile, BadZipFile

# === 配置区域 ===
# 我们的资源都在 output 文件夹下，所以这里指定为 output
BASE_DIR = "output"
PHIRA_DIR = os.path.join(BASE_DIR, "phira")

levels = ["EZ", "HD", "IN", "AT"]

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
        for level in levels:
            os.makedirs(os.path.join(PHIRA_DIR, level), exist_ok=True)
    except Exception as e:
        print(f"错误：创建目录结构失败 - {e}")
        return

    # 2. 读取 info.tsv
    infos = {}
    info_path = os.path.join(BASE_DIR, "info", "info.tsv")
    try:
        with open(info_path, encoding="utf8") as f:
            for line in f:
                line = line.strip().split("\t")
                if len(line) < 5: continue
                infos[line[0]] = {
                    "Name": line[1],
                    "Composer": line[2],
                    "Illustrator": line[3],
                    "Chater": line[4:]
                }
    except FileNotFoundError:
        print(f"错误：找不到 info.tsv ({info_path})，跳过 Phira 打包。")
        return

    # 3. 读取 difficulty.tsv
    diff_path = os.path.join(BASE_DIR, "info", "difficulty.tsv")
    try:
        with open(diff_path, encoding="utf8") as f:
            for line in f:
                line = line.strip().split("\t")
                if len(line) < 2: continue
                if line[0] in infos:
                    infos[line[0]]["difficulty"] = line[1:]
    except FileNotFoundError:
        print(f"错误：找不到 difficulty.tsv ({diff_path})")
        return

    # 4. 开始打包
    count = 0
    for id, info in infos.items():
        # 如果没有难度数据，跳过
        if "difficulty" not in info:
            continue

        print(f"正在打包: {info['Name']} ({id})")
        
        for level_index in range(len(info["difficulty"])):
            level = levels[level_index]
            # 目标 .pez 文件路径
            pez_filename = f"{id}-{level}.pez"
            pez_path = os.path.join(PHIRA_DIR, level, pez_filename)

            # 原材料路径 (在 output 目录下)
            # 注意：这里的路径要对应你 output 里的实际结构
            src_chart = os.path.join(BASE_DIR, "chart", f"{id}.0", f"{level}.json")
            src_img = os.path.join(BASE_DIR, "illustrationLowRes", f"{id}.png") # 假设用低清图减小体积
            src_music = os.path.join(BASE_DIR, "music", f"{id}.ogg")

            # 检查必要文件是否存在
            if not (os.path.exists(src_chart) and os.path.exists(src_img) and os.path.exists(src_music)):
                # print(f"  - 跳过 {level}: 缺少必要资源文件")
                continue

            try:
                with ZipFile(pez_path, "w") as pez:
                    # 写入 info.txt
                    info_txt_content = (
                        f"#\n"
                        f"Name: {info['Name']}\n"
                        f"Song: {id}.ogg\n"
                        f"Picture: {id}.png\n"
                        f"Chart: {id}.json\n"
                        f"Level: {level} Lv.{info['difficulty'][level_index]}\n"
                        f"Composer: {info['Composer']}\n"
                        f"Illustrator: {info['Illustrator']}\n"
                        f"Charter: {info['Chater'][level_index]}"
                    )
                    pez.writestr("info.txt", info_txt_content)

                    # 写入资源文件 (arcname 是文件在 zip 包里的名字)
                    pez.write(src_chart, f"{id}.json")
                    pez.write(src_img, f"{id}.png")
                    pez.write(src_music, f"{id}.ogg")
                    
                    count += 1
            except Exception as e:
                print(f"  !! 打包 {pez_filename} 失败: {e}")

    print(f"--- Phira 打包完成，共生成 {count} 个文件 ---")

if __name__ == "__main__":
    generate_phira_packages()