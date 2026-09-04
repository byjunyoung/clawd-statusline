# -*- coding: utf-8 -*-
"""대화 기록(jsonl)에서 먹이와 스탯 원자료를 뽑는다.

한 번의 호출이 파일에 여러 줄로 저장된다. 생각·글·도구 호출이 각각 한 줄이다.
message.id로 묶어야 한 번만 세어진다. 실측에서 4,190줄이 2,394번의 호출이었다.
"""

import datetime
import glob
import json
import os
import time

OUTER_PREFIXES = ("mcp__",)
OUTER_TOOLS = ("WebSearch", "WebFetch")


def new_raw():
    return {"food": 0, "calls": 0, "compacts": 0, "sidechain": 0,
            "outer_tools": 0, "total_tools": 0, "night_calls": 0, "day_calls": 0,
            "turns_by_session": {}, "days": {}}


def merge(a, b):
    for k in ("food", "calls", "compacts", "sidechain", "outer_tools",
              "total_tools", "night_calls", "day_calls"):
        a[k] += b[k]
    for k, v in b["turns_by_session"].items():
        a["turns_by_session"][k] = a["turns_by_session"].get(k, 0) + v
    for k, v in b["days"].items():
        a["days"][k] = a["days"].get(k, 0) + v
    return a


def _local(ts):
    """UTC 문자열을 그 기기의 지역시로 바꾼다. 밤을 세려면 지역시라야 한다."""
    try:
        dt = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    try:
        return dt.astimezone()
    except ValueError:
        return None


def scan_lines(lines, raw, seen):
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("subtype") == "compact_boundary":
            raw["compacts"] += 1
            continue
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message") or {}
        mid = msg.get("id")
        if not mid or mid in seen:
            continue
        seen.add(mid)
        if rec.get("isSidechain"):
            # 서브에이전트가 쓴 토큰도 먹이지만, 스탯 원자료로는 따로 센다.
            raw["sidechain"] += 1
            continue
        u = msg.get("usage") or {}
        food = ((u.get("output_tokens") or 0) + (u.get("input_tokens") or 0)
                + (u.get("cache_creation_input_tokens") or 0))
        raw["food"] += food
        raw["calls"] += 1
        sid = rec.get("sessionId")
        if sid:
            raw["turns_by_session"][sid] = raw["turns_by_session"].get(sid, 0) + 1
        dt = _local(rec.get("timestamp"))
        if dt:
            key = dt.strftime("%Y-%m-%d")
            raw["days"][key] = raw["days"].get(key, 0) + food
            if dt.hour >= 22 or dt.hour < 6:
                raw["night_calls"] += 1
            else:
                raw["day_calls"] += 1
        for blk in (msg.get("content") or []):
            if isinstance(blk, dict) and blk.get("type") == "tool_use":
                name = blk.get("name", "")
                raw["total_tools"] += 1
                if name.startswith(OUTER_PREFIXES) or name in OUTER_TOOLS:
                    raw["outer_tools"] += 1


def scan_file(path, offset=0, last_id=""):
    """offset 뒤에 늘어난 부분만 읽는다.

    경계에 걸친 호출은 last_id로 걸러진다. 마지막 줄이 아직 다 안 쓰였으면
    그 줄은 넘기고 오프셋을 그 앞까지만 옮긴다.
    """
    raw = new_raw()
    seen = set()
    if last_id:
        seen.add(last_id)
    try:
        size = os.path.getsize(path)
    except OSError:
        return raw, offset, last_id
    if size < offset:  # 파일이 잘렸거나 새로 만들어졌다
        offset = 0
        seen = set()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            data = fh.read()
    except OSError:
        return raw, offset, last_id
    new_offset = offset + len(data.encode("utf-8"))
    lines = data.split("\n")
    if lines and not data.endswith("\n"):
        incomplete = lines.pop()
        new_offset -= len(incomplete.encode("utf-8"))
    scan_lines(lines, raw, seen)
    newest = last_id
    for line in reversed(lines):
        if '"type":"assistant"' not in line:
            continue
        try:
            mid = (json.loads(line).get("message") or {}).get("id")
        except ValueError:
            continue
        if mid:
            newest = mid
            break
    return raw, new_offset, newest


def scan_all(projects_dir, since_days=90):
    """부화할 때 한 번 도는 전수 스캔. 실측으로 1.5GB를 1.5초에 훑는다."""
    raw = new_raw()
    seen = set()
    cutoff = time.time() - since_days * 86400
    for path in glob.glob(os.path.join(projects_dir, "**", "*.jsonl"), recursive=True):
        try:
            if os.path.getmtime(path) < cutoff:
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                scan_lines(fh.read().split("\n"), raw, seen)
        except OSError:
            continue
    return raw
