"""为 PhigrosLabs/PhiInfo 补上 format 45（ETC2_RGB）解码。

上游尚未支持该格式，遇到 ETC2_RGB 贴图会抛 NotSupportedException。
补丁按锚点插入，幂等：上游自行修复后本脚本自动跳过。
"""
import codecs
import re
import sys

CASE_45_BLOCK = """{indent}case 45:
{indent}{{
{indent}    EtcDecoder.DecompressETC2<ColorBGRA<byte>, byte>(
{indent}        bytes, raw.Width, raw.Height, out var data);
{indent}    img = Image.LoadPixelData<Bgra32>(data, raw.Width, raw.Height);
{indent}    break;
{indent}}}

"""


def patch_source(source):
    if re.search(r"(?m)^\s*case\s+45\s*:", source):
        return source
    anchor = re.search(r"(?m)^([ \t]*)case\s+47\s*:", source)
    if anchor is None:
        raise ValueError("未找到 case 47 锚点，上游源码结构已变化")
    block = CASE_45_BLOCK.format(indent=anchor.group(1))
    return source[: anchor.start()] + block + source[anchor.start() :]


def patch_file(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig")
    patched = patch_source(text)
    if patched == text:
        print(f"already supports format 45, skip: {path}")
        return False
    data = patched.encode("utf-8")
    if raw.startswith(codecs.BOM_UTF8):
        data = codecs.BOM_UTF8 + data
    with open(path, "wb") as f:
        f.write(data)
    print(f"patched format 45 decoder: {path}")
    return True


def main(argv):
    if len(argv) != 2:
        print("usage: patch_phiinfo.py <PhiInfoDecoders.cs>", file=sys.stderr)
        return 2
    try:
        patch_file(argv[1])
    except (OSError, ValueError) as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
