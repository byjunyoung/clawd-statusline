---
description: Show Clawd's level, stats, and what is unlocked
allowed-tools: Bash
---

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
ROOT=$(ls -td "$CLAUDE_DIR"/plugins/cache/*/clawd-statusline/*/ 2>/dev/null | head -1)
python3 "$ROOT/scripts/growth_cli.py" card
```

Show the output as it is. Do not summarise or rewrite it.
If it says growth has not started, point at `/clawd-statusline:setup`.
