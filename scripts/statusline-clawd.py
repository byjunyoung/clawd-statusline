#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""상태줄 왼쪽에 Clawd를 세운다.

다른 상태줄 명령을 감싸는 래퍼다. stdin JSON을 그 명령에 그대로 넘기고,
돌아온 줄들 왼쪽에 3행 스프라이트를 붙인다. 감쌀 명령이 없으면 Clawd만 그린다.

설정: $CLAUDE_CONFIG_DIR/clawd-statusline.json (없으면 ~/.claude/)
  {
    "wrap": "명령 문자열 또는 인자 배열",   // 생략하면 claude-hud 자동 탐지
    "gap": 2,                                // 스프라이트와 오른쪽 사이 여백
    "thresholds": {"wary": 50, "alarmed": 25, "panic": 10},
    "jump": true                             // 프롬프트를 보내면 한 번 뛴다
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
from datetime import datetime
from glob import glob

WIDTH = 9        # 스프라이트 폭(문자 칸)
CACHE_TTL = 60   # 감싼 명령의 출력 캐시 수명(초)
JUMP_TICKS = 3   # 프롬프트 직후 점프에 쓰는 틱 수(웅크림·도약·착지)
TAIL_BYTES = 65536   # transcript 꼬리에서 읽어볼 크기
TAIL_LINES = 40      # 그 안에서 들여다볼 줄 수
DEFAULTS = {"wrap": None, "gap": 2, "jump": True,
            "thresholds": {"wary": 50, "alarmed": 25, "panic": 10}}

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
POOF = ("·", "~")   # 웅크릴 때 발밑에 피는 먼지. 원본과 같은 두 글자다.
BLANK = RESET + " " * WIDTH   # 공백뿐인 줄은 상태줄에서 지워진다


def palette():
    """(몸통 전경, 얼굴 배경, 몸통 배경, 얼굴 전경, 먼지). 트루컬러가 아니면 ANSI로 떨어진다."""
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return ("\033[38;2;215;119;87m", "\033[48;2;0;0;0m",
                "\033[48;2;215;119;87m", "\033[38;2;0;0;0m", "\033[38;2;102;102;102m")
    return ("\033[91m", "\033[40m", "\033[101m", "\033[30m", "\033[90m")  # 원본 ANSI 테마와 같은 redBright/black


def render(pose, offset=0, poof=None):
    """포즈 -> ANSI 3행. 각 행을 WIDTH칸으로 맞춘다.

    offset이 1이면 몸을 한 행 내려 웅크린다. 원본과 같이 상자 높이는 그대로여서
    발이 아래로 밀려 잘리고, 남은 아랫줄 양 끝에 먼지가 한 글자씩 뜬다.

    빈 윗줄은 공백만 두면 클로드 코드가 통째로 지워 상태줄이 한 행 줄어든다.
    앞에 RESET을 붙여 줄을 살려둔다.
    """
    body_fg, face_bg, body_bg, face_fg, dim = palette()
    dust = f"{dim}{poof}{RESET}" if offset and poof else None

    if os.environ.get("TERM_PROGRAM") == "Apple_Terminal":
        eyes, mouth = FALLBACK[pose]
        pad = " " * ((WIDTH - len(FALLBACK_FEET)) // 2)
        head = f"{body_fg}▗{face_fg}{body_bg}{eyes}{NO_BG}{body_fg}▖{RESET}"
        if offset:
            body = f"{face_fg}{body_bg}{mouth}{NO_BG}{RESET}"
            return [BLANK, head, f"{dust}{body}{dust}" if dust else f" {body} "]
        return [
            head,
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

    if not offset:
        return out

    # 몸통 줄의 양 끝 한 칸을 먼지로 바꿔 끼운다. 폭은 그대로 WIDTH.
    left, right = arms["r2L"][1:], arms["r2R"][:-1]
    body = f"{body_fg}{left}{face_bg}{mouth}{NO_BG}{right}{RESET}"
    body = f"{dust}{body}{dust}" if dust else f" {body} "
    return [BLANK, out[0], body]


# --- 점프 ------------------------------------------------------------------
def typed_prompt(record):
    """사람이 직접 친 프롬프트인가. 도구 결과·메타·서브에이전트는 뺀다."""
    if record.get("type") != "user" or record.get("isMeta") or record.get("isSidechain"):
        return False
    if "toolUseResult" in record:
        return False
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        kinds = {b.get("type") for b in content if isinstance(b, dict)}
        return bool(kinds) and "tool_result" not in kinds
    return False


def scan_tail(path, size):
    """transcript 꼬리에서 마지막 프롬프트의 시각(epoch)을 찾는다."""
    try:
        with open(path, "rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(-TAIL_BYTES, os.SEEK_END)
            tail = fh.read()
    except OSError:
        return None

    for line in reversed(tail.split(b"\n")[-TAIL_LINES:]):
        # 큰 도구 결과 줄은 열어보지도 않는다. JSON 간격에 기대지 않으려고
        # 키 이름만 훑는다.
        if b'"user"' not in line or b'"tool_result"' in line or b'"toolUseResult"' in line:
            continue
        try:
            record = json.loads(line.decode("utf-8", "replace"))
        except ValueError:
            continue
        if not isinstance(record, dict) or not typed_prompt(record):
            continue
        stamp = record.get("timestamp")
        if not isinstance(stamp, str):
            return None
        try:
            return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def jump_state(payload):
    """세션마다 마지막 프롬프트 시각을 적어두는 파일. 큰 도구 출력이 프롬프트를
    꼬리 밖으로 밀어내도 점프가 중간에 끊기지 않게 하는 용도다."""
    session = "".join(c for c in str(payload.get("session_id") or "") if c.isalnum() or c in "-_")
    return os.path.join(config_dir(), "clawd-cache", "jump-%s.txt" % (session[:64] or "default"))


def prompt_age(payload):
    """마지막 프롬프트 이후 지난 초. 최근에 없으면 None."""
    path = payload.get("transcript_path")
    try:
        stat = os.stat(path)
    except (OSError, TypeError, ValueError):
        return None
    now = time.time()
    if now - stat.st_mtime > JUMP_TICKS + 2:   # 조용한 세션은 파일을 열지도 않는다
        return None

    seen = scan_tail(path, stat.st_size)
    state = jump_state(payload)
    saved = None
    try:
        with open(state, encoding="utf-8") as fh:
            saved = float(fh.read().strip())
    except (OSError, ValueError):
        pass

    if seen is not None and (saved is None or seen > saved + 0.5):
        try:
            os.makedirs(os.path.dirname(state), exist_ok=True)
            with open(state, "w", encoding="utf-8") as fh:
                fh.write(repr(seen))
        except OSError:
            pass
        saved = seen
    stamp = max(x for x in (seen, saved) if x is not None) if (seen or saved) else None
    return None if stamp is None else now - stamp


def jump_frame(payload):
    """0 웅크림 / 1 도약 / 2 착지. 뛸 때가 아니면 None."""
    age = prompt_age(payload)
    if age is None or age <= -1:
        return None
    frame = max(0, int(age))
    return frame if frame < JUMP_TICKS else None


# --- 상태 판정 -------------------------------------------------------------
def pick_pose(payload, cfg, tick):
    """(포즈, 세로 오프셋, 먼지). 컨텍스트 잔량과 사용량 한도 중 나쁜 쪽이 기준이다."""
    thresholds = cfg["thresholds"]
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
        return ("panic" if tick % 2 else "alarmed"), 0, None   # 팔이 오르내린다
    if worst < thresholds["alarmed"]:
        return "alarmed", 0, None
    if worst < thresholds["wary"]:
        return "wary", 0, None

    # 여유가 있을 때만 뛴다. 걱정하는 중에는 원본이 클릭을 흘리는 것과 같다.
    if cfg.get("jump", True):
        frame = jump_frame(payload)
        if frame == 0:
            return "default", 1, POOF[tick % len(POOF)]
        if frame == 1:
            return "arms-up", 0, None
        if frame == 2:
            return "default", 0, None

    rng = random.Random(tick)
    return rng.choices([n for n, _ in IDLE], weights=[w for _, w in IDLE])[0], 0, None


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
    sprite = render(*pick_pose(payload, cfg, int(time.time())))
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
