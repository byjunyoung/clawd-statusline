#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""쓴 토큰으로 레벨을 매기고 사용 습관을 다섯 스탯으로 보여준다.

  growth_cli.py start   과거 기록을 훑어 레벨을 매기고 장부를 만든다
  growth_cli.py card    카드를 낸다
  growth_cli.py json    장부를 그대로 낸다

상태줄은 이 값을 쓰지 않는다. 레벨이 올라도 Clawd가 그려지는 방식은 안 바뀐다.
악세사리로 꾸미는 것도 만들어 봤다가 통째로 뺐다. 9칸짜리 스프라이트에 얹을 수 있는 것이
작은 색덩어리뿐이라 레벨을 올려도 손에 잡히는 보상이 안 됐다. 자세한 경위는 docs/growth.md.
"""

import json
import sys
import time

import feed
import grow
import ledger
import scan
import stats as stats_mod

ORDER = ["appetite", "reach", "stamina", "pack", "nocturne"]


def compact(n):
    n = int(n)
    for unit, size in (("B", 10 ** 9), ("M", 10 ** 6), ("K", 10 ** 3)):
        if n >= size:
            return "%.1f%s" % (n / float(size), unit)
    return str(n)


def bar(value, width=10):
    filled = int(round(max(0, min(100, value)) / 100.0 * width))
    return "█" * filled + "░" * (width - filled)


def refresh(state):
    """카드에 쓰는 파생값. 장부에는 칭호만 남긴다."""
    state["title"] = stats_mod.title(state.get("stats") or {}) or ""
    return state


def start():
    state = ledger.load()
    if state is None:
        state = feed.start(scan.scan_all(feed.projects_dir()), feed.account_info())
    return ledger.update(lambda s: s.update(refresh(state)))


def card(state):
    state = refresh(state)
    level = state.get("level", 1)
    factor = grow.plan_factor(state.get("plan", ""))
    need = max(0, grow.food_for_level(level + 1, factor) - state.get("food", 0))
    s = state.get("stats") or {}
    lines = ["", "  Clawd  Lv.%d" % level, ""]
    body = [" ▐▛███▛█ ", "▝▜██████▀", "  ▝▝ ▝▝  "]
    right = ["FED    %s" % compact(state.get("food", 0)),
             "NEXT   %s to Lv.%d" % (compact(need), level + 1),
             "AGE    %d days" % grow.age_days(state.get("firstTokenDate", ""), time.time())]
    for i in range(3):
        lines.append(("  %s   %s" % (body[i], right[i])).rstrip())
    lines.append("")
    for k in ORDER:
        lines.append("  %-9s %s  %3d" % (k.upper(), bar(s.get(k, 0)), s.get(k, 0)))
    if state.get("title"):
        lines.append("")
        lines.append("  TITLE  %s" % state["title"])
    return "\n".join(lines)


def main(argv):
    cmd = argv[0] if argv else "card"
    if cmd == "start":
        print(json.dumps(start(), ensure_ascii=False))
    elif cmd == "json":
        state = ledger.load()
        print(json.dumps(refresh(state) if state else {}, ensure_ascii=False))
    else:
        state = ledger.load()
        if state is None:
            print("아직 시작하지 않았습니다. /clawd-statusline:setup 을 실행하세요.")
            return
        print(card(state))


if __name__ == "__main__":
    main(sys.argv[1:])
