# -*- coding: utf-8 -*-
"""Clawd가 걸치는 것들. 레벨이 오르면 걸칠 것이 늘어난다.

Clawd 본체는 시즌 1 그대로다. 여기서는 머리 위에 한 행을 얹고 발 옆에 한 칸을
덧붙일 뿐이다. 원본은 건드리지 않는다.

손에 드는 물건도 만들어 봤지만 뺐다. 한 글자짜리 물건은 머그인지 횃불인지
구분이 안 가고 몸에 붙은 혹으로 보인다. 실루엣이 바뀌는 모자만 남긴다.

그림은 2행짜리 픽셀 격자를 사분면 블록 한 행으로 접어 만든다. 문자 셀 하나가
2x2 픽셀이라 위 절반은 위로 솟고 아래 절반은 머리에 닿는다.
"""

WIDTH = 9

_Q = {
    (0, 0, 0, 0): " ", (1, 0, 0, 0): "▘", (0, 1, 0, 0): "▝", (0, 0, 1, 0): "▖",
    (0, 0, 0, 1): "▗", (1, 1, 0, 0): "▀", (0, 0, 1, 1): "▄", (1, 0, 1, 0): "▌",
    (0, 1, 0, 1): "▐", (1, 0, 0, 1): "▚", (0, 1, 1, 0): "▞", (1, 1, 1, 0): "▛",
    (1, 1, 0, 1): "▜", (1, 0, 1, 1): "▙", (0, 1, 1, 1): "▟", (1, 1, 1, 1): "█",
}


def fold(art, width=WIDTH):
    """'#'로 그린 2행 픽셀 그림을 사분면 블록 한 행으로 접는다."""
    rows = art.split("\n")
    while len(rows) < 2:
        rows.append("")
    cols = width * 2
    top, bottom = (r.ljust(cols)[:cols] for r in rows[:2])
    out = "".join(
        _Q[(top[x] == "#", top[x + 1] == "#", bottom[x] == "#", bottom[x + 1] == "#")]
        for x in range(0, cols, 2)
    )
    return out.rstrip().ljust(width)


# --- 모자. 레벨로 해금한다 --------------------------------------------------
# 아래 절반이 머리에 닿고 위 절반이 솟는다. 머리는 대략 2~15번 픽셀 열에 있다.
# (필요 레벨, 그림, 색, 트루컬러 아닐 때 색). 몸과 같은 색이면 혹으로 보인다.
HATS = {
    "none":  (1,  "", None, None),
    "cap":   (5,  "\n.....########...", (92, 148, 214),  "\033[94m"),
    "horn":  (12, "....#......#....\n....#......#....", (236, 228, 206), "\033[97m"),
    "leaf":  (20, ".......##.......\n.......###......", (118, 196, 106), "\033[92m"),
    "cone":  (30, "........##......\n......######....", (236, 196, 84), "\033[93m"),
    "top":   (40, ".....######.....\n...##########...", (78, 80, 96),  "\033[90m"),
    "crown": (50, "....#.#.#.#.#...\n....##########..", (240, 190, 66), "\033[33m"),
    "halo":  (65, "....##.####.##..\n................", (250, 240, 176), "\033[93m"),
}

# --- 친구. 발 옆에 한 칸. 스탯 칭호로만 열린다 ------------------------------
# 레벨로는 못 얻는다. 그렇게 일해야 따라온다.
FRIENDS = {
    "none":  (None, "", None, None),
    "bat":   ("OWL", "#.#\n.#.", (146, 130, 200), "\033[95m"),        # 밤에 일하면
    "trio":  ("LEGION", "#.#\n#.#", (215, 119, 87), "\033[91m"),      # 분신이라 같은 색
    "crumb": ("GLUTTON", "..\n##", (206, 172, 120), "\033[33m"),      # 많이 먹으면
    "globe": ("ROAMER", "##\n##", (92, 172, 204), "\033[96m"),        # 바깥 도구를 쓰면
    "medal": ("MARATHON", ".#\n##", (232, 200, 88), "\033[93m"),      # 오래 끌면
}

SLOTS = ("hat", "friend")


def unlocked(state):
    """지금 걸칠 수 있는 것 목록. 슬롯마다 이름 목록을 준다."""
    level = state.get("level", 1)
    title = state.get("title") or ""
    return {
        "hat": [n for n, item in HATS.items() if level >= item[0]],
        "friend": [n for n, item in FRIENDS.items() if item[0] is None or item[0] == title],
    }


def next_unlock(state):
    """다음에 열리는 것. (슬롯, 이름, 필요 레벨) 또는 None."""
    level = state.get("level", 1)
    coming = [("hat", n, item[0]) for n, item in HATS.items() if item[0] > level]
    return min(coming, key=lambda x: x[2]) if coming else None


def worn(state, slot):
    """실제로 걸치고 있는 것. 아직 못 연 것을 입고 있으면 벗긴다."""
    name = (state.get("worn") or {}).get(slot, "none")
    return name if name in unlocked(state)[slot] else "none"


def color_of(table, name, truecolor):
    """악세사리 색. 몸통색과 달라야 걸친 것으로 읽힌다."""
    item = table.get(name)
    if not item or not item[1]:
        return ""
    rgb, fallback = item[2], item[3]
    return ("\033[38;2;%d;%d;%dm" % rgb) if truecolor else fallback


def hat_row(name):
    """머리 위 한 행. 걸친 게 없으면 빈 줄."""
    item = HATS.get(name)
    return fold(item[1]) if item and item[1] else " " * WIDTH


def friend_cell(name):
    item = FRIENDS.get(name)
    return fold(item[1], 2) if item and item[1] else ""
