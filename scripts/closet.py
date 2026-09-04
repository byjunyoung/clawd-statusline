# -*- coding: utf-8 -*-
"""Clawd가 걸치는 것들. 레벨이 오르면 걸칠 것이 늘어난다.

Clawd 본체는 시즌 1 그대로다. 여기서는 위에 한 행을 얹고, 몸통 오른쪽과
발 옆에 한 칸씩 덧붙일 뿐이다. 원본은 건드리지 않는다.

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
HATS = {
    "none":  (1,  ""),
    "cap":   (5,  "\n.....########..."),
    "horn":  (12, "....#......#....\n....#......#...."),
    "leaf":  (20, "........##......\n.......###......"),
    "cone":  (30, "........##......\n......######...."),
    "top":   (40, ".....######.....\n...##########..."),
    "crown": (50, "....#.#.#.#.#...\n....##########.."),
    "halo":  (65, "....##.####.##..\n................"),
}

# --- 손에 드는 것. 몸통 줄 오른쪽에 한 칸 붙는다 ----------------------------
HOLDS = {
    "none":  (1,  ""),
    "mug":   (8,  "##\n##"),
    "flag":  (18, "#.\n##"),
    "torch": (35, ".#\n##"),
    "wand":  (55, "#.\n.#"),
}

# --- 친구. 발 옆에 한 칸. 스탯 칭호로만 열린다 ------------------------------
# 레벨로는 못 얻는다. 그렇게 일해야 따라온다.
FRIENDS = {
    "none":  (None, ""),
    "bat":   ("OWL", "#.#\n.#."),        # 밤에 일하면 따라붙는다
    "trio":  ("LEGION", "#.#\n#.#"),     # 서브에이전트를 많이 부리면
    "crumb": ("GLUTTON", "..\n##"),      # 많이 먹으면
    "globe": ("ROAMER", "##\n##"),       # 바깥 도구를 많이 쓰면
    "medal": ("MARATHON", ".#\n##"),     # 한 대화를 오래 끌면
}

SLOTS = ("hat", "hold", "friend")


def unlocked(state):
    """지금 걸칠 수 있는 것 목록. 슬롯마다 이름 목록을 준다."""
    level = state.get("level", 1)
    title = state.get("title") or ""
    return {
        "hat": [n for n, (need, _art) in HATS.items() if level >= need],
        "hold": [n for n, (need, _art) in HOLDS.items() if level >= need],
        "friend": [n for n, (need, _art) in FRIENDS.items() if need is None or need == title],
    }


def next_unlock(state):
    """다음에 열리는 것. (슬롯, 이름, 필요 레벨) 또는 None."""
    level = state.get("level", 1)
    coming = [("hat", n, need) for n, (need, _a) in HATS.items() if need > level]
    coming += [("hold", n, need) for n, (need, _a) in HOLDS.items() if need > level]
    return min(coming, key=lambda x: x[2]) if coming else None


def worn(state, slot):
    """실제로 걸치고 있는 것. 아직 못 연 것을 입고 있으면 벗긴다."""
    name = (state.get("worn") or {}).get(slot, "none")
    return name if name in unlocked(state)[slot] else "none"


def hat_row(name):
    """머리 위 한 행. 걸친 게 없으면 빈 줄."""
    need_art = HATS.get(name)
    return fold(need_art[1]) if need_art and need_art[1] else " " * WIDTH


def hold_cell(name):
    art = HOLDS.get(name)
    return fold(art[1], 1) if art and art[1] else ""


def friend_cell(name):
    art = FRIENDS.get(name)
    return fold(art[1], 2) if art and art[1] else ""
