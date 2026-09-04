# -*- coding: utf-8 -*-
"""장부.

플러그인 데이터 폴더가 아니라 설정 폴더에 둔다. 플러그인을 지웠다 다시 깔아도
크리처는 살아 있어야 한다.

쓰기는 훅만 한다. 상태줄은 읽기만 한다.
"""

import json
import os
import tempfile
import time

VERSION = 1
_LOCK_TIMEOUT = 5.0


def config_dir():
    return os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")


def home():
    return os.path.join(config_dir(), "clawd-statusline")


def path():
    return os.path.join(home(), "state.json")


def load():
    try:
        with open(path(), encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def save(state):
    """임시 파일에 쓰고 원자적으로 바꿔치기한다. 도중에 죽어도 헌 장부가 남는다."""
    target = path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _acquire():
    """디렉터리 생성은 원자적이라 잠금으로 쓰기 좋다. 죽은 잠금은 시간이 지나면 걷어낸다."""
    lock = path() + ".lock"
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    deadline = time.time() + _LOCK_TIMEOUT
    while True:
        try:
            os.mkdir(lock)
            return lock
        except OSError:
            if time.time() > deadline:
                try:
                    if time.time() - os.path.getmtime(lock) > _LOCK_TIMEOUT:
                        os.rmdir(lock)
                        continue
                except OSError:
                    pass
                return None
            time.sleep(0.05)


def update(fn):
    """잠금을 잡고 읽어 fn(state)을 적용한 뒤 저장한다. fn은 상태를 제자리에서 고친다."""
    lock = _acquire()
    try:
        state = load() or {}
        fn(state)
        save(state)
        return state
    finally:
        if lock:
            try:
                os.rmdir(lock)
            except OSError:
                pass


def prune_cursors(state, now, days=7):
    cutoff = now - days * 86400
    state["cursors"] = {k: v for k, v in (state.get("cursors") or {}).items()
                        if (v or {}).get("seenAt", 0) >= cutoff}


def blank_state():
    """새 장부. 크리처가 아니라 Clawd 하나를 키운다."""
    return {
        "version": VERSION,
        "startedAt": int(time.time()), "firstTokenDate": "", "plan": "",
        "food": 0, "level": 1,
        "stats": {"appetite": 0, "reach": 0, "stamina": 0, "pack": 0, "nocturne": 0},
        "statsComputedAt": 0, "lastSeenAt": int(time.time()),
        "worn": {"hat": "none", "hold": "none", "friend": "none"},
        "cursors": {},
    }
