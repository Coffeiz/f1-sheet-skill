#!/usr/bin/env python3
"""F1 正赛长距离节奏图 · 母版 f1_chart_r（librsvg 原生矢量栅格化，不做位图放大）

数据源: OpenF1 /v1/laps /v1/stints /v1/session_result /v1/drivers
核心: 每位车手一行，横轴是 race progress（+0s ~ 最慢完赛秒数），中间按 stint 胎段画节奏条 + 圈速 dot
样式: 1200x920 圆角卡片化（沿用早期赞德沃特产物范式）

用法: python3 f1_chart_r.py <session_key> [--prefix 前缀] [--station 站名] [--round N]
                           [--gp-name 大奖赛名] [--date YYYY-MM-DD] [--fig-name 图名] [--laps N]
      数据先跑 f1_fetch.py <session_key>（默认落到 data/s<session_key>_*.json）
      总圈数默认取冠军完成圈数，需要时用 --laps 覆盖
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

# 车手/分站/胎色共享字典：与 f1_chart_fp.py / f1_chart_q.py 同源，改字典改 f1_dict.py 一处
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f1_dict import CN, tire_color, tire_zh, resolve_session, load_json
from f1_i18n import add_lang_arg, init, t, tire_short, is_zh

DEFAULT_SESSION_KEY = 11353   # 无参数时的兜底场次（赞德沃特正赛）；常规用法是传 session_key


def parse_args():
    ap = argparse.ArgumentParser(description=t("r.desc"))
    add_lang_arg(ap)
    ap.add_argument("session_key", nargs="?", type=int, help="场次 session_key，如 11353")
    ap.add_argument("--prefix", help="data/ 里的数据前缀（默认 s<session_key>）")
    ap.add_argument("--station", help="分站中文名（覆盖字典）")
    ap.add_argument("--round", type=int, help="站序（覆盖字典）")
    ap.add_argument("--gp-name", help="标题用的大奖赛名（覆盖字典）")
    ap.add_argument("--date", help="页脚日期标注（覆盖 session 日期）")
    ap.add_argument("--fig-name", help="输出图名（覆盖默认拼法）")
    ap.add_argument("--laps", type=int, help="总圈数（默认取冠军完成圈数）")
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
_FIG_KEY = "r.fig_sprint" if STAGE == "Sprint" else "r.fig_race"
_STAGE_CN = t("r.stage_sprint") if STAGE == "Sprint" else t("r.stage_race")
FIG_NAME = META["fig_name"] or t(_FIG_KEY, station=STATION)

if STAGE and STAGE != "R":
    print(t("common.warn_stage", stage=STAGE,
            chart="正赛长距离节奏图" if is_zh() else "race long-run pace chart",
            expected="正赛" if is_zh() else "race"), file=sys.stderr)
for _k in META["missing"]:
    print(t("common.warn_missing", item=_k), file=sys.stderr)




def build_svg():
    p = []
    p.append('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="920" viewBox="0 0 1200 920">')
    # 渐变背景 + 圆角
    p.append('<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="#151a26"/>'
             '<stop offset="1" stop-color="#0f131c"/></linearGradient></defs>')
    p.append('<rect width="1200" height="920" rx="14" fill="url(#bg)"/>')

    # 读数据（数据目录＝脚本同级 F1/data）
    laps = load_json(DATA_DIR, PREFIX, "laps")
    stints = load_json(DATA_DIR, PREFIX, "stints")
    results = load_json(DATA_DIR, PREFIX, "result")
    drivers_list = load_json(DATA_DIR, PREFIX, "drivers")

    drivers = {d["driver_number"]: d for d in drivers_list}

    # 总圈数：冠军完成圈数（可用 --laps 覆盖）
    TOTAL_LAPS = ARGS.laps or max((r.get("number_of_laps") or 0) for r in results)

    # === 全场统计（用于底部注释） ===
    # 最快圈
    _clean_laps = [L for L in laps if L.get("lap_duration") and not L.get("is_pit_out_lap")]
    if _clean_laps:
        _best_lap = min(_clean_laps, key=lambda x: x["lap_duration"])
        best_overall = _best_lap["lap_duration"]
        _bn = _best_lap["driver_number"]
        _d = drivers.get(_bn, {})
        # OpenF1 /v1/drivers 字段：full_name/name_acronym/broadcast_name/team_name/team_colour/country_code
        best_drv = {
            "name": _d.get("name_acronym") or _d.get("broadcast_name") or _d.get("full_name") or "?",
            "num": _bn,
            "full": _d.get("full_name", ""),
        }
    else:
        best_overall = 0.0
        best_drv = {"name": "?", "num": "?", "full": ""}
    # DNF 数
    dnf_count = sum(1 for r in results if r.get("position") is None)
    # W (画布宽)
    W = 1200

    # 排序：position 升序，None 排最后
    sorted_results = sorted(results, key=lambda x: (x.get("position") is None, x.get("position") or 99))
    # DNF 保留名次：完赛者用官方 position，退赛者按完成圈数降序接在最后一位完赛者之后编号（如 22 位车手里退赛 3 人 → P20/P21/P22）
    _finishers = [r for r in sorted_results if r.get("position") is not None]
    _dnfs = [r for r in sorted_results if r.get("position") is None]
    _next_pos = (max(r["position"] for r in _finishers) if _finishers else 0) + 1
    _dnfs.sort(key=lambda x: -(x.get("number_of_laps") or 0))
    for _i, _r in enumerate(_dnfs):
        _r["display_position"] = _next_pos + _i
    for _r in _finishers:
        _r["display_position"] = _r["position"]
    sorted_results = _finishers + _dnfs
    leader_laps = {}  # 头车每一圈的时间戳（用于算 race progress）
    leader_driver = None
    for r in sorted_results:
        if r.get("position") == 1:
            leader_driver = r["driver_number"]
            leader_duration = r.get("duration") or [None]
            if isinstance(leader_duration, list):
                leader_total = leader_duration[0] if leader_duration else None
            else:
                leader_total = leader_duration
            break

    # 头车每圈的累计时间（基于 laps）
    leader_lap_data = sorted([L for L in laps if L["driver_number"] == leader_driver],
                             key=lambda x: x["lap_number"])
    leader_cum = {}  # lap_number -> 累计秒数（到该圈完成为止）
    cum = 0.0
    for L in leader_lap_data:
        dur = L.get("lap_duration")
        if dur is None: continue
        cum += dur
        leader_cum[L["lap_number"]] = cum

    # 计算横轴范围：race progress = 头车累计差 + 一些缓冲
    # 用 gap_to_leader 最大值 + 头车总时间作 X 轴
    max_gap = 0.0
    for r in sorted_results:
        if r.get("gap_to_leader") is None: continue
        g = r["gap_to_leader"]
        if isinstance(g, (int, float)) and g > max_gap:
            max_gap = g
    # 横轴最大 = max_gap + 缓冲（如果全场都跑完），如果有人 +LAP 用 90s 估算
    x_max = max(85, max_gap + 5)
    x_max = 95  # 跟旧产物对齐 ~85s 范围

    # 脏圈阈值：单圈 lap_duration > 1.25 * 全场中位单圈时长
    all_clean_durs = [L["lap_duration"] for L in laps
                      if L.get("lap_duration") and not L.get("is_pit_out_lap")]
    all_clean_durs.sort()
    median_lap = all_clean_durs[len(all_clean_durs)//2]
    dirty_threshold = median_lap * 1.25
    p.append(f'<!-- dirty-lap threshold: {dirty_threshold:.1f}s (median {median_lap:.1f}s * 1.25) -->')

    # 冠军信息（标题副标）
    winner = drivers.get(leader_driver, {})
    winner_full = winner.get("full_name", f"#{leader_driver}")
    winner_cn = CN.get(leader_driver, "")
    winner_team = winner.get("team_name", "?")
    winner_color = winner.get("team_colour", "888888")
    winner_dur_str = f"{int(leader_total//3600)}:{int((leader_total%3600)//60):02d}:{leader_total%60:06.3f}" if leader_total else "—"

    _cn_txt = f" {winner_cn}" if (winner_cn and is_zh()) else ""

    # === 顶部标题 ==="
    p.append(f'<rect x="24" y="26" width="4" height="46" rx="2" fill="#{winner_color}"/>')
    p.append(f'<text x="40" y="50" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="24" fill="#f4f6fa" font-weight="700">{t("r.title", year=DATE_LABEL[:4], gp=GP_NAME)}</text>')
    p.append(f'<text x="40" y="74" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="12.5" fill="#a3adc0" font-weight="400">{t("r.sub", name=winner_full, cn=_cn_txt, team=winner_team, dur=winner_dur_str, n=len(sorted_results), dirty=f"{dirty_threshold:.1f}")}</text>')

    # === 横轴 grid + 标签（y=116 ~ 712 是数据区，header 在 y=116 之上）===
    PLOT_X0 = 430  # 中间区域起点
    PLOT_X1 = 1150  # 中间区域终点
    RIGHT_X0 = 1000  # 右侧 stint 面板起点
    RIGHT_W = 150  # 右侧 stint 面板总宽（按圈数比例分配）
    PLOT_Y0 = 116  # 横轴标签行
    PLOT_Y1 = 770  # 末行底线（22 行 × 28 + 起始 144 = 760，留 10px 缓冲）
    HEADER_Y = 116  # 数据区起始 y
    ROW_H = 28
    ROW_Y0 = HEADER_Y + 28  # 第一行 y（HEADER_Y + 28）

    # 头部白条（数据区顶部）
    p.append(f'<rect x="24" y="{PLOT_Y0}" width="1152" height="{ROW_H}" rx="6" fill="#ffffff" fill-opacity="0.045"/>')
    p.append(f'<text x="36" y="{PLOT_Y0+19}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11.5" fill="#8fa0b8" font-weight="600" letter-spacing="1">{t("r.col_gap", stage=_STAGE_CN)}</text>')

    # 横向 grid（每 12.1s 一格，实测约 3.826px/秒，跟旧产物对齐）
    x_step = 12.1
    RATE = 46.3 / x_step
    n_cols = 8
    for i in range(n_cols):
        gx = PLOT_X0 + i * x_step * RATE
        if gx > PLOT_X1: break
        gap_s = i * x_step
        p.append(f'<line x1="{gx:.1f}" y1="{PLOT_Y0}" x2="{gx:.1f}" y2="{PLOT_Y1}" stroke="#252c3c" stroke-width="1"/>')
        p.append(f'<text x="{gx:.1f}" y="{PLOT_Y0-10}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10.5" fill="#5f6a7d" font-weight="400" text-anchor="middle">+{gap_s:.1f}s</text>')

    # === 每位车手一行 ===
    n_rows = 0
    for r_idx, r in enumerate(sorted_results):
        pos = r.get("display_position", r.get("position"))
        num = r["driver_number"]
        d = drivers.get(num, {})
        dnf = bool(r.get("dnf")) or r.get("position") is None

        # 行 y
        row_y = HEADER_Y + 28 + n_rows * ROW_H  # 留 28 给 header
        if n_rows >= 1:
            row_y = HEADER_Y + (1 + n_rows) * ROW_H
        # 偶数行底色
        if n_rows % 2 == 1:
            p.append(f'<rect x="24" y="{row_y}" width="1152" height="{ROW_H}" fill="#ffffff" fill-opacity="0.022"/>')
        n_rows += 1

        # P1 紫色高亮
        is_p1 = (pos == 1)
        pos_color = "#C77DFF" if is_p1 else "#77839a"

        # 行内容
        # 左侧位置标签
        p.append(f'<text x="56" y="{row_y+19}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12.5" fill="{pos_color}" font-weight="700" text-anchor="end">{f"P{pos}" if pos else "DNF"}</text>')

        # P1 中间数据区的 BEST 微章（画在中间 gap 条位置，见下方 lap_x）
        if is_p1:
            p.append(f'<rect x="{PLOT_X0+9}" y="{row_y+8}" width="56" height="16" rx="8" fill="#C77DFF"/>')
            p.append(f'<text x="{PLOT_X0+37}" y="{row_y+19.5}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="9.5" fill="#170f26" font-weight="800" text-anchor="middle">BEST</text>')

        # 车手名 + 中文名
        last = d.get("last_name", f"#{num}")
        cn = CN.get(num, "")
        p.append(f'<text x="66" y="{row_y+19}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13.5" fill="#eef1f6" font-weight="600">{last}</text>')
        if is_zh():
            p.append(f'<text x="184" y="{row_y+19}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11" fill="#6b7689" font-weight="400">{cn}</text>')

        # 车队色条 + 车队名
        team_color = d.get("team_colour", "888888")
        team_name = d.get("team_name", "?")
        p.append(f'<rect x="260" y="{row_y+9}" width="8" height="14" rx="2" fill="#{team_color}"/>')
        p.append(f'<text x="274" y="{row_y+19}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11.5" fill="#9aa5b8" font-weight="400">{team_name}</text>')

        # 圈数（显示在中间 gap 条之后）
        laps_count = r.get("number_of_laps", 0)

        # 中间：相对冠军秒差 gap 条（按车队色，实测约 3.826px/秒）
        gap_val = r.get("gap_to_leader")
        if dnf:
            mid_txt, mid_col, mid_end = "DNF", "#7c879b", PLOT_X0
        elif pos == 1:
            mid_txt, mid_col, mid_end = "", "#DBAFFF", PLOT_X0
        elif isinstance(gap_val, str):
            mid_txt, mid_col, mid_end = gap_val, "#eef1f6", PLOT_X0
        else:
            mid_end = PLOT_X0 + float(gap_val) * RATE
            mid_txt, mid_col = f"+{float(gap_val):.3f}", "#eef1f6"
        _txt_w = len(mid_txt) * 6.4  # 10.5px 字体宽度估算（防止与圈数文字相撞）
        bar_w = mid_end - PLOT_X0
        if bar_w > 2:
            p.append(f'<rect x="{PLOT_X0}" y="{row_y+9.5}" width="{bar_w:.1f}" height="13" rx="6.5" fill="#{team_color}" fill-opacity="0.92"/>')
            p.append(f'<text x="{mid_end+9:.1f}" y="{row_y+19}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10.5" fill="{mid_col}" font-weight="600">{mid_txt}</text>')
            lap_x = max(mid_end + 62, mid_end + 9 + _txt_w + 14)
        else:
            p.append(f'<rect x="{PLOT_X0}" y="{row_y+9.5}" width="3" height="13" rx="1.5" fill="#{team_color}"/>')
            p.append(f'<text x="{PLOT_X0+11}" y="{row_y+19}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10.5" fill="{mid_col}" font-weight="600">{mid_txt}</text>')
            lap_x = max(PLOT_X0 + 58, PLOT_X0 + 11 + _txt_w + 14)
        if is_p1:
            lap_x = PLOT_X0 + 79  # 让开中间 BEST 微章
        p.append(f'<text x="{lap_x:.1f}" y="{row_y+19}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10.5" fill="#7c879b" font-weight="400">{laps_count}/{TOTAL_LAPS}l</text>')
        driver_stints = sorted([s for s in stints if s["driver_number"] == num],
                               key=lambda x: x["stint_number"])

        # 右侧 stint 段标注（按各 stint 圈数比例占宽，统一面板对齐）
        _seg_scale = RIGHT_W / TOTAL_LAPS
        seg_x = RIGHT_X0
        for s in driver_stints:
            color = tire_color(s.get("compound", ""))
            compound_zh = tire_zh(s.get("compound", "")) if is_zh() else tire_short(s.get("compound", ""))
            st_laps = int((s.get("lap_end") or 0) - (s.get("lap_start") or 0) + 1)
            if st_laps < 1:
                st_laps = 1
            seg_full = st_laps * _seg_scale
            seg_w = max(2.0, seg_full - 1)
            p.append(f'<rect x="{seg_x:.1f}" y="{row_y+9.5}" width="{seg_w:.1f}" height="13" rx="2" fill="{color}" fill-opacity="0.92"/>')
            if seg_w >= 14:
                p.append(f'<text x="{seg_x+seg_w/2:.1f}" y="{row_y+19.5}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10" fill="#0f131c" font-weight="700" text-anchor="middle">{compound_zh}</text>')
            seg_x += seg_full

        # 行底线
        p.append(f'<line x1="24" y1="{row_y+ROW_H-1}" x2="1176" y2="{row_y+ROW_H-1}" stroke="#141a25" stroke-width="1"/>')

    # === 底部：车队色块 + 胎色图例 + 注释（复用 FP v7 范式） ===
    foot_y = ROW_Y0 + n_rows * ROW_H + 12
    p.append(f'<line x1="{PLOT_X0}" y1="{foot_y-12}" x2="{PLOT_X1}" y2="{foot_y-12}" stroke="#39404d" stroke-width="1"/>')

    legend_y = foot_y + 14
    teams_in = []; seen = set()
    for d in drivers.values():
        tn = d.get("team_name", "?")
        tc = d.get("team_colour", "888888")
        if tn not in seen: seen.add(tn); teams_in.append((tn, tc))
    PER_ROW = 6
    for idx, (tname, tcol) in enumerate(teams_in):
        row_idx = idx // PER_ROW; col_idx = idx % PER_ROW
        leg_x = 30 + col_idx * 180; leg_y_i = legend_y + row_idx * 22
        p.append(f'<rect x="{leg_x}" y="{leg_y_i}" width="10" height="10" rx="2" fill="#{tcol}"/>')
        p.append(f'<text x="{leg_x+15}" y="{leg_y_i+9}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="10.5" fill="#9aa5b8" font-weight="400">{tname}</text>')

    tire_legend_y = legend_y + ((len(teams_in)+PER_ROW-1)//PER_ROW) * 22 + 10
    p.append(f'<text x="920" y="{tire_legend_y+9}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10.5" fill="#8fa0b8" font-weight="600">{t("common.legend_tire")}</text>')
    tires_legend = [(t("tire.SOFT"),"#ff3340"),(t("tire.MEDIUM"),"#ffd200"),(t("tire.HARD"),"#e6e6e6"),(t("tire.INTERMEDIATE"),"#3ecf3e"),(t("tire.WET"),"#3aa6ff")]
    lx = 956
    for tn, tc in tires_legend:
        p.append(f'<rect x="{lx}" y="{tire_legend_y}" width="10" height="10" rx="2" fill="{tc}"/>')
        p.append(f'<text x="{lx+14}" y="{tire_legend_y+9}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10.5" fill="#9aa5b8" font-weight="400">{tn}</text>')
        lx += 50

    note_y = tire_legend_y + 30
    p.append(f'<text x="30" y="{note_y}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="11" fill="#667186" font-weight="400">{t("r.note1")}</text>')
    _bn = best_drv["num"]
    p.append(f'<text x="30" y="{note_y+18}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10.5" fill="#667186" font-weight="400">{t("r.note2", best=f"{best_overall:.3f}", name=best_drv["name"], num=_bn, laps=TOTAL_LAPS, dnf=dnf_count)}</text>')
    p.append(f'<text x="{W-28}" y="{note_y+18}" font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif" font-size="10" fill="#4d5666" font-weight="400" text-anchor="end">{t("common.footer", key=SESSION_KEY, date=DATE_LABEL)}</text>')

    p.append('</svg>')
    return p


# === 出图：写 SVG → 目标像素尺寸原生矢量渲染（librsvg）→ 直出成图目录 ===
LIB_DIR = f"{CHARTS_DIR}/{SEASON}-R{ROUND}-{STATION}"
os.makedirs(LIB_DIR, exist_ok=True)
WORK_SVG = f"{LIB_DIR}/{FIG_NAME}.svg"
WORK_SVG_HI = f"{LIB_DIR}/.{FIG_NAME}.hi.svg"
WORK_PNG = f"{LIB_DIR}/{FIG_NAME}.png"

# 1. 写 SVG
p = build_svg()
svg_content = "\n".join(p)
with open(WORK_SVG, "w", encoding="utf-8") as f:
    f.write(svg_content)
print(f"[1/3] SVG written: {WORK_SVG}", file=sys.stderr)

# 2. 根元素宽高改成目标像素尺寸 → librsvg 原生按该尺寸矢量渲染
#    （ffmpeg 的 librsvg 只认 SVG 自带宽高，-vf scale 只是位图放大，会糊；画布 1200:920）
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

print(f"OK: {FIG_NAME}", file=sys.stderr)