# clawd-statusline

Clawd — the mascot that already ships inside Claude Code — standing in your status line, reacting to how much room you have left. **It keeps whatever status line you already run**, so it costs you nothing to add.

```
 ▐▛███▛█   [Opus] │ my-project git:(main*)
▝▜██████▀  Context ██░░░░░░░░ 22% │ Usage ███░░░░░░░ 30%
  ▝▝ ▝▝    1 CLAUDE.md
```

![Clawd's four poses](docs/poses.png)

## It wraps, it doesn't replace

Claude Code allows exactly one status line command, so a mascot that took that slot would cost you whatever you already run there. This one doesn't. It takes your existing command, feeds it the same stdin JSON, and prints its output to the right of the sprite. `/clawd-statusline:setup` moves your current status line into the `wrap` setting for you.

With nothing configured it goes looking, and takes the first of these it finds:

| Status line | What it looks for | What it runs |
|---|---|---|
| [claude-hud](https://github.com/jarrodwatts/claude-hud) | the plugin in your cache | `node .../dist/index.js` |
| [ccstatusline](https://github.com/sirmalloc/ccstatusline) | the `ccstatusline` binary, else `~/.config/ccstatusline/settings.json` | `ccstatusline`, else `npx -y ccstatusline@latest` |
| [claude-powerline](https://github.com/Owloops/claude-powerline) | `~/.claude/claude-powerline.json` | `npx -y @owloops/claude-powerline@latest` |
| [ccusage](https://ccusage.com/guide/statusline) | the `ccusage` binary | `ccusage statusline` |

An installed binary is always preferred over `npx`. A package only gets pulled through `npx` when
you have actually configured it — having `npx` on your PATH is not on its own a reason to spend a
few seconds a turn on a tool you don't use. Set `wrap` yourself and none of this runs.

With none of them, Clawd stands alone.

## The card

`/clawd-statusline:card` reads the last 90 days of your own transcripts and shows how you
actually use Claude Code. **The status line never reads any of it** — growth lives entirely in
the card, so switching it on changes nothing about how Clawd is drawn.

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

| Remaining | What Clawd does |
|---|---|
| above 50% | mostly stands still, glances left or right now and then |
| 50–25% | glances far more often — restless rather than calm |
| 25–10% | arms up much of the time |
| below 10% | arms up and down every second |

**Only Anthropic's four original poses are used.** Earlier versions drew extra faces — a mouth, a
blink — and that is exactly what made it look like a knock-off. Nothing new is drawn; how worried
Clawd is comes out of which of the four appears and how often.

Movement comes from `refreshInterval: 1`, which re-runs the status line once a second. Drop that key from `settings.json` for a still sprite.

## What Clawd reacts to

A status line never sees your keyboard. Claude Code hands it a JSON payload on stdin and redraws
it on a fixed set of events; the terminal's key and mouse events belong to Claude Code itself.
So everything below is inferred from that payload and from the tail of the transcript — no hooks,
nothing to install.

| You do | How Clawd knows | What he does |
|---|---|---|
| send a prompt | a typed user message appears | crouch, leap, land — one tick each |
| press Esc to stop | `[Request interrupted by user]` lands in the transcript | arms up, body down, frozen for two ticks |
| leave a tool running | the last tool call still has no result | glances around more — one band up from wherever headroom put him |
| walk away | the transcript stops changing for a minute | folds his feet, sits, and holds a single pose |

```
   crouch        jump        land            startle         sit

                ▗▟▛███▛█▄    ▐▛███▛█        ▗▟▛███▛█▄       ▐▛███▛█
  ▐▛███▛█        ▜██████▘   ▝▜██████▀         ▜██████         ▜██████
 ~▜██████~        ▝▝ ▝▝       ▝▝ ▝▝
```

Nothing here is a new drawing. Raised arms, a body dropped one row, two dust characters and the
timing between them are the whole vocabulary, and all four are Anthropic's. Arms up with the body
down is the only frame the jump never uses, which is why the flinch gets it.

Claude Code's own Clawd hops when you click him, playing twelve frames at 60ms. A status line
cannot: `refreshInterval` is capped at one second
([#80290](https://github.com/anthropics/claude-code/issues/80290)), so the hop is compressed to
three, triggered by the closest thing the payload can see — you sending a prompt.

**What is not possible.** Keystrokes never arrive; `vim.mode` is the single exception, since it is
in the payload and toggling it forces a redraw. Nothing can be shown during a permission prompt,
the help menu or autocomplete, because Claude Code hides the status line while those are up. And
switching permission mode triggers a redraw without saying which mode you switched to.

The transcript tail is read only when the file's size or mtime changes, so a session sitting idle
costs one `stat` per tick. Measured at 0.027s a run against a 6MB transcript, the same as before
any of this existed.

## Configuration

Everything is optional. Create `~/.claude/clawd-statusline.json` (or under `$CLAUDE_CONFIG_DIR`) with only the keys you want to change, or run `/clawd-statusline:configure`.

| Key | Default | Meaning |
|---|---|---|
| `wrap` | auto-detect | Command whose output renders to the right. A string runs through the shell, an array runs directly. |
| `gap` | `2` | Blank columns between sprite and wrapped output. |
| `thresholds` | `{"wary": 50, "alarmed": 25, "panic": 10}` | Where the pose changes. Higher means Clawd worries earlier. |
| `jump` | `true` | Hop for three ticks after you send a prompt. |
| `startle` | `true` | Flinch for two ticks after you interrupt with Esc. |
| `busy` | `true` | Glance around more while a tool is still running. |
| `idle` | `60` | Sit down after this many quiet seconds. `0` never sits. |

```json
{
  "wrap": ["/usr/local/bin/node", "/path/to/your/statusline.js"],
  "gap": 3,
  "thresholds": { "wary": 60, "alarmed": 30, "panic": 15 },
  "jump": false,
  "idle": 0
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

Clawd is Anthropic's, not mine. The character, its four poses, and the terminal fallbacks are all reproduced from Claude Code's own renderer, where the sprite is drawn as quadrant blocks over a black field so the unfilled quadrants read as eyes. Nothing has been added to the character itself.

Anthropic has never documented the character, and requests to make the CLI avatar configurable were closed as `not_planned`. This project is not affiliated with or endorsed by Anthropic.

## License

MIT
