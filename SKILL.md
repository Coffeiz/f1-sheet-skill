---
name: f1-charts
description: 用 OpenF1 公开数据出 F1 数据图——FP/排位/正赛圈速差距图、长距离速度图、长距离衰减轨迹图。当用户要出某一站的圈速图，或问某站谁单圈最快、谁长跑节奏好时使用。
---

# F1 数据图（OpenF1 → 圈速图）

用 OpenF1 的公开 API 拉逐圈数据，出深色底的横向对比图。**一张图 = 一个脚本**，五套母版各管各的。

## 何时用

- 用户要出某站/某阶段的圈速图（「出一下马德里 FP2 的图」「排位图来一张」）
- 用户问某站谁单圈最快、排位差距多大、长跑谁快/怎么掉速
- 用户要一整个比赛周末的图

## ⛔ 出图前强制三查（每次出图都必须走）

2026-10-17 踩过：拿 `data/` 里「看起来最新」的 session_key=11731 当成新加坡正赛，实际那是 **巴林大奖赛在马来西亚**（meeting_key 1308，10/2–10/4，Kuala Lumpur 赛道），出图时又忘传 `--station`，直接套字典默认值落进错误目录名。数据错、站名也错。

### 查一：session_key 到底是哪一场（必须回 OpenF1 核 meeting）

`data/` 里会同时存在**两套互不相邻的 session_key**，按「最大/最新」判断必错。本地已知的两套：

| session_key | meeting | 实际是什么 |
| --- | --- | --- |
| 11378 / 11379 / 11383 / 11384 / 11388 | 1296 | 新加坡（Marina Bay，10/9–10/11） |
| 11727 / 11728 / 11729 / 11730 / 11731 | 1308 | 巴林大奖赛**在马来西亚**（Kuala Lumpur，10/2–10/4） |

核法二选一：
```bash
python3 f1_fetch.py --sessions 2026                    # 走脚本，会同时打出 station/日期
curl -s "https://api.openf1.org/v1/sessions?meeting_key=<MEETING_KEY>"
# 或看本地 data/s<key>_session.json 的 meeting_key，再去查
curl -s "https://api.openf1.org/v1/meetings?year=2026"
```

**判定标准**：站名、日期、赛道三项必须和用户要的那场全部对上才准往下走。对不上就停下报给用户，不要猜、不要拿「最接近的那场」顶替。

### 查二：目标站目录里是否已有产物

```bash
ls -la charts/ && ls -la "charts/<赛季>-R<站序>-<站名>/"
```
- 该站该阶段已有同名图 → **先问用户**是覆盖还是另开 `_历史` 目录，别默认覆盖。
- 发现同站有中英文双目录（历史 bug 遗留）→ 先确认再合并，别自己删。

### 查三：数据完整性（`session_result` 在不在）

```bash
ls data/s<key>_*.json
```
- 正赛图 `f1_chart_r.py` 依赖 `s<key>_session_result.json`；缺这个文件就是没抓完，先跑 `f1_fetch.py <key>`，不要硬跑。
- 退赛车手的 `position` 可能是 `null`、`gap_to_leader` 可能是 `'DNF'` / `'+1 LAP'` 这类字符串，脚本和口播都按真实形态处理，**别脑补成 P20/P21/P22 或补 0 分**。

### 附带记住的两条

- **`resolve_session()` 对 2026 赛季实际失效**：OpenF1 `session` 端点的 `meeting_name` 是空的、`location` 与 `country_name` 错配。所以 `--station / --round / --gp-name / --date` 必须**显式手传**，不要依赖自动推断。
- **沙盒里发图**：`send_file` 只认文件库 `file_id`，不认沙盒物理路径。跑完先 `list_dir` 查 `file_id` 再发；直接填 `/workspace/default/...` 会报「未找到文件」。

## 三步流程

```bash
# 1. 先确认站序和场次号（这一步同时完成上面的查一）
python3 f1_fetch.py --rounds 2026      # 分站明细 + 该站是第几站
python3 f1_fetch.py --sessions 2026    # 本赛季全部 session 清单（拿 session_key）

# 2. 抓数据（默认抓 laps stints position result drivers session）
python3 f1_fetch.py <session_key>      # → data/s<session_key>_*.json

# 3. 出图（记得带 --station / --round / --gp-name / --date，见查三的提醒）
python3 f1_chart_fp.py <session_key> --station 新加坡 --round 19 --gp-name 新加坡大奖赛 --date 2026-10-11
```

懒人版（抓数 + 出图一把梭）：

```bash
python3 f1_weekend.py --round 16               # 整站全出
python3 f1_weekend.py --round 16 --only FP1,Q  # 只出指定阶段
python3 f1_weekend.py --round 16 --dry-run     # 只列计划
python3 f1_weekend.py --round 16 --refetch     # 已有数据也重抓
```

## 一张图 = 一个脚本，别混

| 脚本 | 出什么图 | 回答什么问题 | 用什么数据 |
| --- | --- | --- | --- |
| `f1_chart_fp.py` | FP 圈速差距图（排名图） | 谁单圈最快 | 任意 FP |
| `f1_chart_q.py` | 排位圈速差距图 | 谁拿杆位、差距多大 | Q / SQ |
| `f1_chart_r.py` | 正赛节奏图 | 正赛节奏、进站分布 | R / Sprint |
| `f1_chart_long.py` | 长距离速度图 | 长跑谁快 | **只能 FP** |
| `f1_chart_long_traj.py` | 长距离衰减轨迹图 | 长跑怎么掉速 | **只能 FP** |

- **圈速排名图**（fp/q/r）：全车手最快圈横向对比、按快慢排名，**不吃干净段门槛**，所以人人都在、FP3 也能出齐。
- **长距离速度图**：只留合格长跑段，每车每胎取圈数最多那一套，看段尾速度条。
- **长距离衰减轨迹图**：全部合格段逐圈画线，看掉速形状。

「排名」≠「长距离」≠「衰减」，脚本、口径、图名三者独立。用户要排名图时**不要**拿长距离图充数。

## 口径（已定稿，不要自由发挥）

**排名图（FP / Q）**

- P1 行：紫色 `FASTEST`（排位用 `POLE`）徽章 + 完整圈速（`1:34.077`）
- 其余车手：只给 gap（`+0.286`，相对 P1 / 杆位）
- **不显示理论最快圈速 diff**（已否决，别加回来）

**长距离图（只用 FP 数据）**

- 正赛是结果、FP 才是预测输入，所以别拿 R 的 session 跑；脚本会对非 FP 阶段告警
- 合格段：段长 ≥ `MIN_SEG=6` 圈，剔除 > 最快圈 × `CUT=1.07` 的脏圈，每段至少 3 个干净圈
- 速度图：取圈数最多的合格段，条 = 段尾 `TAIL=4` 个干净圈的最快→最慢，点 = 平均；行序按末段均速从快到慢
- 轨迹图：画全部合格段，软/中/硬三个 panel **垂直排列**，横轴胎龄、纵轴圈速（分:秒）；每个点下方标胎龄数字；同车同胎第二套起虚线 + 名字带序号

**图表通用**

- 时间统一 `m:ss.mmm` 显示，差值 / 变化量轴用秒
- 深色底，车手线色用队色
- 出完**自己先看一眼**再交：字有没有被裁、名字有没有叠、左右留白是否对称、有没有大片空档

## 参数

所有出图母版共用一套：

| 参数 | 说明 |
| --- | --- |
| `session_key` | 位置参数，场次号（**换阶段只需改这个**） |
| `--prefix` | `data/` 里的数据前缀，默认 `s<session_key>` |
| `--station` / `--round` / `--gp-name` / `--date` / `--fig-name` | 覆盖自动推断的站名 / 站序 / 大奖赛名 / 日期 / 图名 |
| `--lang` | 图内文案语言 `zh`/`en`，不给就按 locale 自动判（见「语言」一节） |

后面几个**在 2026 赛季必须显式传**——`f1_dict.resolve_session()` 对 2026 数据实际失效（`meeting_name` 为空、`location` 与 `country_name` 错配），自动推断会落到错误的目录名。传错了也能人工发现：目录名对不上就说一声。

## 语言

图内文案全走 `f1_i18n.py` 的 `t()`，脚本里不写死可见文字；中英两套都在那一个文件里。优先级：`--lang` > 环境变量 `F1_LANG` > 系统 locale 自动判 > 兜底中文（简中区 zh，HK/TW 及非中文 locale en）。

- 车手中文名列只在中文图里画；站名目录统一以中文分站名为准（中英文双目录是历史 bug 遗留，新产物不再产生）。
- 新增文案两套都要加；缺英文会回落中文并打 stderr 提醒。
- 改文案只改 `f1_i18n.py`，别在脚本里写死。

## 常见坑

- **中文字体**：无桌面环境（容器/CI）跑 matplotlib 时，两张长距离图会在家目录不可写时自动把 `MPLCONFIGDIR` 兜底到临时目录，不用手动设；字体给多候选列表（PingFang SC / 微软雅黑 / Noto Sans CJK），装了什么用什么。
- **出图糊**：PNG 走 librsvg **原生矢量渲染**（把 SVG 根元素宽高改成目标像素、viewBox 不动），不是位图放大；依赖 `ffmpeg`。
- **数据前缀**：母版按 `s<session_key>` 读 `data/`，定下来别手改。
- **批量出多阶段**：
  ```bash
  for k in 11362 11363 11364; do
    python3 f1_chart_long.py $k
    python3 f1_chart_long_traj.py $k
  done
  ```
- **换赛季**：改 `f1_dict.py` 的 `YEAR`，并把 `MEETINGS` 换成新赛季排期（站序只计大奖赛，赛前测试不入表）。
- **代班 / 换号车手**：往 `f1_dict.DRIVERS` 补一条；未收录的车号会退化显示 `#车号`，不报错。
- **数据源**：OpenF1（免费公开）。抓下来的原始响应原样落盘，不改结构；有疑问先对着 API 回包查，别猜字段。
- **OpenF1 的 live 锁（重要）**：只要有 session 正在进行（FP / Q / R 都算），它对未认证用户会把全局 API（连历史场次一起）临时锁上，所有端点回 **401**，报错文案是 `Live F1 session in progress...`。这不是脚本问题、也不是网络问题，等该 session 结束会自动恢复；跑抓数 / 出图前先确认当前没有 session 在跑（比赛周末的深夜尤其容易撞上）。
