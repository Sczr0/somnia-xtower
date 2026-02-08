import json
import os
import sys
import zipfile
import csv
from UnityPy import Environment


def _sanitize_song_id(song_id):
    """统一处理谱面 ID 后缀"""
    if song_id.endswith(".0") or song_id.endswith("_0"):
        return song_id[:-2]
    return song_id


def _safe_avatar_key(addressable_key):
    """兼容 addressableKey 为空或长度不足的情况"""
    if isinstance(addressable_key, str) and len(addressable_key) >= 7:
        return addressable_key[7:]
    return ""


def _to_fixed_4_difficulty(difficulty_values):
    """将难度列表补齐为 EZ/HD/IN/AT 四列"""
    values = list(difficulty_values[:4])
    while len(values) < 4:
        values.append("")
    return values

# 适配自动化：不再依赖 sys.argv，而是封装成函数供 main.py 调用
def extract_game_info(apk_path, output_root="output"):
    print("--- 开始提取游戏基础信息 (GameInformation) ---")
    
    # 确保目标目录存在：output/info
    info_dir = os.path.join(output_root, "info")
    os.makedirs(info_dir, exist_ok=True)

    # 加载 typetree (确保 typetree.json 在项目根目录)
    if not os.path.exists("typetree.json"):
        print("错误：找不到 typetree.json，无法解析数据！")
        return

    with open("typetree.json", encoding='utf-8') as f:
        typetree = json.load(f)

    env = Environment()
    with zipfile.ZipFile(apk_path) as apk:
        # 加载必要的文件
        if "assets/bin/Data/globalgamemanagers.assets" in apk.namelist():
            with apk.open("assets/bin/Data/globalgamemanagers.assets") as f:
                env.load_file(f.read(), name="assets/bin/Data/globalgamemanagers.assets")
        
        # 尝试加载 level0 (有些版本可能叫其他名字，但这通常是主入口)
        if "assets/bin/Data/level0" in apk.namelist():
            with apk.open("assets/bin/Data/level0") as f:
                env.load_file(f.read())

    # 查找关键对象
    GameInformation = None
    Collections = None
    Tips = None

    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        # 解析 MonoBehaviour
        data = obj.read()
        script = data.m_Script.get_obj().read()
        
        if script.name == "GameInformation":
            GameInformation = obj.read_typetree(typetree["GameInformation"])
        elif script.name == "GetCollectionControl":
            Collections = obj.read_typetree(typetree["GetCollectionControl"], True)
        elif script.name == "TipsProvider":
            Tips = obj.read_typetree(typetree["TipsProvider"], True)

    if not GameInformation:
        print("错误：未找到 GameInformation 数据块！")
        return

    # === 处理 difficulty.tsv / info.tsv 以及 CSV 输出 ===
    difficulty_list = []
    table_list = []
    difficulty_csv_list = []
    info_csv_list = []
    
    for key, songs in GameInformation["song"].items():
        if key == "otherSongs":
            continue
        for song in songs:
            # 数据清洗逻辑（保留你原来的逻辑）
            if len(song["difficulty"]) == 5:
                song["difficulty"].pop()
            if song["difficulty"][-1] == 0.0:
                song["difficulty"].pop()
                if len(song["charter"]) > len(song["difficulty"]):
                    song["charter"].pop() # 防止越界
            
            # 难度保留一位小数
            diff_str = [str(round(d, 1)) for d in song["difficulty"]]
            
            # ID修正
            song_id = _sanitize_song_id(song["songsId"])
            fixed_diff = _to_fixed_4_difficulty(diff_str)

            difficulty_list.append([song_id] + diff_str)
            difficulty_csv_list.append([song_id] + fixed_diff)

            info_csv_row = [song_id, song["songsName"], song["composer"], song["illustrator"]]
            info_csv_row.extend(fixed_diff)
            info_csv_list.append(info_csv_row)
            
            # info.tsv 结构: ID, Name, Composer, Illustrator, Charter...
            row = [song_id, song["songsName"], song["composer"], song["illustrator"]]
            row.extend(song["charter"])
            table_list.append(tuple(row))

    # 写入 output/info/difficulty.tsv
    with open(os.path.join(info_dir, "difficulty.tsv"), "w", encoding="utf8") as f:
        for item in difficulty_list:
            f.write("\t".join(map(str, item)) + "\n")

    # 写入 output/info/info.tsv
    with open(os.path.join(info_dir, "info.tsv"), "w", encoding="utf8") as f:
        for item in table_list:
            f.write("\t".join(map(str, item)) + "\n")

    # 写入 output/info/difficulty.csv
    with open(os.path.join(info_dir, "difficulty.csv"), "w", encoding="utf8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "EZ", "HD", "IN", "AT"])
        writer.writerows(difficulty_csv_list)

    # 写入 output/info/info.csv
    with open(os.path.join(info_dir, "info.csv"), "w", encoding="utf8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "song", "composer", "illustrator", "EZ", "HD", "IN", "AT"])
        writer.writerows(info_csv_list)

    # === 处理 KeyStore (single.txt, illustration.txt) ===
    single = []
    illustration = []
    if "keyStore" in GameInformation:
        for key in GameInformation["keyStore"]:
            if key["kindOfKey"] == 0:
                single.append(key["keyName"])
            elif key["kindOfKey"] == 2 and key["keyName"] != "Introduction" and key["keyName"] not in single:
                illustration.append(key["keyName"])

    with open(os.path.join(info_dir, "single.txt"), "w", encoding="utf8") as f:
        f.write("\n".join(single))

    with open(os.path.join(info_dir, "illustration.txt"), "w", encoding="utf8") as f:
        f.write("\n".join(illustration))

    # === 处理 Collections (collection.tsv, avatar.txt, tmp.tsv) ===
    if Collections:
        collection_dict = {}
        for item in Collections.collectionItems:
            if item.key in collection_dict:
                collection_dict[item.key][1] = item.subIndex
            else:
                collection_dict[item.key] = [item.multiLanguageTitle.chinese, item.subIndex]

        with open(os.path.join(info_dir, "collection.tsv"), "w", encoding="utf8") as f:
            for key, value in collection_dict.items():
                f.write(f"{key}\t{value[0]}\t{value[1]}\n")

        with open(os.path.join(info_dir, "avatar.txt"), "w", encoding="utf8") as f_avatar, \
             open(os.path.join(info_dir, "tmp.tsv"), "w", encoding="utf8") as f_tmp:
            # avatar.txt 存头像名称，tmp.tsv 存头像名称到资源键的映射
            for item in Collections.avatars:
                f_avatar.write(f"{item.name}\n")
                f_tmp.write(f"{item.name}\t{_safe_avatar_key(getattr(item, 'addressableKey', ''))}\n")
    
    # === 处理 Tips ===
    if Tips and len(Tips.tips) > 0:
        with open(os.path.join(info_dir, "tips.txt"), "w", encoding="utf8") as f:
            for tip in Tips.tips[0].tips:
                f.write(f"{tip}\n")

    print(f"--- 游戏信息提取完成，文件已保存至 {info_dir} ---")

if __name__ == "__main__":
    # 允许本地单独测试
    if len(sys.argv) > 1:
        extract_game_info(sys.argv[1], "output")
    else:
        print("用法: python gameInformation.py <apk_path>")
