#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""상태줄 왼쪽에 Clawd를 세운다.

다른 상태줄 명령을 감싸는 래퍼다. stdin JSON을 그 명령에 그대로 넘기고,
돌아온 줄들 왼쪽에 3행 스프라이트를 붙인다. 감쌀 명령이 없으면 Clawd만 그린다.

설정: $CLAUDE_CONFIG_DIR/clawd-statusline.json (없으면 ~/.claude/)
  {
    "wrap": "명령 문자열 또는 인자 배열",   // 생략하면 이미 쓰는 상태줄을 찾아 감싼다
    "gap": 2,                                // 스프라이트와 오른쪽 사이 여백
    "thresholds": {"wary": 50, "alarmed": 25, "panic": 10},
    "jump": true,                            // 프롬프트를 보내면 한 번 뛴다
    "startle": true,                         // Esc로 멈추면 놀란다
    "busy": true,                            // 도구가 도는 동안 두리번거린다
    "idle": 60                               // 이만큼 조용하면 앉는다. 0이면 안 앉는다
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
STARTLE_TICKS = 2    # 중단당한 뒤 팔을 든 채 굳어 있는 틱 수
IDLE_AFTER = 60      # 이만큼 조용하면 앉는다(초)
TAIL_BYTES = 65536   # transcript 꼬리에서 읽어볼 크기
TAIL_LINES = 40      # 그 안에서 들여다볼 줄 수
DEFAULTS = {"wrap": None, "gap": 2, "jump": True, "startle": True, "busy": True, "idle": 60,
            "thresholds": {"wary": 50, "alarmed": 25, "panic": 10}}

# --- 스프라이트 ------------------------------------------------------------
# 얼굴·몸통은 검정 배경 위에 몸통색 블록을 얹는다. 빈 사분면이 비쳐 눈과 입이 된다.
ARMS_DOWN = dict(r1L=" ▐", r1R="", r2L="▝▜", r2R="█▀")
ARMS_UP = dict(r1L="▗▟", r1R="▄", r2L=" ▜", r2R="█▘")
FEET = "  ▝▝ ▝▝  "

# 앤트로픽 원본에 있는 넷이 전부다. 여기에 표정을 더 그리지 않는다.
# 입이나 감은 눈을 새로 그려 붙이면 그 순간 짝퉁이 된다. 여유가 얼마나 남았는지는
# 어느 포즈를 얼마나 자주 쓰느냐로만 말한다.
POSES = {
    "default":    (ARMS_DOWN, "▛███▛█", "█████"),
    "look-left":  (ARMS_DOWN, "▟███▟█", "█████"),
    "look-right": (ARMS_DOWN, "█▟███▟", "█████"),
    "arms-up":    (ARMS_UP,   "▛███▛█", "█████"),
}

# Apple Terminal은 사분면 렌더가 다르다. 앤트로픽 원본도 여기선 색을 반전시켜
# 몸통을 배경으로 칠하고 눈만 전경색으로 찍는다. (눈·입 7칸, 양옆에 귀 1칸씩)
FALLBACK = {
    "default":    (" ▗   ▖ ", "       "),
    "look-left":  (" ▘   ▘ ", "       "),
    "look-right": (" ▝   ▝ ", "       "),
    "arms-up":    (" ▗   ▖ ", "       "),
}
FALLBACK_FEET = "▘▘ ▝▝"

# 도약 프레임에서 팔을 올린 짝. panic은 이미 alarmed 얼굴에 팔만 올린 포즈다.
AIRBORNE = {"default": "arms-up", "look-left": "arms-up",
            "look-right": "arms-up", "arms-up": "arms-up"}   # 뛰는 중엔 팔을 든다

# 잔량 구간마다 포즈를 뽑는 확률이 다르다. 여유로우면 가만히 있고, 줄수록 두리번거리다,
# 위태로우면 팔을 든다. 그림은 넷 그대로고 빈도만 바뀐다.
# 원본이 가만히 있을 때 도는 순서(chunk-j9b3a0wh.js의 autoplay). 60ms짜리를 틱에 얹으면
# 22초 주기가 된다. 무작위로 뽑지 않고 이 순서 그대로 돈다 - 그게 "가라앉았다"로 읽힌다.
IDLE_CYCLE = ["default"] * 12 + ["look-right"] * 5 + ["look-left"] * 5

BANDS = [
    ("calm",    [("default", 60), ("look-left", 15), ("look-right", 15), ("arms-up", 10)]),
    ("wary",    [("default", 25), ("look-left", 32), ("look-right", 33), ("arms-up", 10)]),
    ("alarmed", [("look-left", 30), ("look-right", 30), ("arms-up", 40)]),
]

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


# --- 사람이 낸 신호 --------------------------------------------------------
INTERRUPT_MARK = "[Request interrupted"


def signal_kind(record):
    """사람이 낸 신호인가, 어느 쪽인가. "prompt" / "interrupt" / None.

    Esc로 멈춘 것도 user 메시지로 남고 겉모습이 프롬프트와 똑같다. 그냥 세면 멈출
    때마다 Clawd가 좋다고 뛴다. 0.3.0까지 실제로 그랬다.
    """
    if record.get("type") != "user" or record.get("isMeta") or record.get("isSidechain"):
        return None
    if "toolUseResult" in record:
        return None
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        if not content.strip():
            return None
        texts = [content]
    elif isinstance(content, list):
        kinds = {b.get("type") for b in content if isinstance(b, dict)}
        if not kinds or "tool_result" in kinds:
            return None
        texts = [b.get("text") for b in content if isinstance(b, dict)]
    else:
        return None
    for text in texts:
        if isinstance(text, str) and text.strip().startswith(INTERRUPT_MARK):
            return "interrupt"
    return "prompt"


def working(lines):
    """마지막 도구 호출에 아직 결과가 안 붙었는가. 뒤에서부터 먼저 나오는 쪽이 이긴다."""
    for line in reversed(lines):
        if b'"tool_result"' in line or b'"toolUseResult"' in line:
            return False
        if b'"tool_use"' in line and b'"assistant"' in line:
            return True
    return False


def read_tail(path, size):
    """꼬리를 한 번 읽어 (신호, 시각, 작업중)을 같이 뽑는다.

    셋을 따로 읽으면 같은 파일을 세 번 연다. 매초 도는 명령이라 한 번에 끝낸다.
    """
    try:
        with open(path, "rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(-TAIL_BYTES, os.SEEK_END)
            tail = fh.read()
    except OSError:
        return None, None, False

    lines = [ln for ln in tail.split(b"\n")[-TAIL_LINES:] if ln.strip()]
    busy = working(lines)
    for line in reversed(lines):
        # 큰 도구 결과 줄은 열어보지도 않는다. JSON 간격에 기대지 않으려고
        # 키 이름만 훑는다.
        if b'"user"' not in line or b'"tool_result"' in line or b'"toolUseResult"' in line:
            continue
        try:
            record = json.loads(line.decode("utf-8", "replace"))
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        kind = signal_kind(record)
        if kind is None:
            continue
        stamp = record.get("timestamp")
        if not isinstance(stamp, str):
            break
        try:
            return kind, datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp(), busy
        except ValueError:
            break
    return None, None, busy


def beat_path(payload):
    """세션마다 마지막 신호를 적어두는 파일.

    두 가지를 한다. 큰 도구 출력이 프롬프트를 꼬리 밖으로 밀어내도 점프가 중간에
    끊기지 않게 하고, transcript가 그대로일 때 꼬리를 다시 안 읽게 한다.
    """
    session = "".join(c for c in str(payload.get("session_id") or "") if c.isalnum() or c in "-_")
    return os.path.join(config_dir(), "clawd-cache", "jump-%s.txt" % (session[:64] or "default"))


def read_beat(path):
    try:
        with open(path, encoding="utf-8") as fh:
            saved = json.load(fh)
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}      # 0.3.0이 남긴 숫자 한 줄짜리 파일도 여기로 온다


def beat(payload):
    """(마지막 신호, 그 뒤로 지난 초, 작업 중인가, 조용한 지 지난 초).

    transcript의 크기와 수정시각이 그대로면 꼬리를 다시 읽지 않는다. 파일이 안 변했으면
    마지막 줄도 그대로여서 판정이 바뀔 수가 없다.
    """
    path = payload.get("transcript_path")
    try:
        stat = os.stat(path)
    except (OSError, TypeError, ValueError):
        return None, None, False, None

    now = time.time()
    quiet = now - stat.st_mtime
    state = beat_path(payload)
    saved = read_beat(state)
    prev_at = saved.get("at") if isinstance(saved.get("at"), (int, float)) else None

    if saved.get("mtime") == int(stat.st_mtime) and saved.get("size") == stat.st_size:
        kind, at, busy = saved.get("kind"), prev_at, bool(saved.get("busy"))
    else:
        found_kind, found_at, busy = read_tail(path, stat.st_size)
        if found_at is not None and (prev_at is None or found_at > prev_at + 0.5):
            kind, at = found_kind, found_at
        else:
            kind, at = saved.get("kind"), prev_at   # 꼬리 밖으로 밀려난 신호를 지킨다
        try:
            os.makedirs(os.path.dirname(state), exist_ok=True)
            with open(state, "w", encoding="utf-8") as fh:
                json.dump({"kind": kind, "at": at, "busy": busy,
                           "mtime": int(stat.st_mtime), "size": stat.st_size}, fh)
        except OSError:
            pass

    return kind, (None if at is None else now - float(at)), busy, quiet


def frame_of(age, ticks):
    """신호 이후 몇 번째 틱인가. 다 지났으면 None."""
    if age is None or age <= -1:      # 시계가 앞서 있으면 그냥 안 한다
        return None
    frame = max(0, int(age))
    return frame if frame < ticks else None


# --- 상태 판정 -------------------------------------------------------------
def _draw(weights, tick):
    rng = random.Random(tick)
    return rng.choices([n for n, _ in weights], weights=[w for _, w in weights])[0]


def pick_pose(payload, cfg, tick):
    """(포즈, 세로 오프셋, 먼지).

    바탕은 여유가 얼마나 남았는가고, 그 위에 방금 무슨 일이 있었는지를 얹는다.
    최근 것이 이긴다 - 점프·놀람 > 앉기 > 두리번 > 바탕.
    """
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
    kind, age, busy, quiet = beat(payload)
    panicking = worst < thresholds["panic"]

    if panicking:
        # 바닥까지 오면 팔을 들었다 내렸다 한다. 새 그림 없이 이것만으로 다급해 보인다.
        pose = "arms-up" if tick % 2 else "default"
    else:
        band = 0 if worst >= thresholds["wary"] else (1 if worst >= thresholds["alarmed"] else 2)
        # 도구가 도는 동안은 한 칸 위 구간에서 뽑는다. 걱정해서가 아니라 지켜보느라
        # 두리번거리는 것인데, 그림이 넷뿐이라 같은 몸짓으로 둘을 말한다.
        if busy and cfg.get("busy", True):
            band = min(band + 1, len(BANDS) - 1)
        pose = _draw(BANDS[band][1], tick)

    if kind == "prompt" and cfg.get("jump", True):
        frame = frame_of(age, JUMP_TICKS)
        if frame == 0:
            return pose, 1, POOF[tick % len(POOF)]
        if frame == 1:
            return AIRBORNE.get(pose, pose), 0, None
        if frame == 2:
            return pose, 0, None

    if kind == "interrupt" and cfg.get("startle", True):
        if frame_of(age, STARTLE_TICKS) is not None:
            # 하던 걸 멈춰 세운 참이다. 팔을 든 채로 굳는다.
            # 원본에 offset 1은 default에만 붙는다. arms-up을 내리면 없는 프레임이 된다.
            return "arms-up", 0, None

    idle_after = cfg.get("idle", IDLE_AFTER)
    if (idle_after and not busy and not panicking
            and quiet is not None and quiet >= idle_after):
        # 아무 일도 없으면 원본이 쉴 때 도는 순서로 넘어간다. 무작위로 뽑던 것을
        # 멈추고 정해진 주기로 도는 것 자체가 가라앉은 표시다.
        # 웅크린 채로 두지는 않는다 - 웅크리면 몸통 양 끝 한 칸이 잘리는데, 원본은
        # 그 자리를 먼지로 메운다. 먼지 없이 계속 웅크리면 몸이 줄어 보인다.
        return IDLE_CYCLE[tick % len(IDLE_CYCLE)], 0, None

    return pose, 0, None


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


def xdg_config():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def probe_hud():
    pattern = os.path.join(config_dir(), "plugins", "cache", "claude-hud", "claude-hud", "*", "")
    dirs = sorted(glob(pattern), key=os.path.getmtime, reverse=True)
    node = find_node()
    if not dirs or not node:
        return None
    entry = os.path.join(dirs[0], "dist", "index.js")
    return [node, entry] if os.path.exists(entry) else None


def probe_ccstatusline():
    binary = shutil.which("ccstatusline")
    if binary:
        return [binary]
    npx = shutil.which("npx")
    settings = os.path.join(xdg_config(), "ccstatusline", "settings.json")
    if npx and os.path.exists(settings):
        return [npx, "-y", "ccstatusline@latest"]
    return None


def probe_powerline():
    # 전역 실행 파일을 안 만드는 패키지라 설정 파일이 유일한 흔적이다.
    npx = shutil.which("npx")
    marks = [os.path.join(config_dir(), "claude-powerline.json"),
             os.path.join(xdg_config(), "claude-powerline", "config.json")]
    if npx and any(os.path.exists(m) for m in marks):
        return [npx, "-y", "@owloops/claude-powerline@latest"]
    return None


def probe_ccusage():
    binary = shutil.which("ccusage")
    return [binary, "statusline"] if binary else None


# 위에서부터 처음 맞는 것 하나. 흔적이 확실한 것을 앞에 둔다 - 플러그인이 깔려
# 있거나 그 도구의 설정 파일이 있는 쪽이, PATH에 실행 파일만 있는 쪽보다 세다.
PROBES = (probe_hud, probe_ccstatusline, probe_powerline, probe_ccusage)


def autodetect_wrap():
    """설정에 wrap이 없을 때 이미 쓰고 있는 상태줄을 찾아본다. 없으면 감싸지 않는다.

    빠른 형태(설치된 실행 파일)를 먼저 본다. npx로 떨어지는 것은 그 도구를 실제로
    설정한 흔적이 있을 때뿐이다. 안 쓰는 패키지를 매 턴 끌어오면 몇 초씩 태운다.
    """
    for probe in PROBES:
        found = probe()
        if found:
            return found
    return None


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
    command = cfg["wrap"] or autodetect_wrap()
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
