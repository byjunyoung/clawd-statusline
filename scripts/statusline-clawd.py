#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""상태줄 왼쪽에 Clawd를 세운다.

다른 상태줄 명령을 감싸는 래퍼다. stdin JSON을 그 명령에 그대로 넘기고,
돌아온 줄들 왼쪽에 3행 스프라이트를 붙인다. 감쌀 명령이 없으면 Clawd만 그린다.

설정: $CLAUDE_CONFIG_DIR/clawd-statusline.json (없으면 ~/.claude/)
  {
    "wrap": "명령 문자열 또는 인자 배열",   // 생략하면 claude-hud 자동 탐지
    "gap": 2,                                // 스프라이트와 오른쪽 사이 여백
    "thresholds": {"wary": 50, "alarmed": 25, "panic": 10}
  }
"""
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from glob import glob

WIDTH = 9        # 스프라이트 폭(문자 칸)
CACHE_TTL = 60   # 감싼 명령의 출력 캐시 수명(초)
DEFAULTS = {"wrap": None, "gap": 2, "thresholds": {"wary": 50, "alarmed": 25, "panic": 10}}

# --- 스프라이트 ------------------------------------------------------------
# 얼굴·몸통은 검정 배경 위에 몸통색 블록을 얹는다. 빈 사분면이 비쳐 눈과 입이 된다.
ARMS_DOWN = dict(r1L=" ▐", r1R="", r2L="▝▜", r2R="█▀")
ARMS_UP = dict(r1L="▗▟", r1R="▄", r2L=" ▜", r2R="█▘")
FEET = "  ▝▝ ▝▝  "

POSES = {
    "default":    (ARMS_DOWN, "▛███▛█", "█████"),
    "look-left":  (ARMS_DOWN, "▟███▟█", "█████"),
    "look-right": (ARMS_DOWN, "█▟███▟", "█████"),
    "arms-up":    (ARMS_UP,   "▛███▛█", "█████"),
    "blink":      (ARMS_DOWN, "██████", "█████"),
    "wary":       (ARMS_DOWN, "▛███▛█", "██▄██"),
    "alarmed":    (ARMS_DOWN, "▀███▀█", "█▄▄▄█"),
    "panic":      (ARMS_UP,   "▀███▀█", "█▄▄▄█"),
}

# Apple Terminal은 사분면 렌더가 다르다. 앤트로픽 원본도 여기선 색을 반전시켜
# 몸통을 배경으로 칠하고 눈만 전경색으로 찍는다. (눈·입 7칸, 양옆에 귀 1칸씩)
FALLBACK = {
    "default":    (" ▗   ▖ ", "       "),
    "look-left":  (" ▘   ▘ ", "       "),
    "look-right": (" ▝   ▝ ", "       "),
    "arms-up":    (" ▗   ▖ ", "       "),
    "blink":      ("       ", "       "),
    "wary":       (" ▗   ▖ ", "   ▀   "),
    "alarmed":    (" █   █ ", "  ▀▀▀  "),
    "panic":      (" █   █ ", "  ███  "),
}
FALLBACK_FEET = "▘▘ ▝▝"

IDLE = [("default", 45), ("look-left", 15), ("look-right", 15), ("blink", 15), ("arms-up", 10)]

RESET = "\033[0m"
NO_BG = "\033[49m"


def palette():
    """(몸통 전경, 얼굴 배경, 몸통 배경, 얼굴 전경). 트루컬러가 아니면 ANSI로 떨어진다."""
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return ("\033[38;2;215;119;87m", "\033[48;2;0;0;0m",
                "\033[48;2;215;119;87m", "\033[38;2;0;0;0m")
    return ("\033[91m", "\033[40m", "\033[101m", "\033[30m")  # 원본 ANSI 테마와 같은 redBright/black


def render(pose):
    """포즈 이름 -> ANSI 3행. 각 행을 WIDTH칸으로 맞춘다."""
    body_fg, face_bg, body_bg, face_fg = palette()

    if os.environ.get("TERM_PROGRAM") == "Apple_Terminal":
        eyes, mouth = FALLBACK[pose]
        pad = " " * ((WIDTH - len(FALLBACK_FEET)) // 2)
        return [
            f"{body_fg}▗{face_fg}{body_bg}{eyes}{NO_BG}{body_fg}▖{RESET}",
            f"{face_fg}{body_bg} {mouth} {NO_BG}{RESET}",
            f"{body_fg}{pad}{FALLBACK_FEET}{RESET}{pad}",
        ]

    arms, face, mouth = POSES[pose]
    rows = [
        (arms["r1L"], face, arms["r1R"], True),
        (arms["r2L"], mouth, arms["r2R"], True),
        ("", FEET, "", False),
    ]
    out = []
    for left, mid, right, boxed in rows:
        gap = " " * max(0, WIDTH - len(left + mid + right))
        core = f"{face_bg}{mid}{NO_BG}" if boxed else mid
        out.append(f"{body_fg}{left}{core}{right}{RESET}{gap}")
    return out


# --- 상태 판정 -------------------------------------------------------------
def pick_pose(payload, thresholds, tick):
    """컨텍스트 잔량과 사용량 한도 중 나쁜 쪽을 기준으로 포즈를 고른다."""
    remaining = []
    ctx = payload.get("context_window") or {}
    if isinstance(ctx.get("remaining_percentage"), (int, float)):
        remaining.append(float(ctx["remaining_percentage"]))
    elif isinstance(ctx.get("used_percentage"), (int, float)):
        remaining.append(100.0 - float(ctx["used_percentage"]))
    for window in (payload.get("rate_limits") or {}).values():
        used = (window or {}).get("used_percentage")
        if isinstance(used, (int, float)):
            remaining.append(100.0 - float(used))

    worst = min(remaining) if remaining else 100.0
    if worst < thresholds["panic"]:
        return "panic" if tick % 2 else "alarmed"   # 팔이 오르내린다
    if worst < thresholds["alarmed"]:
        return "alarmed"
    if worst < thresholds["wary"]:
        return "wary"

    rng = random.Random(tick)
    return rng.choices([n for n, _ in IDLE], weights=[w for _, w in IDLE])[0]


# --- 감쌀 명령 -------------------------------------------------------------
def config_dir():
    return os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")


def load_config():
    cfg = dict(DEFAULTS)
    path = os.path.join(config_dir(), "clawd-statusline.json")
    try:
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
        if isinstance(user, dict):
            cfg.update({k: v for k, v in user.items() if k in DEFAULTS})
            if isinstance(user.get("thresholds"), dict):
                cfg["thresholds"] = {**DEFAULTS["thresholds"], **user["thresholds"]}
    except (OSError, ValueError):
        pass
    return cfg


def find_node():
    found = shutil.which("node")
    if found:
        return found
    for guess in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"):
        if os.path.exists(guess):
            return guess
    return None


def autodetect_hud():
    """설정에 wrap이 없을 때 claude-hud를 찾아본다. 없으면 감싸지 않는다."""
    pattern = os.path.join(config_dir(), "plugins", "cache", "claude-hud", "claude-hud", "*", "")
    dirs = sorted(glob(pattern), key=os.path.getmtime, reverse=True)
    node = find_node()
    if not dirs or not node:
        return None
    entry = os.path.join(dirs[0], "dist", "index.js")
    return [node, entry] if os.path.exists(entry) else None


def cache_key(payload, command):
    """대화가 진행됐을 때만 바뀌는 키. 타이머 재실행은 여기 걸려 캐시를 탄다."""
    parts = [repr(command), str(payload.get("session_id")), str(payload.get("cwd")),
             json.dumps(payload.get("model"), sort_keys=True),
             json.dumps(payload.get("context_window"), sort_keys=True),
             json.dumps(payload.get("rate_limits"), sort_keys=True),
             json.dumps(payload.get("vim"), sort_keys=True)]
    path = payload.get("transcript_path")
    if path and os.path.exists(path):
        st = os.stat(path)
        parts += [str(st.st_size), str(int(st.st_mtime))]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def wrapped_lines(payload, raw, command):
    if not command:
        return []
    cache_dir = os.path.join(config_dir(), "clawd-cache")
    key = cache_key(payload, command)
    cache = os.path.join(cache_dir, f"{key[:16]}.txt")
    try:
        if time.time() - os.path.getmtime(cache) < CACHE_TTL:
            with open(cache, encoding="utf-8") as fh:
                return fh.read().splitlines()
    except OSError:
        pass
    try:
        done = subprocess.run(command, input=raw, capture_output=True, text=True,
                              timeout=10, shell=isinstance(command, str))
        lines = done.stdout.rstrip("\n").splitlines()
    except (OSError, subprocess.SubprocessError):
        return []
    try:
        os.makedirs(cache_dir, exist_ok=True)
        for stale in glob(os.path.join(cache_dir, "*.txt")):
            if time.time() - os.path.getmtime(stale) > CACHE_TTL:
                os.unlink(stale)
        with open(cache, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    except OSError:
        pass
    return lines


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    cfg = load_config()
    command = cfg["wrap"] or autodetect_hud()
    sprite = render(pick_pose(payload, cfg["thresholds"], int(time.time())))
    right_lines = wrapped_lines(payload, raw, command)

    gap = " " * max(0, int(cfg["gap"]))
    indent = " " * (WIDTH + len(gap))
    out = []
    for i in range(max(len(sprite), len(right_lines))):
        left = f"{sprite[i]}{gap}" if i < len(sprite) else indent
        right = right_lines[i] if i < len(right_lines) else ""
        out.append((left + right).rstrip())
    print("\n".join(out))


if __name__ == "__main__":
    main()
