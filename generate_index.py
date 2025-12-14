import os
import json
import shutil

# 配置
OUTPUT_DIR = "output"
SOURCE_HTML = "index.html"
JSON_OUTPUT = "files.json"

def generate_site_resources():
    print("--- 开始生成网站索引与静态文件 ---")

    # 1. 复制 index.html 到 output 根目录
    if os.path.exists(SOURCE_HTML):
        target_html = os.path.join(OUTPUT_DIR, "index.html")
        shutil.copy2(SOURCE_HTML, target_html)
        print(f"已部署前端: {SOURCE_HTML} -> {target_html}")
    else:
        print(f"警告: 当前目录下找不到 {SOURCE_HTML}，网站可能无法访问！")

    # 2. 生成 files.json
    # index.html 需要一个纯数组: ["path/to/file1", "path/to/file2"]
    file_list = []
    
    # 我们遍历 output 目录
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for file in files:
            # 排除掉 index.html 和 files.json 自身，以及隐藏文件
            if file in ["index.html", "files.json", "_headers", "_redirects"] or file.startswith("."):
                continue
            
            # 获取完整路径
            full_path = os.path.join(root, file)
            
            # 获取相对路径 (例如: music/song.ogg)
            relative_path = os.path.relpath(full_path, OUTPUT_DIR)
            
            # 统一路径分隔符为 / (Windows下是 \，Web需要 /)
            web_path = relative_path.replace("\\", "/")
            
            file_list.append(web_path)

    # 排序，好看一点
    file_list.sort()

    # 写入 output/files.json
    json_path = os.path.join(OUTPUT_DIR, JSON_OUTPUT)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(file_list, f, ensure_ascii=False) # 紧凑格式，节省流量
    
    print(f"已生成索引: {json_path} (共 {len(file_list)} 个文件)")

if __name__ == "__main__":
    generate_site_resources()