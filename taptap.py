"""从 TapTap 自动拉取 Phigros 最新版 APK 下载信息。"""
import hashlib
import json
import random
import string
import time
import urllib.parse
import uuid
from http.client import HTTPSConnection

SAMPLE = string.ascii_lowercase + string.digits
PHIGROS_APP_ID = 165287


def _build_ua(uid):
    return (
        f"V=1&PN=TapTap&VN=2.40.1-rel.100000&VN_CODE=240011000"
        f"&LOC=CN&LANG=zh_CN&CH=default&UID={uid}"
        f"&NT=1&SR=1080x2030&DEB=Xiaomi&DEM=Redmi+Note+5&OSV=9"
    )


def _api_get(host, path, headers=None):
    """封装 GET 请求，含容错输出。"""
    import sys
    conn = HTTPSConnection(host, timeout=15)
    conn.request("GET", path, headers=headers or {})
    resp = conn.getresponse()
    body = resp.read().decode()
    if resp.status != 200:
        print(f"[taptap] GET {host}{path} → HTTP {resp.status}", file=sys.stderr)
        print(f"[taptap] body: {body[:300]}", file=sys.stderr)
        raise RuntimeError(f"HTTP {resp.status}")
    return json.loads(body)


def _api_post(host, path, body, headers=None):
    """封装 POST 请求，含容错输出。"""
    import sys
    conn = HTTPSConnection(host, timeout=15)
    conn.request("POST", path, body=body.encode(), headers=headers or {})
    resp = conn.getresponse()
    resp_body = resp.read().decode()
    if resp.status != 200:
        print(f"[taptap] POST {host}{path} → HTTP {resp.status}", file=sys.stderr)
        print(f"[taptap] body: {resp_body[:300]}", file=sys.stderr)
        raise RuntimeError(f"HTTP {resp.status}")
    return json.loads(resp_body)


def get_latest_apk(app_id=PHIGROS_APP_ID):
    """返回最新 APK 的下载信息 dict。"""
    uid = uuid.uuid4()
    x_ua = _build_ua(uid)
    host = "api.taptapdada.com"
    headers = {"User-Agent": "okhttp/3.12.1"}

    # 第一步：获取游戏详情 → 拿到 apk_id
    path1 = f"/app/v2/detail-by-id/{app_id}?X-UA={urllib.parse.quote(x_ua)}"
    detail = _api_get(host, path1, headers)
    apk_id = detail["data"]["download"]["apk_id"]

    # 第二步：获取 APK 具体信息（含下载链接）
    nonce = "".join(random.sample(SAMPLE, 5))
    t = int(time.time())
    param = (
        f"abi=arm64-v8a,armeabi-v7a,armeabi"
        f"&id={apk_id}&node={uid}&nonce={nonce}"
        f"&sandbox=1&screen_densities=xhdpi&time={t}"
    )
    sign_data = f"X-UA={x_ua}&{param}PeCkE6Fu0B10Vm9BKfPfANwCUAn5POcs"
    sign = hashlib.md5(sign_data.encode()).hexdigest()
    post_body = f"{param}&sign={sign}"

    path2 = f"/apk/v1/detail?X-UA={urllib.parse.quote(x_ua)}"
    post_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "okhttp/3.12.1",
    }
    apk_info = _api_post(host, path2, post_body, post_headers)

    data = apk_info["data"]
    apk = data["apk"]
    download_url = data.get("download_url") or data.get("url") or ""

    return {
        "download_url": download_url,
        "version_name": apk.get("version_name", ""),
        "version_code": str(apk.get("version_code", "")),
        "size": apk.get("size", 0),
        "md5": apk.get("md5", ""),
    }


if __name__ == "__main__":
    info = get_latest_apk()
    # 输出为 JSON 供 CNB 管线解析
    print(json.dumps(info, ensure_ascii=False, indent=2))

    # 同时输出 CNB 可识别的环境变量格式
    if info["download_url"]:
        print(f"##[set-output APK_DOWNLOAD_URL={info['download_url']}]")
    print(f"##[set-output VERSION_NAME={info['version_name']}]")
    print(f"##[set-output VERSION_CODE={info['version_code']}]")
