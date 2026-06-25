"""構造化 JSON → 白黒間取り図 SVG を生成する。"""
from __future__ import annotations

SIZE = 800


def _n(v: float) -> float:
    return v / 100 * SIZE


def _pt(xy: list) -> str:
    return f"{_n(xy[0]):.1f},{_n(xy[1]):.1f}"


def _equipment(eq: dict) -> str:
    x, y = _n(eq["x"]), _n(eq["y"])
    w, h = _n(eq["w"]), _n(eq["h"])
    cx, cy = x + w / 2, y + h / 2
    rot = eq.get("rot", 0)
    tf = f' transform="rotate({rot},{cx:.1f},{cy:.1f})"' if rot else ""
    t = eq.get("type", "")

    if t == "toilet":
        return (
            f'<g{tf}>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" fill="white" stroke="black" stroke-width="1.5"/>'
            f'<ellipse cx="{cx:.1f}" cy="{y+h*0.65:.1f}" rx="{w*0.38:.1f}" ry="{h*0.28:.1f}" fill="white" stroke="black" stroke-width="1.2"/>'
            f'<rect x="{x+w*0.1:.1f}" y="{y+h*0.05:.1f}" width="{w*0.8:.1f}" height="{h*0.22:.1f}" rx="2" fill="white" stroke="black" stroke-width="1"/>'
            f'</g>'
        )
    if t == "bath":
        return (
            f'<g{tf}>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="3" fill="white" stroke="black" stroke-width="1.5"/>'
            f'<ellipse cx="{cx:.1f}" cy="{cy+h*0.08:.1f}" rx="{w*0.37:.1f}" ry="{h*0.33:.1f}" fill="white" stroke="black" stroke-width="1.2"/>'
            f'<rect x="{x+w*0.1:.1f}" y="{y+h*0.05:.1f}" width="{w*0.8:.1f}" height="{h*0.1:.1f}" rx="1" fill="#ccc" stroke="black" stroke-width="0.8"/>'
            f'</g>'
        )
    if t == "sink":
        r = min(w, h) * 0.32
        return (
            f'<g{tf}>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" fill="white" stroke="black" stroke-width="1.5"/>'
            f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{r:.1f}" ry="{r:.1f}" fill="white" stroke="black" stroke-width="1.2"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{min(w,h)*0.07:.1f}" fill="black"/>'
            f'</g>'
        )
    if t == "kitchen_sink":
        pw = w * 0.43
        ph = h * 0.76
        return (
            f'<g{tf}>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="white" stroke="black" stroke-width="1.5"/>'
            f'<rect x="{x+w*0.05:.1f}" y="{y+h*0.12:.1f}" width="{pw:.1f}" height="{ph:.1f}" rx="2" fill="white" stroke="black" stroke-width="1"/>'
            f'<rect x="{x+w*0.52:.1f}" y="{y+h*0.12:.1f}" width="{pw:.1f}" height="{ph:.1f}" rx="2" fill="white" stroke="black" stroke-width="1"/>'
            f'</g>'
        )
    if t == "stove":
        r = min(w, h) * 0.15
        return (
            f'<g{tf}>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="white" stroke="black" stroke-width="1.5"/>'
            f'<circle cx="{x+w*0.27:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="white" stroke="black" stroke-width="1"/>'
            f'<circle cx="{x+w*0.73:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="white" stroke="black" stroke-width="1"/>'
            f'<circle cx="{cx:.1f}" cy="{y+h*0.28:.1f}" r="{r*0.8:.1f}" fill="white" stroke="black" stroke-width="1"/>'
            f'</g>'
        )
    if t == "washing_machine":
        r = min(w, h) * 0.33
        return (
            f'<g{tf}>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" fill="white" stroke="black" stroke-width="1.5"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="white" stroke="black" stroke-width="1.2"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r*0.3:.1f}" fill="#ddd" stroke="black" stroke-width="0.8"/>'
            f'</g>'
        )
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="white" stroke="black" stroke-width="1.2"{tf}/>'


def _door(d: dict) -> str:
    x, y = _n(d["x"]), _n(d["y"])
    w = _n(d["w"])
    rot = d.get("rot", 0)
    swing = d.get("swing", "left")
    tf = f'rotate({rot},{x:.1f},{y:.1f})'
    if swing == "right":
        arc = f'<path d="M {x+w:.1f} {y:.1f} A {w:.1f} {w:.1f} 0 0 1 {x:.1f} {y+w:.1f}" fill="none" stroke="black" stroke-width="1" stroke-dasharray="4,2"/>'
    else:
        arc = f'<path d="M {x:.1f} {y:.1f} A {w:.1f} {w:.1f} 0 0 0 {x+w:.1f} {y+w:.1f}" fill="none" stroke="black" stroke-width="1" stroke-dasharray="4,2"/>'
    line = f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+w:.1f}" y2="{y:.1f}" stroke="black" stroke-width="2"/>'
    return f'<g transform="{tf}">{line}{arc}</g>'


def _window(win: dict) -> str:
    x, y = _n(win["x"]), _n(win["y"])
    w = _n(win["w"])
    rot = win.get("rot", 0)
    tf = f' transform="rotate({rot},{x:.1f},{y:.1f})"' if rot else ""
    g = 2.5
    return (
        f'<g{tf}>'
        f'<line x1="{x:.1f}" y1="{y-g:.1f}" x2="{x+w:.1f}" y2="{y-g:.1f}" stroke="black" stroke-width="1"/>'
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+w:.1f}" y2="{y:.1f}" stroke="black" stroke-width="3"/>'
        f'<line x1="{x:.1f}" y1="{y+g:.1f}" x2="{x+w:.1f}" y2="{y+g:.1f}" stroke="black" stroke-width="1"/>'
        f'</g>'
    )


def _compass(cx: float, cy: float) -> str:
    r = 18
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="white" stroke="black" stroke-width="1.5"/>'
        f'<polygon points="{cx:.1f},{cy-r+3:.1f} {cx-5:.1f},{cy+4:.1f} {cx+5:.1f},{cy+4:.1f}" fill="black"/>'
        f'<text x="{cx:.1f}" y="{cy+r-4:.1f}" text-anchor="middle" '
        f'font-size="10" font-weight="bold" fill="black">N</text>'
    )


def render_svg(data: dict) -> str:
    parts: list[str] = []

    parts.append(f'<rect width="{SIZE}" height="{SIZE}" fill="white"/>')

    # 外形（外壁の内側を白塗り）
    outer = data.get("outer_polygon", [])
    if outer:
        pts = " ".join(_pt(p) for p in outer)
        parts.append(f'<polygon points="{pts}" fill="white" stroke="none"/>')

    # 部屋ラベル
    for room in data.get("rooms", []):
        rx, ry = _n(room["x"]), _n(room["y"])
        rw, rh = _n(room["w"]), _n(room["h"])
        cx, cy = rx + rw / 2, ry + rh / 2
        name = room.get("name", "")
        size = room.get("size", "")
        fs = 10 if len(name) > 7 else (12 if len(name) > 4 else 14)
        parts.append(
            f'<text x="{cx:.1f}" y="{cy - (6 if size else 0):.1f}" text-anchor="middle" '
            f'font-size="{fs}" font-weight="bold" fill="black">{name}</text>'
        )
        if size:
            parts.append(
                f'<text x="{cx:.1f}" y="{cy+12:.1f}" text-anchor="middle" '
                f'font-size="11" fill="#222">{size}</text>'
            )

    # 柱（黒塗り）— 壁より前に描く
    for p in data.get("pillars", []):
        parts.append(
            f'<rect x="{_n(p["x"]):.1f}" y="{_n(p["y"]):.1f}" '
            f'width="{_n(p["w"]):.1f}" height="{_n(p["h"]):.1f}" fill="black"/>'
        )

    # 窓
    for win in data.get("windows", []):
        parts.append(_window(win))

    # 外壁
    if outer:
        pts = " ".join(_pt(p) for p in outer)
        parts.append(
            f'<polygon points="{pts}" fill="none" stroke="black" stroke-width="5" stroke-linejoin="miter"/>'
        )

    # 内壁
    for wall in data.get("inner_walls", []):
        f = wall["from"]
        t = wall["to"]
        parts.append(
            f'<line x1="{_n(f[0]):.1f}" y1="{_n(f[1]):.1f}" '
            f'x2="{_n(t[0]):.1f}" y2="{_n(t[1]):.1f}" '
            f'stroke="black" stroke-width="2.5" stroke-linecap="square"/>'
        )

    # 設備
    for eq in data.get("equipment", []):
        parts.append(_equipment(eq))

    # ドア
    for door in data.get("doors", []):
        parts.append(_door(door))

    # ラベル（PS・MB等）
    for lbl in data.get("labels", []):
        parts.append(
            f'<text x="{_n(lbl["x"]):.1f}" y="{_n(lbl["y"]):.1f}" text-anchor="middle" '
            f'font-size="9" fill="black">{lbl["text"]}</text>'
        )

    # 方位磁針
    comp = data.get("compass", {"x": 92, "y": 92})
    parts.append(_compass(_n(comp["x"]), _n(comp["y"])))

    font = "'Noto Sans JP','Yu Gothic','Hiragino Kaku Gothic ProN',sans-serif"
    inner = "\n  ".join(parts)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" viewBox="0 0 {SIZE} {SIZE}">
  <defs>
    <style>text {{ font-family: {font}; }}</style>
  </defs>
  {inner}
</svg>"""
