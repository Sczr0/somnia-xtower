import os
import sys
import shutil
import time
import subprocess
import platform

# 引入你的功能模块
import gameInformation
import resource
import phira 
import generate_index

def flush_print(msg):
    """强制刷新打印，确保 GitHub Actions 日志实时显示"""
    print(msg, flush=True)

def check_environment():
    """检查必要的系统命令是否存在"""
    if shutil.which("aria2c") is None:
        flush_print("警告: 未找到 aria2c，下载速度可能会受限 (GitHub Actions 环境建议安装)")

def download_apk(url, filename):
    """使用 Aria2 下载 APK (多线程断点续传)"""
    flush_print(f"--- [Step 1] 开始下载 APK: {url} ---")
    
    if not url:
        flush_print("错误: 下载链接为空！")
        return False

    # 构建 aria2c 命令
    # -x 16: 16线程
    # -s 16: 16连接
    # -k 1M: 块大小
    cmd = [
        "aria2c", "-x", "16", "-s", "16", "-k", "1M",
        "--user-agent=Mozilla/5.0", 
        "--console-log-level=warn",
        "-o", filename, 
        url
    ]

    try:
        # 调用系统命令下载
        subprocess.run(cmd, check=True)
        if os.path.exists(filename) and os.path.getsize(filename) > 1024:
            flush_print("下载成功！")
            return True
        else:
            flush_print("下载命令执行完毕，但文件似乎无效。")
            return False
    except subprocess.CalledProcessError:
        flush_print("下载失败！请检查链接或网络。")
        return False
    except FileNotFoundError:
        # 如果没装 aria2，回退到 python requests (仅作备用，速度慢)
        flush_print("未找到 aria2c，尝试使用 requests 下载...")
        import requests
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
        except Exception as e:
            flush_print(f"Requests 下载也失败了: {e}")
            return False

def main():
    start_time = time.time()
    
    # === 配置 ===
    APK_FILENAME = "game.apk"
    OUTPUT_DIR = "output"
    
    # 优先从环境变量获取链接 (GitHub Actions 传入)，如果没有则尝试读取 input 参数
    # 注意：在 Actions yaml 里我们会把 inputs 映射到环境变量
    APK_URL = os.environ.get('APK_DOWNLOAD_URL')

    # === 初始化 ===
    check_environment()
    
    # 清理旧的 output 目录，确保干净构建
    if os.path.exists(OUTPUT_DIR):
        flush_print(f"清理旧目录: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # === 1. 下载 ===
    if not APK_URL:
        flush_print("警告: 环境变量 APK_DOWNLOAD_URL 未设置。如果你在本地已有 game.apk，将直接使用。")
        if not os.path.exists(APK_FILENAME):
            flush_print("错误: 本地找不到 game.apk 且未提供下载链接，退出。")
            sys.exit(1)
    else:
        if not download_apk(APK_URL, APK_FILENAME):
            sys.exit(1)

    # === 2. 提取信息 (GameInfo) ===
    flush_print("\n--- [Step 2] 提取游戏文本信息 (GameInfo) ---")
    try:
        # 调用 gameInformation.py 中的函数
        gameInformation.extract_game_info(APK_FILENAME, OUTPUT_DIR)
    except Exception as e:
        flush_print(f"!! 提取 GameInfo 失败: {e}")
        # Info 失败通常不影响资源提取，继续运行

    # === 3. 提取资源 (Resource) ===
    flush_print("\n--- [Step 3] 提取图片与音乐 (Resource) ---")
    try:
        # 调用 resource.py 中的函数
        resource.extract_resources(APK_FILENAME, OUTPUT_DIR)
    except Exception as e:
        flush_print(f"!! 提取资源失败: {e}")
        sys.exit(1) # 资源提取失败则是严重错误

    # === 4. 打包 Phira (.pez) ===
    flush_print("\n--- [Step 4] 打包 Phira 资源 (.pez) ---")
    try:
        # phira.py 会自动扫描 OUTPUT_DIR 并将结果写回 OUTPUT_DIR/phira
        phira.generate_phira_packages()
    except Exception as e:
        flush_print(f"!! Phira 打包失败: {e}")

    # === 5. 生成索引 (Index) ===
    # 允许在 CI 中先跳过索引，待 PhiInfo 等后处理完成后再统一生成
    skip_index = os.environ.get("SKIP_INDEX_GENERATION", "").lower() in ("1", "true", "yes")
    if skip_index:
        flush_print("\n--- [Step 5] 跳过索引生成 (由后续流程统一生成) ---")
    else:
        flush_print("\n--- [Step 5] 生成网站索引 (Generate Index) ---")
        try:
            generate_index.generate_site_resources()
        except Exception as e:
            flush_print(f"!! 生成索引失败: {e}")

    # === 结束 ===
    elapsed = time.time() - start_time
    flush_print(f"\n=== 所有任务完成！耗时: {elapsed:.2f} 秒 ===")
    flush_print(f"输出目录: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    main()
