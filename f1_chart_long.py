#!/usr/bin/env python3
"""F1 长距离速度图 · 母版 f1_chart_long（一车一行多胎 · 末段基准）

用法: python3 f1_chart_long.py <session_key> [--prefix 前缀] [--station 站名] [--round N]
                                [--gp-name 大奖赛名] [--date YYYY-MM-DD] [--fig-name 图名]
      数据先跑 f1_fetch.py <session_key>（默认落到 data/s<session_key>_*.json）
      不带 <session_key> 时用内部默认场次（仅调试兜底）
口径: 每车每胎取圈数最多的合格 stint（段长 >= MIN_SEG 圈，剔除 >最快圈×CUT 的脏圈），
      取该段尾 TAIL 个干净圈：条 = 最快→最慢，点 = 平均
产物: charts/<赛季>-R<站序>-<分站>/<图名>.png
注: 长距离图只用练习赛数据（FP 是预测输入，正赛是结果），别拿 R 的 session 跑
"""
import argparse
import collections
import os
import statistics
import sys
import tempfile

# matplotlib 缓存目录兜底：家目录不可写（沙盒 / CI）时挪到临时目录，免得每次刷警告
if not os.access(os.path.expanduser("~"), os.W_OK):
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mpl"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.ticker import FuncFormatter

rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
                               "Noto Sans CJK SC", "Noto Sans CJK JP",
                               "WenQuanYi Zen Hei", "Arial Unicode MS", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f1_dict import DRIVERS, tire_color, tire_zh, resolve_session, load_json
from f1_i18n import add_lang_arg, init, t, tire_short, is_zh

DEFAULT_SESSION_KEY = 11363   # 无参数时的兜底场次（马德里 FP2）
MIN_SEG = 6                   # 合格 stint 最短圈数
CUT = 1.07                    # 脏圈阈值：> 本段最快圈 × CUT 的圈剔除
TAIL = 4                      # 末段基准取几个干净圈
BG, PANEL = "#0f131c", "#151b26"
LAYER = {"SOFT": 0.30, "MEDIUM": 0.0, "HARD": -0.30}   # 行内微层偏移（上→下 软/中/硬）


def parse_args():
    ap = argparse.ArgumentParser(description=t("long.desc"))
    add_lang_arg(ap)
    ap.add_argument("session_key", nargs="?", type=int, help="场次 session_key，如 11363")
    ap.add_argument("--prefix", help="data/ 里的数据前缀（默认 s<session_key>）")
    ap.add_argument("--station", help="分站中文名（覆盖字典）")
    ap.add_argument("--round", type=int, help="站序（覆盖字典）")
    ap.add_argument("--gp-name", help="标题用的大奖赛名（覆盖字典）")
    ap.add_argument("--date", help="页脚日期标注（覆盖 session 日期）")
    ap.add_argument("--fig-name", help="输出图名（覆盖默认拼法）")
    return ap.parse_args()


def fmt_lap(t):
    """秒 → 分:秒.毫秒"""
    m = int(t) // 60
    return f"{m}:{t - m * 60:06.3f}"


def fmt_axis(v, _p=None):
    """x 轴刻度：分:秒（一位小数）"""
    m = int(v) // 60
    return f"{m}:{v - m * 60:04.1f}"


ARGS = parse_args()
init(ARGS.lang)            # 语言优先级：--lang > F1_LANG > 系统 locale > zh
SESSION_KEY = ARGS.session_key or DEFAULT_SESSION_KEY
PREFIX = ARGS.prefix or f"s{SESSION_KEY}"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
CHARTS_DIR = os.path.join(HERE, "charts")
META = resolve_session(DATA_DIR, PREFIX, ARGS, lang="zh" if is_zh() else "en")

SEASON, ROUND = META["season"], META["round"]
STATION, STAGE = META["station"], META["stage"]
DATE_LABEL = META["date_label"]
FIG_NAME = META["fig_name"] or t("long.fig", station=STATION, stage=STAGE)

if STAGE and STAGE not in ("FP1", "FP2", "FP3"):
    print(t("common.warn_stage", stage=STAGE,
            chart="长距离速度图" if is_zh() else "long-run pace chart",
            expected="练习赛" if is_zh() else "practice"), file=sys.stderr)
for _k in META["missing"]:
    print(t("common.warn_missing", item=_k), file=sys.stderr)

laps = load_json(DATA_DIR, PREFIX, "laps")
stints = load_json(DATA_DIR, PREFIX, "stints")
drivers = load_json(DATA_DIR, PREFIX, "drivers")

NAME = {d["driver_number"]: (DRIVERS.get(d["driver_number"], {}).get("last")
                             or d.get("last_name") or f"#{d['driver_number']}")
        for d in drivers}
TCOL = {d["driver_number"]: "#" + (d.get("team_colour") or "9aa5b8") for d in drivers}

LAPS = collections.defaultdict(dict)
for l in laps:
    if l.get("lap_duration"):
        LAPS[l["driver_number"]][l["lap_number"]] = l

# 每车每胎留圈数最多的那一个合格 stint
best = {}
for st in stints:
    n, c = st["driver_number"], st.get("compound")
    if c not in LAYER:
        continue
    pts = []
    for i in range(st["lap_start"], st["lap_end"] + 1):
        l = LAPS[n].get(i)
        if not l or l.get("is_pit_out_lap"):
            continue
        pts.append((i, l["lap_duration"]))
    if not pts:
        continue
    fast = min(d for _, d in pts)
    clean = [(i, d) for i, d in pts if d <= fast * CUT]
    seg = st["lap_end"] - st["lap_start"] + 1
    if seg < MIN_SEG or len(clean) < 3:
        continue
    k = (n, c)
    if k not in best or seg > best[k]["seg"]:
        best[k] = dict(seg=seg, clean=clean)

rows = {}
for (n, c), v in best.items():
    tail = [d for _, d in v["clean"][-min(TAIL, len(v["clean"])):]]
    rows[(n, c)] = dict(fast=min(tail), slow=max(tail), avg=statistics.mean(tail),
                        nclean=len(v["clean"]), seg=v["seg"])

bycar = collections.defaultdict(list)
for (n, c), r in rows.items():
    bycar[n].append(r["avg"])
order = sorted(bycar, key=lambda n: min(bycar[n]))
ypos = {n: len(order) - 1 - i for i, n in enumerate(order)}

fig, ax = plt.subplots(figsize=(15, 11.5), facecolor=BG)
ax.set_facecolor(PANEL)
for s in ax.spines.values():
    s.set_color("#39404d")
ax.tick_params(colors="#9aa5b8", labelsize=9)
ax.grid(True, axis="x", color="#252c3c", lw=0.7)
for n in order:
    ax.axhline(ypos[n] - 0.5, color="#1f2735", lw=0.8, zorder=0)

for n in order:
    for c in ("SOFT", "MEDIUM", "HARD"):
        r = rows.get((n, c))
        if not r:
            continue
        y, col = ypos[n] + LAYER[c], tire_color(c)
        ax.hlines(y, r["fast"], r["slow"], color=col, lw=6.5, alpha=0.30)
        ax.plot([r["fast"], r["slow"]], [y, y], "|", color=col, ms=9, alpha=0.85, markeredgewidth=1.3)
        ax.plot(r["avg"], y, "o", color=col, ms=7, markeredgecolor=BG, markeredgewidth=1.1, zorder=3)
        ax.annotate(fmt_lap(r["avg"]), (r["slow"], y), color=col, fontsize=8.2,
                    xytext=(6, -2.4), textcoords="offset points", va="center")

ax.set_yticks([ypos[n] for n in order])
ax.set_yticklabels([NAME.get(n, f"#{n}") for n in order], fontsize=10.5)
for lbl, n in zip(ax.get_yticklabels(), order):
    lbl.set_color(TCOL.get(n, "#c8d0de"))
ax.set_xlim(min(r["fast"] for r in rows.values()) - 0.6,
            max(r["slow"] for r in rows.values()) + 1.8)
ax.set_ylim(-0.75, len(order) - 0.25)
ax.xaxis.set_major_formatter(FuncFormatter(fmt_axis))
ax.set_xlabel(t("long.xlabel", tail=TAIL), color="#9aa5b8", fontsize=10.5)
ax.set_title(t("long.title", station=STATION, stage=STAGE), color="#f4f6fa", fontsize=14, pad=14)

for c in ("SOFT", "MEDIUM", "HARD"):
    if any((n, c) in rows for n in order):
        ax.scatter([], [], s=110, color=tire_color(c), edgecolors=BG,
                   label=t("long.legend", tire=(tire_zh(c) if is_zh() else tire_short(c))))
ax.legend(facecolor="#1b2230", edgecolor="#39404d", labelcolor="#c8d0de", fontsize=10,
          loc="lower right", ncol=3)
fig.text(0.5, 0.015,
         t("long.note", min_seg=MIN_SEG, cut=CUT) + " · "
         + t("common.footer", key=SESSION_KEY, date=DATE_LABEL),
         ha="center", color="#667186", fontsize=9)

fig.subplots_adjust(left=0.09, right=0.96, top=0.955, bottom=0.105)

OUT_DIR = os.path.join(CHARTS_DIR, f"{SEASON}-R{ROUND}-{STATION}")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, f"{FIG_NAME}.png")
fig.savefig(OUT, dpi=120, facecolor=BG)
print(f"OK -> {OUT}")
print(t("long.stats", drivers=len(order), stints=len(rows)))
