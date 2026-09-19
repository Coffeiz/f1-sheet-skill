#!/usr/bin/env python3
"""F1 FP 圈速差距图 · 母版 f1_chart_fp（librsvg 原生矢量栅格化，不做位图放大）

用法: python3 f1_chart_fp.py <session_key> [--prefix 前缀] [--station 站名] [--round N]
                            [--gp-name 大奖赛名] [--date YYYY-MM-DD] [--fig-name 图名]
      数据先跑 f1_fetch.py <session_key>（默认落到 data/s<session_key>_*.json）
      不带 <session_key> 时用内部默认场次（仅调试兜底）
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

# 车手/分站/胎色共享字典：与 f1_chart_q.py / f1_chart_r.py 同源，改字典改 f1_dict.py 一处
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f1_dict import DRIVERS, CN, tire_color, resolve_session, load_json
from f1_i18n import add_lang_arg, init, t, tire_short, is_zh

DEFAULT_SESSION_KEY = 11363   # 无参数时的兜底场次（马德里 FP2）；常规用法是传 session_key


def parse_args():
    ap = argparse.ArgumentParser(description=t("fp.desc"))
    add_lang_arg(ap)   # --lang：图内文案语言（zh/en）
    ap.add_argument("session_key", nargs="?", type=int, help="场次 session_key，如 11362")
    ap.add_argument("--prefix", help="data/ 里的数据前缀（默认 s<session_key>）")
    ap.add_argument("--station", help="分站中文名（覆盖字典）")
    ap.add_argument("--round", type=int, help="站序（覆盖字典）")
    ap.add_argument("--gp-name", help="标题用的大奖赛名（覆盖字典）")
    ap.add_argument("--date", help="页脚日期标注（覆盖 session 日期）")
    ap.add_argument("--fig-name", help="输出图名（覆盖默认拼法）")
    return ap.parse_args()


ARGS = parse_args()
init(ARGS.lang)   # 文案语言：--lang > 环境变量 F1_LANG > zh
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
FIG_NAME = META["fig_name"] or t("fp.fig", station=STATION, stage=STAGE)

if STAGE and STAGE not in ("FP1", "FP2", "FP3"):
    print(t("common.warn_stage", stage=STAGE, chart="FP", expected="practice"), file=sys.stderr)
for _k in META["missing"]:
    print(t("common.warn_missing", item=_k), file=sys.stderr)

laps = load_json(DATA_DIR, PREFIX, "laps")
stints = load_json(DATA_DIR, PREFIX, "stints")

clean = []
for L in laps:
    if L.get("is_pit_out_lap"): continue
    d = L.get("lap_duration")
    if d is None or d > 130: continue
    s1, s2, s3 = L.get("duration_sector_1"), L.get("duration_sector_2"), L.get("duration_sector_3")
    if s1 is None or s2 is None or s3 is None or s1 > 80 or s2 > 80 or s3 > 80: continue
    clean.append(L)

best, best_lap, total_laps = {}, {}, {}
for L in clean:
    n = L["driver_number"]; d = L["lap_duration"]
    if n not in best or d < best[n]:
        best[n] = d; best_lap[n] = L["lap_number"]
    total_laps[n] = total_laps.get(n, 0) + 1

def tire_for(drv, ln):
    for s in stints:
        if s["driver_number"] == drv and s["lap_start"] <= ln <= s["lap_end"]: return s.get("compound", "")
    return ""

rows = []
for n, b in best.items():
    d = DRIVERS.get(n, {"last":f"#{n}","team":"Unknown","color":"888888","full":f"#{n}"})
    rows.append({"num":n,"name":d["last"],"team":d["team"],"color":d["color"],"full":d["full"],"cn":CN.get(n,d["last"]),"best":b,"laps":total_laps.get(n,0),"tire":tire_for(n, best_lap.get(n,0))})
rows.sort(key=lambda r: r["best"])
gap0 = rows[0]["best"]
for r in rows: r["gap"] = r["best"] - gap0
gap_max = max(r["gap"] for r in rows) * 1.06

W = 1200; ROW_H = 28; HEADER_Y = 116
ROW_Y0 = HEADER_Y + 32  # 修复: 再加 4 让 FASTEST 框避表头
PLOT_X0 = 460; PLOT_X1 = 940; PLOT_W = PLOT_X1 - PLOT_X0
CN_X = 220
TEAM_BLOCK_X = 320; TEAM_X = 334
N = len(rows)

def hx(c): return "#"+c

def mmss(v):
    m = int(v // 60); s = v - m * 60
    return f"{m}:{s:06.3f}"

p = []
p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="910" viewBox="0 0 {W} 910">')
p.append('<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#151a26"/><stop offset="1" stop-color="#0f131c"/></linearGradient></defs>')
p.append(f'<rect width="{W}" height="910" rx="14" fill="url(#bg)"/>')
p.append('<rect x="24" y="26" width="4" height="46" rx="2" fill="#ED1131"/>')
p.append(f'<text x="40" y="50" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="24" fill="#f4f6fa" font-weight="700">2026 F1 {GP_NAME}</text>')
sub = t("fp.sub", name=rows[0]["full"], team=rows[0]["team"], n=N)
p.append(f'<text x="40" y="74" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="12.5" fill="#a3adc0" font-weight="400">{sub}</text>')

g_top = max(2.0, gap_max)
for i in range(8):
    gv = g_top * i / 7; x = PLOT_X0 + PLOT_W * i / 7
    p.append(f'<line x1="{x:.1f}" y1="{HEADER_Y-12}" x2="{x:.1f}" y2="{ROW_Y0 + N*ROW_H}" stroke="#252c3c" stroke-width="1"/>')
    p.append(f'<text x="{x:.1f}" y="{HEADER_Y-22}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10.5" fill="#5f6a7d" font-weight="400" text-anchor="middle">+{gv:.1f}s</text>')

p.append(f'<rect x="24" y="{HEADER_Y-12}" width="{W-48}" height="28" rx="6" fill="#ffffff" fill-opacity="0.045"/>')
p.append(f'<text x="36" y="{HEADER_Y+7}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11.5" fill="#8fa0b8" font-weight="600" letter-spacing="1">{t("fp.col_stage", stage=STAGE)}</text>')
p.append(f'<text x="1092" y="{HEADER_Y+7}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11.5" fill="#8fa0b8" font-weight="600" letter-spacing="1">{t("fp.col_tire")}</text>')

for i, r in enumerate(rows):
    y = ROW_Y0 + i * ROW_H
    if i % 2 == 1:
        p.append(f'<rect x="24" y="{y-10}" width="{W-48}" height="{ROW_H}" fill="#ffffff" fill-opacity="0.022"/>')
    color = "#C77DFF" if i == 0 else "#77839a"
    if i == 0:
        p.append(f'<text x="56" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12.5" fill="{color}" font-weight="700" text-anchor="end">P1</text>')
        # P1 的名字前不挂徽章，最快标记在数据区（FASTEST 徽章 + 完整圈速）
    else:
        p.append(f'<text x="56" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12.5" fill="{color}" font-weight="700" text-anchor="end">P{i+1}</text>')
    p.append(f'<text x="66" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13.5" fill="#eef1f6" font-weight="600">{r["name"]}</text>')
    if is_zh():   # 中文名只在 zh 图里画；en 图这一列留空
        p.append(f'<text x="{CN_X}" y="{y+8.5}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11" fill="#6b7689" font-weight="400">{r["cn"]}</text>')
    team_col = hx(r["color"])
    p.append(f'<rect x="{TEAM_BLOCK_X}" y="{y-3}" width="8" height="14" rx="2" fill="{team_col}"/>')
    p.append(f'<text x="{TEAM_X}" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11.5" fill="#9aa5b8" font-weight="400">{r["team"]}</text>')
    bw = max(3.0, (r["gap"] / g_top) * PLOT_W); by = y - 2.5
    p.append(f'<rect x="{PLOT_X0}" y="{by}" width="{bw:.1f}" height="13" rx="6.5" fill="{team_col}" fill-opacity="0.92"/>')
    if i == 0:
        # P1：FASTEST 徽章 + 完整圈速（分:秒.毫秒）；其余车手只给 gap
        _bx = PLOT_X0 + bw + 19
        p.append(f'<rect x="{_bx:.1f}" y="{y-4}" width="64" height="16" rx="8" fill="#C77DFF"/>')
        p.append(f'<text x="{_bx+32:.1f}" y="{y+7.4}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="9.5" fill="#170f26" font-weight="800" text-anchor="middle">FASTEST</text>')
        p.append(f'<text x="{_bx+72:.1f}" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11.5" fill="#e8ecf3" font-weight="600">{mmss(r["best"])}</text>')
    else:
        p.append(f'<text x="{PLOT_X0 + bw + 19:.1f}" y="{y+8.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11" fill="#e8ecf3" font-weight="600">+{r["gap"]:.3f}</text>')
    tc = tire_color(r["tire"]); tz = tire_short(r["tire"])
    p.append(f'<rect x="1100" y="{y-3}" width="36" height="14" rx="3" fill="{tc}" fill-opacity="0.92"/>')
    p.append(f'<text x="1118" y="{y+7.5}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="9.5" fill="#0f131c" font-weight="700" text-anchor="middle">{tz}</text>')

foot_y = ROW_Y0 + N*ROW_H + 12
p.append(f'<line x1="{PLOT_X0}" y1="{foot_y-12}" x2="{PLOT_X1}" y2="{foot_y-12}" stroke="#39404d" stroke-width="1"/>')

legend_y = foot_y + 14
teams_in = []; seen = set()
for r in rows:
    if r["team"] not in seen: seen.add(r["team"]); teams_in.append((r["team"], r["color"]))
PER_ROW = 6
for idx, (tname, tcol) in enumerate(teams_in):
    row_idx = idx // PER_ROW; col_idx = idx % PER_ROW
    leg_x = 30 + col_idx * 180; leg_y_i = legend_y + row_idx * 22
    p.append(f'<rect x="{leg_x}" y="{leg_y_i}" width="10" height="10" rx="2" fill="{hx(tcol)}"/>')
    p.append(f'<text x="{leg_x+15}" y="{leg_y_i+9}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10.5" fill="#9aa5b8" font-weight="400">{tname}</text>')

tire_legend_y = legend_y + ((len(teams_in)+PER_ROW-1)//PER_ROW) * 22 + 10
p.append(f'<text x="920" y="{tire_legend_y+9}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10.5" fill="#8fa0b8" font-weight="600">{t("common.legend_tire")}</text>')
tires_legend = [(tire_short("SOFT"),"#ff3340"),(tire_short("MEDIUM"),"#ffd200"),(tire_short("HARD"),"#e6e6e6"),(tire_short("INTERMEDIATE"),"#3ecf3e"),(tire_short("WET"),"#3aa6ff")]
lx = 956
for tn, tc in tires_legend:
    p.append(f'<rect x="{lx}" y="{tire_legend_y}" width="10" height="10" rx="2" fill="{tc}"/>')
    p.append(f'<text x="{lx+14}" y="{tire_legend_y+9}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10.5" fill="#9aa5b8" font-weight="400">{tn}</text>')
    lx += 50

note_y = tire_legend_y + 30
p.append(f'<text x="30" y="{note_y}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11" fill="#667186" font-weight="400">{t("fp.note")}</text>')
p.append(f'<text x="{W-28}" y="{note_y}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10" fill="#4d5666" font-weight="400" text-anchor="end">{t("common.footer", key=SESSION_KEY, date=DATE_LABEL)}</text>')
p.append('</svg>')

# === 出图：写 SVG → 目标像素尺寸原生矢量渲染（librsvg）→ 直出成图目录 ===
LIB_DIR = f"{CHARTS_DIR}/{SEASON}-R{ROUND}-{STATION}"
os.makedirs(LIB_DIR, exist_ok=True)
WORK_SVG = f"{LIB_DIR}/{FIG_NAME}.svg"
WORK_SVG_HI = f"{LIB_DIR}/.{FIG_NAME}.hi.svg"
WORK_PNG = f"{LIB_DIR}/{FIG_NAME}.png"

# 1. 写 SVG
svg_content = "\n".join(p)
with open(WORK_SVG, "w", encoding="utf-8") as f:
    f.write(svg_content)
print(f"[1/3] SVG written: {WORK_SVG}", file=sys.stderr)

# 2. 根元素宽高改成目标像素尺寸 → librsvg 原生按该尺寸矢量渲染
#    （ffmpeg 的 librsvg 只认 SVG 自带宽高，-vf scale 只是位图放大，会糊）
TARGET_W = 2400
m = re.search(r'(<svg\b[^>]*?)width="([\d.]+)"\s+height="([\d.]+)"', svg_content)
assert m, "SVG 根元素缺少 width/height"
TARGET_H = round(float(m.group(3)) * TARGET_W / float(m.group(2)))
with open(WORK_SVG_HI, "w", encoding="utf-8") as f:
    f.write(svg_content[:m.start()] + f'{m.group(1)}width="{TARGET_W}" height="{TARGET_H}"' + svg_content[m.end():])

ffmpeg_cmd = ["ffmpeg", "-y", "-i", WORK_SVG_HI, "-frames:v", "1", "-update", "1", WORK_PNG]
subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.remove(WORK_SVG_HI)
print(f"[2/3] rasterized: {WORK_PNG} ({TARGET_W}x{TARGET_H}) via librsvg 原生渲染", file=sys.stderr)

# 3. 产物已直出成图目录，无需同步
print(f"[3/3] done: {LIB_DIR}/", file=sys.stderr)

# 数据摘要（调试输出）
print(f"P1: {rows[0]['name']} {rows[0]['best']:.3f}s ({rows[0]['team']})", file=sys.stderr)
print(f"laps_total={len(clean)}  drivers={N}", file=sys.stderr)
for i, r in enumerate(rows[:10]):
    print(f"  P{i+1} #{r['num']:<3} {r['name']:<12} {r['cn']:<6} {r['best']:.3f}s +{r['gap']:.3f}", file=sys.stderr)
