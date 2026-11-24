"""Bounded RIFF/WebP inspection and WhatsApp pack metadata."""
import json
import struct
from pathlib import Path

MAX_INPUT = 256 * 1024 * 1024
PACK_PREFIX = bytes.fromhex("49492a0008000000010041570700")
KNOWN = {"VP8X", "VP8 ", "VP8L", "ALPH", "ICCP", "ANIM", "ANMF", "EXIF", "XMP "}


def chunks(data):
    offset = 0
    while offset < len(data):
        if len(data) - offset < 8:
            raise ValueError("Cabecera RIFF truncada")
        name = bytes(data[offset:offset + 4]).decode("ascii", "replace")
        size = struct.unpack_from("<I", data, offset + 4)[0]
        start = offset + 8
        end = start + size
        offset = end + (size & 1)
        if offset > len(data):
            raise ValueError("Bloque RIFF truncado")
        yield name, data[start:end]


def container(data):
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("Se esperaba RIFF/WebP")
    end = 8 + struct.unpack_from("<I", data, 4)[0]
    if end < 12 or end > len(data):
        raise ValueError("Longitud RIFF inválida")
    return list(chunks(memoryview(data)[12:end])), len(data) - end


def u24(data, offset):
    return int.from_bytes(data[offset:offset + 3], "little")


def size_of(name, data):
    if name == "VP8 " and len(data) >= 10 and data[3:6] == b"\x9d\x01\x2a":
        width, height = struct.unpack_from("<HH", data, 6)
        return width & 16383, height & 16383
    if name == "VP8L" and len(data) >= 5 and data[0] == 47:
        bits = struct.unpack_from("<I", data, 1)[0]
        return (bits & 16383) + 1, ((bits >> 14) & 16383) + 1
    raise ValueError("Cabecera VP8/VP8L inválida")


def pack_info(data):
    endian = {b"II": "<", b"MM": ">"}.get(bytes(data[:2]))
    if endian is None or len(data) < 8:
        return None
    marker, directory = struct.unpack_from(endian + "HI", data, 2)
    if marker != 42 or directory < 8 or directory + 2 > len(data):
        return None
    count = struct.unpack_from(endian + "H", data, directory)[0]
    for entry in range(directory + 2, min(directory + 2 + count * 12, len(data) - 11), 12):
        tag, kind, length, start = struct.unpack_from(endian + "HHII", data, entry)
        if tag != 0x5741 or kind != 7 or length <= 4:
            continue
        if start < entry + 12 or start + length > len(data):
            return None
        try:
            value = json.loads(bytes(data[start:start + length]))
            return value if isinstance(value, dict) else None
        except (ValueError, UnicodeError, RecursionError):
            return None
    return None


def inspect(data):
    blocks, trailing = container(data)
    width = height = flags = 0
    frames = []
    encodings = set()
    loop = metadata = None
    for name, payload in blocks:
        if name == "VP8X":
            if len(payload) != 10:
                raise ValueError("VP8X inválido")
            flags = payload[0]
            width, height = u24(payload, 4) + 1, u24(payload, 7) + 1
        elif name == "ANIM":
            if len(payload) != 6:
                raise ValueError("ANIM inválido")
            loop = struct.unpack_from("<H", payload, 4)[0]
        elif name == "ANMF":
            if len(payload) < 16:
                raise ValueError("ANMF inválido")
            frame_blocks = list(chunks(payload[16:]))
            codecs = [kind for kind, part in frame_blocks if kind in {"VP8 ", "VP8L"} and size_of(kind, part)]
            if len(codecs) != 1:
                raise ValueError("ANMF sin un único fotograma VP8/VP8L")
            encodings.update(codecs)
            frames.append(dict(x=2*u24(payload, 0), y=2*u24(payload, 3),
                               width=u24(payload, 6)+1, height=u24(payload, 9)+1,
                               ms=u24(payload, 12), flags=payload[15],
                               chunks=[kind for kind, _ in frame_blocks]))
        elif name in {"VP8 ", "VP8L"}:
            image_size = size_of(name, payload)
            if width == 0:
                width, height = image_size
            encodings.add(name)
        elif name == "EXIF":
            metadata = pack_info(payload)
    if not width or not height or not encodings:
        raise ValueError("WebP sin imagen")
    if frames and (loop is None or not flags & 2):
        raise ValueError("Animación sin cabecera ANIM/VP8X")
    if any(f["x"]+f["width"] > width or f["y"]+f["height"] > height for f in frames):
        raise ValueError("Fotograma fuera del lienzo")
    return dict(width=width, height=height, flags=flags, bytes=len(data), frames=frames,
                frame_count=len(frames) or 1, duration_ms=sum(f["ms"] for f in frames),
                animated=bool(frames), codecs=sorted(encodings), loop=loop, pack=metadata,
                chunks=[dict(type=k, bytes=len(p)) for k, p in blocks],
                unknown_chunks=sorted({k for k, _ in blocks if k not in KNOWN}),
                trailing_bytes=trailing)


def read(path):
    with Path(path).open("rb") as file:
        data = file.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise ValueError("WebP supera 256 MiB")
    return inspect(data)


def add_pack(data, metadata):
    report = inspect(data)
    blocks, _ = container(data)
    payload = json.dumps(metadata, ensure_ascii=False).encode()
    exif = PACK_PREFIX + struct.pack("<III", len(payload), 26, 0) + payload
    extended = next((bytes(p) for k, p in blocks if k == "VP8X"), None)
    if extended is None:
        alpha = any(k == "VP8L" and p[4] & 16 for k, p in blocks)
        extended = bytes([16 if alpha else 0, 0, 0, 0])
        extended += (report["width"] - 1).to_bytes(3, "little")
        extended += (report["height"] - 1).to_bytes(3, "little")
    extended = bytes([extended[0] | 8]) + extended[1:]
    body = b"WEBP"
    blocks = [("VP8X", extended), *((k, p) for k, p in blocks if k not in {"VP8X", "EXIF"})]
    position = next((i for i, (k, _) in enumerate(blocks) if k == "XMP "), len(blocks))
    blocks.insert(position, ("EXIF", exif))
    parts = [body]
    for name, payload in blocks:
        parts.extend((name.encode("ascii"), struct.pack("<I", len(payload)),
                      bytes(payload), b"\x00" if len(payload) % 2 else b""))
    body = b"".join(parts)
    return b"RIFF" + struct.pack("<I", len(body)) + body
