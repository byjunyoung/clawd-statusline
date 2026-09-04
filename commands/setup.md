---
description: Configure clawd-statusline as your status line
allowed-tools: Bash, Read, Edit
---

Set up clawd-statusline as the user's status line. Work through the steps in order and stop at the first one that fails, telling the user what went wrong.

**The most important rule: do not take away a status line the user already has.** If one is configured, it gets wrapped, not replaced.

## Step 1 - locate the plugin and the interpreter

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
# 낡은 버전 폴더가 캐시에 남아 있을 수 있다. 스크립트가 실제로 있는 것 중 최신을 고른다.
SCRIPT=$(for d in "$CLAUDE_DIR"/plugins/cache/*/clawd-statusline/*/; do
  [ -f "$d/scripts/statusline-clawd.py" ] && echo "$d/scripts/statusline-clawd.py"
done | sort -V | tail -1)
echo "script: $SCRIPT"; test -f "$SCRIPT" && echo "found" || echo "MISSING"
command -v python3 || echo "NO PYTHON3"
```

If the script is missing, the plugin did not install cleanly - tell the user to run `/plugin` and reinstall. If `python3` is missing, tell them to install Python 3.9 or newer; do not continue.

## Step 2 - read the current status line

```bash
python3 -c "
import json, os
p = os.path.join(os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude'), 'settings.json')
d = json.load(open(p)) if os.path.exists(p) else {}
print(json.dumps(d.get('statusLine'), ensure_ascii=False))
"
```

Three cases:

| Current `statusLine` | What to do |
|---|---|
| absent | Nothing to wrap. Clawd looks for claude-hud, ccstatusline, claude-powerline and ccusage; with none of them it stands alone. |
| already this plugin's script | Already set up. Report that and stop - do not write anything. |
| any other command | **Move that command into `wrap`** so it keeps rendering to the right of Clawd. |

## Step 3 - write the config, if there is something to wrap

Only when Step 2 found a third-party command. Write `$CLAUDE_DIR/clawd-statusline.json`, preserving any keys the file already has:

```json
{ "wrap": "<the exact command string from the old statusLine>" }
```

## Step 4 - point settings.json at Clawd

Back up first, then set `statusLine`. Keep every other key in the file untouched.

```json
{
  "statusLine": {
    "type": "command",
    "command": "<absolute path to scripts/statusline-clawd.py from Step 1>",
    "refreshInterval": 1
  }
}
```

`refreshInterval: 1` is what makes Clawd move between turns. Drop it if the user prefers a still sprite.

On Windows the shebang does not run, so use `python <path>` as the command instead.

## Step 5 - switch growth on

`/clawd-statusline:card` shows a level and five stats read out of your own history.

```bash
python3 "$(dirname "$SCRIPT")/growth_cli.py" start
```

This reads the last 90 days of your own transcripts and sets the level that history earned,
so nobody starts at zero. It takes a few seconds if there is a lot of history. The hooks that
keep it fed come with the plugin - there is nothing to wire up.

Read the level out of the returned JSON and tell the user.
Skipping this step is fine: the status line never reads the ledger, so with or without it Clawd
is drawn exactly the same way.

## Step 6 - verify before reporting success

Feed the script a sample payload and show the user the actual output:

```bash
echo '{"session_id":"setup","context_window":{"remaining_percentage":80,"used_percentage":20},"rate_limits":{}}' | "$SCRIPT"
python3 "$(dirname "$SCRIPT")/growth_cli.py" card
```

The sprite must appear, with whatever was wrapped to the right of it, and the card must show a
level. Then tell the user three things: the status line takes effect on the next Claude Code
start, the backup from Step 4 is how they undo this, and `/clawd-statusline:card` is where the
level and stats live.
