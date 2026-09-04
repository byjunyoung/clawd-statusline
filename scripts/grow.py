# -*- coding: utf-8 -*-
"""먹이에서 레벨을, 레벨과 나이에서 단계를, 스탯에서 진화 갈래를 정한다."""

import datetime

BASE = 5000
MAX_LEVEL = 99

# 소비 여력 비의 제곱근. 높은 요금제가 여전히 빨리 크되 격차를 절반으로 줄인다.
PLAN_FACTOR = {
    "claude_pro": 0.45,
    "default_claude_pro": 0.45,
    "claude_max": 1.0,
    "claude_max_5x": 1.0,
    "default_claude_max_5x": 1.0,
    "claude_max_20x": 2.0,
    "default_claude_max_20x": 2.0,
}




def plan_factor(tier):
    return PLAN_FACTOR.get(tier or "", 1.0)


def food_for_level(level, factor):
    return int(BASE * (level ** 3) * factor)


def level_for(food, factor):
    lo, hi = 1, MAX_LEVEL
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if food >= food_for_level(mid, factor):
            lo = mid
        else:
            hi = mid - 1
    return lo





def age_days(first_token_date, now):
    """나이는 부화가 아니라 클로드 코드를 처음 쓴 날부터 센다."""
    if not first_token_date:
        return 0
    try:
        start = datetime.datetime.strptime(str(first_token_date)[:10], "%Y-%m-%d")
    except ValueError:
        return 0
    return max(0, int((now - start.timestamp()) // 86400))



