# tools

플러그인 동작과는 무관한 보조 스크립트.

## 측정

`stats.ANCHORS`와 `grow.BASE`를 다시 맞출 때 쓴다.

```bash
python3 tools/measure_usage.py    # 먹이 총량, 일별 분포, 시간대, 모델
python3 tools/measure_traits.py   # 컴팩트, 서브에이전트, 도구 분포, 세션당 턴
```

둘 다 `~/.claude/projects`의 대화 기록만 읽고 아무것도 쓰지 않는다.

## README 포즈 그림

`docs/poses.png`를 다시 만든다. 포즈 표를 손으로 옮겨 적지 않고 `statusline-clawd.py`에서
읽어 오므로 그림이 코드보다 뒤처지지 않는다. 0.3.0까지 실제로 뒤처져 있었다 — 지운 포즈
넷을 README가 계속 "new"라고 광고하고 있었다.

```bash
python3 tools/render_poses.py     # docs/poses.html + 필요한 창 크기를 찍어준다
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --force-device-scale-factor=2 --hide-scrollbars --default-background-color=1c1917ff \
  --screenshot=docs/poses.png --window-size=<위에서 찍어준 크기> docs/poses.html
rm docs/poses.html
```
