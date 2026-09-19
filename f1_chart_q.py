#!/usr/bin/env python3
"""F1 排位赛圈速差距图 · 母版 f1_chart_q（librsvg 原生矢量栅格化，不做位图放大）

设计（与 FP/R 图同一套视觉语言）:
  - 左侧 P1-P22 名次（P1 紫色）
  - 中间：分类圈相对杆位圈的秒差条（车队色），条尾 +0.xxx
  - 右侧：分类圈时间 m:ss.mmm + 最深阶段微章（Q3 紫 / Q2 蓝 / Q1 灰）
  - P10 / P15 之后画晋级分隔线，淘汰行整体压暗

用法: python3 f1_chart_q.py <session_key> [--prefix 前缀] [--station 站名] [--round N]
                           [--gp-name 大奖赛名] [--date YYYY-MM-DD] [--fig-name 图名]
      数据先跑 f1_fetch.py <session_key>（默认落到 data/s<session_key>_*.json）
依赖: ffmpeg (librsvg 后端)
产物: charts/<赛季>-R<站序>-<分站>/<图名>.svg + .png（librsvg 原生矢量渲染）
"""
import argparse
import json
import os
import re
import subprocess
import sys

from PIL import Image

# 车手/分站/胎色共享字典：与 f1_chart_fp.py / f1_chart_r.py 同源，改字典改 f1_dict.py 一处
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f1_dict import DRIVERS, CN, resolve_session, load_json
from f1_i18n import add_lang_arg, init, t, is_zh

DEFAULT_SESSION_KEY = 11357   # 无参数时的兜底场次（蒙扎排位赛）；常规用法是传 session_key


def parse_args():
    ap = argparse.ArgumentParser(description=t("q.desc"))
    add_lang_arg(ap)
    ap.add_argument("session_key", nargs="?", type=int, help="场次 session_key，如 11357")
    ap.add_argument("--prefix", help="data/ 里的数据前缀（默认 s<session_key>）")
    ap.add_argument("--station", help="分站中文名（覆盖字典）")
    ap.add_argument("--round", type=int, help="站序（覆盖字典）")
    ap.add_argument("--gp-name", help="标题用的大奖赛名（覆盖字典）")
    ap.add_argument("--date", help="页脚日期标注（覆盖 session 日期）")
    ap.add_argument("--fig-name", help="输出图名（覆盖默认拼法）")
    return ap.parse_args()


ARGS = parse_args()
init(ARGS.lang)            # 语言优先级：--lang > F1_LANG > 系统 locale > zh
SESSION_KEY = ARGS.session_key or DEFAULT_SESSION_KEY
PREFIX = ARGS.prefix or f"s{SESSION_KEY}"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CHARTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charts")
META = resolve_session(DATA_DIR, PREFIX, ARGS, lang="zh" if is_zh() else "en")

SEASON = META["season"]
ROUND = META["round"]
STATION = META["station"]
GP_NAME = META["gp_name"]
DATE_LABEL = META["date_label"]
STAGE = META["stage"]
FIG_NAME = META["fig_name"] or t("q.fig", station=STATION, stage=STAGE)

if STAGE and STAGE != "Q":
    print(t("common.warn_stage", stage=STAGE,
            chart="排位圈速差距图" if is_zh() else "qualifying gap chart",
            expected="排位赛" if is_zh() else "qualifying"), file=sys.stderr)
for _k in META["missing"]:
    print(t("common.warn_missing", item=_k), file=sys.stderr)



_SG = STAGE or "Q"
STAGE_NAME = {2: f"{_SG}3", 1: f"{_SG}2", 0: f"{_SG}1"}
STAGE_FILL = {2: "#C77DFF", 1: "#59C2FF", 0: "#6B7280"}
STAGE_TXT = {2: "#170f26", 1: "#0b1420", 0: "#f2f4f8"}


def fmt_time(t):
    m = int(t // 60)
    return f"{m}:{t - 60 * m:06.3f}"


def hx(c):
    return "#" + c

# ---------- 数据 ----------
RESULT = load_json(DATA_DIR, PREFIX, "result")
DRV_LIST = load_json(DATA_DIR, PREFIX, "drivers")


def stage_of(pos):
    if pos <= 10:
        return 2
    if pos <= 15:
        return 1
    return 0


pole = None
for r in RESULT:
    for _d in (r.get("duration") or []):   # 注意别用 t 作变量名，会遮住 i18n 的 t()
        if _d and (pole is None or _d < pole):
            pole = _d

rows = []
for r in RESULT:
    pos = int(r.get("position") or 99)
    num = r["driver_number"]
    d = DRIVERS.get(num, {"last": f"#{num}", "team": "Unknown", "color": "888888", "full": f"#{num}"})
    dur = list(r.get("duration") or [])
    while len(dur) < 3:
        dur.append(None)
    st = stage_of(pos)
    best = dur[st]
    rows.append({
        "pos": pos, "num": num, "name": d["last"], "cn": CN.get(num, ""),
        "team": d["team"], "color": d["color"], "full": d["full"],
        "q1": dur[0], "q2": dur[1], "q3": dur[2],
        "stage": st, "best": best, "out": pos > 10,
    })
rows.sort(key=lambda r: r["pos"])
for r in rows:
    r["gap"] = (r["best"] - pole) if r["best"] else None

N = len(rows)

# ---------- 布局 ----------
W = 1200
ROW_H = 28
HEADER_Y = 116
ROW_Y0 = HEADER_Y + 32
PLOT_X0, PLOT_X1 = 430, 920
PLOT_W = PLOT_X1 - PLOT_X0
G_TOP = 3.5  # 秒差轴上限
CN_X = 220
TEAM_BLOCK_X, TEAM_X = 320, 334
TIME_X = 1008
CHIP_X, CHIP_W, CHIP_H = 1104, 40, 15
BOUND = {9: t("q.bound_q2", stage=_SG), 14: t("q.bound_q1", stage=_SG)}

# 页脚各段的纵向位置先算出来，画布高度按内容收——行数少时不留一大片空白
PER_ROW = 6
TEAMS_IN = []
_seen = set()
for _r in rows:
    if _r["team"] not in _seen:
        _seen.add(_r["team"])
        TEAMS_IN.append((_r["team"], _r["color"]))
FOOT_Y = ROW_Y0 + N * ROW_H + 12
LEGEND_Y = FOOT_Y + 14
LG_Y = LEGEND_Y + ((len(TEAMS_IN) + PER_ROW - 1) // PER_ROW) * 22 + 10
NOTE_Y = LG_Y + 30
H = int(NOTE_Y + 18 + 30)


def hx_ok(c):
    return hx(c)


p = []
p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
p.append('<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#151a26"/><stop offset="1" stop-color="#0f131c"/></linearGradient></defs>')
p.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/>')
p.append('<rect x="24" y="26" width="4" height="46" rx="2" fill="#ED1131"/>')
p.append(f'<text x="40" y="50" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="24" fill="#f4f6fa" font-weight="700">2026 F1 {GP_NAME}</text>')
sub = t("q.sub", name=rows[0]["full"], team=rows[0]["team"], time=fmt_time(pole), n=N)
p.append(f'<text x="40" y="74" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="12.5" fill="#a3adc0" font-weight="400">{sub}</text>')
p.append(f'<text x="{W-32}" y="50" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" fill="#8fa0b8" font-weight="600" text-anchor="end">{DATE_LABEL}</text>')

# 秒差轴网格
for k in range(1, 8):
    gv = G_TOP * k / 7
    x = PLOT_X0 + PLOT_W * k / 7
    p.append(f'<line x1="{x:.1f}" y1="{HEADER_Y-12}" x2="{x:.1f}" y2="{ROW_Y0 + N*ROW_H}" stroke="#252c3c" stroke-width="1"/>')
    p.append(f'<text x="{x:.1f}" y="{HEADER_Y-22}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10.5" fill="#5f6a7d" font-weight="400" text-anchor="middle">+{gv:.1f}s</text>')

# 表头带
p.append(f'<rect x="24" y="{HEADER_Y-12}" width="{W-48}" height="28" rx="6" fill="#ffffff" fill-opacity="0.045"/>')
p.append(f'<text x="36" y="{HEADER_Y+7}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11.5" fill="#8fa0b8" font-weight="600" letter-spacing="1">{t("q.col_gap")}</text>')
p.append(f'<text x="{TIME_X}" y="{HEADER_Y+7}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11.5" fill="#8fa0b8" font-weight="600" letter-spacing="1">{t("q.col_best")}</text>')
p.append(f'<text x="{CHIP_X+20}" y="{HEADER_Y+7}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11.5" fill="#8fa0b8" font-weight="600" letter-spacing="1" text-anchor="middle">{t("q.col_stage")}</text>')

# ---------- 行 ----------
for i, r in enumerate(rows):
    y = ROW_Y0 + i * ROW_H
    if i % 2 == 1:
        p.append(f'<rect x="24" y="{y-10}" width="{W-48}" height="{ROW_H}" fill="#ffffff" fill-opacity="0.022"/>')
    out = r["out"]
    pos_col = "#C77DFF" if i == 0 else ("#4f586b" if out else "#77839a")
    p.append(f'<text x="34" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12.5" fill="{pos_col}" font-weight="700">P{r["pos"]}</text>')
    name_col = "#98a3b5" if out else "#eef1f6"
    p.append(f'<text x="88" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13.5" fill="{name_col}" font-weight="600">{r["name"]}</text>')
    if r["cn"] and is_zh():
        p.append(f'<text x="{CN_X}" y="{y+8.5}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11" fill="#6b7689" font-weight="400">{r["cn"]}</text>')
    team_col = hx(r["color"])
    p.append(f'<rect x="{TEAM_BLOCK_X}" y="{y-3}" width="8" height="14" rx="2" fill="{team_col}" fill-opacity="{0.45 if out else 0.95}"/>')
    p.append(f'<text x="{TEAM_X}" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11.5" fill="#9aa5b8" font-weight="400">{r["team"]}</text>')
    # 秒差条
    bw = max(3.0, min(PLOT_W, (r["gap"] or 0) / G_TOP * PLOT_W))
    p.append(f'<rect x="{PLOT_X0}" y="{y-2.5}" width="{bw:.1f}" height="13" rx="6.5" fill="{team_col}" fill-opacity="{0.45 if out else 0.92}"/>')
    if i == 0:
        _bx = PLOT_X0 + bw + 19
        p.append(f'<rect x="{_bx:.1f}" y="{y-4}" width="56" height="16" rx="8" fill="#C77DFF"/>')
        p.append(f'<text x="{_bx+28:.1f}" y="{y+7.4}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="9.5" fill="#170f26" font-weight="800" text-anchor="middle">POLE</text>')
    else:
        p.append(f'<text x="{PLOT_X0 + bw + 19:.1f}" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11" fill="#e8ecf3" font-weight="600">+{r["gap"]:.3f}</text>')
    # 右侧：时间 + 阶段微章
    p.append(f'<text x="{TIME_X}" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11.5" fill="{"#98a3b5" if out else "#dbe2ec"}" font-weight="600">{fmt_time(r["best"])}</text>')
    st = r["stage"]
    p.append(f'<rect x="{CHIP_X}" y="{y-3.5}" width="{CHIP_W}" height="{CHIP_H}" rx="7.5" fill="{STAGE_FILL[st]}" fill-opacity="{0.75 if out else 1}"/>')
    p.append(f'<text x="{CHIP_X+CHIP_W/2}" y="{y+7.6}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="9.5" fill="{STAGE_TXT[st]}" font-weight="800" text-anchor="middle">{STAGE_NAME[st]}</text>')
    # 晋级分隔线
    if i in BOUND:
        by = y + 18
        lbl = BOUND[i]
        half = 100
        p.append(f'<line x1="24" y1="{by}" x2="{612-half}" y2="{by}" stroke="#3a4356" stroke-width="1"/>')
        p.append(f'<line x1="{612+half}" y1="{by}" x2="{W-24}" y2="{by}" stroke="#3a4356" stroke-width="1"/>')
        p.append(f'<text x="612" y="{by+4}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10" fill="#8b97aa" font-weight="600" text-anchor="middle">{lbl}</text>')

# ---------- 页脚 ----------
p.append(f'<line x1="{PLOT_X0}" y1="{FOOT_Y-12}" x2="{PLOT_X1}" y2="{FOOT_Y-12}" stroke="#39404d" stroke-width="1"/>')
for idx, (tname, tcol) in enumerate(TEAMS_IN):
    row_idx = idx // PER_ROW
    col_idx = idx % PER_ROW
    leg_x = 30 + col_idx * 180
    leg_y_i = LEGEND_Y + row_idx * 22
    p.append(f'<rect x="{leg_x}" y="{leg_y_i}" width="10" height="10" rx="2" fill="{hx(tcol)}"/>')
    p.append(f'<text x="{leg_x+15}" y="{leg_y_i+9}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10.5" fill="#9aa5b8" font-weight="400">{tname}</text>')

# 阶段图例：整块右对齐到右边距，标签用 end 锚点——英文 "Segment" 比「阶段」宽，锚在固定 x 会压到第一个微章上
CHIP_LW, CHIP_LGAP = 26, 20
lx = W - 28 - (CHIP_LW * 3 + CHIP_LGAP * 2)
p.append(f'<text x="{lx-12}" y="{LG_Y+9}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10.5" fill="#8fa0b8" font-weight="600" text-anchor="end">{t("q.col_stage")}</text>')
for sn, sf in ((f"{_SG}3", STAGE_FILL[2]), (f"{_SG}2", STAGE_FILL[1]), (f"{_SG}1", STAGE_FILL[0])):
    p.append(f'<rect x="{lx}" y="{LG_Y}" width="{CHIP_LW}" height="11" rx="5.5" fill="{sf}"/>')
    p.append(f'<text x="{lx+CHIP_LW/2}" y="{LG_Y+9}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="9" fill="#0f131c" font-weight="800" text-anchor="middle">{sn}</text>')
    lx += CHIP_LW + CHIP_LGAP

note_y = NOTE_Y
p.append(f'<text x="30" y="{note_y}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11" fill="#667186" font-weight="400">{t("q.note1", pole=fmt_time(pole), stage=_SG)}</text>')
p.append(f'<text x="30" y="{note_y+18}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10.5" fill="#667186" font-weight="400">{t("q.note2", stage=_SG)}</text>')
p.append(f'<text x="{W-28}" y="{NOTE_Y+18}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10" fill="#4d5666" font-weight="400" text-anchor="end">{t("common.footer", key=SESSION_KEY, date=DATE_LABEL)}</text>')
p.append('</svg>')

# === 出图：写 SVG → 目标像素尺寸原生矢量渲染（librsvg）→ 直出成图目录 ===
LIB_DIR = f"{CHARTS_DIR}/{SEASON}-R{ROUND}-{STATION}"
os.makedirs(LIB_DIR, exist_ok=True)
WORK_SVG = f"{LIB_DIR}/{FIG_NAME}.svg"
WORK_SVG_HI = f"{LIB_DIR}/.{FIG_NAME}.hi.svg"
WORK_PNG = f"{LIB_DIR}/{FIG_NAME}.png"

SVG = "\n".join(p)
with open(WORK_SVG, "w", encoding="utf-8") as f:
    f.write(SVG)
print(f"[1/3] SVG written: {WORK_SVG}", file=sys.stderr)

# 关键：ffmpeg 的 librsvg 只按 SVG 自带宽高栅格化，-vf scale 是位图放大（会糊）。
# 改成把根元素宽高直接写成目标像素尺寸（viewBox 不动），让它按该尺寸原生矢量渲染。
TARGET_W = 2400
m = re.search(r'(<svg\b[^>]*?)width="([\d.]+)"\s+height="([\d.]+)"', SVG)
assert m, "SVG 根元素缺少 width/height"
TARGET_H = round(float(m.group(3)) * TARGET_W / float(m.group(2)))
with open(WORK_SVG_HI, "w", encoding="utf-8") as f:
    f.write(SVG[:m.start()] + f'{m.group(1)}width="{TARGET_W}" height="{TARGET_H}"' + SVG[m.end():])

subprocess.run(["ffmpeg", "-y", "-i", WORK_SVG_HI, "-frames:v", "1", "-update", "1", WORK_PNG],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.remove(WORK_SVG_HI)
print(f"[2/3] rasterized: {WORK_PNG} ({TARGET_W}x{TARGET_H}) via librsvg 原生渲染", file=sys.stderr)

print(f"[3/3] done: {LIB_DIR}/", file=sys.stderr)

print(f"POLE: P1 {rows[0]['name']} {fmt_time(pole)} ({rows[0]['team']})", file=sys.stderr)
for i, r in enumerate(rows):
    print(f"  P{r['pos']:<3} #{r['num']:<3} {r['name']:<12} {r['cn']:<6} {STAGE_NAME[r['stage']]} {fmt_time(r['best'])} +{r['gap']:.3f}", file=sys.stderr)
