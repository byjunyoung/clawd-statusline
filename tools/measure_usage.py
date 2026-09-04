import json, os, glob, collections, datetime
root = os.path.expanduser("~/.claude/projects")
files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
seen = set(); n_rec = 0
tot = collections.Counter(); by_month = collections.defaultdict(collections.Counter)
by_hour = collections.Counter(); by_model = collections.Counter(); by_day = collections.defaultdict(collections.Counter)
first_ts = None; last_ts = None
KST = datetime.timezone(datetime.timedelta(hours=9))
for f in files:
    try:
        fh = open(f, "rb")
    except OSError:
        continue
    with fh:
        for line in fh:
            if b'"type":"assistant"' not in line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            mid = msg.get("id"); u = msg.get("usage") or {}
            if not mid or mid in seen:
                continue
            seen.add(mid); n_rec += 1
            ts = rec.get("timestamp") or ""
            try:
                dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(KST)
            except Exception:
                continue
            first_ts = min(first_ts, dt) if first_ts else dt
            last_ts = max(last_ts, dt) if last_ts else dt
            o = u.get("output_tokens") or 0; i = u.get("input_tokens") or 0
            cc = u.get("cache_creation_input_tokens") or 0; cr = u.get("cache_read_input_tokens") or 0
            for c in (tot, by_month[dt.strftime("%Y-%m")], by_day[dt.strftime("%Y-%m-%d")]):
                c["out"] += o; c["in"] += i; c["cc"] += cc; c["cr"] += cr; c["calls"] += 1
            by_hour[dt.hour] += 1
            by_model[msg.get("model", "?")] += o
print("files", len(files), "distinct messages", n_rec, "span", first_ts.date() if first_ts else None, "->", last_ts.date() if last_ts else None)
print("TOTAL", dict(tot))
print("food(out+in+cc) =", tot["out"]+tot["in"]+tot["cc"], " cache_read =", tot["cr"])
for m in sorted(by_month):
    c = by_month[m]; print(m, "food", c["out"]+c["in"]+c["cc"], "out", c["out"], "calls", c["calls"])
days = sorted(by_day)
foods = sorted((by_day[d]["out"]+by_day[d]["in"]+by_day[d]["cc"]) for d in days)
print("active days", len(days), "food/day median", foods[len(foods)//2], "p90", foods[int(len(foods)*0.9)], "max", foods[-1])
print("by hour (KST, calls):", " ".join(f"{h}:{by_hour[h]}" for h in range(24)))
night = sum(v for h, v in by_hour.items() if h >= 22 or h < 6)
print("night share", round(night/max(1, sum(by_hour.values())), 3))
print("by model (out tokens):", dict(by_model))
