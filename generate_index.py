import os
import json
import shutil
import hashlib
import random
from itertools import cycle

# === 配置区域 ===
OUTPUT_DIR = "output"
JSON_INDEX_FILENAME = "files.json"
CHECKSUM_FILENAME = "checksums.sha256"
MANUAL_ASSETS_DIR = "manual_assets"

# 要迁移的静态文件列表
STATIC_FILES_TO_COPY = [
    "index.html",
    "robots.txt",
    "_headers"
]

def calculate_sha256(filepath):
    """计算文件的 SHA-256 哈希值"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # 逐块读取以防文件过大
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def generate_site_resources():
    print("--- 开始生成网站索引与静态文件 ---")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. 复制静态文件
    print("正在部署静态文件...")
    for filename in STATIC_FILES_TO_COPY:
        source_path = filename
        target_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(source_path):
            shutil.copy2(source_path, target_path)
            print(f"  - 已部署: {source_path} -> {target_path}")
        else:
            print(f"  - 警告: 静态文件 {source_path} 不存在，跳过。")

    if os.path.isdir(MANUAL_ASSETS_DIR):
        print(f"\n正在部署手动资源目录: {MANUAL_ASSETS_DIR} -> {OUTPUT_DIR}")
        shutil.copytree(MANUAL_ASSETS_DIR, OUTPUT_DIR, dirs_exist_ok=True)

    # 2. 生成 files.json
    print("\n正在生成文件索引 (files.json)...")
    file_list_for_search = []
    
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for file in files:
            # 排除元文件
            if file in STATIC_FILES_TO_COPY or file == JSON_INDEX_FILENAME or file.startswith("."):
                continue
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, OUTPUT_DIR)
            web_path = relative_path.replace("\\", "/")
            file_list_for_search.append(web_path)

    file_list_for_search.sort()
    json_path = os.path.join(OUTPUT_DIR, JSON_INDEX_FILENAME)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(file_list_for_search, f, ensure_ascii=False)
    print(f"已生成搜索索引: {json_path} (共 {len(file_list_for_search)} 个资源条目)")

    # 2.5 生成 illustration 虚拟入口
    print("\n正在生成 illustration 虚拟入口 (_redirects)...")
    # 筛选 illustration/ 开头的文件
    illustration_files = [f for f in file_list_for_search if f.startswith("illustration/")]
    
    if illustration_files:
        # 配置
        HASH_LENGTH = 2
        
        # 256 (00-ff) per group
        VIRTUAL_CAPACITY_PER_GROUP = 16 ** HASH_LENGTH 
        
        # 打乱图片顺序
        random.shuffle(illustration_files)
        
        # 计算需要多少个分组才能装下所有图片
        # 例如: 298 张图 / 256 = 1.16 -> 需要 2 个组
        import math
        num_groups = math.ceil(len(illustration_files) / VIRTUAL_CAPACITY_PER_GROUP)
        
        # 为了冗余和未来扩展，至少保证生成2个组 (512容量)
        # 如果图片非常少，也会生成两个组，只是会有重复
        if num_groups < 2:
            num_groups = 2
            
        print(f"  - 找到 {len(illustration_files)} 个插画文件")
        print(f"  - 将生成 {num_groups} 个分组 (每组 {VIRTUAL_CAPACITY_PER_GROUP} 个入口)，总容量 {num_groups * VIRTUAL_CAPACITY_PER_GROUP}")
        
        img_iterator = cycle(illustration_files)
        new_rules = []
        new_rules.append(f"\n# === Auto-generated illustration redirects ({len(illustration_files)} files, {num_groups} groups) ===")
        
        for group_id in range(1, num_groups + 1):
            # 比如 /ill/1, /ill/2
            group_prefix = f"/ill/{group_id}"
            
            for i in range(VIRTUAL_CAPACITY_PER_GROUP):
                hex_name = f"{i:0{HASH_LENGTH}x}"
                target = next(img_iterator)
                
                # 规则: /ill/1/00.jpg -> /illustration/a.png
                virtual_path = f"{group_prefix}/{hex_name}.jpg"
                new_rules.append(f"{virtual_path} /{target} 200")
                
        redirects_path = os.path.join(OUTPUT_DIR, "_redirects")
        
        # 读取现有内容 (如果有)
        existing_content = ""
        if os.path.exists(redirects_path):
            with open(redirects_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
        
        # 写入合并后的内容
        with open(redirects_path, "w", encoding="utf-8") as f:
            if existing_content:
                f.write(existing_content + "\n")
            f.write("\n".join(new_rules))
            
        print(f"  - 已更新 _redirects 文件")
    else:
        print("  - 未找到 illustration/ 目录下的文件，跳过虚拟入口生成。")

    # 3. 生成校验和文件
    print(f"\n正在生成终极校验和文件 ({CHECKSUM_FILENAME})...")
    checksum_entries = []
    
    # 再次遍历 output 目录，这次包含所有文件
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for file in files:
            # 我们要校验所有文件，但 checksum 文件本身不能包含自己
            if file == CHECKSUM_FILENAME:
                continue
            
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, OUTPUT_DIR).replace("\\", "/")
            
            # 计算哈希
            file_hash = calculate_sha256(full_path)
            
            # 格式化: hash  filename
            checksum_entries.append(f"{file_hash}  {relative_path}")

    # 按文件名排序，让文件更整洁
    checksum_entries.sort(key=lambda x: x.split("  ", 1)[1])
    
    checksum_path = os.path.join(OUTPUT_DIR, CHECKSUM_FILENAME)
    with open(checksum_path, "w", encoding="utf-8") as f:
        f.write("\n".join(checksum_entries))
    print(f"已生成校验和文件: {checksum_path}")

if __name__ == "__main__":
    generate_site_resources()
