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
from UnityPy.classes import AudioClip
from UnityPy.enums import ClassIDType

# 尝试导入 FSB5，如果环境里没有安装，可能会报错
try:
    from fsb5 import FSB5
except ImportError:
    print("警告: 未找到 fsb5 模块，音频将无法解码为 .ogg (可能保存为原格式或跳过)")
    FSB5 = None

# ---------------- 配置区域 ----------------
# 默认全开启
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
OUTPUT_ROOT = "output" # 默认值，会被 run() 函数覆盖

# ---------------- 工具类 ----------------
class ByteReader:
    def __init__(self, data):
        self.data = data
        self.position = 0

    def readInt(self):
        self.position += 4
        return self.data[self.position - 4] ^ self.data[self.position - 3] << 8 ^ self.data[self.position - 2] << 16

def io_worker():
    """消费者线程：负责写文件"""
    while True:
        item = queue_in.get()
        if item is None:
            break
        
        rel_path, resource = item
        # 拼接完整路径: output/music/xxx.ogg
        full_path = os.path.join(OUTPUT_ROOT, rel_path)
        
        # 确保父目录存在
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        print(f"Writing: {rel_path}")
        
        try:
            if isinstance(resource, BytesIO):
                with open(full_path, "wb") as f:
                    f.write(resource.getbuffer())
            else:
                with open(full_path, "wb") as f:
                    f.write(resource)
        except Exception as e:
            print(f"Error writing {rel_path}: {e}")
            
        queue_in.task_done()

def save_image(rel_path, image):
    bytesIO = BytesIO()
    image.save(bytesIO, "png")
    queue_in.put((rel_path, bytesIO))

def save_music(rel_path, music: AudioClip):
    if not FSB5:
        return # 没库解不了
    try:
        # 尝试解码 FSB5
        fsb = FSB5(music.m_AudioData)
        # 获取第一个 sample (通常只有一个)
        if len(fsb.samples) > 0:
            rebuilt_sample = fsb.rebuild_sample(fsb.samples[0])
            queue_in.put((rel_path, rebuilt_sample))
    except Exception as e:
        print(f"音频解码失败 {rel_path}: {e}")

# ---------------- 核心逻辑 ----------------

def process_object(key, obj, avatar_map):
    """处理单个资源对象"""
    # 1. 头像
    if CONFIG["avatar"] and key.startswith("avatar."):
        real_key = key[7:]
        # 尝试映射名字
        if real_key != "Cipher1" and real_key in avatar_map:
            real_key = avatar_map[real_key]
        
        bytesIO = BytesIO()
        obj.image.save(bytesIO, "png")
        queue_in.put((f"avatar/{real_key}.png", bytesIO))

    # 2. 谱面 json
    elif CONFIG["chart"] and "/Chart_" in key and key.endswith(".json"):
        # key 类似: Assets/Tracks/SongID/Chart_IN.json
        # 提取 SongID 和 Difficulty
        parts = key.split("/")
        # 倒数第二个通常是 SongID (但要小心路径变化)
        # 原逻辑 key[:-14] 比较脆弱，我们用 split 稳妥点
        # 假设格式是 .../SongID/Chart_XX.json
        song_id = parts[-2]
        diff = parts[-1].replace("Chart_", "").replace(".json", "")
        
        # 按照 output/chart/SongID/IN.json 结构
        queue_in.put((f"chart/{song_id}.0/{diff}.json", obj.script))

    # 3. 曲绘 (模糊)
    elif CONFIG["illustrationBlur"] and key.endswith(".0/IllustrationBlur."):
        # Assets/Tracks/SongID.0/IllustrationBlur.
        song_id = key.split("/")[-2].replace(".0", "") # 粗暴提取
        bytesIO = BytesIO()
        obj.image.save(bytesIO, "png")
        queue_in.put((f"illustrationBlur/{song_id}.png", bytesIO))

    # 4. 曲绘 (低清)
    elif CONFIG["illustrationLowRes"] and key.endswith(".0/IllustrationLowRes."):
        song_id = key.split("/")[-2].replace(".0", "")
        save_image(f"illustrationLowRes/{song_id}.png", obj.image)

    # 5. 曲绘 (高清)
    elif CONFIG["illustration"] and key.endswith(".0/Illustration."):
        song_id = key.split("/")[-2].replace(".0", "")
        save_image(f"illustration/{song_id}.png", obj.image)

    # 6. 音乐
    elif CONFIG["music"] and key.endswith(".0/music.wav"):
        song_id = key.split("/")[-2].replace(".0", "")
        # 注意: 这里的 .wav 只是 Unity 里的名字，实际上内部数据是 fsb5
        save_music(f"music/{song_id}.ogg", obj)


def extract_resources(apk_path, output_dir="output"):
    global OUTPUT_ROOT
    OUTPUT_ROOT = output_dir

    print(f"--- 开始提取资源文件 (Music/Image/Chart) ---")
    print(f"APK: {apk_path}")
    print(f"Output: {OUTPUT_ROOT}")

    # 1. 准备目录
    for sub in ["avatar", "chart", "illustrationBlur", "illustrationLowRes", "illustration", "music"]:
        os.makedirs(os.path.join(OUTPUT_ROOT, sub), exist_ok=True)
    
    # 2. 读取 Catalog
    print("读取 Catalog...")
    try:
        with ZipFile(apk_path) as apk:
            with apk.open("assets/aa/catalog.json") as f:
                data = json.load(f)
    except KeyError:
        print("错误: 无法在 APK 中找到 assets/aa/catalog.json，可能是旧版本或加固包")
        return

    # 3. 解析 Catalog (复制原作者的解码逻辑)
    key = base64.b64decode(data["m_KeyDataString"])
    bucket = base64.b64decode(data["m_BucketDataString"])
    entry = base64.b64decode(data["m_EntryDataString"])

    table = []
    reader = ByteReader(bucket)
    for x in range(reader.readInt()):
        key_position = reader.readInt()
        key_type = key[key_position]
        key_position += 1
        if key_type == 0:
            length = key[key_position]
            key_position += 4
            key_value = key[key_position:key_position + length].decode()
        elif key_type == 1:
            length = key[key_position]
            key_position += 4
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
    
    # 处理 table 引用
    for i in range(len(table)):
        if table[i][1] != 65535:
            table[i][1] = table[table[i][1]][0]
    
    # 过滤无效条目
    final_table = []
    for k, v in table:
        if isinstance(k, int): continue
        if k.startswith("Assets/Tracks/#"): continue
        if not (k.startswith("Assets/Tracks/") or k.startswith("avatar.")): continue
        
        if k.startswith("Assets/Tracks/"):
            k = k[14:] # 去掉前缀方便处理
        final_table.append((k, v))
    
    print(f"Found {len(final_table)} resources to extract.")

    # 4. 加载 avatar 映射 (依赖 info/tmp.tsv，如果上一阶段 gameInformation 生成了的话)
    avatar_map = {}
    tmp_tsv = os.path.join(OUTPUT_ROOT, "info", "tmp.tsv")
    if os.path.exists(tmp_tsv):
        try:
            with open(tmp_tsv, encoding="utf8") as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        avatar_map[parts[1]] = parts[0]
        except Exception:
            print("Avatar map load failed.")

    # 5. 启动 IO 线程
    io_thread = threading.Thread(target=io_worker)
    io_thread.start()

    # 6. 多线程解包
    # 全量解包，不再过滤 update 数量
    
    classes_to_load = (ClassIDType.TextAsset, ClassIDType.Sprite, ClassIDType.AudioClip)
    
    ti = time.time()
    
    with ZipFile(apk_path) as apk:
        # UnityPy 的 Environment 可以复用吗？对于多文件 bundle 最好是逐个处理
        # 为了避免内存爆炸，我们分批或逐个处理
        
        def job(item):
            k, v = item
            try:
                # 这是一个潜在的性能瓶颈：每次都 open zip 和 load file
                # 但 UnityPy 没有简单的流式接口处理这种 Android bundle 路径
                bundle_data = apk.read(f"assets/aa/Android/{v}")
                env = Environment()
                env.load_file(bundle_data, name=k)
                
                for obj in env.objects:
                    if obj.type in classes_to_load:
                        # 再次过滤: 只需要 TextAsset(Chart), Sprite(Img), AudioClip(Music)
                        process_object(k, obj.read(), avatar_map)
                        
            except Exception as e:
                print(f"Failed to process {k}: {e}")

        # 使用线程池加速解析 (IO是瓶颈，所以用多线程有帮助)
        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.map(job, final_table)

    # 7. 结束
    queue_in.put(None)
    io_thread.join()
    print(f"资源提取完成，耗时: {round(time.time() - ti, 2)}s")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract_resources(sys.argv[1], "output")
    else:
        print("Usage: python resource.py <apk_path>")