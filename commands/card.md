---
description: Show how you actually use Claude Code - level, tokens, and five stats
allowed-tools: Bash
---

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
# 낡은 버전 폴더가 캐시에 남아 있을 수 있다. 스크립트가 실제로 있는 것 중 최신을 고른다.
ROOT=$(for d in "$CLAUDE_DIR"/plugins/cache/*/clawd-statusline/*/; do
  [ -f "$d/scripts/growth_cli.py" ] && echo "$d"
done | sort -V | tail -1)
python3 "$ROOT/scripts/growth_cli.py" card
```

Show the output as it is. Do not summarise or rewrite it.
If it says growth has not started, point at `/clawd-statusline:setup`.
