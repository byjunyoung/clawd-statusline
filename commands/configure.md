---
description: Change what clawd-statusline wraps, its spacing, and its pose thresholds
allowed-tools: Bash, Read, Edit, AskUserQuestion
---

Edit `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/clawd-statusline.json`. Create it only if a change is actually requested - the plugin runs on defaults without it.

## Fields

| Key | Default | Meaning |
|---|---|---|
| `wrap` | absent | Command whose output renders to the right of Clawd. A string runs through the shell; an array runs directly. Absent means auto-detect claude-hud, and stand alone if it is not there. |
| `gap` | `2` | Blank columns between the sprite and the wrapped output. |
| `thresholds` | `{"wary": 50, "alarmed": 25, "panic": 10}` | Remaining-percentage cutoffs where the pose changes. Higher numbers mean Clawd worries earlier. |

## How to work

Read the file first and keep the keys that are already there - a partial file is valid, and unknown keys are ignored rather than rejected.

Ask which of the three the user wants to change before writing anything, unless they already said. Then verify with a sample payload and show the result:

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SCRIPT=$(ls -td "$CLAUDE_DIR"/plugins/cache/*/clawd-statusline/*/ 2>/dev/null | head -1)scripts/statusline-clawd.py
for pct in 80 40 18 5; do
  echo "--- remaining ${pct}% ---"
  echo "{\"session_id\":\"cfg\",\"context_window\":{\"remaining_percentage\":$pct,\"used_percentage\":$((100-pct))},\"rate_limits\":{}}" | "$SCRIPT"
done
```

Changes apply on the next status line render, so there is nothing to restart.
