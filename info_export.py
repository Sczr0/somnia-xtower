"""/info 发布契约的唯一生产者。

PhiInfo 只负责从 APK 提取原始数据（output/info/*.json），发布格式由本模块独占定义，
避免"外部库换字段 → 线上文件跟着变形"。

契约（v1，列宽固定，任何一条不满足都会让 validate() 抛错并阻断发布）：

    info.csv        id, song, composer, illustrator, EZ, HD, IN, AT, EZC, HDC, INC, ATC
    difficulty.csv  id, EZ, HD, IN, AT
    info.tsv        同 info.csv（tab 分隔）
    difficulty.tsv  同 difficulty.csv（tab 分隔）

语义统一：EZ/HD/IN/AT 是定数（一位小数或空串），EZC/HDC/INC/ATC 是对应难度的谱师。
CSV/TSV 里的 id 一律不带 ".0" 后缀；all_info.json 保持 PhiInfo 原样（仍带 ".0"）。
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys

OUTPUT_DIR = "output"
INFO_SUBDIR = "info"
LEVELS = ("EZ", "HD", "IN", "AT")
SONG_HEADER = ["id", "song", "composer", "illustrator", "EZ", "HD", "IN", "AT", "EZC", "HDC", "INC", "ATC"]
DIFFICULTY_HEADER = ["id", "EZ", "HD", "IN", "AT"]
TABLES = {
    "info.csv": SONG_HEADER,
    "difficulty.csv": DIFFICULTY_HEADER,
    "info.tsv": SONG_HEADER,
    "difficulty.tsv": DIFFICULTY_HEADER,
}
MANIFEST_NAME = "manifest.json"
SCHEMA_VERSION = 1
TIPS_LANGUAGE_ORDER = ("zh_cn", "zh_tw", "en", "ja", "ko")
MIN_SONG_COUNT = 100
MAX_DIFFICULTY = 20.0
VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+)*\s*\(\d+\)$")
EXPORTS = {
    "songs": ("songs.json", True),
    "version": ("version.json", True),
    "collection": ("collection.json", False),
    "avatars": ("avatars.json", False),
    "tips": ("tips.json", False),
}


class InfoContractError(RuntimeError):
    """发布契约不满足：宁可让流水线失败，也不要把半成品推到线上。"""


def sanitize_song_id(song_id):
    """统一去掉 PhiInfo 带出的 ".0" 后缀。"""
    if song_id.endswith(".0") or song_id.endswith("_0"):
        return song_id[:-2]
    return song_id


def pick_language(mapping, preferred="zh_cn"):
    """从多语言字段里取指定语言，缺失时退回任意非空语言。"""
    if not isinstance(mapping, dict):
        return ""
    if mapping.get(preferred):
        return str(mapping[preferred])
    for value in mapping.values():
        if value:
            return str(value)
    return ""


def safe_avatar_key(addressable_key):
    """兼容 addressableKey 为空或长度不足（去掉 "avatar." 前缀，与旧 tmp.tsv 一致）。"""
    if isinstance(addressable_key, str) and len(addressable_key) >= 7:
        return addressable_key[7:]
    return ""


def format_difficulty(value):
    if value is None or value == "":
        return ""
    return f"{float(value):.1f}"


def _text(value):
    return "" if value is None else str(value).strip()


def _load_json(info_dir, filename, required):
    path = os.path.join(info_dir, filename)
    if not os.path.exists(path):
        if required:
            raise InfoContractError(f"缺少 PhiInfo 导出文件: {path}")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise InfoContractError(f"无法解析 {path}: {exc}") from exc


def load_exports(info_dir):
    exports = {}
    for key, (filename, required) in EXPORTS.items():
        exports[key] = _load_json(info_dir, filename, required)

    songs = exports["songs"]
    if not isinstance(songs, list) or not songs:
        raise InfoContractError("songs.json 为空或不是数组")
    version = exports["version"]
    if not isinstance(version, dict):
        raise InfoContractError("version.json 不是对象")
    return exports


def normalize_songs(raw_songs):
    records = []
    seen = set()
    for index, song in enumerate(raw_songs):
        if not isinstance(song, dict):
            raise InfoContractError(f"songs[{index}] 不是对象")
        song_id = sanitize_song_id(_text(song.get("id")))
        if not song_id:
            raise InfoContractError(f"songs[{index}] 缺少 id")
        if song_id in seen:
            raise InfoContractError(f"songs.json 存在重复 id: {song_id}")
        seen.add(song_id)

        levels = song.get("levels")
        if not isinstance(levels, dict):
            levels = {}

        difficulties = {}
        charters = {}
        for level in LEVELS:
            entry = levels.get(level)
            if isinstance(entry, dict):
                difficulties[level] = format_difficulty(entry.get("difficulty"))
                charters[level] = _text(entry.get("charter"))
            else:
                difficulties[level] = ""
                charters[level] = ""

        name = song.get("name")
        records.append({
            "id": song_id,
            "name": pick_language(name) if isinstance(name, dict) else _text(name),
            "composer": _text(song.get("composer")),
            "illustrator": _text(song.get("illustrator")),
            "difficulties": difficulties,
            "charters": charters,
        })
    return records


def normalize_collection(raw_folders):
    """展开 PhiInfo 的 文件夹 → 条目 结构：同 key 保留首个名称、取最后一个 sub_index。"""
    collection = {}
    for folder in raw_folders or []:
        if not isinstance(folder, dict):
            continue
        for item in folder.get("files") or []:
            if not isinstance(item, dict):
                continue
            key = _text(item.get("key"))
            if not key:
                continue
            if key in collection:
                collection[key]["sub_index"] = item.get("sub_index")
            else:
                collection[key] = {
                    "key": key,
                    "name": pick_language(item.get("name")),
                    "sub_index": item.get("sub_index"),
                }
    return list(collection.values())


def normalize_avatars(raw_avatars):
    avatars = []
    for item in raw_avatars or []:
        if not isinstance(item, dict):
            continue
        avatars.append({
            "name": _text(item.get("name")),
            "addressable_key": safe_avatar_key(item.get("addressable_key", "")),
        })
    return avatars


def normalize_tips(raw_tips):
    if isinstance(raw_tips, dict):
        for language in TIPS_LANGUAGE_ORDER:
            values = raw_tips.get(language)
            if values:
                return [str(value) for value in values]
        for values in raw_tips.values():
            if values:
                return [str(value) for value in values]
        return []
    if isinstance(raw_tips, list):
        return [str(value) for value in raw_tips]
    return []


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _write_tsv(path, header, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for row in rows:
            f.write("\t".join(row) + "\n")


def _song_rows(records):
    return [
        [record["id"], record["name"], record["composer"], record["illustrator"]]
        + [record["difficulties"][level] for level in LEVELS]
        + [record["charters"][level] for level in LEVELS]
        for record in records
    ]


def _difficulty_rows(records):
    return [
        [record["id"]] + [record["difficulties"][level] for level in LEVELS]
        for record in records
    ]


def _write_version(path, version):
    name = _text(version.get("name")) or "unknown"
    code = version.get("code", "0")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{name} ({code})\n")
    return f"{name} ({code})"


def _write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def _write_manifest(info_dir, counts, version_text):
    files = {}
    for name in sorted(os.listdir(info_dir)):
        full_path = os.path.join(info_dir, name)
        if name == MANIFEST_NAME or not os.path.isfile(full_path):
            continue
        files[name] = {
            "bytes": os.path.getsize(full_path),
            "sha256": _sha256(full_path),
        }
    manifest = {
        "schema": SCHEMA_VERSION,
        "version": version_text,
        "counts": counts,
        "files": files,
    }
    with open(os.path.join(info_dir, MANIFEST_NAME), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return manifest


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_published_info(output_root=OUTPUT_DIR):
    info_dir = os.path.join(output_root, INFO_SUBDIR)
    os.makedirs(info_dir, exist_ok=True)

    exports = load_exports(info_dir)
    records = normalize_songs(exports["songs"])
    collection = normalize_collection(exports["collection"])
    avatars = normalize_avatars(exports["avatars"])
    tips = [tip for tip in normalize_tips(exports["tips"]) if tip.strip() and not tip.startswith("#")]

    song_rows = _song_rows(records)
    _write_csv(os.path.join(info_dir, "info.csv"), SONG_HEADER, song_rows)
    _write_csv(os.path.join(info_dir, "difficulty.csv"), DIFFICULTY_HEADER, _difficulty_rows(records))
    _write_tsv(os.path.join(info_dir, "info.tsv"), SONG_HEADER, song_rows)
    _write_tsv(os.path.join(info_dir, "difficulty.tsv"), DIFFICULTY_HEADER, _difficulty_rows(records))

    with open(os.path.join(info_dir, "all_info.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "songs": exports["songs"],
                "collection": collection,
                "avatars": avatars,
                "tips": normalize_tips(exports["tips"]),
            },
            f,
            ensure_ascii=False,
        )

    version_text = _write_version(os.path.join(info_dir, "version.txt"), exports["version"])

    _write_lines(
        os.path.join(info_dir, "collection.tsv"),
        [f"{item['key']}\t{item['name']}\t{item['sub_index']}" for item in collection],
    )
    _write_lines(os.path.join(info_dir, "avatar.txt"), [item["name"] for item in avatars])
    _write_lines(
        os.path.join(info_dir, "tmp.tsv"),
        [f"{item['name']}\t{item['addressable_key']}" for item in avatars],
    )
    _write_lines(os.path.join(info_dir, "tips.txt"), tips)

    counts = {
        "songs": len(records),
        "collection": len(collection),
        "avatars": len(avatars),
        "tips": len(tips),
    }
    _write_manifest(info_dir, counts, version_text)

    print(f"--- 已生成 {info_dir} 发布契约 ---", flush=True)
    print(
        f"    songs={counts['songs']} collection={counts['collection']} "
        f"avatars={counts['avatars']} tips={counts['tips']} version={version_text}",
        flush=True,
    )
    return validate(output_root)


def _read_table(info_dir, name):
    path = os.path.join(info_dir, name)
    if not os.path.exists(path):
        raise InfoContractError(f"缺少发布文件: {path}")
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    if not text.strip():
        raise InfoContractError(f"{name} 为空")
    if name.endswith(".csv"):
        rows = list(csv.reader(io.StringIO(text)))
    else:
        rows = [line.split("\t") for line in text.splitlines()]
    if rows and rows[-1] == [""]:
        rows.pop()
    return rows


def _check_table(info_dir, name):
    expected = TABLES[name]
    rows = _read_table(info_dir, name)
    if rows[0] != expected:
        raise InfoContractError(f"{name} 表头不符: {rows[0]}，期望 {expected}")
    ids = []
    for line_number, row in enumerate(rows[1:], start=2):
        if len(row) != len(expected):
            raise InfoContractError(
                f"{name} 第 {line_number} 行有 {len(row)} 列，期望 {len(expected)} 列"
            )
        if not row[0]:
            raise InfoContractError(f"{name} 第 {line_number} 行缺少 id")
        ids.append(row[0])
        for cell in row[1:]:
            if "\n" in cell or "\r" in cell or "\t" in cell:
                raise InfoContractError(f"{name} 第 {line_number} 行存在换行/制表符")
    if len(set(ids)) != len(ids):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        raise InfoContractError(f"{name} 存在重复 id: {duplicates[:5]}")
    return rows, ids


def _check_difficulties(name, rows, offset):
    for line_number, row in enumerate(rows[1:], start=2):
        for cell in row[offset:offset + len(LEVELS)]:
            if not cell:
                continue
            try:
                value = float(cell)
            except ValueError as exc:
                raise InfoContractError(f"{name} 第 {line_number} 行定数无法解析: {cell!r}") from exc
            if not 0 < value <= MAX_DIFFICULTY:
                raise InfoContractError(f"{name} 第 {line_number} 行定数越界: {cell!r}")


def validate(output_root=OUTPUT_DIR, check_manifest=False):
    info_dir = os.path.join(output_root, INFO_SUBDIR)
    tables = {}
    for name in TABLES:
        tables[name] = _check_table(info_dir, name)

    info_rows, song_ids = tables["info.csv"]
    if len(song_ids) < MIN_SONG_COUNT:
        raise InfoContractError(f"曲目数量异常偏少: {len(song_ids)} < {MIN_SONG_COUNT}")

    for name, (_, ids) in tables.items():
        if set(ids) != set(song_ids):
            missing = sorted(set(song_ids) - set(ids))[:5]
            extra = sorted(set(ids) - set(song_ids))[:5]
            raise InfoContractError(f"{name} 的曲目集合与 info.csv 不一致: 缺 {missing} 多 {extra}")

    _check_difficulties("info.csv", info_rows, 4)
    _check_difficulties("difficulty.csv", tables["difficulty.csv"][0], 1)
    _check_difficulties("difficulty.tsv", tables["difficulty.tsv"][0], 1)

    all_info_path = os.path.join(info_dir, "all_info.json")
    if not os.path.exists(all_info_path):
        raise InfoContractError(f"缺少发布文件: {all_info_path}")
    with open(all_info_path, encoding="utf-8") as f:
        all_info = json.load(f)
    if not isinstance(all_info, dict) or not isinstance(all_info.get("songs"), list):
        raise InfoContractError("all_info.json 结构异常")
    all_info_ids = {sanitize_song_id(_text(song.get("id"))) for song in all_info["songs"]}
    if all_info_ids != set(song_ids):
        raise InfoContractError(
            f"all_info.json 的曲目集合与 info.csv 不一致: "
            f"缺 {sorted(set(song_ids) - all_info_ids)[:5]} 多 {sorted(all_info_ids - set(song_ids))[:5]}"
        )

    version_path = os.path.join(info_dir, "version.txt")
    if not os.path.exists(version_path):
        raise InfoContractError(f"缺少发布文件: {version_path}")
    with open(version_path, encoding="utf-8") as f:
        version_text = f.read().strip()
    if not VERSION_PATTERN.match(version_text):
        raise InfoContractError(f"version.txt 格式异常: {version_text!r}（期望形如 4.0.0 (155)）")

    if check_manifest:
        _check_manifest(info_dir)

    return {
        "songs": len(song_ids),
        "version": version_text,
        "files": sorted(TABLES),
    }


def _check_manifest(info_dir):
    path = os.path.join(info_dir, MANIFEST_NAME)
    if not os.path.exists(path):
        raise InfoContractError(f"缺少 {MANIFEST_NAME}，无法校验发布内容")
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    recorded = manifest.get("files")
    if not isinstance(recorded, dict):
        raise InfoContractError(f"{MANIFEST_NAME} 缺少 files 清单")

    for name, entry in recorded.items():
        full_path = os.path.join(info_dir, name)
        if not os.path.isfile(full_path):
            raise InfoContractError(f"{MANIFEST_NAME} 记录的 {name} 不存在")
        if entry.get("sha256") != _sha256(full_path):
            raise InfoContractError(f"{name} 内容与 {MANIFEST_NAME} 不一致（sha256 不匹配）")

    present = {
        name for name in os.listdir(info_dir)
        if name != MANIFEST_NAME and os.path.isfile(os.path.join(info_dir, name))
    }
    unlisted = sorted(present - set(recorded))
    if unlisted:
        raise InfoContractError(f"{MANIFEST_NAME} 未覆盖已发布文件: {unlisted}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="/info 发布契约生成与校验")
    parser.add_argument("--output-root", default=OUTPUT_DIR, help="发布目录（默认 output）")
    parser.add_argument(
        "--verify-only",
        nargs="?",
        const=OUTPUT_DIR,
        default=None,
        metavar="DIR",
        help="只校验已发布目录（默认 output），不重新生成",
    )
    args = parser.parse_args(argv)

    try:
        if args.verify_only is not None:
            summary = validate(args.verify_only, check_manifest=True)
            print(
                f"--- 校验通过（{args.verify_only}）: songs={summary['songs']} "
                f"version={summary['version']} ---",
                flush=True,
            )
        else:
            summary = export_published_info(args.output_root)
            print(
                f"--- 生成并校验通过: songs={summary['songs']} version={summary['version']} ---",
                flush=True,
            )
    except InfoContractError as exc:
        print(f"!! /info 发布契约校验失败: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
