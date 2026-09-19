#!/usr/bin/env python3
"""F1 长距离衰减轨迹图 · 母版 f1_chart_long_traj（各 stint 圈速走势）

用法: python3 f1_chart_long_traj.py <session_key> [--prefix 前缀] [--station 站名] [--round N]
                                     [--gp-name 大奖赛名] [--date YYYY-MM-DD] [--fig-name 图名]
      数据先跑 f1_fetch.py <session_key>（默认落到 data/s<session_key>_*.json）
      不带 <session_key> 时用内部默认场次（仅调试兜底）
口径: 画每一套合格 stint（段长 >= MIN_SEG 圈，剔除 >最快圈×CUT 的脏圈）的逐圈走势，
      横轴 = 胎龄（段内第几圈），纵轴 = 圈速（分:秒）；同一车手同一轮胎有多套时，
      第二套起用虚线并在名字后带序号
产物: charts/<赛季>-R<站序>-<分站>/<图名>.png
注: 长距离图只用练习赛数据（FP 是预测输入，正赛是结果），别拿 R 的 session 跑
"""
import argparse
import collections
import os
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
from f1_dict import DRIVERS, tire_zh, resolve_session, load_json
from f1_i18n import add_lang_arg, init, t, tire_short, is_zh

DEFAULT_SESSION_KEY = 11363   # 无参数时的兜底场次（马德里 FP2）
MIN_SEG = 6                   # 合格 stint 最短圈数
CUT = 1.07                    # 脏圈阈值：> 本段最快圈 × CUT 的圈剔除
BG, PANEL = "#0f131c", "#151b26"
PANELS = ("SOFT", "MEDIUM", "HARD")


def parse_args():
    ap = argparse.ArgumentParser(description=t("traj.desc"))
    add_lang_arg(ap)
    ap.add_argument("session_key", nargs="?", type=int, help="场次 session_key，如 11363")
    ap.add_argument("--prefix", help="data/ 里的数据前缀（默认 s<session_key>）")
    ap.add_argument("--station", help="分站中文名（覆盖字典）")
    ap.add_argument("--round", type=int, help="站序（覆盖字典）")
    ap.add_argument("--gp-name", help="标题用的大奖赛名（覆盖字典）")
    ap.add_argument("--date", help="页脚日期标注（覆盖 session 日期）")
    ap.add_argument("--fig-name", help="输出图名（覆盖默认拼法）")
    return ap.parse_args()


def fmt_axis(v, _p=None):
    """y 轴刻度：分:秒（一位小数）"""
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
FIG_NAME = META["fig_name"] or t("traj.fig", station=STATION, stage=STAGE)

if STAGE and STAGE not in ("FP1", "FP2", "FP3"):
    print(t("common.warn_stage", stage=STAGE,
            chart="长距离衰减轨迹图" if is_zh() else "long-run degradation chart",
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

# 留下每一套合格 stint（不像速度图只留最长那套）
segs = []
for st in stints:
    n, c = st["driver_number"], st.get("compound")
    if c not in PANELS:
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
    if st["lap_end"] - st["lap_start"] + 1 < MIN_SEG or len(clean) < 3:
        continue
    segs.append(dict(n=n, c=c, base=st["lap_start"], clean=clean))

# 同车同胎多套：按开跑圈排序，第二套起虚线 + 名字带序号
grp = collections.defaultdict(list)
for s in segs:
    grp[(s["n"], s["c"])].append(s)
for lst in grp.values():
    lst.sort(key=lambda x: x["base"])
    for i, s in enumerate(lst):
        s["seq"] = i + 1
        s["multi"] = len(lst) > 1
        s["label"] = NAME.get(s["n"], f"#{s['n']}") + (f" {i + 1}" if s["multi"] else "")

fig, axes = plt.subplots(3, 1, figsize=(14, 16), facecolor=BG, sharex=True, sharey=True)
AX = dict(zip(PANELS, axes))
ends = {c: [] for c in PANELS}
gxmin, gxmax = None, 0

for c in PANELS:
    ax = AX[c]
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_color("#39404d")
    ax.tick_params(colors="#9aa5b8", labelsize=10)
    ax.grid(True, color="#252c3c", lw=0.6, alpha=0.7)
    cnt = 0
    for s in segs:
        if s["c"] != c:
            continue
        col = TCOL.get(s["n"], "#9aa5b8")
        xs = [i - s["base"] + 1 for i, _ in s["clean"]]
        ys = [d for _, d in s["clean"]]
        ax.plot(xs, ys, marker="o", ms=3.4, lw=1.4, color=col, alpha=0.9,
                ls="-" if not s["multi"] or s["seq"] == 1 else (0, (4, 2.2)))
        for xx, yy in zip(xs, ys):
            ax.annotate(f"{xx}", (xx, yy), color=col, alpha=0.7, fontsize=5.8,
                        xytext=(0, -7.5), textcoords="offset points",
                        ha="center", va="center")
        ends[c].append((ys[-1], xs[-1], s["label"], col))
        cnt += 1
        gxmin = xs[0] if gxmin is None else min(gxmin, xs[0])
        gxmax = max(gxmax, xs[-1])
    ax.set_title(t("traj.panel", tire=(tire_zh(c) if is_zh() else tire_short(c)), n=cnt),
                 color="#f4f6fa", fontsize=13, loc="left", pad=7)

# 三个 panel 共用同一条 x 轴范围，横向可直接比（左右都贴紧数据，别留空档）
LX = (gxmin - 0.45) if gxmin is not None else 0.75
GX = gxmax + 0.85 if gxmax else 20.0
# 末端车手名：同一 panel 内 y 挨太近就往上错开，并加半透明底框防止被线穿过
MIN_DY = 0.34
ymax_lab = None
for c in PANELS:
    lst = sorted(ends[c], key=lambda t: t[0])
    adj = [t[0] for t in lst]
    for i in range(1, len(adj)):
        if adj[i] - adj[i - 1] < MIN_DY:
            adj[i] = adj[i - 1] + MIN_DY
    for i, (_y0, x, lab, col) in enumerate(lst):
        AX[c].annotate(lab, (x, adj[i]), color=col, fontsize=8.2, va="center",
                       xytext=(5, 0), textcoords="offset points",
                       bbox=dict(facecolor=BG, alpha=0.6, edgecolor="none", pad=1.0))
        ymax_lab = adj[i] if ymax_lab is None else max(ymax_lab, adj[i])

axes[0].set_xlim(LX, GX)
if segs:
    _lo = min(d for s in segs for _, d in s["clean"])
    _hi = max(d for s in segs for _, d in s["clean"])
    if ymax_lab is not None:
        _hi = max(_hi, ymax_lab + 0.2)
    axes[0].set_ylim(_lo - 0.25, _hi)

axes[-1].set_xlabel(t("traj.xlabel"), color="#9aa5b8", fontsize=11)
axes[0].yaxis.set_major_formatter(FuncFormatter(fmt_axis))
axes[0].set_ylabel(t("traj.ylabel"), color="#9aa5b8", fontsize=11)

fig.suptitle(t("traj.title", station=STATION, stage=STAGE),
             color="#f4f6fa", fontsize=16, y=0.977)
fig.text(0.5, 0.010,
         t("traj.note", min_seg=MIN_SEG, cut=CUT) + "\n"
         + t("traj.note2") + " · " + t("common.footer", key=SESSION_KEY, date=DATE_LABEL),
         ha="center", color="#667186", fontsize=8.6, linespacing=1.6)
fig.subplots_adjust(left=0.075, right=0.955, top=0.945, bottom=0.058, hspace=0.16)

OUT_DIR = os.path.join(CHARTS_DIR, f"{SEASON}-R{ROUND}-{STATION}")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, f"{FIG_NAME}.png")
fig.savefig(OUT, dpi=120, facecolor=BG)
print(f"OK -> {OUT}")
for c in PANELS:
    print(t("traj.stats", tire=(tire_zh(c) if is_zh() else c.title()),
            n=sum(1 for s in segs if s["c"] == c)))
