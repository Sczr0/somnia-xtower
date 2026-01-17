import os
import json
import shutil
import hashlib

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
