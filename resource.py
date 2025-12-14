import base64
import os
import sys
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from queue import Queue
from zipfile import ZipFile

from UnityPy import Environment
from UnityPy.classes import AudioClip, Sprite
from UnityPy.enums import ClassIDType

try:
    from fsb5 import FSB5
except ImportError:
    print("警告: 缺少 fsb5 模块，音频将无法解码。请运行 'pip install fsb5'。")
    FSB5 = None

# ---------------- 配置区域 ----------------
CONFIG = {
    "avatar": True,
    "chart": True,
    "illustrationBlur": True,
    "illustrationLowRes": True,
    "illustration": True,
    "music": True
}

# ---------------- 全局变量 ----------------
queue_in = Queue()
OUTPUT_ROOT = "output"

# ---------------- 工具类与函数 ----------------
class ByteReader:
    def __init__(self, data):
        self.data = data
        self.position = 0

    def readInt(self):
        self.position += 4
        return self.data[self.position - 4] ^ self.data[self.position - 3] << 8 ^ self.data[self.position - 2] << 16

def io_worker():
    """消费者线程：专门负责写文件，是唯一的写入者"""
    while True:
        item = queue_in.get()
        if item is None:
            break
        
        rel_path, resource = item
        full_path = os.path.join(OUTPUT_ROOT, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        print(f"Writing: {rel_path}")
        try:
            if isinstance(resource, BytesIO):
                with open(full_path, "wb") as f: f.write(resource.getbuffer())
            else:
                with open(full_path, "wb") as f: f.write(resource)
        except Exception as e:
            print(f"Error writing {rel_path}: {e}")
        queue_in.task_done()

def process_object(key, obj, avatar_map):
    """
    处理单个资源对象。
    """
    obj_type = obj.type.name
    
    # 1. 头像
    if CONFIG["avatar"] and key.startswith("avatar.") and isinstance(obj, Sprite):
        real_key = key[7:]
        if real_key != "Cipher1" and real_key in avatar_map:
            real_key = avatar_map[real_key]
        
        bytesIO = BytesIO()
        obj.image.save(bytesIO, "png")
        queue_in.put((f"avatar/{real_key}.png", bytesIO))

    # 2. 谱面 json
    elif CONFIG["chart"] and "/Chart_" in key and key.endswith(".json") and obj_type == "TextAsset":
        try:
            parts = key.replace("\\", "/").split("/")
            song_id_folder = parts[-2] # e.g., "SongID.0"
            diff = parts[-1].replace("Chart_", "").replace(".json", "")
            
            queue_in.put((f"chart/{song_id_folder}/{diff}.json", obj.script))

        except Exception as e:
            print(f"处理谱面失败: {key}, 错误: {e}")

    # 3. 曲绘
    elif isinstance(obj, Sprite):
        try:
            subfolder = None
            if CONFIG["illustration"] and "Illustration." in key:
                subfolder = "illustration"
            elif CONFIG["illustrationBlur"] and "IllustrationBlur." in key:
                subfolder = "illustrationBlur"
            elif CONFIG["illustrationLowRes"] and "IllustrationLowRes." in key:
                subfolder = "illustrationLowRes"
            
            if subfolder:
                parts = key.replace("\\", "/").split("/")
                song_id = parts[-2].replace(".0", "")
                rel_path = f"{subfolder}/{song_id}.png"
                
                bytesIO = BytesIO()
                obj.image.save(bytesIO, "png")
                queue_in.put((rel_path, bytesIO))

        except Exception as e:
            print(f"处理曲绘失败: {key}, 错误: {e}")

    # 4. 音乐
    elif CONFIG["music"] and key.endswith(".0/music.wav") and isinstance(obj, AudioClip):
        if not FSB5: return
        try:
            # 这里也统一使用 parts[-2] 提取，保持一致性
            song_id_folder = key.replace("\\", "/").split("/")[-2]
            song_id = song_id_folder.replace(".0", "")
            rel_path = f"music/{song_id}.ogg"
            
            fsb = FSB5(obj.m_AudioData)
            if fsb.samples:
                rebuilt_sample = fsb.rebuild_sample(fsb.samples[0])
                queue_in.put((rel_path, rebuilt_sample))
        except Exception as e:
            print(f"音频解码失败 {key}: {e}")

def extract_resources(apk_path, output_dir="output"):
    global OUTPUT_ROOT
    OUTPUT_ROOT = output_dir
    print(f"--- 开始提取资源文件 (Music/Image/Chart) ---")

    io_thread = threading.Thread(target=io_worker)
    io_thread.start()
    
    try:
        with ZipFile(apk_path) as apk:
            with apk.open("assets/aa/catalog.json") as f: data = json.load(f)
    except KeyError:
        print("错误: 找不到 catalog.json")
        queue_in.put(None); io_thread.join()
        return

    key = base64.b64decode(data["m_KeyDataString"])
    bucket = base64.b64decode(data["m_BucketDataString"])
    entry = base64.b64decode(data["m_EntryDataString"])
    table = []
    reader = ByteReader(bucket)
    for x in range(reader.readInt()):
        key_position = reader.readInt(); key_type = key[key_position]; key_position += 1
        if key_type == 0:
            length = key[key_position]; key_position += 4
            key_value = key[key_position:key_position + length].decode()
        elif key_type == 1:
            length = key[key_position]; key_position += 4
            key_value = key[key_position:key_position + length].decode("utf16")
        elif key_type == 4:
            key_value = key[key_position]
        else:
            raise BaseException(key_position, key_type)
        for i in range(reader.readInt()):
            entry_position = reader.readInt()
            entry_value = entry[4 + 28 * entry_position:4 + 28 * entry_position + 28]
            entry_value = entry_value[8] ^ entry_value[9] << 8
        table.append([key_value, entry_value])
    
    for i in range(len(table)):
        if table[i][1] != 65535: table[i][1] = table[table[i][1]][0]
    
    final_table = []
    for k, v in table:
        if isinstance(k, int) or k.startswith("Assets/Tracks/#") or not (k.startswith("Assets/Tracks/") or k.startswith("avatar.")):
            continue
        if k.startswith("Assets/Tracks/"): k = k[14:]
        final_table.append((k, v))
    print(f"Catalog 解析完成，找到 {len(final_table)} 个潜在资源。")

    avatar_map = {}
    tmp_tsv = os.path.join(OUTPUT_ROOT, "info", "tmp.tsv")
    if os.path.exists(tmp_tsv):
        with open(tmp_tsv, encoding="utf8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2: avatar_map[parts[1]] = parts[0]

    ti = time.time()
    classes_to_load = (ClassIDType.TextAsset, ClassIDType.Sprite, ClassIDType.AudioClip)
    
    with ZipFile(apk_path) as apk:
        def job(item):
            k, v = item
            try:
                bundle_data = apk.read(f"assets/aa/Android/{v}")
                env = Environment()
                env.load_file(bundle_data, name=k)
                for obj in env.objects:
                    if obj.type in classes_to_load:
                        process_object(k, obj.read(), avatar_map)
            except Exception:
                pass 

        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.map(job, final_table)

    queue_in.put(None)
    io_thread.join()
    print(f"资源提取完成，耗时: {round(time.time() - ti, 2)}s")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract_resources(sys.argv[1], "output")
    else:
        print("Usage: python resource.py <apk_path>")