import os
import shutil
from zipfile import ZipFile

BASE_DIR = "output"
PHIRA_DIR = os.path.join(BASE_DIR, "phira")
LEVELS = ["EZ", "HD", "IN", "AT"]

def generate_phira_packages():
    print("--- 开始打包 Phira (.pez) 文件 ---")
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
    # 增加一个变量来跟踪为什么打包失败
    missing_parts_log = []

    for song_id, info in infos.items():
        if "difficulty" not in info:
            continue

        # print(f"正在处理: {info['Name']} ({song_id})") # 这行已有
        
        for level_index, difficulty_value in enumerate(info["difficulty"]):
            if level_index >= len(LEVELS) or level_index >= len(info["Chater"]):
                continue
            level = LEVELS[level_index]
            
            src_chart = os.path.join(BASE_DIR, "chart", f"{song_id}.0", f"{level}.json")
            src_img = os.path.join(BASE_DIR, "illustrationLowRes", f"{song_id}.png")
            src_music = os.path.join(BASE_DIR, "music", f"{song_id}.ogg")

            chart_exists = os.path.exists(src_chart)
            img_exists = os.path.exists(src_img)
            music_exists = os.path.exists(src_music)

            if not (chart_exists and img_exists and music_exists):
                reason = f"Song '{song_id}' Level '{level}': "
                if not chart_exists: reason += f"谱面缺失({src_chart}) "
                if not img_exists: reason += f"图片缺失({src_img}) "
                if not music_exists: reason += f"音乐缺失({src_music})"
                missing_parts_log.append(reason)
                continue

            pez_filename = f"{song_id}-{level}.pez"
            pez_path = os.path.join(PHIRA_DIR, level, pez_filename)
            try:
                with ZipFile(pez_path, "w") as pez:
                    info_txt_content = (f"#\nName: {info['Name']}\nSong: {song_id}.ogg\nPicture: {song_id}.png\n"
                                        f"Chart: {song_id}.json\nLevel: {level} Lv.{difficulty_value}\n"
                                        f"Composer: {info['Composer']}\nIllustrator: {info['Illustrator']}\n"
                                        f"Charter: {info['Chater'][level_index]}")
                    pez.writestr("info.txt", info_txt_content)
                    pez.write(src_chart, f"{song_id}.json")
                    pez.write(src_img, f"{song_id}.png")
                    pez.write(src_music, f"{song_id}.ogg")
                    packaged_count += 1
            except Exception as e:
                print(f"!! 打包 {pez_filename} 失败: {e}")

    # 在最后打印出所有失败的原因
    if packaged_count == 0 and missing_parts_log:
        print("\n--- Phira 打包失败原因分析 (抽样前5条) ---")
        for log_entry in missing_parts_log[:5]:
            print(log_entry)

    print(f"--- Phira 打包完成, 共生成 {packaged_count} 个文件 ---")

if __name__ == "__main__":
    generate_phira_packages()