import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import scan


def assistant(mid, out=100, cin=10, cc=20, cr=9999, tools=(), ts="2026-09-01T05:00:00.000Z"):
    return json.dumps({
        "type": "assistant", "sessionId": "s1", "timestamp": ts, "isSidechain": False,
        "requestId": "r-" + mid,
        "message": {
            "id": mid, "model": "claude-opus-5",
            "usage": {"output_tokens": out, "input_tokens": cin,
                      "cache_creation_input_tokens": cc, "cache_read_input_tokens": cr},
            "content": [{"type": "tool_use", "name": t} for t in tools],
        },
    })


class TestScan(unittest.TestCase):
    def test_food_excludes_cache_reads(self):
        raw = scan.new_raw()
        scan.scan_lines([assistant("m1")], raw, set())
        self.assertEqual(raw["food"], 130)

    def test_one_call_split_across_lines_counts_once(self):
        raw = scan.new_raw()
        scan.scan_lines([assistant("m1"), assistant("m1"), assistant("m1")], raw, set())
        self.assertEqual(raw["food"], 130)
        self.assertEqual(raw["calls"], 1)

    def test_tools_are_split_into_outer_and_total(self):
        raw = scan.new_raw()
        scan.scan_lines([assistant("m1", tools=["Bash", "mcp__notion__fetch", "WebSearch"])],
                        raw, set())
        self.assertEqual(raw["total_tools"], 3)
        self.assertEqual(raw["outer_tools"], 2)

    def test_night_calls_use_local_hours(self):
        raw = scan.new_raw()
        scan.scan_lines([assistant("m1", ts="2026-09-01T18:00:00.000Z")], raw, set())
        self.assertEqual(raw["day_calls"] + raw["night_calls"], 1)

    def test_compact_and_sidechain_records_are_counted(self):
        raw = scan.new_raw()
        scan.scan_lines([
            json.dumps({"type": "system", "subtype": "compact_boundary", "sessionId": "s1"}),
            json.dumps({"type": "assistant", "isSidechain": True, "sessionId": "s1",
                        "timestamp": "2026-09-01T05:00:00.000Z",
                        "message": {"id": "x1", "usage": {"output_tokens": 1}}}),
        ], raw, set())
        self.assertEqual(raw["compacts"], 1)
        self.assertEqual(raw["sidechain"], 1)

    def test_resuming_from_an_offset_does_not_double_count(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.jsonl")
            with open(p, "w") as f:
                f.write(assistant("m1") + "\n")
            first, off, last = scan.scan_file(p)
            with open(p, "a") as f:
                f.write(assistant("m2") + "\n")
            second, off2, _ = scan.scan_file(p, off, last)
            self.assertEqual(first["food"], 130)
            self.assertEqual(second["food"], 130)
            self.assertGreater(off2, off)


if __name__ == "__main__":
    unittest.main()
