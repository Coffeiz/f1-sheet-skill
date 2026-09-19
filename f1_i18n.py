#!/usr/bin/env python3
"""F1 图件文案字典（i18n）—— 所有面向用户的文字集中在这里

用法
    from f1_i18n import add_lang_arg, init, t, tire_short, is_zh
    add_lang_arg(ap)              # 给 argparse 加 --lang
    ARGS = ap.parse_args()
    init(ARGS.lang)               # 定语言（不传就靠环境变量 / 默认）
    print(t("common.footer", key=11363, date="2026-09-12"))

约定
  - 脚本里不写死可见文字，一律 t("key", **kw)；key 用点分嵌套，按脚本/图归类
  - 语言优先级：--lang > 环境变量 F1_LANG > 系统 locale 自动判 > 默认 zh
    （locale 判法见 ZH_REGIONS：简中习惯区走 zh，HK/TW/MO 及所有非中文 locale 走 en）
  - 车手中文名只在 zh 下显示；各母版用 is_zh() 决定要不要画中文名列
  - 新增文案：两套字典都要加；缺 en 会回落 zh 并在 stderr 提醒（不静默）
"""
import locale
import os
import sys

LANGS = ("zh", "en")
DEFAULT_LANG = "zh"

# 默认按系统 locale 自动选语言：
#   zh_CN / zh_SG / zh_MY 等简中习惯区 -> zh
#   其余（含 zh_HK / zh_TW / zh_MO 这类繁体区，以及任何非中文 locale）-> en
# 要强制指定：传 --lang zh|en，或设环境变量 F1_LANG。
ZH_REGIONS = {"CN", "SG", "MY"}

# key 命名：common.* 通用 / tire.* 胎名 / <脚本前缀>.* 各图专属
# 占位符用 str.format 语法，脚本调用时传关键字参数
STRINGS = {
    "zh": {
        # ---------------- 通用 ----------------
        "common.footer": "数据 via OpenF1 · session_key={key} · 咕咕整理 · {date}",
        "common.warn_missing": "[警告] {item} 没能自动推断，请用命令行参数覆盖（--station/--round/--gp-name）",
        "common.warn_stage": "[警告] 该 session 是 {stage}，{chart} 按 {expected} 口径出图，确认没拿错脚本",
        "common.legend_tire": "胎色",
        "common.legend_team": "车手",
        # ---------------- 胎名（图内小格用短名） ----------------
        "tire.SOFT": "软", "tire.MEDIUM": "中", "tire.HARD": "硬",
        "tire.INTERMEDIATE": "间", "tire.WET": "雨", "tire.UNKNOWN": "—",
        # ---------------- FP 圈速差距图 ----------------
        "fp.desc": "F1 FP 圈速差距图（数据先跑 f1_fetch.py）",
        "fp.fig": "F1{station}-{stage}-圈速差距图",
        "fp.sub": "最快 {name}（{team}）· 共 {n} 位车手",
        "fp.col_stage": "{stage} 圈速对比",
        "fp.col_tire": "最快圈胎",
        "fp.note": "注：圈速差距相对 P1；右侧色块为该车手最快圈的用胎（红=软/黄=中/白=硬/绿=间/蓝=雨）",
        # ---------------- Q 排位圈速差距图 ----------------
        "q.desc": "F1 排位赛圈速差距图（数据先跑 f1_fetch.py）",
        "q.fig": "F1{station}-{stage}-圈速差距图",
        "q.sub": "杆位 {name}（{team}）{time} · 共 {n} 位车手",
        "q.col_gap": "排位赛 · 秒差（相对杆位）",
        "q.col_best": "最快圈",
        "q.col_stage": "阶段",
        "q.bound_q2": "{stage}2 淘汰线（P11–P15）",
        "q.bound_q1": "{stage}1 淘汰线（P16–P22）",
        "q.note1": "注：秒差 = 该车手分类圈（所在最深阶段的最快圈）相对杆位圈 {pole} 的差值；{stage}1/{stage}2 成绩含赛道演进影响，仅供参考",
        "q.note2": "P1–P10 进 {stage}3 · P11–P15 {stage}2 淘汰 · P16–P22 {stage}1 淘汰（淘汰行压暗）",
        # ---------------- R 正赛长距离节奏图 ----------------
        "r.desc": "F1 正赛长距离节奏图（数据先跑 f1_fetch.py）",
        "r.fig_race": "F1{station}-正赛-长距离图",
        "r.fig_sprint": "F1{station}-Sprint-长距离图",
        "r.stage_race": "正赛",
        "r.stage_sprint": "冲刺赛",
        "r.title": "{year} F1 {gp}长距离表现",
        "r.sub": "冠军 {name}{cn}（{team}）· 完赛时长 {dur} · 统计 {n} 位车手 · 脏圈阈值 {dirty}s",
        "r.col_gap": "{stage}相对冠军差距",
        "r.note1": "注：按名次排序，条 = 相对冠军秒差（车队色）；套圈写 +N LAPS；退赛保留名次（按完成圈数排）、数据条写 DNF；右侧色块 = 各 stint 用胎（宽度按圈数比例）",
        "r.note2": "最快圈 {best}s（{name} · #{num}）· 总圈数 {laps} · DNF {dnf}",
        # ---------------- 长距离速度图 ----------------
        "long.desc": "F1 长距离速度图（数据先跑 f1_fetch.py）",
        "long.fig": "F1{station}-{stage}-长距离速度图",
        "long.title": "F1 {station} {stage} · 长距离速度 · 一车一行多胎",
        "long.xlabel": "段尾 {tail} 个干净圈：条 = 最快→最慢，点 = 平均（分:秒）",
        "long.legend": "{tire}胎",
        "long.note": "口径：每车每胎取圈数最多的合格 stint（段长 ≥{min_seg} 圈，剔除 >最快圈×{cut}）；行内自上而下为软/中/硬，缺失即该胎无长段",
        "long.stats": "车手数 {drivers} · 段数 {stints}",
        # ---------------- 长距离衰减轨迹图 ----------------
        "traj.desc": "F1 长距离衰减轨迹图（数据先跑 f1_fetch.py）",
        "traj.fig": "F1{station}-{stage}-长距离衰减轨迹图",
        "traj.title": "F1 {station} {stage} · 长距离衰减轨迹 · 各 stint 圈速走势",
        "traj.panel": "{tire}胎 · {n} 段",
        "traj.xlabel": "胎龄（圈）",
        "traj.ylabel": "圈速（分:秒）",
        "traj.note": "口径：每套合格 stint（段长 ≥{min_seg} 圈，剔除 >最快圈×{cut} 的脏圈）逐圈画出，被剔除的慢圈不占位置（跨过它直接连）；",
        "traj.note2": "同车同胎有多套时第二套起用虚线并标序号",
        "traj.stats": "  {tire}胎 · {n} 段",
        # ---------------- 抓数控制台（f1_fetch.py） ----------------
        "fetch.not_counted": "（不计站）",
        "fetch.rounds_total": "\n共 {n} 站（已排除赛前测试）",
        "fetch.sessions_total": "\n共 {n} 场次",
        "fetch.skip_endpoint": "跳过未知端点: {name}",
        "fetch.fail": "[失败] {name}: {err}",
        "fetch.ok": "[ok] {name:<8} {n:>6} 条 -> {path}",
        # ---------------- 全站调度控制台（f1_weekend.py） ----------------
        "weekend.desc": "F1 一个周末全站出图（抓数 + 出图）",
        "weekend.help_meeting": "meeting_key，例 1292",
        "weekend.help_round": "用站序代替 meeting_key",
        "weekend.help_only": "只跑指定阶段，逗号分隔，如 FP1,Q,R",
        "weekend.help_dry_run": "只列计划，不执行",
        "weekend.help_refetch": "已有数据也重新抓",
        "weekend.err_no_key": "请给一个 meeting_key，或用 --round <站序>",
        "weekend.err_round_unknown": "[错误] 字典里查不到第 {round} 站，请直接传 meeting_key",
        "weekend.unknown_station": "未知分站",
        "weekend.header": "== 第 {round} 站 · {station} · meeting_key={key}",
        "weekend.skip_session": "  - 跳过 {name}（没有对应母版）",
        "weekend.err_no_plan": "[错误] 该站没有可出图的场次（检查 --only 或场次数据）",
        "weekend.plan_count": "\n计划：{n} 场",
        "weekend.state_have": "数据已有",
        "weekend.state_todo": "待抓数",
        "weekend.row": "  {stage:<6} {label:<5} key={key}  {when}  {state:<8}  {script}",
        "weekend.skipped_fetch": "  （已有数据，跳过抓取；要重抓加 --refetch）",
        "weekend.fail_fetch": "{stage} 抓数失败",
        "weekend.fail_chart": "{stage} 出图失败",
        "weekend.summary": "\n== 小结 ==",
        "weekend.all_done": "  {n} 场全部完成 ✅",
    },
    "en": {
        # ---------------- common ----------------
        "common.footer": "Data via OpenF1 · session_key={key} · chart by gugu · {date}",
        "common.warn_missing": "[warn] could not infer {item}; override with --station / --round / --gp-name",
        "common.warn_stage": "[warn] session is {stage}, but {chart} renders {expected} charts - check the script",
        "common.legend_tire": "Tyre",
        "common.legend_team": "Driver",
        # ---------------- tyre ----------------
        "tire.SOFT": "S", "tire.MEDIUM": "M", "tire.HARD": "H",
        "tire.INTERMEDIATE": "I", "tire.WET": "W", "tire.UNKNOWN": "-",
        # ---------------- FP gap chart ----------------
        "fp.desc": "F1 practice lap-gap chart (run f1_fetch.py first)",
        "fp.fig": "F1{station}-{stage}-lap-gap",
        "fp.sub": "Fastest {name} ({team}) · {n} drivers",
        "fp.col_stage": "{stage} lap time",
        "fp.col_tire": "Best-lap tyre",
        "fp.note": "Note: gaps are relative to P1; the chip on the right is the tyre used on that driver's fastest lap (red=soft / yellow=medium / white=hard / green=intermediate / blue=wet)",
        # ---------------- Qualifying gap chart ----------------
        "q.desc": "F1 qualifying lap-gap chart (run f1_fetch.py first)",
        "q.fig": "F1{station}-{stage}-lap-gap",
        "q.sub": "Pole {name} ({team}) {time} · {n} drivers",
        "q.col_gap": "Qualifying · gap to pole",
        "q.col_best": "Best lap",
        "q.col_stage": "Segment",
        "q.bound_q2": "{stage}2 cut-off (P11-P15)",
        "q.bound_q1": "{stage}1 cut-off (P16-P22)",
        "q.note1": "Note: gap = the driver's best lap in their deepest segment, relative to pole {pole}; {stage}1/{stage}2 times include track evolution - reference only",
        "q.note2": "P1-P10 advance to {stage}3 · P11-P15 out in {stage}2 · P16-P22 out in {stage}1 (eliminated rows dimmed)",
        # ---------------- Race long-run pace chart ----------------
        "r.desc": "F1 race long-run pace chart (run f1_fetch.py first)",
        "r.fig_race": "F1{station}-race-long-run",
        "r.fig_sprint": "F1{station}-sprint-long-run",
        "r.stage_race": "Race",
        "r.stage_sprint": "Sprint",
        "r.title": "{year} F1 {gp} long-run pace",
        "r.sub": "Winner {name}{cn} ({team}) · total time {dur} · {n} drivers · dirty-lap threshold {dirty}s",
        "r.col_gap": "Gap to winner - {stage}",
        "r.note1": "Note: sorted by position; bar = gap to winner in team colour; lapped cars show +N LAPS; retired cars keep a position (ordered by laps completed) with a DNF bar; blocks on the right = stints, width proportional to laps",
        "r.note2": "Fastest lap {best}s ({name} · #{num}) · {laps} laps · DNF {dnf}",
        # ---------------- Long-run pace chart ----------------
        "long.desc": "F1 long-run pace chart (run f1_fetch.py first)",
        "long.fig": "F1{station}-{stage}-long-run-pace",
        "long.title": "F1 {station} {stage} · Long-run pace · one row per driver, per compound",
        "long.xlabel": "Last {tail} clean laps: bar = fastest → slowest, dot = mean (m:ss)",
        "long.legend": "{tire} tyre",
        "long.note": "Definition: per driver per compound, the longest eligible stint (>= {min_seg} laps, dropping laps slower than best x {cut}); rows read soft / medium / hard top to bottom, a gap means no long run on that compound",
        "long.stats": "drivers {drivers} · stints {stints}",
        # ---------------- Long-run degradation chart ----------------
        "traj.desc": "F1 long-run degradation chart (run f1_fetch.py first)",
        "traj.fig": "F1{station}-{stage}-long-run-degradation",
        "traj.title": "F1 {station} {stage} · Long-run degradation · lap time trend per stint",
        "traj.panel": "{tire} · {n} stints",
        "traj.xlabel": "Tyre age (laps)",
        "traj.ylabel": "Lap time (m:ss)",
        "traj.note": "Definition: every eligible stint (>= {min_seg} laps, dropping laps slower than best x {cut}) drawn lap by lap; dropped slow laps take no slot (the line skips them);",
        "traj.note2": "a second stint on the same compound is dashed and numbered",
        "traj.stats": "  {tire} · {n} stints",
        # ---------------- fetch console (f1_fetch.py) ----------------
        "fetch.not_counted": "(not a round)",
        "fetch.rounds_total": "\n{n} rounds (pre-season testing excluded)",
        "fetch.sessions_total": "\n{n} sessions",
        "fetch.skip_endpoint": "skipping unknown endpoint: {name}",
        "fetch.fail": "[fail] {name}: {err}",
        "fetch.ok": "[ok] {name:<8} {n:>6} rows -> {path}",
        # ---------------- weekend console (f1_weekend.py) ----------------
        "weekend.desc": "F1 full-weekend charts (fetch + render)",
        "weekend.help_meeting": "meeting_key, e.g. 1292",
        "weekend.help_round": "use a round number instead of meeting_key",
        "weekend.help_only": "run only these stages, comma-separated, e.g. FP1,Q,R",
        "weekend.help_dry_run": "list the plan only",
        "weekend.help_refetch": "re-fetch even if the data already exists",
        "weekend.err_no_key": "pass a meeting_key, or use --round <n>",
        "weekend.err_round_unknown": "[error] round {round} not in the dictionary; pass a meeting_key instead",
        "weekend.unknown_station": "unknown round",
        "weekend.header": "== round {round} · {station} · meeting_key={key}",
        "weekend.skip_session": "  - skip {name} (no template)",
        "weekend.err_no_plan": "[error] no renderable sessions for this round (check --only or the session data)",
        "weekend.plan_count": "\nplan: {n} sessions",
        "weekend.state_have": "data ok",
        "weekend.state_todo": "to fetch",
        "weekend.row": "  {stage:<6} {label:<5} key={key}  {when}  {state:<8}  {script}",
        "weekend.skipped_fetch": "  (data present, skipping fetch; add --refetch to force)",
        "weekend.fail_fetch": "{stage} fetch failed",
        "weekend.fail_chart": "{stage} render failed",
        "weekend.summary": "\n== summary ==",
        "weekend.all_done": "  all {n} sessions done ✅",
    },
}

_LANG = None
_LANG_SOURCE = ""   # 语言是按什么定下来的：--lang / F1_LANG / locale / default


def lang_from_locale(raw):
    """把 locale 串（zh_CN.UTF-8 / en-US / zh_TW.Big5 …）判成 zh 或 en。
    判不出来给 None，交给调用方兜底。"""
    s = str(raw or "").split(":")[0].split(".")[0].split("@")[0].replace("-", "_").lower()
    parts = [p for p in s.split("_") if p]
    if not parts:
        return None
    if parts[0] != "zh":
        return "en"                      # 非中文 locale 一律 en
    region = parts[1].upper() if len(parts) > 1 else ""
    return "zh" if region in ZH_REGIONS else "en"


def locale_raw():
    """拿当前环境的 locale 串（先看环境变量，再看 Python 自己看到的）；拿不到给空串。"""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        v = (os.environ.get(var) or "").strip()
        if v and v not in ("C", "POSIX"):
            return v
    try:
        got = locale.getlocale()
        return ".".join(x for x in got if x)
    except Exception:
        return ""


def init(lang=None, use_locale=True):
    """定当前语言：显式参数 > 环境变量 F1_LANG > 系统 locale > 默认 zh。
    use_locale=False 可关掉自动判定（只看显式指定与环境变量）。返回生效语言。
    """
    global _LANG, _LANG_SOURCE
    if lang:
        v, src = str(lang).strip().lower(), "--lang"
    else:
        env = (os.environ.get("F1_LANG") or "").strip().lower()
        if env:
            v, src = env, "F1_LANG"
        elif use_locale:
            raw = locale_raw()
            guess = lang_from_locale(raw)
            v, src = (guess, f"locale({raw})") if guess else (DEFAULT_LANG, "default")
        else:
            v, src = DEFAULT_LANG, "default"
    _LANG = v if v in LANGS else DEFAULT_LANG
    _LANG_SOURCE = src
    return _LANG


def lang_source():
    """语言是按什么定下来的（排查 / 打日志用）"""
    lang()
    return _LANG_SOURCE


def lang():
    """当前语言（未初始化就按默认规则初始化一次）"""
    return _LANG or init()


def is_zh():
    """是否中文；母版用它决定要不要画中文名列"""
    return lang() == "zh"


def t(_key, **kw):
    """取文案：_key 是文案名，其余关键字参数填占位符。
    参数名故意用 _key，避开占位符里可能出现的 key/name（否则会撞成多个值）。
    当前语言没有就回落 zh（并在 stderr 提醒），再没有就报错。
    """
    s = STRINGS.get(lang(), {}).get(_key)
    if s is None:
        s = STRINGS[DEFAULT_LANG].get(_key)
        if s is None:
            raise KeyError(f"缺少文案 key: {_key}")
        print(f"[i18n] {_key} 缺 {lang()} 译文，回落 zh", file=sys.stderr)
    return s.format(**kw) if kw else s


def tire_short(compound):
    """胎名短名（图内小格用）：软/中/硬 → S/M/H"""
    return t(f"tire.{compound or 'UNKNOWN'}")


def add_lang_arg(ap):
    """给 argparse 加统一的口 --lang（各母版都调一行）"""
    ap.add_argument("--lang", choices=list(LANGS),
                    help="图内文案语言。不给就自动判：环境变量 F1_LANG > 系统 locale"
                         "（简中区 zh，HK/TW 及非中文区 en）> zh")
    return ap
