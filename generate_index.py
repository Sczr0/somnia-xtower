import os
import json
import shutil
import hashlib
import random
import math
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

def copy_missing_files(source_dir, target_dir):
    copied_count = 0
    skipped_count = 0

    for root, dirs, files in os.walk(source_dir):
        for file in files:
            source_path = os.path.join(root, file)
            relative_path = os.path.relpath(source_path, source_dir)
            target_path = os.path.join(target_dir, relative_path)

            parent_dir = os.path.dirname(target_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            if os.path.exists(target_path):
                skipped_count += 1
                continue

            shutil.copy2(source_path, target_path)
            copied_count += 1

    return copied_count, skipped_count

def _collect_illustration_files(file_list_for_search, extension):
    suffix = f".{extension.lower()}"
    return [
        path for path in file_list_for_search
        if path.startswith("illustration/") and path.lower().endswith(suffix)
    ]


def _build_group_redirect_rules(
    source_files,
    group_prefix,
    request_extension,
    hash_length=2,
    min_groups=2,
    fixed_num_groups=None,
    rng=None,
):
    files = list(source_files)
    if not files:
        return [], 0, 0

    rng = rng or random
    rng.shuffle(files)

    capacity_per_group = 16 ** hash_length
    num_groups = fixed_num_groups
    if num_groups is None:
        num_groups = math.ceil(len(files) / capacity_per_group)
    num_groups = max(min_groups, num_groups)

    img_iterator = cycle(files)
    rules = []
    for group_id in range(1, num_groups + 1):
        group_entry_prefix = f"{group_prefix}/{group_id}"
        for i in range(capacity_per_group):
            hex_name = f"{i:0{hash_length}x}"
            target = next(img_iterator)
            virtual_path = f"{group_entry_prefix}/{hex_name}.{request_extension}"
            rules.append(f"{virtual_path} /{target} 200")

    return rules, num_groups, capacity_per_group


def build_illustration_redirect_rules(file_list_for_search, hash_length=2, min_groups=2, rng=None):
    illustration_png_files = _collect_illustration_files(file_list_for_search, "png")
    if not illustration_png_files:
        return [], {}

    new_rules = []
    ill_rules, num_groups, capacity_per_group = _build_group_redirect_rules(
        illustration_png_files,
        "/ill",
        "jpg",
        hash_length=hash_length,
        min_groups=min_groups,
        rng=rng,
    )
    new_rules.append(
        f"\n# === Auto-generated illustration redirects ({len(illustration_png_files)} png files, {num_groups} groups) ==="
    )
    new_rules.extend(ill_rules)

    return new_rules, {
        "png_count": len(illustration_png_files),
        "num_groups": num_groups,
        "capacity_per_group": capacity_per_group,
    }


def generate_site_resources():
    print("--- 开始生成网站索引与静态文件 ---")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. 部署手动资源 (Manual Assets)
    if os.path.isdir(MANUAL_ASSETS_DIR):
        print(f"\n[Step 1] 部署手动资源目录: {MANUAL_ASSETS_DIR} -> {OUTPUT_DIR}")
        copied_count, skipped_count = copy_missing_files(MANUAL_ASSETS_DIR, OUTPUT_DIR)
        print(f"  - 兜底补齐文件: {copied_count}，跳过同名文件: {skipped_count}")

    # 2. 复制静态文件 (覆盖 manual_assets)
    print("\n[Step 2] 部署静态文件...")
    for filename in STATIC_FILES_TO_COPY:
        source_path = filename
        target_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(source_path):
            shutil.copy2(source_path, target_path)
            print(f"  - 已部署: {source_path} -> {target_path}")
        else:
            print(f"  - 警告: 静态文件 {source_path} 不存在，跳过。")

    # 3. 生成 files.json
    print("\n[Step 3] 正在生成文件索引 (files.json)...")
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

    # 3.5 生成 illustration 虚拟入口
    print("\n正在生成 illustration 虚拟入口 (_redirects)...")
    new_rules, redirect_meta = build_illustration_redirect_rules(file_list_for_search)

    if new_rules:
        print(f"  - 找到 {redirect_meta['png_count']} 个 png 曲绘文件")
        print(
            f"  - 将生成 {redirect_meta['num_groups']} 个分组 (每组 {redirect_meta['capacity_per_group']} 个入口)"
        )
        redirects_path = os.path.join(OUTPUT_DIR, "_redirects")

        # 读取现有内容 (如果有)
        existing_content = ""
        if os.path.exists(redirects_path):
            with open(redirects_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
            filtered_lines = []
            for line in existing_content.splitlines():
                if "/lilith/ill/" in line:
                    continue
                if "Auto-generated lilith illustration redirects" in line:
                    continue
                filtered_lines.append(line)
            existing_content = "\n".join(filtered_lines).rstrip()

        # 写入合并后的内容
        with open(redirects_path, "w", encoding="utf-8") as f:
            if existing_content:
                f.write(existing_content + "\n")
            f.write("\n".join(new_rules))

        print(f"  - 已更新 _redirects 文件")
    else:
        print("  - 未找到 illustration/*.png，跳过虚拟入口生成。")

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
