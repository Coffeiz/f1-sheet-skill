---
name: f1-charts-en
description: Render F1 charts from OpenF1 public data — practice / qualifying / race lap-gap charts, long-run speed chart, long-run degradation trajectory. Use when the user wants a chart for a session, or asks who was fastest in a session, how big the qualifying gaps were, or who has the best long-run pace.
---

# F1 Charts (OpenF1 → lap charts)

Pull lap-by-lap data from the OpenF1 public API and render dark-theme side-by-side charts. **One chart = one script**; five templates, each self-contained.

## When to use

- The user wants a chart for a venue / session ("chart Madrid FP2", "give me the qualifying chart")
- The user asks who was fastest in a session, how big the gaps were, who was quick on a long run, or how the pace fell away
- The user wants charts for a whole race weekend

## Three-step flow

```bash
# 1. confirm the round and the session key
python3 f1_fetch.py --rounds 2026      # venue breakdown + which round it is
python3 f1_fetch.py --sessions 2026    # every session this season (grab session_key)

# 2. fetch (laps stints position result drivers session by default)
python3 f1_fetch.py <session_key>      # → data/s<session_key>_*.json

# 3. render
python3 f1_chart_fp.py <session_key>   # → charts/<season>-R<round>-<station>/<fig>.png
```

Lazy mode (fetch + render in one go):

```bash
python3 f1_weekend.py --round 16               # the whole weekend
python3 f1_weekend.py --round 16 --only FP1,Q  # named sessions only
python3 f1_weekend.py --round 16 --dry-run     # plan only
python3 f1_weekend.py --round 16 --refetch     # refetch even if data exists
```

## One chart = one script, don't mix them

| Script | Chart | Answers | Data |
| --- | --- | --- | --- |
| `f1_chart_fp.py` | practice lap-gap chart (ranking) | who was fastest on one lap | any FP |
| `f1_chart_q.py` | qualifying lap-gap chart | who took pole, by how much | Q / SQ |
| `f1_chart_r.py` | race pace chart | race pace, stop spread | R / Sprint |
| `f1_chart_long.py` | long-run speed chart | who is quick over a long run | **practice only** |
| `f1_chart_long_traj.py` | long-run degradation trajectory | how the long run falls away | **practice only** |

- **Lap-gap ranking charts** (fp/q/r): every driver's fastest lap side by side, ranked, **no clean-stint threshold** — nobody is dropped, so even FP3 renders a full field.
- **Long-run speed chart**: qualifying stints only, one longest stint per driver per compound, read the bar at the end.
- **Long-run degradation trajectory**: all qualifying stints, lap by lap — the shape of the drop-off.

"Ranking" ≠ "long run" ≠ "degradation". Scripts, definitions and filenames are separate. When the user wants a ranking chart, do **not** hand in a long-run chart instead.

## Definitions (settled — don't improvise)

**Ranking charts (FP / Q)**

- P1 row: purple `FASTEST` (`POLE` in qualifying) badge + full lap time (`1:34.077`)
- Everyone else: gap only (`+0.286`, relative to P1 / pole)
- **No theoretical-best-lap diff** (rejected — don't add it back)

**Long-run charts (practice data only)**

- The race is the outcome, practice is the input. Don't point these at an R session; the script warns on non-practice sessions.
- Qualifying stint: at least `MIN_SEG=6` laps, laps slower than fastest × `CUT=1.07` dropped, at least 3 clean laps per stint
- Speed chart: longest qualifying stint; bar = fastest→slowest of the last `TAIL=4` clean laps, dot = average; rows ordered by end-of-stint average, quickest first
- Trajectory: all qualifying stints, three panels (soft / medium / hard) **stacked vertically**, x = tyre age, y = lap time (m:ss); tyre age printed under each point; second stint on the same compound dashed with an index after the name

**All charts**

- Times always as `m:ss.mmm`; delta / change axes in seconds
- Dark background, driver line colour taken from team colour
- **Look at the chart yourself** before handing it over: clipped text, overlapping names, symmetric margins, big empty patches

## Arguments

Every chart template shares one set:

| Argument | Meaning |
| --- | --- |
| `session_key` | positional, the session number (**switching session = changing only this**) |
| `--prefix` | data prefix under `data/`, defaults to `s<session_key>` |
| `--station` / `--round` / `--gp-name` / `--date` / `--fig-name` | override the inferred venue / round / GP name / date / figure name |
| `--lang` | `zh` / `en`; omit to auto-detect (env `F1_LANG` > system locale > `zh`) |

You normally don't pass the middle ones — `f1_dict.resolve_session()` infers them from the session payload and warns when it can't, which is when you override by hand.

## Language

All visible text comes from `f1_i18n.py`. Resolution: `--lang` > `F1_LANG` > system locale > `zh`. Auto-detection treats `zh_CN` / `zh_SG` / `zh_MY` as Chinese and everything else (including `zh_HK` / `zh_TW` / `zh_MO`, plus any non-Chinese locale) as English. The Chinese driver-name column is drawn only in `zh`, and English output goes to a separately named folder so the two runs never overwrite each other.

## Gotchas

- **CJK fonts**: on a headless box (container / CI) the two long-run charts fall back to a temp `MPLCONFIGDIR` on their own when the home dir is not writable, so no manual setup is needed; fonts go through a candidate list (PingFang SC / Microsoft YaHei / Noto Sans CJK), whatever is installed wins.
- **Blurry output**: PNGs come from librsvg **native vector rendering** (rewrite the SVG root width/height to the target size, leave the viewBox alone) — not bitmap upscaling. Needs `ffmpeg`.
- **Data prefix**: templates read `data/` as `s<session_key>`; pick it once and don't hand-edit.
- **Batching sessions**:
  ```bash
  for k in 11362 11363 11364; do
    python3 f1_chart_long.py $k
    python3 f1_chart_long_traj.py $k
  done
  ```
- **New season**: change `YEAR` in `f1_dict.py` and swap `MEETINGS` for the new calendar (rounds count Grands Prix only; pre-season testing is not in the table).
- **Stand-in / renumbered drivers**: add a row to `f1_dict.DRIVERS`; unknown car numbers degrade to `#<number>` instead of erroring.
- **Data source**: OpenF1 (free, public). Raw responses are written to disk as-is, structure untouched; when in doubt check the API response, don't guess at fields.
- **OpenF1 live lock (important)**: while any session is running (FP / Q / R all count) it temporarily locks the whole API for unauthenticated users — historical sessions included — and every endpoint returns **401** with `Live F1 session in progress...`. This is not a script bug and not a network problem; it clears itself when the session ends. Check that no session is running before fetching or rendering (late on a race weekend is when you hit this).
