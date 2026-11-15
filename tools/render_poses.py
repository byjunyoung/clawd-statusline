#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README에 넣을 포즈 그림을 만든다.

포즈 표를 손으로 옮겨 적지 않고 statusline-clawd.py에서 그대로 읽는다. 포즈가 바뀌면
그림도 같이 바뀌어야 하는데, 손으로 그리면 예전 판이 README에 남는다. 실제로 그랬다.

    python3 tools/render_poses.py            # docs/poses.html
    <chrome> --headless --screenshot=docs/poses.png --window-size=W,H docs/poses.html
"""
import importlib.util
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location(
    "sl", os.path.join(ROOT, "scripts", "statusline-clawd.py"))
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)

# 사분면 문자 -> 켜진 칸 (좌상, 우상, 좌하, 우하)
QUAD = {
    " ": (0, 0, 0, 0), "█": (1, 1, 1, 1),
    "▘": (1, 0, 0, 0), "▝": (0, 1, 0, 0), "▖": (0, 0, 1, 0), "▗": (0, 0, 0, 1),
    "▀": (1, 1, 0, 0), "▄": (0, 0, 1, 1), "▌": (1, 0, 1, 0), "▐": (0, 1, 0, 1),
    "▚": (1, 0, 0, 1), "▞": (0, 1, 1, 0),
    "▙": (1, 0, 1, 1), "▛": (1, 1, 1, 0), "▜": (1, 1, 0, 1), "▟": (0, 1, 1, 1),
}

BODY = "#d77757"
EYE = "#000000"
PAGE = "#1c1917"
PX = 9        # 사분면 한 칸의 화면 픽셀
CELL = PX * 2


def cells(pose):
    """포즈 한 개를 (문자, 바탕) 격자로 편다. render()의 행 구성 그대로.

    바탕은 None(없음), "eye"(검정 위에 몸통색), "lid"(몸통색 위에 검은 눈꺼풀 선).
    """
    eyes, arms, feet = sl.POSES[pose]
    arms = sl.ARMS[arms]
    face = [(ch, "lid" if lid else "eye") for glyphs, lid in sl.EYES[eyes] for ch in glyphs]
    rows = [(arms["r1L"], face, arms["r1R"]),
            (arms["r2L"], [(ch, "eye") for ch in sl.BODY], arms["r2R"]),
            ("", [(ch, None) for ch in sl.FEET[feet]], "")]   # 발 줄은 검은 배경을 깔지 않는다
    out = []
    for left, mid, right in rows:
        line = [(ch, None) for ch in left] + mid + [(ch, None) for ch in right]
        line += [(" ", None)] * max(0, sl.WIDTH - len(line))
        out.append(line)
    return out


def tile(pose):
    parts = []
    for r, line in enumerate(cells(pose)):
        for c, (ch, ground) in enumerate(line):
            x, y = c * CELL, r * CELL
            if ground:
                parts.append(
                    '<i style="left:%dpx;top:%dpx;width:%dpx;height:%dpx;background:%s"></i>'
                    % (x, y, CELL, CELL, BODY if ground == "lid" else EYE))
            if ground == "lid":      # ▂: 칸 아래 4분의 1만 검게
                parts.append(
                    '<i style="left:%dpx;top:%dpx;width:%dpx;height:%dpx;background:%s"></i>'
                    % (x, y + CELL - CELL // 4, CELL, CELL // 4, EYE))
                continue
            on = QUAD.get(ch, (0, 0, 0, 0))
            for q, lit in enumerate(on):
                if not lit:
                    continue
                parts.append(
                    '<i style="left:%dpx;top:%dpx;width:%dpx;height:%dpx;background:%s"></i>'
                    % (x + (q % 2) * PX, y + (q // 2) * PX, PX, PX, BODY))
    return "".join(parts)


DESC = {"default": "idle", "look-left": "looking left",
        "look-right": "looking right", "arms-up": "arms up",
        "closed": "blink", "wink": "reply done", "closed-arms-up": "sneeze",
        "step-left": "tapping", "step-right": "tapping"}

CSS = """
body{margin:0;background:%s;font:600 15px/1.4 -apple-system,BlinkMacSystemFont,sans-serif;
     color:#e7e5e4;display:flex;gap:26px;padding:34px;align-items:flex-start}
.pose{width:%dpx;min-width:210px;white-space:nowrap}
.art{position:relative;height:%dpx;margin-bottom:18px}
.art i{position:absolute}
.d{color:#a8a29e;font-weight:400}
.note{color:#78716c;font-weight:400;font-size:13px;padding:34px 0 0;max-width:200px}
""" % (PAGE, sl.WIDTH * CELL, 3 * CELL)


def html():
    tiles = []
    for pose in sl.POSES:
        tiles.append('<div class="pose"><div class="art">%s</div>%s <span class="d">%s</span></div>'
                     % (tile(pose), pose, DESC.get(pose, "")))
    note = ('<div class="note">Anthropic drew all of these.<br>Nothing here is ours.</div>')
    return "<!doctype html><meta charset=utf-8><style>%s</style>%s%s" % (
        CSS, "".join(tiles), note)


if __name__ == "__main__":
    out = os.path.join(ROOT, "docs", "poses.html")
    io.open(out, "w", encoding="utf-8").write(html())
    print(out)
    print("size: %d x %d" % (34 * 2 + len(sl.POSES) * (210 + 26) + 160, 34 * 2 + 3 * CELL + 34))
