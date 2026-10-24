#!/usr/bin/env python3
"""F1 单场 session 一条命令出全套图

用法:
  python3 f1_all.py 11389              # 抓数（缺则抓）+ 跑三张母版 + 列出产物
  python3 f1_all.py 11389 --no-fetch   # 只出图，不抓数
  python3 f1_all.py 11389 --refetch    # 强制重抓
  python3 f1_all.py 11389 --only fp,traj
  python3 f1_all.py 11389 --dry-run    # 只列计划

做什么:
  1) 数据齐不齐：缺就调 f1_fetch.py 抓（默认走内网代理）
  2) 跑三张母版：f1_chart_fp.py（圈速差距图）、f1_chart_long.py（长距离速度图）、
     f1_chart_long_traj.py（长距离衰减轨迹图）
  3) 打印产物绝对路径，方便回传文件库

说明:
  - 排名/最佳圈/差距一律以官方 session_result 为准，无效圈过滤由 f1_dict 共享函数负责
  - 数据前缀统一 s<session_key>，母版按同一前缀读 data/
  - 这里只负责出图和报路径，回传文件库由调用方按路径拿 file_id
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import f1_dict as D  # noqa: E402

DATA_DIR = os.path.join(HERE, "data")
PY = sys.executable or "python3"
ENDPOINTS = ["laps", "stints", "position", "result", "drivers", "session"]
PROXY = os.environ.get("F1_PROXY", "http://192.168.110.50:7890")

# chart → 母版；顺序固定，便于产物清单阅读
CHARTS = {
    "fp": "f1_chart_fp.py",
    "long": "f1_chart_long.py",
    "traj": "f1_chart_long_traj.py",
}
CHART_ORDER = ["fp", "long", "traj"]


def ensure_proxy():
    """沙盒出网必须走代理；已在代理里就不重复设。"""
    if os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY"):
        return
    os.environ["http_proxy"] = PROXY
    os.environ["https_proxy"] = PROXY
    os.environ["HTTP_PROXY"] = PROXY
    os.environ["HTTPS_PROXY"] = PROXY


def has_data(prefix):
    return all(os.path.exists(os.path.join(DATA_DIR, f"{prefix}_{e}.json")) for e in ENDPOINTS)


def run(cmd):
    print("  $ " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, cwd=HERE).returncode == 0


def session_name(key):
    """从本地 session 数据反查 session_name，拿不到就空。"""
    path = os.path.join(DATA_DIR, f"s{key}_session.json")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return ""
    for r in rows:
        if r.get("session_key") == key:
            return r.get("session_name", "")
    return ""


def products(limit=12):
    """列出 charts/ 下最近生成的图（按 mtime 倒序）。"""
    charts_dir = os.path.join(HERE, "charts")
    if not os.path.isdir(charts_dir):
        return []
    out = []
    for root, _dirs, files in os.walk(charts_dir):
        for fn in files:
            if not fn.endswith((".png", ".svg")):
                continue
            p = os.path.join(root, fn)
            try:
                mt = os.path.getmtime(p)
            except OSError:
                continue
            out.append((mt, p))
    out.sort(reverse=True)
    return [p for _mt, p in out[:limit]]


def main():
    ap = argparse.ArgumentParser(description="F1 单场 session 一条命令出全套图")
    ap.add_argument("session_key", type=int, help="OpenF1 session_key")
    ap.add_argument("--only", help="只跑指定图：fp,long,traj")
    ap.add_argument("--no-fetch", action="store_true", help="不抓数")
    ap.add_argument("--refetch", action="store_true", help="强制重抓")
    ap.add_argument("--dry-run", action="store_true", help="只列计划")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"], help="图内语言，默认 zh")
    args = ap.parse_args()

    key = args.session_key
    prefix = D.session_prefix(key)
    name = session_name(key)
    stage, stage_zh = D.SESSION_STAGE.get(name, ("", ""))
    label = stage_zh or stage or name or "?"

    only = {x.strip().lower() for x in args.only.split(",")} if args.only else None
    charts = [c for c in CHART_ORDER if not only or c in only]
    if not charts:
        print("没有可用图类型，可选：fp,long,traj", file=sys.stderr)
        return 1

    print(f"== session {key} · {label}", file=sys.stderr)
    state = "data ok" if has_data(prefix) else "to fetch"
    for c in charts:
        print(f"  {c:<5} {CHARTS[c]:<22} {state}", file=sys.stderr)
    if args.dry_run:
        return 0

    ensure_proxy()
    # 语言显式透传：沙盒 locale 是 en，母版自动判定会出英文图，这里固定住
    lang_arg = ["--lang", args.lang]
    if not args.no_fetch and (args.refetch or not has_data(prefix)):
        if not run([PY, "f1_fetch.py", str(key)] + lang_arg):
            print("抓数失败", file=sys.stderr)
            return 1
    elif not has_data(prefix):
        print(f"缺数据且 --no-fetch：{prefix}_*.json 不全", file=sys.stderr)
        return 1
    else:
        print("数据已齐，跳过抓数", file=sys.stderr)

    failed = []
    for c in charts:
        print(f"\n>>> {c}", file=sys.stderr)
        if not run([PY, CHARTS[c], str(key)] + lang_arg):
            failed.append(c)

    print("\n== 产物", file=sys.stderr)
    for p in products():
        print("  " + p, file=sys.stderr)
    if failed:
        for c in failed:
            print(f"  [fail] {c}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())