---
description: Change what Clawd is wearing
allowed-tools: Bash, AskUserQuestion
---

Clawd wears one thing per slot: `hat`, `hold`, `friend`. Only unlocked things can be worn.

Read what is available first:

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
# 낡은 버전 폴더가 캐시에 남아 있을 수 있다. 스크립트가 실제로 있는 것 중 최신을 고른다.
ROOT=$(for d in "$CLAUDE_DIR"/plugins/cache/*/clawd-statusline/*/; do
  [ -f "$d/scripts/growth_cli.py" ] && echo "$d"
done | sort -V | tail -1)
python3 "$ROOT/scripts/growth_cli.py" json
```

If the user named a slot and an item, put it on. If not, show what each slot has open and
ask which they want. Hats unlock by level; friends only by a stat title, so a slot with
nothing in it is not a bug - say what would open it.

```bash
python3 "$ROOT/scripts/growth_cli.py" wear <hat|hold|friend> <name>
```

Then show the result so they can see it:

```bash
python3 "$ROOT/scripts/growth_cli.py" card
```

The status line picks it up on its next redraw.
