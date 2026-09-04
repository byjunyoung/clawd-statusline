# -*- coding: utf-8 -*-
"""훅 진입점. 장부에 쓰는 것은 이 파일뿐이다.

상태줄이 매초 돌면서 쓰기까지 하면 세션 여러 개가 같은 파일을 동시에 건드리고,
실행 중 다음 갱신이 오면 취소되어 누락이 생긴다. 그래서 쓰기를 여기로 모았다.
"""

import json
import os
import sys
import time

import grow
import ledger
import scan
import stats as stats_mod

STATS_TTL = 6 * 3600  # 스탯 재계산 간격. 전수 스캔이라 자주 돌릴 일이 아니다


def account_info():
    info = {"plan": "", "first_token_date": ""}
    try:
        with open(os.path.expanduser("~/.claude.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return info
    oauth = data.get("oauthAccount") or {}
    info["plan"] = oauth.get("organizationRateLimitTier") or ""
    info["first_token_date"] = str(data.get("claudeCodeFirstTokenDate") or "")[:10]
    return info


age_days = grow.age_days   # 나이 계산은 grow가 정본이다. 여기서는 이름만 빌려 쓴다


def projects_dir():
    return os.path.join(ledger.config_dir(), "projects")


def start(raw, account):
    """설치하는 순간 과거 기록을 그 자리에서 다 먹여 현재 레벨로 시작한다."""
    state = ledger.blank_state()
    state["plan"] = account["plan"]
    state["firstTokenDate"] = account["first_token_date"]
    state["food"] = raw["food"]
    state["stats"] = stats_mod.compute(raw)
    state["statsComputedAt"] = int(time.time())
    state["level"] = grow.level_for(state["food"], grow.plan_factor(state["plan"]))
    ledger.save(state)
    return state


def _refresh_stats(state, now):
    if now - state.get("statsComputedAt", 0) < STATS_TTL:
        return
    state["stats"] = stats_mod.compute(scan.scan_all(projects_dir()))
    state["statsComputedAt"] = int(now)


def apply_event(payload):
    if ledger.load() is None:
        return None  # 아직 부화 전이다. 설치 커맨드가 부화시킨다
    now = time.time()
    sid = payload.get("session_id") or ""
    tpath = payload.get("transcript_path") or ""

    def mutate(state):
        if tpath and os.path.exists(tpath):
            cur = (state.get("cursors") or {}).get(sid) or {}
            raw, offset, last_id = scan.scan_file(
                tpath, cur.get("offset", 0), cur.get("last_id", ""))
            state["food"] = state.get("food", 0) + raw["food"]
            state.setdefault("cursors", {})[sid] = {
                "offset": offset, "last_id": last_id, "seenAt": int(now)}
        state["level"] = grow.level_for(state.get("food", 0),
                                        grow.plan_factor(state.get("plan", "")))
        state["lastSeenAt"] = int(now)
        _refresh_stats(state, now)
        ledger.prune_cursors(state, now)

    return ledger.update(mutate)


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    if isinstance(payload, dict):
        apply_event(payload)


if __name__ == "__main__":
    main()
