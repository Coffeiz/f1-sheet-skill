#!/usr/bin/env python3
"""F1 一个周末一条命令出全站图

用法:
  python3 f1_weekend.py 1292                 # 直接给 meeting_key
  python3 f1_weekend.py --round 14           # 用站序（查 f1_dict.MEETINGS）
  python3 f1_weekend.py --round 14 --only FP1,Q
  python3 f1_weekend.py --round 14 --dry-run # 只列计划
  python3 f1_weekend.py --round 14 --refetch # 强制重抓（默认已有数据就跳过）

做什么：列出该站所有 session → 按阶段自动配母版 → f1_fetch.py 抓数 → 母版出图。
阶段 → 母版：FP1/FP2/FP3 → f1_chart_fp.py；Q/SQ → f1_chart_q.py；Sprint/R → f1_chart_r.py
数据前缀统一 s<session_key>（f1_fetch.py 的默认），母版按同一前缀读 data/。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import f1_dict as D  # noqa: E402
from f1_i18n import add_lang_arg, init, t, lang, is_zh  # noqa: E402

BASE = "https://api.openf1.org/v1"
DATA_DIR = os.path.join(HERE, "data")
PY = sys.executable or "python3"
ENDPOINTS = ["laps", "stints", "position", "result", "drivers", "session"]
SCRIPT_BY_STAGE = {
    "FP1": "f1_chart_fp.py", "FP2": "f1_chart_fp.py", "FP3": "f1_chart_fp.py",
    "Q": "f1_chart_q.py", "SQ": "f1_chart_q.py",
    "R": "f1_chart_r.py", "Sprint": "f1_chart_r.py",
}
STAGE_ORDER = ["FP1", "FP2", "FP3", "SQ", "Sprint", "Q", "R"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "gugu-f1/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def sessions_of(meeting_key):
    rows = get(f"{BASE}/sessions?meeting_key={meeting_key}")
    return sorted(rows, key=lambda s: s.get("date_start", ""))


def has_data(prefix):
    return all(os.path.exists(os.path.join(DATA_DIR, f"{prefix}_{e}.json")) for e in ENDPOINTS)


def run(cmd):
    print("  $ " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, cwd=HERE).returncode == 0


def main():
    ap = argparse.ArgumentParser(description=t("weekend.desc"))
    add_lang_arg(ap)
    ap.add_argument("meeting_key", nargs="?", type=int, help=t("weekend.help_meeting"))
    ap.add_argument("--round", type=int, help=t("weekend.help_round"))
    ap.add_argument("--only", help=t("weekend.help_only"))
    ap.add_argument("--dry-run", action="store_true", help=t("weekend.help_dry_run"))
    ap.add_argument("--refetch", action="store_true", help=t("weekend.help_refetch"))
    args = ap.parse_args()
    init(args.lang)                 # 语言优先级：--lang > F1_LANG > 系统 locale > zh
    LANG_ARG = ["--lang", lang()]   # 透传给 f1_fetch.py 和母版，子进程语言跟父进程一致

    meeting_key = args.meeting_key
    if meeting_key is None and args.round is None:
        ap.error(t("weekend.err_no_key"))
    if meeting_key is None:
        m = D.meeting_by_round(args.round)
        if not m:
            print(t("weekend.err_round_unknown", round=args.round), file=sys.stderr)
            return 1
        meeting_key = m["meeting_key"]

    round_no = D.round_of(meeting_key)
    station = D.station_of(meeting_key) or t("weekend.unknown_station")
    print(t("weekend.header", round=round_no or "?", station=station, key=meeting_key),
          file=sys.stderr)

    only = {x.strip().upper() for x in args.only.split(",")} if args.only else None
    plan = []
    for s in sessions_of(meeting_key):
        name = s.get("session_name", "")
        stage, stage_zh = D.SESSION_STAGE.get(name, ("", ""))
        script = SCRIPT_BY_STAGE.get(stage)
        if not script:
            print(t("weekend.skip_session", name=name), file=sys.stderr)
            continue
        if only and stage.upper() not in only:
            continue
        plan.append({"key": s["session_key"], "stage": stage, "zh": stage_zh,
                     "script": script, "when": s.get("date_start", "")[:16]})
    plan.sort(key=lambda p: STAGE_ORDER.index(p["stage"]) if p["stage"] in STAGE_ORDER else 99)

    if not plan:
        print(t("weekend.err_no_plan"), file=sys.stderr)
        return 1

    print(t("weekend.plan_count", n=len(plan)), file=sys.stderr)
    for p in plan:
        prefix = D.session_prefix(p["key"])
        state = t("weekend.state_have") if has_data(prefix) else t("weekend.state_todo")
        label = p["zh"] if is_zh() else p["stage"]
        print(t("weekend.row", stage=p["stage"], label=label, key=p["key"],
                when=p["when"], state=state, script=p["script"]), file=sys.stderr)
    if args.dry_run:
        return 0

    failed = []
    for p in plan:
        prefix = D.session_prefix(p["key"])
        print(f"\n>>> {p['stage']} ({p['key']})", file=sys.stderr)
        if args.refetch or not has_data(prefix):
            if not run([PY, "f1_fetch.py", str(p["key"])] + LANG_ARG):
                failed.append(t("weekend.fail_fetch", stage=p["stage"]))
                continue
        else:
            print(t("weekend.skipped_fetch"), file=sys.stderr)
        if not run([PY, p["script"], str(p["key"])] + LANG_ARG):
            failed.append(t("weekend.fail_chart", stage=p["stage"]))

    print(t("weekend.summary"), file=sys.stderr)
    if failed:
        for f in failed:
            print(f"  [fail] {f}", file=sys.stderr)
        return 1
    print(t("weekend.all_done", n=len(plan)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
