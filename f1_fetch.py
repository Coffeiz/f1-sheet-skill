#!/usr/bin/env python3
"""F1 数据抓取（OpenF1）· 通用

用法:
  python3 f1_fetch.py <session_key> [prefix] [endpoint ...]   # prefix 省略时用 s<session_key>
  python3 f1_fetch.py --sessions 2026            # 列本赛季所有场次 session_key
  python3 f1_fetch.py --rounds 2026              # 列分站明细 + 第几站（R数字，赛前测试不计）

默认抓: laps stints position result drivers session
落盘: <脚本同目录>/data/<prefix>_<endpoint>.json（原始响应，不改结构）
      母版默认按 s<session_key> 前缀读取，前缀定下来就别手改

OpenF1 端点（均支持 session_key 过滤）:
  /v1/sessions?year=2026           场次清单（拿 session_key）
  /v1/drivers?session_key=K        车手（车号→缩写/全名/队色）
  /v1/laps?session_key=K           逐圈（lap_number/lap_duration_s/date_start/is_pit_out_lap）
  /v1/stints?session_key=K         胎段（stint_number/lap_start/lap_end/compound/tyre_age_at_start）
  /v1/position?session_key=K       名次变化时间线
  /v1/session_result?session_key=K 官方结果（position/dnf/number_of_laps/gap_to_leader）
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f1_i18n import init, t  # noqa: E402

BASE = "https://api.openf1.org/v1"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 端点名 -> 路径
ENDPOINTS = {
    "session": "sessions",
    "drivers": "drivers",
    "laps": "laps",
    "stints": "stints",
    "position": "position",
    "result": "session_result",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "gugu-f1/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def list_rounds(year):
    """按日期排列本周历，输出「第几站 R数字」（仅计大奖赛，赛前测试排除）。"""
    rows = sorted(get(f"{BASE}/meetings?year={year}"), key=lambda m: m.get("date_start", ""))
    r = 0
    for m in rows:
        name = m.get("meeting_name", "")
        if "testing" in name.lower():
            print(f"    -     {m.get('date_start','')[:10]}  {m.get('location','')} · {name}{t('fetch.not_counted')}")
            continue
        r += 1
        print(f"R{r:<4} {m.get('date_start','')[:10]}  {m.get('location','')} · {name}")
    print(t("fetch.rounds_total", n=r), file=sys.stderr)


def list_sessions(year):
    rows = get(f"{BASE}/sessions?year={year}")
    for s in rows:
        print(f"{s['session_key']:<7} {s.get('meeting_key'):<7} {s.get('date_start','')[:16]}  "
              f"{s.get('location','')} · {s.get('session_name','')}")
    print(t("fetch.sessions_total", n=len(rows)), file=sys.stderr)


def main():
    args = sys.argv[1:]
    lang_opt = None
    if "--lang" in args:            # 手写解析：本脚本不走 argparse
        i = args.index("--lang")
        if i + 1 < len(args):
            lang_opt = args[i + 1]
            del args[i:i + 2]
        else:
            del args[i:i + 1]
    init(lang_opt)                  # 语言优先级：--lang > F1_LANG > 系统 locale > zh
    if not args:
        print(__doc__)
        return 1
    if args[0] == "--rounds":
        list_rounds(args[1] if len(args) > 1 else 2026)
        return 0
    if args[0] == "--sessions":
        list_sessions(args[1] if len(args) > 1 else 2026)
        return 0

    session_key = args[0]
    rest = args[1:]
    # 第二个参数不是端点名就当作前缀；省略时统一用 s<session_key>（母版按它读）
    if rest and rest[0] not in ENDPOINTS:
        prefix, rest = rest[0], rest[1:]
    else:
        prefix = f"s{session_key}"
    want = rest or ["laps", "stints", "position", "result", "drivers", "session"]
    for name in want:
        if name not in ENDPOINTS:
            print(t("fetch.skip_endpoint", name=name), file=sys.stderr)
            continue
        url = f"{BASE}/{ENDPOINTS[name]}?session_key={session_key}"
        try:
            data = get(url)
        except Exception as e:
            print(t("fetch.fail", name=name, err=e), file=sys.stderr)
            continue
        path = os.path.join(DATA_DIR, f"{prefix}_{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        n = len(data) if isinstance(data, list) else 1
        print(t("fetch.ok", name=name, n=n, path=path), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
