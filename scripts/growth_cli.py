#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""성장을 켜고, 걸친 것을 바꾸고, 카드를 낸다.

  growth_cli.py start            과거 기록을 훑어 레벨을 매기고 장부를 만든다
  growth_cli.py wear hat cap     걸친 것을 바꾼다
  growth_cli.py card             카드를 낸다
  growth_cli.py json             장부를 그대로 낸다 (커맨드가 읽는 용도)
"""

import json
import sys
import time

import closet
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


def wear(slot, name):
    if slot not in closet.SLOTS:
        raise SystemExit("모르는 자리입니다: %s" % slot)
    state = ledger.load() or {}
    if name not in closet.unlocked(refresh(state))[slot]:
        raise SystemExit("아직 못 여는 것입니다: %s" % name)

    def mutate(s):
        s.setdefault("worn", {})[slot] = name
    return ledger.update(mutate)


def card(state):
    state = refresh(state)
    level = state.get("level", 1)
    factor = grow.plan_factor(state.get("plan", ""))
    need = max(0, grow.food_for_level(level + 1, factor) - state.get("food", 0))
    s = state.get("stats") or {}
    lines = ["", "  Clawd  Lv.%d" % level, ""]
    body = [closet.hat_row(closet.worn(state, "hat")),
            " ▐▛███▛█ ", "▝▜██████▀", "  ▝▝ ▝▝  "]
    right = ["", "FED    %s" % compact(state.get("food", 0)),
             "NEXT   %s to Lv.%d" % (compact(need), level + 1),
             "AGE    %d days" % grow.age_days(state.get("firstTokenDate", ""), time.time())]
    for i in range(4):
        lines.append(("  %s   %s" % (body[i], right[i])).rstrip())
    lines.append("")
    for k in ORDER:
        lines.append("  %-9s %s  %3d" % (k.upper(), bar(s.get(k, 0)), s.get(k, 0)))
    if state.get("title"):
        lines.append("")
        lines.append("  TITLE  %s" % state["title"])
    lines.append("")
    open_now = closet.unlocked(state)
    for slot in closet.SLOTS:
        worn_now = closet.worn(state, slot)
        others = [n for n in open_now[slot] if n != worn_now]
        lines.append("  %-7s %s%s" % (slot.upper(), worn_now,
                                      ("   (%s)" % " ".join(others)) if others else ""))
    nxt = closet.next_unlock(state)
    if nxt:
        lines.append("")
        lines.append("  NEXT UNLOCK  %s %s at Lv.%d" % (nxt[0], nxt[1], nxt[2]))
    return "\n".join(lines)


def main(argv):
    cmd = argv[0] if argv else "card"
    if cmd == "start":
        print(json.dumps(start(), ensure_ascii=False))
    elif cmd == "wear":
        if len(argv) < 3:
            raise SystemExit("growth_cli.py wear <hat|hold|friend> <이름>")
        print(json.dumps(wear(argv[1], argv[2]), ensure_ascii=False))
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
