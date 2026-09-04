import json, os, glob, collections, datetime
root = os.path.expanduser("~/.claude/projects")
files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
KST = datetime.timezone(datetime.timedelta(hours=9))
tools = collections.Counter(); mcp = collections.Counter()
sidechain_msgs = 0; compact_marks = collections.Counter()
turns_per_session = collections.Counter(); sess_span = {}
user_prompt_len = []; interrupts = 0; keys_seen = collections.Counter()
subagent_calls = 0; sessions = set(); projects = set()
seen_msg = set()
for f in files:
    projects.add(os.path.basename(os.path.dirname(f)))
    try: fh = open(f, "rb")
    except OSError: continue
    with fh:
        for line in fh:
            try: rec = json.loads(line)
            except Exception: continue
            t = rec.get("type"); sid = rec.get("sessionId")
            if sid: sessions.add(sid)
            for k in rec.keys(): keys_seen[k] += 1
            if rec.get("isSidechain"): sidechain_msgs += 1
            if rec.get("isCompactSummary"): compact_marks["isCompactSummary"] += 1
            if rec.get("subtype"): compact_marks["subtype:" + str(rec.get("subtype"))] += 1
            if t == "assistant":
                msg = rec.get("message") or {}
                mid = msg.get("id")
                if mid and mid in seen_msg: continue
                if mid: seen_msg.add(mid)
                if sid: turns_per_session[sid] += 1
                for blk in (msg.get("content") or []):
                    if isinstance(blk, dict) and blk.get("type") == "tool_use":
                        nm = blk.get("name", "?")
                        tools[nm] += 1
                        if nm.startswith("mcp__"): mcp[nm.split("__")[1] if "__" in nm else nm] += 1
                        if nm in ("Task", "Agent"): subagent_calls += 1
            elif t == "user":
                msg = rec.get("message") or {}
                c = msg.get("content")
                if isinstance(c, str):
                    user_prompt_len.append(len(c))
                    if "[Request interrupted" in c or "interrupted by user" in c: interrupts += 1
                elif isinstance(c, list):
                    for blk in c:
                        if isinstance(blk, dict) and blk.get("type") == "text":
                            txt = blk.get("text", ""); user_prompt_len.append(len(txt))
                            if "[Request interrupted" in txt or "interrupted by user" in txt: interrupts += 1
print("sessions", len(sessions), "projects", len(projects))
print("compact marks:", dict(compact_marks))
print("sidechain msgs:", sidechain_msgs, "Task/Agent calls:", subagent_calls)
tv = turns_per_session.values(); tv = sorted(tv)
print("turns/session: n", len(tv), "median", tv[len(tv)//2] if tv else 0, "p90", tv[int(len(tv)*.9)] if tv else 0, "max", tv[-1] if tv else 0)
print("top tools:", tools.most_common(18))
print("edit-ish", sum(tools[k] for k in ("Edit","Write","NotebookEdit","MultiEdit")), "read-ish", sum(tools[k] for k in ("Read","Grep","Glob","LS")), "bash", tools["Bash"], "web", tools["WebSearch"]+tools["WebFetch"], "mcp total", sum(mcp.values()))
print("mcp by server:", mcp.most_common(10))
pl = sorted(user_prompt_len)
print("user text blocks", len(pl), "median len", pl[len(pl)//2] if pl else 0, "p90", pl[int(len(pl)*.9)] if pl else 0)
print("interrupt markers:", interrupts)
print("record keys:", [k for k,_ in keys_seen.most_common(30)])
