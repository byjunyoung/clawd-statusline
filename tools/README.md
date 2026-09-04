# tools

`stats.ANCHORS`와 `grow.BASE`를 다시 맞출 때 쓰는 측정 스크립트. 플러그인 동작과는 무관하다.

```bash
python3 tools/measure_usage.py    # 먹이 총량, 일별 분포, 시간대, 모델
python3 tools/measure_traits.py   # 컴팩트, 서브에이전트, 도구 분포, 세션당 턴
```

둘 다 `~/.claude/projects`의 대화 기록만 읽고 아무것도 쓰지 않는다.
