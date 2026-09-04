# -*- coding: utf-8 -*-
"""원자료를 스탯 다섯으로 접는다.

전부 클로드를 어떻게 쓰는지를 잰다. 기준점은 실측에서 뽑았고, 남의 환경에서
이상하면 이 표만 고치면 된다.
"""

ANCHORS = {
    # 활동일당 먹이 중앙값
    "appetite": [(0, 0), (1e5, 10), (1e6, 40), (5e6, 70), (1e7, 85), (2e7, 95), (5e7, 100)],
    # 바깥 도구(MCP·웹) 비율 %
    "reach": [(0, 0), (20, 30), (40, 60), (60, 83), (80, 95), (100, 100)],
    # 세션당 턴 중앙값에 세션당 컴팩트를 열 배로 얹은 값
    "stamina": [(0, 0), (5, 10), (15, 30), (30, 50), (60, 70), (120, 85), (300, 95), (600, 100)],
    # 세션당 서브에이전트 호출 수
    "pack": [(0, 0), (1, 20), (5, 45), (15, 70), (40, 90), (100, 100)],
    # 심야(22-06시) 비율 %
    "nocturne": [(0, 0), (5, 15), (15, 45), (30, 75), (50, 95), (70, 100)],
}

TITLES = {"appetite": "GLUTTON", "reach": "ROAMER", "stamina": "MARATHON",
          "pack": "LEGION", "nocturne": "OWL"}

ORDER = ["appetite", "reach", "stamina", "pack", "nocturne"]


def interp(anchors, x):
    """기준점 사이를 선형으로 잇는다. 밖으로 나가면 양 끝 값에 붙인다."""
    if x <= anchors[0][0]:
        return anchors[0][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x <= x1:
            span = x1 - x0
            return int(round(y0 + (y1 - y0) * ((x - x0) / span if span else 1)))
    return anchors[-1][1]


def _median(values):
    vs = sorted(values)
    if not vs:
        return 0
    mid = len(vs) // 2
    return vs[mid] if len(vs) % 2 else (vs[mid - 1] + vs[mid]) / 2.0


def compute(raw):
    sessions = max(1, len(raw["turns_by_session"]))
    day_food = _median(raw["days"].values()) if raw["days"] else 0
    outer_pct = (100.0 * raw["outer_tools"] / raw["total_tools"]) if raw["total_tools"] else 0
    depth = _median(raw["turns_by_session"].values()) + 10.0 * raw["compacts"] / sessions
    pack = 1.0 * raw["sidechain"] / sessions
    calls = raw["night_calls"] + raw["day_calls"]
    night_pct = (100.0 * raw["night_calls"] / calls) if calls else 0
    return {
        "appetite": interp(ANCHORS["appetite"], day_food),
        "reach": interp(ANCHORS["reach"], outer_pct),
        "stamina": interp(ANCHORS["stamina"], depth),
        "pack": interp(ANCHORS["pack"], pack),
        "nocturne": interp(ANCHORS["nocturne"], night_pct),
    }


def title(stats_):
    best = max(ORDER, key=lambda k: (stats_.get(k, 0), -ORDER.index(k)))
    return TITLES[best] if stats_.get(best, 0) >= 90 else None
