"""从 APK 的 GameInformation 里提取 keyStore 派生的 single.txt / illustration.txt。

PhiInfo 不导出 keyStore，所以这两个文件继续用 UnityPy + typetree.json 兜底；
其余 info/ 发布文件全部由 info_export.py 负责，避免两个生产者抢同一批文件。
本模块失败只告警，不阻断发布。
"""
import json
import os
import sys
import zipfile

from UnityPy import Environment


def _to_text(value):
    return "" if value is None else str(value).strip()


def extract_keystore(apk_path, output_root="output"):
    """写入 output/info/{single.txt,illustration.txt}，成功返回 True。"""
    info_dir = os.path.join(output_root, "info")
    os.makedirs(info_dir, exist_ok=True)

    if not os.path.exists("typetree.json"):
        print("警告：找不到 typetree.json，无法提取 keyStore。")
        return False

    with open("typetree.json", encoding="utf-8") as f:
        typetree = json.load(f)

    env = Environment()
    with zipfile.ZipFile(apk_path) as apk:
        if "assets/bin/Data/globalgamemanagers.assets" in apk.namelist():
            with apk.open("assets/bin/Data/globalgamemanagers.assets") as f:
                env.load_file(f.read(), name="assets/bin/Data/globalgamemanagers.assets")
        if "assets/bin/Data/level0" in apk.namelist():
            with apk.open("assets/bin/Data/level0") as f:
                env.load_file(f.read())

    key_store = None
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            candidate = obj.read_typetree(typetree["GameInformation"], False)
        except Exception:
            continue
        if isinstance(candidate, dict) and "keyStore" in candidate:
            key_store = candidate["keyStore"]
            break

    if key_store is None:
        print("警告：未能从 level0 读到 GameInformation.keyStore（游戏版本可能已变更）。")
        return False

    single = []
    illustration = []
    for key in key_store:
        kind = key["kindOfKey"]
        key_name = _to_text(key["keyName"])
        if kind == 0:
            single.append(key_name)
        elif kind == 2 and key_name != "Introduction" and key_name not in single:
            illustration.append(key_name)

    with open(os.path.join(info_dir, "single.txt"), "w", encoding="utf8") as f:
        f.write("\n".join(single))
    with open(os.path.join(info_dir, "illustration.txt"), "w", encoding="utf8") as f:
        f.write("\n".join(illustration))

    print(
        f"--- keyStore 提取完成: single={len(single)} illustration={len(illustration)} ---",
        flush=True,
    )
    return True


if __name__ == "__main__":
    argv = [arg for arg in sys.argv[1:] if arg != "--keystore-only"]
    if not argv:
        print("用法: python gameInformation.py [--keystore-only] <apk_path> [output_root]")
        sys.exit(2)
    root = argv[1] if len(argv) > 1 else "output"
    sys.exit(0 if extract_keystore(argv[0], root) else 1)
