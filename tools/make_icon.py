"""Erzeugt assets/icon.ico (dunkle Kachel mit grünen Equalizer-Balken).

Bewusst ohne Zusatzpakete gehalten – nur Python-Standardbibliothek.
"""

import os
import struct
import zlib

TILE = (24, 24, 24)      # dunkle Kachel
BAR = (29, 185, 84)      # Spotify-Grün

BAR_HEIGHTS = [0.30, 0.52, 0.74, 0.44, 0.26]
BAR_WIDTH = 0.085
BAR_GAP = 0.052
TILE_MARGIN = 0.02
TILE_RADIUS = 0.22


def _inside_rounded(x, y, cx, cy, hw, hh, r):
    dx = abs(x - cx) - (hw - r)
    dy = abs(y - cy) - (hh - r)
    qx = dx if dx > 0 else 0.0
    qy = dy if dy > 0 else 0.0
    return (qx * qx + qy * qy) <= r * r


def render(size, ss=4):
    """Liefert Liste von Zeilen (bytearray, RGBA) mit Kantenglättung."""
    total = len(BAR_HEIGHTS) * BAR_WIDTH + (len(BAR_HEIGHTS) - 1) * BAR_GAP
    x0 = 0.5 - total / 2
    centers = [x0 + BAR_WIDTH / 2 + i * (BAR_WIDTH + BAR_GAP)
               for i in range(len(BAR_HEIGHTS))]
    n = size * ss
    samples = ss * ss
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            acc_tile = 0
            acc_bar = 0
            for sy in range(ss):
                y = (py * ss + sy + 0.5) / n
                for sx in range(ss):
                    x = (px * ss + sx + 0.5) / n
                    if _inside_rounded(x, y, 0.5, 0.5, 0.5 - TILE_MARGIN,
                                       0.5 - TILE_MARGIN, TILE_RADIUS):
                        acc_tile += 1
                        for cx, h in zip(centers, BAR_HEIGHTS):
                            if _inside_rounded(x, y, cx, 0.5, BAR_WIDTH / 2,
                                               h / 2, BAR_WIDTH / 2):
                                acc_bar += 1
                                break
            if acc_tile == 0:
                row += b"\x00\x00\x00\x00"
            else:
                a_tile = acc_tile / samples
                f_bar = acc_bar / acc_tile
                r = int(BAR[0] * f_bar + TILE[0] * (1 - f_bar) + 0.5)
                g = int(BAR[1] * f_bar + TILE[1] * (1 - f_bar) + 0.5)
                b = int(BAR[2] * f_bar + TILE[2] * (1 - f_bar) + 0.5)
                row += bytes((r, g, b, int(a_tile * 255 + 0.5)))
        rows.append(row)
    return rows


def to_png(size, rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def to_bmp(size, rows):
    """32-Bit-BMP-DIB (für kleine Icon-Größen im ICO-Container)."""
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         size * size * 4, 0, 0, 0, 0)
    pixels = bytearray()
    for row in reversed(rows):
        for i in range(0, len(row), 4):
            r, g, b, a = row[i], row[i + 1], row[i + 2], row[i + 3]
            pixels += bytes((b, g, r, a))
    mask_stride = ((size + 31) // 32) * 4
    mask = b"\x00" * (mask_stride * size)
    return header + bytes(pixels) + mask


def build_ico(images):
    """images: Liste von (size, daten_bytes)."""
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for size, data in images:
        dim = size if size < 256 else 0
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                               len(data), offset)
        offset += len(data)
    return out + entries + b"".join(d for _, d in images)


GLYPH_COLOR = (255, 255, 255)
DISC_COLOR = (28, 28, 28)      # dunkle Scheibe hinter dem Symbol (Kontrast)
DISC_RADIUS = 0.50


def _glyph_play(x, y):
    return 0.28 <= x <= 0.82 and abs(y - 0.5) <= (0.82 - x) / 0.54 * 0.30


def _glyph_pause(x, y):
    return 0.22 <= y <= 0.78 and (0.30 <= x <= 0.44 or 0.56 <= x <= 0.70)


def _glyph_prev(x, y):
    if 0.20 <= x <= 0.31 and 0.26 <= y <= 0.74:
        return True
    return 0.36 <= x <= 0.80 and abs(y - 0.5) <= (x - 0.36) / 0.44 * 0.26


def _glyph_next(x, y):
    return _glyph_prev(1.0 - x, y)


def render_glyph(size, inside, ss=6):
    """Weißes Symbol auf dunkler Kreisscheibe (kontrastreich auf jedem
    Vorschaufenster-Hintergrund der Taskleiste)."""
    n = size * ss
    samples = ss * ss
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            acc_disc = 0
            acc_glyph = 0
            for sy in range(ss):
                y = (py * ss + sy + 0.5) / n
                for sx in range(ss):
                    x = (px * ss + sx + 0.5) / n
                    dx, dy = x - 0.5, y - 0.5
                    if dx * dx + dy * dy <= DISC_RADIUS * DISC_RADIUS:
                        acc_disc += 1
                        if inside(x, y):
                            acc_glyph += 1
            if acc_disc == 0:
                row += b"\x00\x00\x00\x00"
                continue
            a_disc = acc_disc / samples
            f_glyph = acc_glyph / acc_disc
            r = int(GLYPH_COLOR[0] * f_glyph + DISC_COLOR[0] * (1 - f_glyph) + 0.5)
            g = int(GLYPH_COLOR[1] * f_glyph + DISC_COLOR[1] * (1 - f_glyph) + 0.5)
            b = int(GLYPH_COLOR[2] * f_glyph + DISC_COLOR[2] * (1 - f_glyph) + 0.5)
            row += bytes((r, g, b, int(a_disc * 255 + 0.5)))
        rows.append(row)
    return rows


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "assets")
    os.makedirs(out_dir, exist_ok=True)
    images = [(256, to_png(256, render(256)))]
    for size in (48, 32, 16):
        images.append((size, to_bmp(size, render(size, ss=6))))
    out_path = os.path.join(out_dir, "icon.ico")
    with open(out_path, "wb") as fh:
        fh.write(build_ico(images))
    print("Icon geschrieben:", out_path)

    glyphs = {"tb_play.ico": _glyph_play, "tb_pause.ico": _glyph_pause,
              "tb_prev.ico": _glyph_prev, "tb_next.ico": _glyph_next}
    for name, fn in glyphs.items():
        entries = [(s, to_bmp(s, render_glyph(s, fn))) for s in (32, 24, 16)]
        path = os.path.join(out_dir, name)
        with open(path, "wb") as fh:
            fh.write(build_ico(entries))
        print("Icon geschrieben:", path)


if __name__ == "__main__":
    main()
