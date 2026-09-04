# -*- coding: utf-8 -*-
"""터미널에서 사람이 낸 신호에 Clawd가 어떻게 반응하는가.

새 그림은 없다. 넷 중 어느 것을 언제 뽑느냐와 세로 오프셋이 전부다.
"""
import importlib.util
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timezone

spec = importlib.util.spec_from_file_location(
    "sl", os.path.join(os.path.dirname(__file__), "..", "scripts", "statusline-clawd.py"))
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)

CFG = dict(sl.DEFAULTS)


def iso(epoch):
    # 실제 기록은 밀리초까지 있다. 초로 잘라 쓰면 점프 프레임이 한 칸 밀린다.
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def prompt(epoch, text="hello"):
    return {"type": "user", "timestamp": iso(epoch),
            "message": {"role": "user", "content": text}}


def interrupt(epoch):
    return prompt(epoch, "[Request interrupted by user]")


def tool_call(epoch):
    return {"type": "assistant", "timestamp": iso(epoch),
            "message": {"role": "assistant",
                        "content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}


def tool_done(epoch):
    return {"type": "user", "timestamp": iso(epoch), "toolUseResult": {"ok": True},
            "message": {"role": "user", "content": [{"type": "tool_result"}]}}


def said(epoch):
    return {"type": "assistant", "timestamp": iso(epoch),
            "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]}}


class TestSignalKind(unittest.TestCase):
    def test_a_typed_prompt_is_a_prompt(self):
        self.assertEqual(sl.signal_kind(prompt(0)), "prompt")

    def test_an_interrupt_is_not_a_prompt(self):
        # 이게 이 파일의 이유다. 예전에는 Esc로 멈추면 Clawd가 좋다고 뛰었다.
        self.assertEqual(sl.signal_kind(interrupt(0)), "interrupt")

    def test_an_interrupt_inside_a_content_list_is_caught_too(self):
        rec = {"type": "user", "timestamp": iso(0), "message": {"role": "user", "content": [
            {"type": "text", "text": "[Request interrupted by user]"}]}}
        self.assertEqual(sl.signal_kind(rec), "interrupt")

    def test_tool_results_and_meta_and_subagents_are_not_signals(self):
        for rec in (tool_done(0),
                    dict(prompt(0), isMeta=True),
                    dict(prompt(0), isSidechain=True),
                    prompt(0, "   "),
                    said(0)):
            self.assertIsNone(sl.signal_kind(rec))


class TestWorking(unittest.TestCase):
    def line(self, rec):
        return json.dumps(rec).encode()

    def test_an_unanswered_tool_call_means_busy(self):
        self.assertTrue(sl.working([self.line(prompt(0)), self.line(tool_call(1))]))

    def test_a_result_ends_it(self):
        self.assertFalse(sl.working([self.line(tool_call(1)), self.line(tool_done(2))]))

    def test_plain_talk_is_not_busy(self):
        self.assertFalse(sl.working([self.line(prompt(0)), self.line(said(1))]))


class Session(unittest.TestCase):
    """가짜 대화 기록 하나를 놓고 pick_pose를 돌린다."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp
        self.path = os.path.join(self.tmp, "t.jsonl")
        self.n = 0

    def tearDown(self):
        if self.old is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, records, quiet=0.0):
        with io.open(self.path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
        if quiet:
            old = time.time() - quiet
            os.utime(self.path, (old, old))

    def payload(self, **extra):
        self.n += 1
        out = {"session_id": "s%d" % self.n, "transcript_path": self.path}
        out.update(extra)
        return out

    def pose(self, tick=7, cfg=None, **extra):
        return sl.pick_pose(self.payload(**extra), cfg or CFG, tick)


class TestPrompt(Session):
    def test_a_fresh_prompt_crouches_then_leaps_then_lands(self):
        seen = []
        for age in (0.2, 1.2, 2.2):
            self.write([prompt(time.time() - age)])
            seen.append(self.pose())
        self.assertEqual(seen[0][1], 1)               # 웅크림
        self.assertIsNotNone(seen[0][2])              # 발밑 먼지
        self.assertEqual(seen[1][0], "arms-up")       # 도약
        self.assertEqual(seen[1][1], 0)
        self.assertEqual(seen[2][1], 0)               # 착지

    def test_an_old_prompt_does_not_jump(self):
        self.write([prompt(time.time() - 30)], quiet=30)
        self.assertEqual(self.pose()[1], 0)


class TestInterrupt(Session):
    def test_stopping_is_read_as_an_interrupt_not_a_prompt(self):
        # 이 한 줄이 이 반응의 핵심이다. 예전에는 여기서 "prompt"가 나와 뛰었다.
        self.write([interrupt(time.time() - 0.2)])
        self.assertEqual(sl.beat(self.payload())[0], "interrupt")

    def test_stopping_flinches(self):
        self.write([interrupt(time.time() - 0.2)])
        self.assertEqual(self.pose(), ("arms-up", 1, None))

    def test_it_never_kicks_up_dust(self):
        # 먼지는 뛰기 직전 웅크릴 때만 난다. 멈춰 세운 건 뛰는 게 아니다.
        self.write([interrupt(time.time() - 0.2)])
        for tick in range(12):
            pose, offset, dust = self.pose(tick=tick)
            self.assertEqual((pose, offset), ("arms-up", 1))
            self.assertIsNone(dust)

    def test_the_startle_wears_off(self):
        self.write([interrupt(time.time() - 5)], quiet=5)
        self.assertNotEqual(self.pose()[:2], ("arms-up", 1))

    def test_startle_can_be_switched_off(self):
        self.write([interrupt(time.time() - 0.2)])
        cfg = dict(CFG, startle=False)
        pose, offset, dust = self.pose(cfg=cfg)
        self.assertEqual(offset, 0)      # 꺼도 프롬프트로 오해해 뛰지는 않는다
        self.assertIsNone(dust)


class TestIdle(Session):
    def test_going_quiet_sits_down(self):
        self.write([prompt(time.time() - 300), said(time.time() - 300)], quiet=300)
        self.assertEqual(self.pose(), ("default", 1, None))

    def test_sitting_still_means_the_same_pose_every_tick(self):
        self.write([said(time.time() - 300)], quiet=300)
        self.assertEqual({self.pose(tick=t) for t in range(20)}, {("default", 1, None)})

    def test_a_running_tool_is_not_idle(self):
        # 오래 도는 Bash는 파일을 안 건드린다. 조용하다고 앉으면 안 된다.
        self.write([prompt(time.time() - 300), tool_call(time.time() - 300)], quiet=300)
        self.assertEqual(self.pose()[1], 0)

    def test_it_does_not_sit_when_room_is_nearly_gone(self):
        self.write([said(time.time() - 300)], quiet=300)
        low = {"context_window": {"remaining_percentage": 3}}
        self.assertEqual(self.pose(**low)[1], 0)

    def test_idle_can_be_switched_off(self):
        self.write([said(time.time() - 300)], quiet=300)
        self.assertEqual(self.pose(cfg=dict(CFG, idle=0))[1], 0)


class TestBusy(Session):
    def glances(self, cfg):
        out = 0
        for tick in range(200):
            self.write([prompt(time.time() - 300), tool_call(time.time() - 300)], quiet=300)
            if sl.pick_pose(self.payload(), cfg, tick)[0] != "default":
                out += 1
        return out

    def test_a_running_tool_makes_clawd_glance_around_more(self):
        self.assertGreater(self.glances(CFG), self.glances(dict(CFG, busy=False)))

    def test_it_still_only_uses_the_four(self):
        for tick in range(60):
            self.write([tool_call(time.time() - 300)], quiet=300)
            self.assertIn(sl.pick_pose(self.payload(), CFG, tick)[0], sl.POSES)


class TestNoTranscript(Session):
    def test_a_missing_transcript_changes_nothing(self):
        pose, offset, dust = sl.pick_pose({"session_id": "x"}, CFG, 3)
        self.assertIn(pose, sl.POSES)
        self.assertEqual((offset, dust), (0, None))


if __name__ == "__main__":
    unittest.main()
