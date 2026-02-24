import os
from io import BytesIO
from typing import Callable, Iterable, Iterator, Sequence

from PIL import Image

DEFAULT_IMAGE_FORMATS: tuple[str, ...] = ("png", "webp")
SUPPORTED_FORMATS: tuple[str, ...] = ("png", "webp", "jpeg", "avif")
FORMAT_ALIASES: dict[str, str] = {
    "jpg": "jpeg",
    "jpe": "jpeg",
}
PIL_SAVE_FORMAT: dict[str, str] = {
    "png": "PNG",
    "webp": "WEBP",
    "jpeg": "JPEG",
    "avif": "AVIF",
}
FILE_EXTENSION: dict[str, str] = {
    "png": "png",
    "webp": "webp",
    "jpeg": "jpg",
    "avif": "avif",
}


def normalize_format_token(token: str) -> str:
    normalized = (token or "").strip().lower()
    return FORMAT_ALIASES.get(normalized, normalized)


def parse_requested_formats(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    tokens: list[str] = []
    for chunk in raw_value.replace(";", ",").replace(" ", ",").split(","):
        fmt = normalize_format_token(chunk)
        if fmt and fmt not in tokens:
            tokens.append(fmt)
    return tokens


def is_format_save_supported(fmt: str) -> bool:
    pil_format = PIL_SAVE_FORMAT.get(fmt)
    if not pil_format:
        return False
    Image.init()
    return pil_format in Image.SAVE


def resolve_export_formats(
    raw_formats: str | None = None,
    default_formats: Sequence[str] = DEFAULT_IMAGE_FORMATS,
    support_checker: Callable[[str], bool] | None = None,
    logger: Callable[[str], None] | None = print,
) -> list[str]:
    requested = parse_requested_formats(raw_formats if raw_formats is not None else os.environ.get("RESOURCE_IMAGE_FORMATS"))
    if not requested:
        requested = [normalize_format_token(x) for x in default_formats if normalize_format_token(x)]

    # 强制保留 png，避免破坏既有直链约定。
    if "png" not in requested:
        requested.insert(0, "png")

    checker = support_checker or is_format_save_supported
    resolved: list[str] = []

    for fmt in requested:
        if fmt not in SUPPORTED_FORMATS:
            if logger:
                logger(f"[image_export] 忽略未知图片格式: {fmt}")
            continue
        if checker(fmt):
            if fmt not in resolved:
                resolved.append(fmt)
        else:
            if logger:
                logger(f"[image_export] 当前环境不支持 {fmt} 编码，已自动跳过。")

    if not resolved:
        resolved = ["png"]
        if logger:
            logger("[image_export] 未找到可用格式，已回退为 png。")

    if "png" not in resolved:
        resolved.insert(0, "png")
    return resolved


def _get_quality_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, min(100, value))


def _get_save_kwargs(fmt: str) -> dict[str, int]:
    if fmt == "webp":
        return {
            "quality": _get_quality_from_env("RESOURCE_WEBP_QUALITY", 85),
            "method": 6,
        }
    if fmt == "jpeg":
        return {
            "quality": _get_quality_from_env("RESOURCE_JPEG_QUALITY", 90),
            "subsampling": 0,
        }
    if fmt == "avif":
        return {
            "quality": _get_quality_from_env("RESOURCE_AVIF_QUALITY", 60),
        }
    return {}


def _prepare_image_for_format(image: Image.Image, fmt: str) -> Image.Image:
    if fmt == "jpeg":
        # JPEG 不支持透明通道，统一铺白底后写入。
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image


def iter_image_variant_payloads(
    image: Image.Image,
    base_relative_path_no_ext: str,
    export_formats: Iterable[str],
    logger: Callable[[str], None] | None = print,
) -> Iterator[tuple[str, BytesIO]]:
    for fmt in export_formats:
        normalized = normalize_format_token(fmt)
        pil_format = PIL_SAVE_FORMAT.get(normalized)
        extension = FILE_EXTENSION.get(normalized)
        if not pil_format or not extension:
            if logger:
                logger(f"[image_export] 跳过未知格式: {fmt}")
            continue

        output = BytesIO()
        target_path = f"{base_relative_path_no_ext}.{extension}"
        try:
            prepared = _prepare_image_for_format(image, normalized)
            prepared.save(output, pil_format, **_get_save_kwargs(normalized))
            output.seek(0)
            yield target_path, output
        except Exception as exc:
            if logger:
                logger(f"[image_export] 编码失败 {target_path}: {exc}")
