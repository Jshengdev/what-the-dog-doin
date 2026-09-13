# wtdd/hue

Philips Hue over local CLIP v2. `python -m wtdd.hue probe | pair | lights | read <light> | set <light> --on/--off [--bri N] [--xy x,y] | signal <light> --seconds N | zone <name> --on/--off [--bri N]`. Every call is one row in `ledger.jsonl`; every PUT is followed by a GET read-back that must match or the row fails.

`zones.json` is a placeholder: Johnny must fill each zone's `lights` with full light ids from `python -m wtdd.hue lights` (zone a is the first 1.5 m of the corridor, b the next, c the last; see docs/ARCHITECTURE.md section 4). `zone` refuses to run on an empty zone.

`test_stub.py` is test-only: a local HTTPS fake bridge that exercises request shaping, the read-back rule, bad key, rate limit, and the signal schema probe without a real bridge. Run `python -m wtdd.hue.test_stub`.
