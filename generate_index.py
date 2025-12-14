import os
import json
import shutil

# === 配置区域 ===
OUTPUT_DIR = "output"
JSON_OUTPUT_FILENAME = "files.json"

# 把所有需要复制的静态文件都列在这里
# 以后如果还有其他文件，比如 sitemap.xml，直接加到这个列表里就行
STATIC_FILES_TO_COPY = [
    "index.html",
    "robots.txt",
    "_headers"
]

def generate_site_resources():
    print("--- 开始生成网站索引与静态文件 ---")

    # 1. 复制所有必要的静态文件到 output 根目录
    print("正在部署静态文件...")
    for filename in STATIC_FILES_TO_COPY:
        source_path = filename
        target_path = os.path.join(OUTPUT_DIR, filename)
        
        if os.path.exists(source_path):
            shutil.copy2(source_path, target_path)
            print(f"  - 已部署: {source_path} -> {target_path}")
        else:
            # _headers 可能不存在，这是一个可选文件，所以用警告而不是错误
            print(f"  - 警告: 静态文件 {source_path} 不存在，跳过。")

    # 2. 生成 files.json
    print("\n正在生成文件索引 (files.json)...")
    file_list = []
    
    # 遍历 output 目录
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for file in files:
            # 排除掉不希望被搜索到的元文件
            # 用户不需要搜索到 index.html 或 files.json 本身
            if file in STATIC_FILES_TO_COPY or file == JSON_OUTPUT_FILENAME or file.startswith("."):
                continue
            
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, OUTPUT_DIR)
            web_path = relative_path.replace("\\", "/")
            file_list.append(web_path)

    file_list.sort()

    json_path = os.path.join(OUTPUT_DIR, JSON_OUTPUT_FILENAME)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(file_list, f, ensure_ascii=False) # 紧凑格式
    
    print(f"已生成索引: {json_path} (共 {len(file_list)} 个资源条目)")

if __name__ == "__main__":
    generate_site_resources()