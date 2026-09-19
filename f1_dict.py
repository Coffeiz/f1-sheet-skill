#!/usr/bin/env python3
"""F1 共享字典（2026 赛季）：车手 + 分站 + 胎色

单一来源：f1_chart_fp.py / f1_chart_q.py / f1_chart_r.py 都从这里 import，
不要再在各脚本里各写一份 CN / DRIVERS / tire_color / tire_zh。

维护指引
  - 换赛季：改 YEAR，并把 MEETINGS 换成新赛季排期（站序只计大奖赛，赛前测试不入表）
  - 代班/换号车手：往 DRIVERS 里补一条，未收录的车号脚本会退化显示 #车号，不报错
  - 队色 team_colour：不带 # 号（画图时用 "#"+color 自己拼，胎色表才带 #）
"""
import json
import os

YEAR = "2026"

# ---------------------------------------------------------------- 车手
# 车号 -> 姓氏 / 三字母缩写 / 全名 / 车队 / 队色(不带#) / 中文名
DRIVERS = {
    1:  {"last": "Norris",     "abbr": "NOR", "full": "Lando NORRIS",     "team": "McLaren",        "color": "F47600", "cn": "诺里斯"},
    3:  {"last": "Verstappen", "abbr": "VER", "full": "Max VERSTAPPEN",   "team": "Red Bull Racing", "color": "4781D7", "cn": "维斯塔潘"},
    5:  {"last": "Bortoleto",  "abbr": "BOR", "full": "Gabriel BORTOLETO", "team": "Audi",         "color": "F50537", "cn": "博尔托雷托"},
    10: {"last": "Gasly",      "abbr": "GAS", "full": "Pierre GASLY",     "team": "Alpine",        "color": "00A1E8", "cn": "加斯利"},
    11: {"last": "Perez",      "abbr": "PER", "full": "Sergio PEREZ",     "team": "Cadillac",      "color": "909090", "cn": "佩雷兹"},
    12: {"last": "Antonelli",  "abbr": "ANT", "full": "Kimi ANTONELLI",   "team": "Mercedes",      "color": "00D7B6", "cn": "安东内利"},
    14: {"last": "Alonso",     "abbr": "ALO", "full": "Fernando ALONSO",  "team": "Aston Martin",  "color": "229971", "cn": "阿隆索"},
    16: {"last": "Leclerc",    "abbr": "LEC", "full": "Charles LECLERC",  "team": "Ferrari",       "color": "ED1131", "cn": "勒克莱尔"},
    18: {"last": "Stroll",     "abbr": "STR", "full": "Lance STROLL",     "team": "Aston Martin",  "color": "229971", "cn": "斯特罗尔"},
    22: {"last": "Tsunoda",    "abbr": "TSU", "full": "Yuki TSUNODA",     "team": "Racing Bulls",  "color": "6C98FF", "cn": "角田"},
    23: {"last": "Albon",      "abbr": "ALB", "full": "Alexander ALBON",  "team": "Williams",      "color": "1868DB", "cn": "阿尔本"},
    25: {"last": "Herta",      "abbr": "HER", "full": "Colton HERTA",     "team": "Cadillac",      "color": "909090", "cn": "赫塔"},
    27: {"last": "Hulkenberg", "abbr": "HUL", "full": "Nico HULKENBERG",  "team": "Audi",          "color": "F50537", "cn": "霍肯伯格"},
    30: {"last": "Lawson",     "abbr": "LAW", "full": "Liam LAWSON",      "team": "Red Bull Racing", "color": "4781D7", "cn": "劳森"},
    31: {"last": "Ocon",       "abbr": "OCO", "full": "Esteban OCON",     "team": "Haas F1 Team",  "color": "9C9FA2", "cn": "奥康"},
    36: {"last": "Iwasa",      "abbr": "IWA", "full": "Ayumu IWASA",      "team": "Red Bull Racing", "color": "4781D7", "cn": "岩佐"},
    41: {"last": "Lindblad",   "abbr": "LIN", "full": "Arvid LINDBLAD",   "team": "Racing Bulls",  "color": "6C98FF", "cn": "林德布拉德"},
    43: {"last": "Colapinto",  "abbr": "COL", "full": "Franco COLAPINTO", "team": "Alpine",        "color": "00A1E8", "cn": "科拉平托"},
    44: {"last": "Hamilton",   "abbr": "HAM", "full": "Lewis HAMILTON",   "team": "Ferrari",       "color": "ED1131", "cn": "汉密尔顿"},
    46: {"last": "Browning",   "abbr": "BRO", "full": "Luke BROWNING",    "team": "Williams",      "color": "1868DB", "cn": "布朗宁"},
    55: {"last": "Sainz",      "abbr": "SAI", "full": "Carlos SAINZ",     "team": "Williams",      "color": "1868DB", "cn": "塞恩斯"},
    61: {"last": "Aron",       "abbr": "ARO", "full": "Paul ARON",        "team": "Alpine",        "color": "00A1E8", "cn": "阿伦"},
    63: {"last": "Russell",    "abbr": "RUS", "full": "George RUSSELL",   "team": "Mercedes",      "color": "00D7B6", "cn": "拉塞尔"},
    77: {"last": "Bottas",     "abbr": "BOT", "full": "Valtteri BOTTAS",  "team": "Cadillac",      "color": "909090", "cn": "博塔斯"},
    81: {"last": "Piastri",    "abbr": "PIA", "full": "Oscar PIASTRI",    "team": "McLaren",       "color": "F47600", "cn": "皮亚斯特里"},
    87: {"last": "Bearman",    "abbr": "BEA", "full": "Oliver BEARMAN",   "team": "Haas F1 Team",  "color": "9C9FA2", "cn": "贝尔曼"},
}

# 中文名快捷表（兼容脚本里的 CN.get(n, "") 写法）
CN = {n: d["cn"] for n, d in DRIVERS.items()}

# ---------------------------------------------------------------- 分站（2026，25 站）
# 站序 -> meeting_key / 首日 / OpenF1 location / 中文分站名 / 中文大奖赛名
MEETINGS = {
    1:  {"meeting_key": 1279, "date": "2026-03-06", "location": "Melbourne",          "station": "墨尔本",     "gp": "澳大利亚大奖赛"},
    2:  {"meeting_key": 1280, "date": "2026-03-13", "location": "Shanghai",           "station": "上海",       "gp": "中国大奖赛"},
    3:  {"meeting_key": 1281, "date": "2026-03-27", "location": "Suzuka",             "station": "铃鹿",       "gp": "日本大奖赛"},
    4:  {"meeting_key": 1282, "date": "2026-04-10", "location": "Sakhir",             "station": "萨基尔",     "gp": "巴林大奖赛"},
    5:  {"meeting_key": 1283, "date": "2026-04-17", "location": "Jeddah",             "station": "吉达",       "gp": "沙特阿拉伯大奖赛"},
    6:  {"meeting_key": 1284, "date": "2026-05-01", "location": "Miami Gardens",      "station": "迈阿密",     "gp": "迈阿密大奖赛"},
    7:  {"meeting_key": 1285, "date": "2026-05-22", "location": "Montreal",           "station": "蒙特利尔",   "gp": "加拿大大奖赛"},
    8:  {"meeting_key": 1286, "date": "2026-06-05", "location": "Monte Carlo",        "station": "摩纳哥",     "gp": "摩纳哥大奖赛"},
    9:  {"meeting_key": 1287, "date": "2026-06-12", "location": "Barcelona",          "station": "巴塞罗那",   "gp": "巴塞罗那大奖赛"},
    10: {"meeting_key": 1288, "date": "2026-06-26", "location": "Spielberg",          "station": "施皮尔贝格", "gp": "奥地利大奖赛"},
    11: {"meeting_key": 1289, "date": "2026-07-03", "location": "Silverstone",        "station": "银石",       "gp": "英国大奖赛"},
    12: {"meeting_key": 1290, "date": "2026-07-17", "location": "Spa-Francorchamps",  "station": "斯帕",       "gp": "比利时大奖赛"},
    13: {"meeting_key": 1291, "date": "2026-07-24", "location": "Budapest",           "station": "布达佩斯",   "gp": "匈牙利大奖赛"},
    14: {"meeting_key": 1292, "date": "2026-08-21", "location": "Zandvoort",          "station": "赞德沃特",   "gp": "荷兰大奖赛"},
    15: {"meeting_key": 1293, "date": "2026-09-04", "location": "Monza",              "station": "蒙扎",       "gp": "意大利大奖赛"},
    16: {"meeting_key": 1294, "date": "2026-09-11", "location": "Madrid",             "station": "马德里",     "gp": "西班牙大奖赛"},
    17: {"meeting_key": 1295, "date": "2026-09-24", "location": "Baku",               "station": "巴库",       "gp": "阿塞拜疆大奖赛"},
    18: {"meeting_key": 1308, "date": "2026-10-02", "location": "Kuala Lumpur",       "station": "吉隆坡",     "gp": ""},  # gp 名待确认：OpenF1 该场 meeting_name 给的是 Bahrain Grand Prix，疑似源数据问题，别照抄
    19: {"meeting_key": 1296, "date": "2026-10-09", "location": "Marina Bay",         "station": "新加坡",     "gp": "新加坡大奖赛"},
    20: {"meeting_key": 1297, "date": "2026-10-23", "location": "Austin",             "station": "奥斯汀",     "gp": "美国大奖赛"},
    21: {"meeting_key": 1298, "date": "2026-10-30", "location": "Mexico City",        "station": "墨西哥城",   "gp": "墨西哥城大奖赛"},
    22: {"meeting_key": 1299, "date": "2026-11-06", "location": "Sao Paulo",          "station": "圣保罗",     "gp": "圣保罗大奖赛"},
    23: {"meeting_key": 1300, "date": "2026-11-20", "location": "Las Vegas",          "station": "拉斯维加斯", "gp": "拉斯维加斯大奖赛"},
    24: {"meeting_key": 1301, "date": "2026-11-27", "location": "Lusail",             "station": "卢赛尔",     "gp": "卡塔尔大奖赛"},
    25: {"meeting_key": 1302, "date": "2026-12-04", "location": "Yas Marina",         "station": "亚斯码头",   "gp": "阿布扎比大奖赛"},
}

# 英文站名 / 大奖赛名（与 MEETINGS 同站序；图内语言切 en 时用）
# 键与 MEETINGS 的站序一一对应；gp 留空的与 MEETINGS 同口径（不猜）
MEETING_EN = {
    1:  {"station": "Melbourne",    "gp": "Australian Grand Prix"},
    2:  {"station": "Shanghai",     "gp": "Chinese Grand Prix"},
    3:  {"station": "Suzuka",       "gp": "Japanese Grand Prix"},
    4:  {"station": "Sakhir",       "gp": "Bahrain Grand Prix"},
    5:  {"station": "Jeddah",       "gp": "Saudi Arabian Grand Prix"},
    6:  {"station": "Miami",        "gp": "Miami Grand Prix"},
    7:  {"station": "Montreal",     "gp": "Canadian Grand Prix"},
    8:  {"station": "Monte Carlo",  "gp": "Monaco Grand Prix"},
    9:  {"station": "Barcelona",    "gp": "Barcelona Grand Prix"},
    10: {"station": "Spielberg",    "gp": "Austrian Grand Prix"},
    11: {"station": "Silverstone",  "gp": "British Grand Prix"},
    12: {"station": "Spa",          "gp": "Belgian Grand Prix"},
    13: {"station": "Budapest",     "gp": "Hungarian Grand Prix"},
    14: {"station": "Zandvoort",    "gp": "Dutch Grand Prix"},
    15: {"station": "Monza",        "gp": "Italian Grand Prix"},
    16: {"station": "Madrid",       "gp": "Spanish Grand Prix"},
    17: {"station": "Baku",         "gp": "Azerbaijan Grand Prix"},
    18: {"station": "Kuala Lumpur", "gp": ""},  # 同 MEETINGS：gp 名待确认，别照抄源数据
    19: {"station": "Singapore",    "gp": "Singapore Grand Prix"},
    20: {"station": "Austin",       "gp": "United States Grand Prix"},
    21: {"station": "Mexico City",  "gp": "Mexico City Grand Prix"},
    22: {"station": "Sao Paulo",    "gp": "Sao Paulo Grand Prix"},
    23: {"station": "Las Vegas",    "gp": "Las Vegas Grand Prix"},
    24: {"station": "Lusail",       "gp": "Qatar Grand Prix"},
    25: {"station": "Abu Dhabi",    "gp": "Abu Dhabi Grand Prix"},
}

# 阶段码 -> 英文阶段名（图内语言切 en 时替代 stage_zh）
STAGE_EN = {"FP1": "FP1", "FP2": "FP2", "FP3": "FP3", "Q": "Qualifying",
            "SQ": "Sprint Qualifying", "Sprint": "Sprint", "R": "Race"}


def meeting_by_round(r):
    """按站序取场次信息（1 起，查不到给 None）"""
    return MEETINGS.get(int(r))

def meeting_by_key(meeting_key):
    """按 meeting_key 取场次信息（查不到给 None）"""
    key = int(meeting_key)
    for m in MEETINGS.values():
        if m["meeting_key"] == key:
            return m
    return None

def round_of(meeting_key):
    """按 meeting_key 反查站序，查不到给 None"""
    key = int(meeting_key)
    for r, m in MEETINGS.items():
        if m["meeting_key"] == key:
            return r
    return None

def station_of(meeting_key):
    """按 meeting_key 取中文分站名，查不到给空串（不猜）"""
    m = meeting_by_key(meeting_key)
    return m["station"] if m else ""

# ---------------------------------------------------------------- 胎色
# 返回带 # 的颜色；注意与车队队色（不带 #）口径不同
TIRE_COLOR = {"SOFT": "#ff3340", "MEDIUM": "#ffd200", "HARD": "#e6e6e6",
              "INTERMEDIATE": "#3ecf3e", "WET": "#3aa6ff", "UNKNOWN": "#888"}
TIRE_ZH = {"SOFT": "软", "MEDIUM": "中", "HARD": "硬",
           "INTERMEDIATE": "间", "WET": "雨"}

def tire_color(t):
    return TIRE_COLOR.get(t, "#888")

def tire_zh(t):
    return TIRE_ZH.get(t, "—")


# ---------------------------------------------------------------- 场次元信息
# OpenF1 /v1/sessions 的 session_name ->（图内阶段码, 中文阶段名）
SESSION_STAGE = {
    "Practice 1": ("FP1", "FP1"),
    "Practice 2": ("FP2", "FP2"),
    "Practice 3": ("FP3", "FP3"),
    "Qualifying": ("Q", "排位赛"),
    "Sprint Qualifying": ("SQ", "冲刺排位"),
    "Sprint Shootout": ("SQ", "冲刺排位"),
    "Sprint": ("Sprint", "冲刺赛"),
    "Race": ("R", "正赛"),
}


def session_prefix(session_key):
    """场次数据文件前缀（f1_fetch.py 默认用它落盘）：s<session_key>"""
    return f"s{int(session_key)}"


def load_json(data_dir, prefix, endpoint):
    """读 data/<prefix>_<endpoint>.json；缺文件时报错并提示先抓数。"""
    path = os.path.join(data_dir, f"{prefix}_{endpoint}.json")
    if not os.path.exists(path):
        raise SystemExit(f"[缺少数据] {path}\n先抓数：python3 f1_fetch.py <session_key> {prefix}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_session(data_dir, prefix, args=None, lang="zh"):
    """从 data/<prefix>_session.json 推断出图元信息，供三份母版统一取用。

    args: argparse 结果（可含 station/round/gp_name/date/fig_name 覆盖项），可传 None
    返回 {session_key, season, round, station, location, gp, stage, stage_zh,
          date_label, gp_name, fig_name, missing[]}
    字典里查不到的项留空（不猜），列进 missing 让调用方提示用参数覆盖。
    """
    def ov(name):
        return getattr(args, name, None) if args is not None else None

    rec = load_json(data_dir, prefix, "session")
    s = rec[0] if isinstance(rec, list) and rec else (rec or {})
    stage, stage_zh = SESSION_STAGE.get(s.get("session_name") or "", ("", ""))
    mk = s.get("meeting_key")
    m = meeting_by_key(mk) if mk is not None else None
    round_ = ov("round") or (round_of(mk) if mk is not None else None) or ""
    m_en = MEETING_EN.get(int(round_)) if str(round_).isdigit() else None
    if lang == "en":
        station = ov("station") or (m_en["station"] if m_en else "") or (m["location"] if m else "")
        gp = (m_en["gp"] if m_en else "") or (m["gp"] if m else "")
        stage_label = STAGE_EN.get(stage, stage)
    else:
        station = ov("station") or (m["station"] if m else "")
        gp = m["gp"] if m else ""
        stage_label = stage_zh
    gp_name = ov("gp_name") or (f"{gp} · {station} · {stage_label}" if (gp and station and stage_label) else "")
    date_label = ov("date") or (s.get("date_start") or "")[:10]

    missing = []
    if not round_: missing.append("站序 ROUND")
    if not station: missing.append("分站名 STATION")
    if not gp_name: missing.append("大奖赛名 GP_NAME")
    if not stage: missing.append("session_name 未识别（用 --gp-name/--fig-name 覆盖）")

    return {"session_key": s.get("session_key") or prefix.lstrip("s"),
            "season": str(s.get("year") or YEAR),
            "round": round_, "station": station,
            "location": s.get("location") or "", "gp": gp,
            "stage": stage, "stage_zh": stage_zh, "stage_label": stage_label,
            "date_label": date_label, "gp_name": gp_name,
            "fig_name": ov("fig_name") or "", "missing": missing}
