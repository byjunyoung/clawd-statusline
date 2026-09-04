# clawd-statusline

Clawd — the mascot that already ships inside Claude Code — standing in your status line, reacting to how much room you have left.

```
 ▐▛███▛█   [Opus] │ my-project git:(main*)
▝▜██████▀  Context ██░░░░░░░░ 22% │ Usage ███░░░░░░░ 30%
  ▝▝ ▝▝    1 CLAUDE.md
```

![Clawd's eight poses](docs/poses.png)

## The card

`/clawd-statusline:card` reads the last 90 days of your own transcripts and shows how you
actually use Claude Code. It is the only thing 0.3.0 adds; **the status line itself is byte for
byte what it was in 0.2.0.**

```
  Clawd  Lv.36

   ▐▛███▛█    FED    245.0M
  ▝▜██████▀   NEXT   8.3M to Lv.37
    ▝▝ ▝▝     AGE    177 days

  APPETITE  ████████░░   75
  REACH     ████████░░   76
  STAMINA   ███████░░░   68
  PACK      ██░░░░░░░░   24
  NOCTURNE  █░░░░░░░░░    9
```

The level comes from tokens spent. Output, new input and cache writes count as food; cache reads
do not, since locally they came to 12 billion tokens and would drown every other signal. The plan
you are on scales the curve at half strength — Pro 0.45, Max 5x 1.0, Max 20x 2.0 — so higher
plans still climb faster, but not by the four-to-one raw token counts would give.

The five stats measure how you work. `APPETITE` tokens per active day, `REACH` share of tool
calls that leave the machine, `STAMINA` how long you hold one conversation, `PACK` how often you
send subagents out, `NOCTURNE` share of calls between 22:00 and 06:00. Push one past 90 and it
earns a title: `GLUTTON`, `ROAMER`, `MARATHON`, `LEGION`, `OWL`.

Levelling used to unlock hats for Clawd to wear. That is gone — on a nine-cell sprite a hat is a
small coloured blob, and seven of them across sixty-five levels never felt like a reward.
`docs/growth.md` has the whole account, including the three creature designs that failed before
it.

**Skipping it is fine.** Never run setup's growth step and nothing is written, nothing is read,
and the status line behaves exactly as it always has.

## It wraps, it doesn't replace

Claude Code allows exactly one status line command, so a mascot that took that slot would cost you whatever you already run there. This one doesn't. It takes your existing command, feeds it the same stdin JSON, and prints its output to the right of the sprite. `/clawd-statusline:setup` moves your current status line into the `wrap` setting for you.

With nothing configured it looks for [claude-hud](https://github.com/jarrodwatts/claude-hud) and wraps that. With neither, Clawd stands alone.

## Install

```
/plugin marketplace add byjunyoung/clawd-statusline
/plugin install clawd-statusline
/clawd-statusline:setup
```

Or from the shell:

```bash
claude plugin marketplace add byjunyoung/clawd-statusline
claude plugin install clawd-statusline@clawd-statusline
```

Needs Python 3.9+, standard library only. The status line takes effect on the next Claude Code start.

## Poses

The pose follows whichever is worse — context headroom or rate-limit headroom.

| Remaining | Pose |
|---|---|
| above 50% | `default`, `look-left`, `look-right`, `blink`, `arms-up`, shuffled every second |
| 50–25% | `wary` |
| 25–10% | `alarmed` |
| below 10% | `panic` — arms going up and down |

Movement comes from `refreshInterval: 1`, which re-runs the status line once a second. Drop that key from `settings.json` for a still sprite.

## Jump

Claude Code's own Clawd hops when you click him. A status line command never learns about the click - all it is handed is a JSON payload on stdin, and the terminal's mouse events belong to Claude Code itself. So the hop is here, triggered by the closest thing the payload can see: you sending a prompt.

```
   crouch        jump        land
                ▗▟▛███▛█▄    ▐▛███▛█
  ▐▛███▛█        ▜██████▘   ▝▜██████▀
 ~▜██████~        ▝▝ ▝▝       ▝▝ ▝▝
```

One tick each, read from the transcript rather than any hook, so nothing needs installing. Clawd stays put below the `wary` threshold - the same way the original ignores a click while an animation is already running. Set `"jump": false` to turn it off.

The original plays twelve frames at 60ms. A status line cannot: `refreshInterval` is capped at one second ([#80290](https://github.com/anthropics/claude-code/issues/80290)), so the sequence is compressed to three.

## Configuration

Everything is optional. Create `~/.claude/clawd-statusline.json` (or under `$CLAUDE_CONFIG_DIR`) with only the keys you want to change, or run `/clawd-statusline:configure`.

| Key | Default | Meaning |
|---|---|---|
| `wrap` | auto-detect | Command whose output renders to the right. A string runs through the shell, an array runs directly. |
| `gap` | `2` | Blank columns between sprite and wrapped output. |
| `thresholds` | `{"wary": 50, "alarmed": 25, "panic": 10}` | Where the pose changes. Higher means Clawd worries earlier. |
| `jump` | `true` | Hop for three ticks after you send a prompt. |

```json
{
  "wrap": ["/usr/local/bin/node", "/path/to/your/statusline.js"],
  "gap": 3,
  "thresholds": { "wary": 60, "alarmed": 30, "panic": 15 },
  "jump": false
}
```

## Terminals

Truecolor terminals get the sprite in Clawd's own `rgb(215,119,87)`. Elsewhere it falls back to ANSI bright red on black, the same pair Claude Code's own ANSI theme uses. Apple Terminal renders quadrant blocks differently, so it gets the alternate silhouette Claude Code carries for exactly that case — body painted as background, eyes punched through in the foreground.

Windows is untested. Two things are known: the shebang won't run, so set the command to `python <path>`, and the legacy console host doesn't accept ANSI.

## Cost

The wrapped command's output is cached under `clawd-cache/`, keyed partly on the transcript's size and mtime. A once-a-second timer re-run therefore hits the cache instead of spawning your status line process again — measured at 0.10s cold, 0.02s warm against claude-hud.

## Uninstall

`/clawd-statusline:setup` backs up `settings.json` before it writes; restore that file and remove the plugin.

## Where Clawd comes from

Clawd is Anthropic's, not mine. The character, the four original poses, and the terminal fallbacks are all reproduced from Claude Code's own renderer, where the sprite is drawn as quadrant blocks over a black field so the unfilled quadrants read as eyes. The body's second row works the same way, which is where the four new poses get their mouths.

Anthropic has never documented the character, and requests to make the CLI avatar configurable were closed as `not_planned`. This project is not affiliated with or endorsed by Anthropic.

## License

MIT
